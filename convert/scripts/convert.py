#!/usr/local/env python3
import typing
import re
import os
import sys
import os.path
import pathlib
import enum
import argparse
import functools
import datetime
from zoneinfo import ZoneInfo
import calendar
import unicodedata
import xml.dom.minidom
import xml.etree.ElementTree
import xml.parsers.expat
import urllib.request
import requests

import logging
logging.basicConfig(level=os.environ.get("LOGLEVEL", "INFO"))

import pypandoc
from slugify import slugify

import gitlab.client
import gitlab.base
import gitlab.v4.objects.issues
import gitlab.v4.objects.notes

from junit import PentextUnit
pentext_unit = PentextUnit()

# determines the final return status
#global has_errors
has_errors = False

class ThreatLevels(enum.IntEnum):
	UNKNOWN = 0
	LOW = 1
	MODERATE = 2
	ELEVATED = 3
	HIGH = 4
	EXTREME = 5

def get_threat_level_number(threatLevel: typing.Optional[str]) -> int:
	if (threatLevel is None):
		return ThreatLevels.UNKNOWN
	_threatLevel =threatLevel.upper()
	if (_threatLevel not in ThreatLevels._member_names_):
		return ThreatLevels.UNKNOWN
	return ThreatLevels[_threatLevel].value


class FindingMergeStrategy(enum.IntFlag):
	RETEST = enum.auto() # <update> and finding status attribute
	META = enum.auto() # threatLevel, type, status
	LABELS = enum.auto()
	TITLE = enum.auto()
	DESCRIPTION = enum.auto()
	TECHNICALDESCRIPTION = enum.auto()
	RECOMMENDATION = enum.auto()
	IMPACT = enum.auto()

	def __str__(self):
		return self.name

	@staticmethod
	def parse_argument(value: str):
		_value = value.upper().strip("\"'")
		if (_value == "*"):
			_value = ",".join([flag.name for flag in FindingMergeStrategy])
		return functools.reduce(
			lambda i, k: i | k,
			[FindingMergeStrategy[flag.strip()] for flag in _value.split(",")],
			FindingMergeStrategy(0)
		)

def log_pentext_error(message, hint=None):
	global has_errors
	has_errors = True
	logging.error(message);
	if hint is not None:
		for line in hint.splitlines():
			logging.error(f"  {line}")

def _truthy(value: typing.Union[str, int], default: bool=False) -> bool:
	_value = str(value).lower()
	if _value in ["1", "on", "yes", "true"]:
		return True
	elif _value in ["0", "off", "no", "false"]:
		return False

def env_flag(name: str, default: bool) -> bool:
	state = _truthy(os.environ.get(name, default))
	return state

CI_PROJECT_URL=os.getenv("CI_PROJECT_URL", "/");
SKIP_EXISTING=env_flag("SKIP_EXISTING", True)
SKIP_UNMODIFIED_TODO=env_flag("SKIP_UNMODIFIED_TODO", True)
GITLAB_TOKEN=os.environ["PROJECT_ACCESS_TOKEN"]
COOKIE = os.environ.get("COOKIE")
INDENT_CHARACTER = "  "
TIMEZONE = os.environ.get("TIMEZONE", "Europe/Amsterdam")

MILESTONE = os.environ.get("MILESTONE")
LABELS = list(filter(
	lambda x: len(x),
	os.environ.get("MATCH_LABELS", "").split(",")
))

parser = argparse.ArgumentParser()
parser.add_argument(
	'--merge-strategy',
	type=FindingMergeStrategy.parse_argument,
	metavar=["*"] + [strategy.name for strategy in FindingMergeStrategy],
	default="*",
	required=False,
	help="Finding merge strategy when XML file exists"
)
parser.add_argument(
	'--include-labels',
	default=False,
	required=False,
	action=argparse.BooleanOptionalAction
)
parser.add_argument(
	'--highlight-syntax',
	default=False,
	required=False,
	action=argparse.BooleanOptionalAction
)
options = parser.parse_args()

# Standard env variable for the base URL of the GitLab instance,
# including protocol and port (for example https://gitlab.example.org:8080)
GITLAB_SERVER_URL = os.environ.get(
	"CI_SERVER_URL",
	"https://git.radicallyopensecurtity.com"
)

PENTEXT_CONVERT_COMMENT = "pentext-docker: convert"
def has_pentext_convert_comment(
	root: xml.dom.minidom.Element
) -> typing.Tuple[int, int]:
	"""Return True of an XML document has a pentext-convert comment."""
	for node in root.childNodes:
		if node.nodeType != node.COMMENT_NODE:
			continue
		if node.data == PENTEXT_CONVERT_COMMENT:
			return True
	return False

if hasattr(xml.etree.ElementTree, "indent") is False:
	logging.warning("Python XML/HTML indentation not supported")

session = requests.Session()
session.headers["PRIVATE-TOKEN"] = GITLAB_TOKEN
if COOKIE is not None:
	session.headers["Cookie"] = COOKIE
client = gitlab.client.Gitlab(
	url=GITLAB_SERVER_URL,
	private_token=GITLAB_TOKEN,
	session=session,
	keep_base_url=True
)
client.auth()

opener = urllib.request.build_opener()
opener.addheaders = [('PRIVATE-TOKEN', GITLAB_TOKEN)]
if COOKIE is not None:
	opener.addheaders.append(('COOKIE', COOKIE))
urllib.request.install_opener(opener)

pathlib.Path("uploads").mkdir(parents=True, exist_ok=True)
pathlib.Path("findings").mkdir(parents=True, exist_ok=True)
pathlib.Path("non-findings").mkdir(parents=True, exist_ok=True)

class InvalidUploadPathException(Exception):
	pass


class HTMLParsingError(Exception):

	LINE_RADIUS = 1
	HIGHLIGHT_RADIUS = 0

	def __init__(self, msg: str, position: typing.Tuple[int, int], html: str) -> None:
		super().__init__(msg)
		self.position = position
		self.html = html
	
	@property
	def surrounding_lines(self):
		error_line = self.position[0]-1
		error_column = self.position[1]
		lines = self.html.splitlines()

		# highlight text with distance around issue
		_line = lines[error_line]

		error_character = _line[error_column]
		if unicodedata.category(error_character)[0] == "C":
			error_character = hex(ord(error_character))

		_line = "".join([
			_line[0:error_column],
			"\033[91m",
			error_character,
			"\033[0m",
			_line[error_column+1:]
		])
		lines[error_line] = _line

		# return including surrounding lines
		return "\n".join(lines[error_line-self.LINE_RADIUS:error_line+self.LINE_RADIUS+1])


def curry_project_obj_cls(obj_cls, pentext_project):
	def _obj_cls(*args, **kwargs):
		return obj_cls(*args, **kwargs, pentext_project=pentext_project)
	return _obj_cls

def to_prettyxml(doc):
	output = doc.toxml(encoding="UTF-8").decode("UTF-8")
	# force newline after XML declaration
	output = re.sub(r"^(<\?xml[^>\n]*>)", r"\1\n", output, count=1)
	# end file with newline
	output = re.sub(r"\n*$", "\n", output)
	return output

p_pre_code_open = re.compile(r"<pre>[\s\r\n]*<code>[\s\r\n]*", re.MULTILINE)
p_pre_code_close = re.compile(r"[\s\r\n]*</code>[\s\r\n]*</pre>", re.MULTILINE)
p_syntax_highlighting = re.compile(r"^```(.+)$", re.MULTILINE)
p_hidden_links = re.compile(r'<a href="#gitlab[^>]*" aria-hidden="true"></a>', re.MULTILINE)

def _fix_code_blocks(html: str) -> str:
	html = re.sub(p_pre_code_open, "<pre><code>", html)
	html = re.sub(p_pre_code_close, "</code></pre>", html)
	return html

def _remove_syntax_highlighting(markdown_text: str) -> str:
	# simply remove the syntax definition
	return re.sub(p_syntax_highlighting, "```", markdown_text)

def _remove_hidden_links(html: str) -> str:
	# simply remove the syntax definition
	return re.sub(p_hidden_links, "", html)

def _dom_to_html(htmlTree: xml.etree.ElementTree) -> str:
	return xml.etree.ElementTree.tostring(htmlTree).decode("UTF-8")

def _html_to_dom(html: str) -> xml.etree.ElementTree.Element:
	_html = f"<root>\n{html.strip()}\n</root>" # can parse only one root element
	error = None
	try:
		return xml.etree.ElementTree.fromstring(_html)
	except xml.etree.ElementTree.ParseError as err:
		error = HTMLParsingError(err.msg, err.position, _html)
		raise error

# Inspired by https://github.com/python/cpython/blob/bfc57d43d8766120ba0c8f3f6d7b2ac681a81d8a/Lib/xml/etree/ElementTree.py#L1140
def _indent(tree: xml.etree.ElementTree.Element, level: int=0) -> None:
	indentations = ["\n" + level * INDENT_CHARACTER]
	def _indent_children(elem, level):
		child_level = level + 1
		try:
			child_indentation = indentations[child_level]
		except IndexError:
			child_indentation = indentations[level] + INDENT_CHARACTER
			indentations.append(child_indentation)
		if not elem.text or not elem.text.strip():
			elem.text = child_indentation
		for child in elem:
			# ignore pre elements
			if (child.tag != "pre") and len(child):
				_indent_children(child, child_level)
			if not child.tail or not child.tail.strip():
				child.tail = child_indentation
		if not child.tail.strip():
			child.tail = indentations[level]
	_indent_children(tree, 0)

def markdown(
	markdown_text: str,
	id_prefix: str,
	level=0
) -> str:
	# pre-processing
	markdown_text = _resolve_internal_links(markdown_text)
	if not options.highlight_syntax:
		markdown_text = _remove_syntax_highlighting(markdown_text)
	if re.search(r"[^A-Za-z0-9_\-\\\/]", str(id_prefix)) is not None:
		# prevent shell argument injection
		raise Exception(f"Invalid id_prefix: {id_prefix}")
	_id_prefix = f"{id_prefix}_"

	# convert markdown to HTML
	html = pypandoc.convert_text(
		markdown_text,
		'html5',
		format='gfm',
		extra_args=[f"--id-prefix={_id_prefix}"]
	).replace('\r\n', '\n')

	# post-processing
	if options.highlight_syntax:
		html = _remove_hidden_links(html)
	html = _fix_code_blocks(html)
	element = _html_to_dom(html)
	_indent(element, level)

	return _dom_to_html(element)

def markdown_to_dom(*args, **kwargs) -> typing.List[xml.dom.minidom.Element]:
	html = markdown(*args, **kwargs)
	dom = xml.dom.minidom.parseString(html)
	return dom.firstChild.childNodes

def _is_pentext_label(label) -> bool:
	_label = label.lower()
	if _label in ["finding", "non-finding", "future-work", "done"]:
		return True
	elif _label.startswith("threatlevel:"):
		return True
	elif _label.startswith("reteststatus:"):
		return True


class Upload:

	upload_path_pattern = re.compile(
		"(?:\.{2})?/uploads/(?P<hex>[A-Fa-f0-9]{32})/(?P<filename>[^\.][^/]+)"
	)

	def __init__(self, path, pentext_project=None) -> None:
		self.path = path
		self.pentext_project = pentext_project

	@property
	def path(self):
		return f"/uploads/{self.hex}/{self.filename}"
	
	@path.setter
	def path(self, value):
		match = self.upload_path_pattern.match(value)
		if match is None:
			raise InvalidUploadPathException()
		self.hex = match["hex"]
		self.filename = match["filename"]

	@property
	def url(self):
		project_url = urllib.parse.urljoin(
			client._base_url,
			f"-/project/{self.pentext_project.id}"
		)
		return f"{project_url}{self.path}"
	
	@property
	def local_path(self):
		return f"uploads/{self.hex}/{self.filename}"

	def download(self) -> None:
		if os.path.exists(self.local_path) is True:
			logging.info(f"skip download {self.local_path} - file exists")
			return
		dirname = os.path.dirname(self.local_path)
		os.makedirs(dirname, exist_ok=True)
		logging.info(f"downloading {self.url} to {self.local_path}")
		try:
			urllib.request.urlretrieve(self.url, self.local_path)
		except Exception as err:
			print("download failed")
			raise err


class PentextXMLFile:
	"""
	Pentext XML file.

	Typically located in source/*.xml, but includes (non-)findings/*.xml as well.
	"""

	source_dir = "source"

	def __init__(
		self,
		pentext_project=None,
	) -> None:
		self.pentext_project = pentext_project
		self._doc = None

	@property
	def doc(self):
		"""Existing file XML dom."""
		if (self._doc is None) and self.exists:
			self.read()
		return self._doc

	@property
	def processed_doc(self):
		doc = self.doc
		images = doc.getElementsByTagName("img")
		image_urls = [image.getAttribute("src") for image in images]
		for image in images:
			image_url = image.getAttribute("src");
			try:
				attachment = Upload(image_url, pentext_project=self.pentext_project)
				attachment.download()
				image.setAttribute("src", f"../{attachment.local_path}")
			except InvalidUploadPathException:
				pass
		return doc

	def read(self):
		if not self.exists:
			raise Exception(f"File {self.relative_path} does not exist")
		logging.info(f"parsing {self.relative_path}")
		self._doc = xml.dom.minidom.parse(self.relative_path)

	def write(self) -> None:
		prettyxml = None
		try:
			prettyxml = to_prettyxml(self.processed_doc)
		except Exception:
			logging.error(f"failed to obtain XML content of {self.relative_path}")
			return
		with open(self.relative_path, "w", encoding="UTF-8") as file:
			logging.info(f"writing {self.relative_path}")
			file.write(prettyxml)

	@property
	def exists(self):
		return os.path.isfile(self.relative_path)

	@property
	def relative_path(self):
		return os.path.join(self.source_dir, self.filename)

	@property
	def filename(self):
		raise NotImplementedError()


class ProjectIssuePentextSection(gitlab.v4.objects.issues.ProjectIssue):
	"""
	Pentext section GitLab.
	"""
	__module__ = "gitlab.v4.objects.issues"

	@property
	def extra_labels(self) -> typing.List[str]:
		"""Return GitLab Issue labels that are not associated with Pentext."""
		return [label for label in self.labels if not _is_pentext_label(label)]


class ProjectIssuePentextXMLFile(
	PentextXMLFile,
	ProjectIssuePentextSection
):
	"""
	GitLab Issue associated with a Pentext XML file.

	Pentext Findings or Non-Findig XML files (findings/f1-finding-title-slug.xml)
	are related to a GitLab Issue.
	"""
	__module__ = "gitlab.v4.objects.issues"

	def __init__(self, *args, pentext_project, **kwargs) -> None:
		gitlab.v4.objects.issues.ProjectIssue.__init__(self, *args, **kwargs)
		PentextXMLFile.__init__(self, pentext_project=pentext_project)
		self.existing_doc = None

	@property
	def slug(self):
		return f"f{self.iid}-{slugify(self.title)}"

	@property
	def filename(self):
		return f"{self.slug}.xml"

	@property
	def relative_path(self):
		return os.path.join(self.source_dir, self.filename)


class FindingIssueNote(gitlab.v4.objects.notes.ProjectIssueNote):
	"""
	GitLab Issue Discussion starting with a prefix keyword.
	"""
	__module__ = "gitlab.v4.objects.notes"

	NOTE_KEYWORDS = [
		"recommendation",
		"impact",
		"update",
		"type",
		"technicaldescription"
	]

	def __init__(self, *args, **kwargs):
		super().__init__(*args, **kwargs)
		lines = self.body.splitlines()
		first_line = lines.pop(0)
		keyword = first_line.lower().replace(" ", "").strip().strip("#:")
		if keyword in self.NOTE_KEYWORDS:
			# remove leading empty lines
			while len(lines) and lines[0].strip() == "":
				lines.pop(0)
			self.markdown = "\n".join(lines).strip()
			self.keyword = keyword
		else:
			self.markdown = self.body.strip()
			self.keyword = None

	def __str__(self):
		return self.markdown


class TodoNote:
	"""
	Placeholder when an expected ProjectIssueNote was not found.
	"""
	def __init__(self, keyword, message="ToDo", *args, **kwargs):
		self.keyword = keyword
		self.markdown = message

	def __str__(self):
		return self.markdown


class Finding(ProjectIssuePentextXMLFile):
	"""
	Pentext finding XML structure associated with a GitLab Issue.
	"""
	__module__ = "gitlab.v4.objects.issues"

	def __init__(self, *args, **kwargs):
		super().__init__(*args, **kwargs)
		self._pentext_notes = None
		self.strategy = options.merge_strategy

	@property
	def pentext_notes(self):
		if self._pentext_notes is None:
			self._pentext_notes = []
			_obj_cls = self.notes._obj_cls
			self.notes._obj_cls = FindingIssueNote
			first_note = None
			has_technical_description = False
			for note in self.notes.list(
				sort="asc",
				order_by="created_at",
				iterator=True
			):
				if note.system is True:
					continue
				if first_note is None:
					first_note = note
				if note.keyword == "technicaldescription":
					has_technical_description = True
				self._pentext_notes.append(note)
			self.notes._obj_cls = _obj_cls
			if not has_technical_description and (first_note.keyword is None):
				first_note.keyword = "technicaldescription"
		return self._pentext_notes
	
	@property
	def technicaldescription(self) -> FindingIssueNote:
		try:
			return next(self.get_note_by_type("technicaldescription"))
		except StopIteration:
			return TodoNote("technicaldescription")

	@property
	def type(self) -> FindingIssueNote:
		try:
			return next(self.get_note_by_type("type"))
		except StopIteration:
			return TodoNote("type")

	@property
	def recommendation(self) -> FindingIssueNote:
		try:
			return next(self.get_note_by_type("recommendation"))
		except StopIteration:
			return TodoNote("recommendation")

	@property
	def impact(self) -> FindingIssueNote:
		try:
			return next(self.get_note_by_type("impact"))
		except StopIteration:
			return TodoNote("impact")

	@property
	def updates(self) -> typing.List[FindingIssueNote]:
		return self.get_note_by_type("update")

	@property
	def status(self) -> str:
		for label in self.labels:
			if label.lower().startswith("reteststatus:"):
				return label.split(":", maxsplit=1)[1]
		return "none"

	@property
	def threatlevel(self) -> str:
		for label in self.labels:
			if label.lower().startswith("threatlevel:"):
				return label.split(":", maxsplit=1)[1]
		return "Unknown"

	def get_note_by_type(self, note_type) -> typing.List[FindingIssueNote]:
		for note in self.pentext_notes:
			if note.keyword == note_type:
				yield note

	@staticmethod
	def get_dom_section(*args, **kwargs) -> xml.dom.minidom.Element:
		try:
			return next(Finding.get_dom_sections(*args, **kwargs))
		except StopIteration:
			return None

	@staticmethod
	def get_dom_sections(root, tagName, slug=None) -> xml.dom.minidom.Element:
		for node in root.childNodes:
			if node.nodeType == node.ELEMENT_NODE and node.tagName == tagName:
				if (slug is not None) and (node.getAttribute("id") != slug):
					continue
				yield node

	@property
	def doc(self):
		status = dict(
			errors=0,
			failures=0,
			skipped=0,
			tests=0
		)
		global has_errors
		global pentext_unit

		testsuite_name = f"Finding {self.iid}"

		level = 1
		exists = self.exists
		if exists is True:
			if self._doc is None:
				self.read()
			doc = self._doc
			root = doc.documentElement
		else:
			doc = xml.dom.minidom.Document()
			root = doc.createElement("finding")
			root.appendChild(doc.createTextNode("\n"))
			doc.appendChild(root)

		if not exists or (FindingMergeStrategy.META in self.strategy):
			root.setAttribute("id", self.slug)
			root.setAttribute("number", str(self.iid))
			root.setAttribute("threatLevel", str(self.threatlevel))
			root.setAttribute("type", str(self.type))
		if not exists or ((FindingMergeStrategy.META & FindingMergeStrategy.RETEST) in self.strategy):
			root.setAttribute("status", self.status)

		title = self.get_dom_section(root, "title")
		if not exists or (FindingMergeStrategy.TITLE in self.strategy):
			if title is None:
				title = doc.createElement("title")
				root.appendChild(doc.createTextNode(INDENT_CHARACTER * level))
				root.appendChild(title)
				root.appendChild(doc.createTextNode("\n"))
			while title.hasChildNodes():
				title.removeChild(title.firstChild)
			title.appendChild(doc.createTextNode(self.title))

		# Description
		section_status = None
		try:
			added = self._append_section(doc, root, "description", FindingMergeStrategy.DESCRIPTION)
			if added is False:
				status["skipped"] = status["skipped"] + 1
				section_status = doc.createElement("skipped")
				section_status.appendChild(doc.createTextNode("untouched"))
		except Exception as err:
			section_status = doc.createElement("error")
			section_status.appendChild(doc.createTextNode(str(err)))
			status["errors"] = status["errors"] + 1
			has_errors = True
		finally:
			status["tests"] = status["tests"] + 1
			pentext_unit.add_testcase(testsuite_name, "description", self.relative_path, section_status)

		# Technical Description
		section_status = None
		try:
			added = self._append_section(doc, root, "technicaldescription", FindingMergeStrategy.TECHNICALDESCRIPTION)
			if added is False:
				status["skipped"] = status["skipped"] + 1
				section_status = doc.createElement("skipped")
				section_status.appendChild(doc.createTextNode("untouched"))
		except Exception as err:
			section_status = doc.createElement("error")
			section_status.appendChild(doc.createTextNode(str(err)))
			status["errors"] = status["errors"] + 1
			has_errors = True
		finally:
			status["tests"] = status["tests"] + 1
			pentext_unit.add_testcase(testsuite_name, "technicaldescription", self.relative_path, section_status)

		# Impact
		section_status = None
		try:
			added = self._append_section(doc, root, "impact", FindingMergeStrategy.IMPACT)
			if added is False:
				status["skipped"] = status["skipped"] + 1
				section_status = doc.createElement("skipped")
				section_status.appendChild(doc.createTextNode("untouched"))
		except Exception as err:
			section_status = doc.createElement("error")
			section_status.appendChild(doc.createTextNode(str(err)))
			status["errors"] = status["errors"] + 1
			has_errors = True
		finally:
			status["tests"] = status["tests"] + 1
			pentext_unit.add_testcase(testsuite_name, "impact", self.relative_path, section_status)

		# Recommendation
		section_status = None
		try:
			added = self._append_section(doc, root, "recommendation", FindingMergeStrategy.RECOMMENDATION, unwrap=False)
			if added is False:
				status["skipped"] = status["skipped"] + 1
				section_status = doc.createElement("skipped")
				section_status.appendChild(doc.createTextNode("untouched"))
		except Exception as err:
			section_status = doc.createElement("error")
			section_status.appendChild(doc.createTextNode(str(err)))
			status["errors"] = status["errors"] + 1
			has_errors = True
		finally:
			status["tests"] = status["tests"] + 1
			pentext_unit.add_testcase(testsuite_name, "recommendation", self.relative_path, section_status)

		updates = self.updates
		update_slugs = [
			f"gitlab_project_{os.environ['CI_PROJECT_ID']}_issues_{update.issue_iid}_note_{update.id}"
			for update in updates
		]

		if (FindingMergeStrategy.RETEST in self.strategy):
			# remove all matching tags without slug (cleanup from prior conversion revision)
			for other_section in self.get_dom_sections(root, "update"):
				if (other_section.hasAttribute("id") is False) or (other_section.getAttribute("id") not in update_slugs):
					if (other_section.previousSibling.nodeType == doc.TEXT_NODE):
						root.removeChild(other_section.previousSibling)
					root.removeChild(other_section)

			for update in self.updates:
				slug = f"gitlab_project_{os.environ['CI_PROJECT_ID']}_issues_{update.issue_iid}_note_{update.id}"

				# convert local date
				utc_date = datetime.datetime.strptime(update.created_at, "%Y-%m-%dT%H:%M:%S.%fZ")
				timestamp = calendar.timegm(utc_date.timetuple())
				local_date = datetime.datetime.fromtimestamp(timestamp, tz=ZoneInfo(TIMEZONE))

				# there can be multiple update sections
				self._append_section(doc, root, "update",
					FindingMergeStrategy.RETEST,
					update.markdown,
					slug=slug,
					created_at=update.created_at,
					updated_at=update.updated_at,
					date=local_date.strftime("%Y-%m-%d %H:%M")
				)

		labels = self.get_dom_section(root, "labels")
		if options.include_labels and (not exists or (FindingMergeStrategy.LABELS in self.strategy)):
			if labels is None:
				labels = doc.createElement("labels")
				root.appendChild(doc.createTextNode(INDENT_CHARACTER * level))
				root.appendChild(labels)
				root.appendChild(doc.createTextNode("\n"))
			while labels.hasChildNodes():
				labels.removeChild(labels.firstChild)
			for label_title in self.extra_labels:
				label = doc.createElement("label")
				label.appendChild(doc.createTextNode(label_title))
				labels.appendChild(
					doc.createTextNode(f"\n{INDENT_CHARACTER * (level + 1)}")
				)
				labels.appendChild(label)
			if len(self.extra_labels):
				labels.appendChild(doc.createTextNode("\n" + (INDENT_CHARACTER * level)))

		testsuite = pentext_unit.get_or_add_testsuite(testsuite_name)
		for [k, v] in status.items():
			testsuite.setAttribute(k, str(v))

		return doc

	@doc.setter
	def doc(self, value) -> None:
		self._dom = value

	def __unwrap_single_paragraph_node(self, nodes) -> typing.List[xml.dom.minidom.Element]:
		"""
		Unwrap single paragraph DOM (e.g. <description><p>.*</p></description>).
		"""
		first_element_index = None
		for index, node in enumerate(nodes):
			if (node.nodeType == node.ELEMENT_NODE):
				if first_element_index is None:
					first_element_index = index
				else:
					# do nothing when multiple element nodes are found
					return nodes
		if first_element_index is not None:
			exclusions = ["ul"]
			if nodes[first_element_index].tagName in exclusions:
				return nodes
			return nodes[first_element_index].childNodes
		return nodes

	def _append_section(
		self,
		doc,
		parentNode,
		name,
		update_strategy,
		markdown_text=None,
		level=1,
		unwrap=True,
		slug=None,
		**sectionAttributes
	) -> None:
		try:
			section = self.get_dom_section(parentNode, name, slug)
		except Exception as err:
			log_pentext_error(
				f"Parsing finding {self.iid} section {name} from XML failed",
				hint=f"Spot the issue in {self.relative_path}"
			)
			raise err
		if section is None:
			section = doc.createElement(name)
			parentNode.appendChild(doc.createTextNode(INDENT_CHARACTER * level))
			parentNode.appendChild(section)
			parentNode.appendChild(doc.createTextNode("\n"))
		elif update_strategy not in self.strategy:
			logging.debug(f"Finding section {name} exists but skipped because update strategy {update_strategy} is not enabled")
			return False
		else:
			while section.hasChildNodes():
				section.removeChild(section.firstChild)

		if slug is not None:
			section.setAttribute("id", slug)
		elif section.hasAttribute("id"):
			section.removeAttribute("id")

		for name, value in sectionAttributes.items():
			section.setAttribute(name, value)

		issue_url = urllib.parse.urljoin( # used in error hints
			CI_PROJECT_URL,
			f"-/issues/{self.iid}"
		).strip()

		if markdown_text is None:
			_value = getattr(self, name)
			# description is native value str
			markdown_text = _value if isinstance(_value, str) else _value.markdown
		try:
			section_nodes = markdown_to_dom(
				markdown_text,
				slug if slug is not None else self.iid,
				level=level
			)
		except HTMLParsingError as err:
			log_pentext_error(
				f"finding {self.iid} section '{name}' has an HTML markup error after converting from Markdown", (
					f"Spot the issue in {issue_url}\nAlso check for strings invisible in the preview, such as HTML tags"
					f"\n\n{err.surrounding_lines}"
				)
			)
			raise err
		except Exception as err:
			log_pentext_error(
				f"Markdown to HTML conversion of Finding {self.iid} section '{name}' failed",
				f"Spot the issue in {issue_url}"
			)
			raise err

		if unwrap is True:
			section_nodes = self.__unwrap_single_paragraph_node(section_nodes)

		while len(section_nodes):
			node = section_nodes.pop(0)
			node.parentNode = None
			section.appendChild(node)

		return True

	@property
	def relative_path(self):
		return f"findings/{self.filename}"


class NonFinding(ProjectIssuePentextXMLFile):

	__module__ = "gitlab.v4.objects.issues"

	@property
	def doc(self):
		doc = xml.dom.minidom.Document()
		root = doc.createElement("non-finding");
		root.setAttribute("id", self.slug)
		root.setAttribute("number", str(self.iid))
		root.appendChild(doc.createTextNode("\n"))

		title = doc.createElement("title");
		title.appendChild(doc.createTextNode(self.title))
		root.appendChild(title)
		root.appendChild(doc.createTextNode("\n"))

		content_nodes = markdown_to_dom(self.description, self.iid, level=1)
		while len(content_nodes):
			node = content_nodes[0]
			root.appendChild(node)
		doc.appendChild(root)
		return doc

	@property
	def relative_path(self):
		return f"non-findings/{self.filename}"


class PentextXMLFileSection(PentextXMLFile):
	"""
	Section with multiple parts associated with multiple or no GitLab Issues.
	"""
	def __init__(
		self,
		*parts,
		pentext_project=None
	) -> None:
		super().__init__(pentext_project=pentext_project)
		self._doc = None
		self.parts = parts

	@property
	def doc(self):
		return self._doc

	@property
	def is_user_modified(self):
		return len(self.parts) > 0


class PentextXMLFileTodoSection(PentextXMLFileSection):
	"""
  Report section in separate Pentext XML file.

  A source file is read (e.g. source/conclusion.xml) and content from GitLab
  Issues is replacing the <todo/> note.

	  <wrapper id="gitlab/project/[0-9]+/issues/[0-9]+/">
			<title optional/>
			<markdown_description/>
	  </wrapper>

	Each section can have multiple parts, for instance multiple GitLab Issues
	matching the criteria. This can be useful when generating Milestone reports
	or filter results by certain label.
	"""

	# wrapping the Markdown content from GitLab
	wrapper_element = "div"

	# include GitLab Issue title (e.g. Future Work <li><b>Title</b>...</li>)
	title_element = None
	
	# match documents indentation level
	# <pre/> elements cannot be indented later
	indent_level = 1
	
	# Versions of Pentext wrap a ToDo in an inline element, which should removed
	todo_element_wrapper = "p" # <p><todo/></p>

	def getDOM(self, *args, **kwargs):
		"""Concate"""
		for part in self.parts:
			yield from part.getDOM(*args, **kwargs)

	@property
	def doc(self):
		if self._doc is None:
			logging.info(f"Reading {self.section_title} from {self.relative_path}")
			doc = xml.dom.minidom.parse(self.relative_path)
			self._doc = self.replace_todo(doc)
		return self._doc

	def replace_todo(self, doc):
		if has_pentext_convert_comment(doc.documentElement) is True:
			logging.debug(
				f"{self.section_title} is already converted - skip replacing <todo/>"
			)
			return doc
		todos = doc.documentElement.getElementsByTagName("todo")
		if len(todos) == 0:
			# skip when no <todo> element was found in XML
			return doc
		if (self.is_user_modified is False) and (SKIP_UNMODIFIED_TODO is True):
			# skip when this asset was not found in GitLab issues
			return doc

		todo = todos[0]
		if todo.parentNode.tagName == self.todo_element_wrapper:
			todo = todo.parentNode

		prefix = "\n"
		before_todo = todo.previousSibling
		if (before_todo is not None) and (before_todo.nodeType == doc.TEXT_NODE):
			prefix = "\n" + before_todo.nodeValue.splitlines().pop()

		todo.parentNode.insertBefore(doc.createComment(PENTEXT_CONVERT_COMMENT), todo)
		todo.parentNode.insertBefore(doc.createTextNode(prefix), todo)
		for node in self.getDOM(
			wrapper_element=self.wrapper_element,
			title_element=self.title_element,
			indent_level=self.indent_level
		):
			todo.parentNode.insertBefore(node, todo)
			todo.parentNode.insertBefore(doc.createTextNode(prefix), todo)
		todo.parentNode.insertBefore(doc.createComment(PENTEXT_CONVERT_COMMENT), todo)

		# remove empty text node before the todo item
		prev = todo.previousSibling
		if (prev is not None) and (prev.nodeType == doc.TEXT_NODE) and (len(prev.nodeValue.strip()) == 0):
			prev.parentNode.removeChild(prev)
		todo.parentNode.removeChild(todo)

		return doc


class Conclusion(PentextXMLFileTodoSection):

	section_title = "Conclusion"
	filename = "conclusion.xml"


class ResultsInANutshell(PentextXMLFileTodoSection):

	section_title = "Results In A Nutshell"
	filename = "resultsinanutshell.xml"


class FutureWork(PentextXMLFileTodoSection):

	section_title = "Future Work"
	filename = "futurework.xml"
	wrapper_element = "li"
	title_element = "b"
	indent_level = 2
	todo_element_wrapper = "li" # <li><todo/></li>


class SectionPart(gitlab.v4.objects.issues.ProjectIssue):
	"""
	One single part of a PentextXMLFileSection represented by a GitLab Issue each.
	"""
	__module__ = "gitlab.v4.objects.issues"

	def __init__(self, *args, pentext_project, **kwargs) -> None:
		#self.pentext_project = pentext_project
		super().__init__(*args, **kwargs)

	@property
	def identifier_slug(self):
		return f"{self.manager.path}_{self.encoded_id}"

	def _getDOM(self, wrapper_element, title_element, indent_level):
		doc = xml.dom.minidom.Document()
		root = doc.createElement(wrapper_element or "root")
		root.setAttribute("id", self.identifier_slug)

		if title_element is not None:
			title = doc.createElement(title_element)
			title.appendChild(doc.createTextNode(self.title))
			root.appendChild(
				doc.createTextNode("\n" + ((indent_level+1) * INDENT_CHARACTER))
			)
			root.appendChild(title)
			#root.appendChild(doc.createTextNode("\n"))

		dom = markdown_to_dom(self.description, self.identifier_slug, level=indent_level)
		while(len(dom) > 0):
			root.appendChild(dom[0])
		return root

	def getDOM(self, wrapper_element, title_element, indent_level):
		dom = self._getDOM(
			wrapper_element=wrapper_element or "root",
			title_element=title_element,
			indent_level=indent_level
		)
		if wrapper_element is None:
			# flatten childNodes in case the wrapper element itself is omitted
			for el in dom:
				yield from el.firstChild.childNodes
		else:
			yield dom


class Report(PentextXMLFile):

	filename = "report.xml"

	def __init__(
		self,
	) -> None:
		self._added_hrefs = []
		self._doc = None
		self.read()

	@property
	def doc(self):
		return self._doc

	@doc.setter
	def doc(self, value: xml.dom.minidom.Document) -> None:
		self._doc = value

	def get_section(self, section_name):
		for section in self.doc.documentElement.getElementsByTagName("section"):
			if section.getAttribute("id") == section_name:
				return section

	@property
	def findings(self):
		return self.get_section("findings")

	@property
	def non_findings(self):
		return self.get_section("nonFindings")

	@staticmethod
	def _is_include_element(node: typing.Any) -> bool:
		if isinstance(node, xml.dom.minidom.Element) is False:
			return False
		elif node.tagName != "xi:include":
			return False
		elif node.hasAttribute("href") is False:
			return False
		return True

	def _should_include_be_visible(
		self,
		node: xml.dom.minidom.Element
	) -> typing.Optional[bool]:
		if self._is_include_element(node) is False:
			return None
		return node.getAttribute("href").strip() in self._added_hrefs

	def _get_include_by_href(
		self,
		section: xml.dom.minidom.Element,
		href: str
	) -> typing.Optional[typing.Union[
		xml.dom.minidom.Comment,
		xml.dom.minidom.Element
	]]:
		for node in section.childNodes:
			if self._is_include_element(node):
				if node.getAttribute("href") == href:
					return node
			if isinstance(node, xml.dom.minidom.Comment):
				try:
					include = xml.dom.minidom.parseString(node.nodeValue.strip())
					if include.documentElement.getAttribute("href") == href:
						return node
				except xml.parsers.expat.ExpatError:
					pass
		return None

	def _toggle_comment(
		self,
		element: xml.dom.minidom.Element,
		visible: typing.Optional[bool]=None
	) -> None:
		parent = element.parentNode
		if isinstance(element, xml.dom.minidom.Comment):
			# comment out
			if visible is False:
				return # already commented out
			root = xml.dom.minidom.parseString(element.nodeValue.strip())
			node = root.documentElement
			nodes = root.childNodes
			while len(nodes):
				node = nodes[0]
				parent.insertBefore(node, element)
			parent.removeChild(element)
		elif self._is_include_element(element):
			if visible is True:
				return # should not be commented out
			comment = element.toxml(encoding="UTF-8").decode("UTF-8")
			parent.insertBefore(xml.dom.minidom.Comment(comment), element)
			parent.removeChild(element)

	def toggle_include_comments(
		self,
		section: typing.Optional[typing.List[xml.dom.minidom.Node]]=None
	) -> None:

		if section is None:
			for section_name in ["findings", "nonFindings"]:
				target = self.get_section(section_name)
				if target is not None:
					self.toggle_include_comments(target)
			return

		for item in section.childNodes:
			# check existing comments for items to comment in
			if isinstance(item, xml.dom.minidom.Comment):
				try:
					parsed = xml.dom.minidom.parseString(item.nodeValue.strip())
					if self._should_include_be_visible(parsed.documentElement) is True:
						self._toggle_comment(item, visible=True)
				except:
					# ignore comments with invalid content
					pass
			elif self._is_include_element(item):
				# check existing item and comment out if necessary
				if self._should_include_be_visible(item) is not True:
					self._toggle_comment(item, visible=False)

	def add(self, section_name, item):

		doc = self.doc
		section = self.get_section(section_name)
		href = os.path.join("..", item.relative_path)
		self._added_hrefs.append(href)

		line_prefix = "\n"
		if (section.firstChild.nodeType == doc.TEXT_NODE):
			line_prefix = section.firstChild.nodeValue

		existing_include = self._get_include_by_href(section, href)
		if existing_include is not None:
			self._toggle_comment(existing_include, visible=True)
			return

		el = doc.createElement("xi:include")
		el.setAttribute("xmlns:xi", "http://www.w3.org/2001/XInclude")
		el.setAttribute("href", href)

		if section is None:
			raise Exception(f"Cannot add {section_name} - section not found in XML")

		_line_prefix = self.doc.createTextNode(line_prefix)
		if (section.lastChild.nodeType == doc.TEXT_NODE):
			section.insertBefore(_line_prefix, section.lastChild)
			section.insertBefore(el, section.lastChild)
		else:
			# append as last element else
			section.appendChild(_line_prefix)
			section.appendChild(el)

	def add_finding(self, finding: Finding) -> None:
		self.add("findings", finding)

	def add_non_finding(self, non_finding: NonFinding) -> None:
		self.add("nonFindings", non_finding)

	def update_labels(self, labels) -> None:
		meta_elements = self.doc.documentElement.getElementsByTagName("meta")
		if len(meta_elements) == 0:
			raise Exception("Report XML file misses <meta/> element")
		meta_element = meta_elements[0]

		# get meta indent level
		indent_level = 3
		before_meta = meta_element.previousSibling
		if (before_meta is None) or (before_meta.nodeType == before_meta.TEXT_NODE):
			_indent_character = before_meta.nodeValue.splitlines().pop()
		else:
			_indent_character = INDENT_CHARACTER

		labels_elements = meta_element.getElementsByTagName("labels")
		if len(labels_elements) == 0:
			labels_element = self.doc.createElement("labels")
			meta_element.appendChild(self.doc.createTextNode(_indent_character))
			meta_element.appendChild(labels_element)
			meta_element.appendChild(self.doc.createTextNode("\n" + (_indent_character * (indent_level-2))))
		else:
			labels_element = labels_elements[0]
		while labels_element.hasChildNodes():
			labels_element.removeChild(labels_element.firstChild)
		if len(labels) > 0:
			labels_element.appendChild(self.doc.createTextNode("\n" + (_indent_character * (indent_level-1))))
			for label in labels:
				if not label.is_project_label:
					continue
				label_element = self.doc.createElement("label")
				label_element.setAttribute("name", label.name)
				label_element.setAttribute("color", label.color)
				label_element.setAttribute("text", label.text_color)
				if label.description is not None:
					label_element.appendChild(self.doc.createTextNode(label.description))
				labels_element.appendChild(self.doc.createTextNode(_indent_character))
				labels_element.appendChild(label_element)
				labels_element.appendChild(self.doc.createTextNode("\n" + (_indent_character * (indent_level-1))))


class PentextProject(gitlab.v4.objects.projects.Project):

	__module__ = "gitlab.v4.objects.projects"

	def __init__(self, *args, **kwargs) -> None:
		super().__init__(*args, **kwargs)
		self.report = Report()

	@property
	def findings(self):
		return self.get_report_assets(Finding, labels=["finding", *LABELS])

	@property
	def non_findings(self):
		return self.get_report_assets(NonFinding, labels=["non-finding", *LABELS])

	def get_report_assets(self, obj_cls, labels=LABELS, milestone=MILESTONE, **kwargs):
		_obj_cls = self.issues._obj_cls
		self.issues._obj_cls = curry_project_obj_cls(obj_cls, pentext_project=self)
		for issue in self.issues.list(
			state="opened",
			milestone=milestone,
			labels=labels,
			**kwargs,
			iterator=True
		):
			yield issue
		self.issues._obj_cls = _obj_cls

	@staticmethod
	def __simplify(text: str) -> str:
		return text.lower().replace(" ", "").strip().strip(":#")

	def _match_milestone_and_labels(self, issue):
		if len(issue.labels) and len(LABELS):
			# always accept issues without any label
			match = False
			for label in LABELS:
				if label in issue.labels:
					match = True
					break
			if match is False:
				# skip when issue has labels, but none matches the input query
				return False
		if MILESTONE is not None:
			# always accept issues without milestone
			if (issue.milestone is not None) and (issue.milestone != MILESTONE):
				# skip when milestone is not empty or does not match
				return False
		return True

	def search_report_section_parts(self, section_name):
		kwargs = {
			"search": section_name,
			"in": "title"
		}
		issues = self.get_report_assets(
			SectionPart,
			labels=[],
			milestone=None,
			**kwargs
		)
		for issue in issues:
			if self.__simplify(issue.title) != self.__simplify(section_name):
				# skip when title does not match
				continue
			if not self._match_milestone_and_labels(issue):
				continue
			yield issue

	def search_report_section(self, section_name, obj_cls):
		parts = [*self.search_report_section_parts(section_name)]
		return obj_cls(*parts, pentext_project=self)

	def get_report_section_parts_by_labels(self, labels):
		for issue in self.get_report_assets(SectionPart, labels=labels, milestone=None):
			if self._match_milestone_and_labels(issue):
				yield issue

	def get_report_section_by_labels(self, labels, obj_cls):
		parts = [*self.get_report_section_parts_by_labels(labels)]
		return obj_cls(*parts, pentext_project=self)

	@property
	def conclusion(self):
		return self.search_report_section("Conclusion", Conclusion)

	@property
	def resultsinanutshell(self):
		return self.search_report_section("Results In A Nutshell", ResultsInANutshell)

	@property
	def futurework(self):
		return self.get_report_section_by_labels(["future-work"], FutureWork)

	def write(self):
		findings_by_severity = sorted(
			self.findings,
			key=lambda finding: get_threat_level_number(finding.threatlevel),
			reverse=True
		)
		for finding in findings_by_severity:
			if not finding.exists or (SKIP_EXISTING is False):
				finding.write()
			else:
				testsuite = pentext_unit.get_or_add_testsuite(finding.iid)
				testsuite.setAttribute("tests", "0")
				testsuite.setAttribute("skipped", "1")
			self.report.add_finding(finding)

		non_findings = self.non_findings
		if non_findings is not None:
			logging.warning("Non-findings section does not exist in report.xml")
			for non_finding in self.non_findings:
				if not non_finding.exists or (SKIP_EXISTING is False):
					non_finding.write();
				self.report.add_non_finding(non_finding)

		self.conclusion.write()
		self.resultsinanutshell.write()
		self.futurework.write()
		self.report.toggle_include_comments()

		if options.include_labels is True:
			self.report.update_labels(self.labels.list(iterator=True))

		self.report.write()
		logging.info("ROS Project written")


client.projects._obj_cls = PentextProject
project = client.projects.get(os.environ["CI_PROJECT_ID"])

def _resolve_internal_links(markdown_text: str) -> str:

	def resolve_link(match):
		try:
			target_finding = next(filter(
				lambda finding: finding.iid == int(match.group(1)),
				project.findings
			))
			return f'<a href="#{target_finding.slug}"/>';
		except StopIteration:
			return f"{match.group()}"

	return re.sub(
		r'#(\d+)',
		resolve_link,
		markdown_text
	)

if __name__ == "__main__":
	project.write()
	pentext_unit.write()
	if has_errors is True:
		logging.error("Exited with errors")
		sys.exit(1)
