#!/usr/local/env python3
import typing
import re
import os
import os.path
import pathlib
import xml.dom.minidom
import urllib.request

from gitlab import Gitlab
from markdown import markdown
from slugify import slugify

GITLAB_SERVER_URL = os.environ.get(
	"CI_SERVER_URL",
	"https://git.radicallyopensecurtity.com"
)

gitlab = Gitlab(
  GITLAB_SERVER_URL,
  private_token=os.environ["GITLAB_TOKEN"]
)
gitlab.auth()

opener = urllib.request.build_opener()
opener.addheaders = [('PRIVATE-TOKEN', os.environ["GITLAB_TOKEN"])]
urllib.request.install_opener(opener)

pathlib.Path("uploads").mkdir(parents=True, exist_ok=True)
pathlib.Path("findings").mkdir(parents=True, exist_ok=True)
pathlib.Path("non-findings").mkdir(parents=True, exist_ok=True)


class InvalidUploadPathException(Exception):
	pass


upload_path_pattern = re.compile(
	"(?:\.{2})?/uploads/(?P<hex>[A-Fa-f0-9]{32})/(?P<filename>[^\.][^/]+)"
)


class Upload:

	def __init__(self, path) -> None:
		self.path = path

	@property
	def path(self):
		return f"/uploads/{self.hex}/{self.filename}"
	
	@path.setter
	def path(self, value):
		match = upload_path_pattern.match(value)
		if match is None:
			raise InvalidUploadPathException()
		self.hex = match["hex"]
		self.filename = match["filename"]

	@property
	def url(self):
		project_url = os.environ["CI_PROJECT_URL"]
		return f"{project_url}{self.path}"
	
	@property
	def local_path(self):
		return f"uploads/{self.hex}/{self.filename}"

	def download(self) -> None:
		if os.path.exists(self.local_path) is True:
			print(f"skip download {self.local_path} - file exists")
			return
		dirname = os.path.dirname(self.local_path)
		os.makedirs(dirname, exist_ok=True)
		print(f"downloading {self.url} to {self.local_path}")
		urllib.request.urlretrieve(self.url, self.local_path)


class ReportAsset:

	def __init__(
		self,
		id: int,
		title: str
	):
		self.id = id
		self.title = title

	@property
	def doc(self):
		raise NotImplementedError()

	@property
	def processed_doc(self):
		doc = self.doc
		images = doc.getElementsByTagName("img")
		image_urls = [image.getAttribute("src") for image in images]
		for image in images:
			image_url = image.getAttribute("src");
			try:
				attachment = Upload(image_url)
				attachment.download()
				image.setAttribute("src", f"../{attachment.local_path}")
			except InvalidUploadPathException:
				pass
		return doc

	@property
	def prettyxml(self):
		return self.processed_doc.toprettyxml(
			indent="\t",
			encoding="UTF-8"
		)

	@staticmethod
	def _markdown_to_dom(markdown_text: str) -> typing.List[xml.dom.minidom.Element]:
		# gitlab.markdown does not close single elements (e.g. <img/>) properly
		# html = gitlab.markdown(markdown_text, gmf=True)
		html = markdown(markdown_text)
		dom = xml.dom.minidom.parseString(f"<root>{html}</root>")
		return dom.firstChild.childNodes

	def write(self, path=None) -> None:
		if path is None:
			path = self.relative_path
		with open(path, "w") as file:
			print(f"writing {path}")
			file.write(self.prettyxml.decode("UTF-8"))

	@property
	def relative_path(self):
		return self.filename;

	@property
	def filename(self):
		return f"{self.slug}.xml"

	@property
	def slug(self):
		return f"f{self.id}-{slugify(self.title)}"


class Finding(ReportAsset):

	def __init__(
		self,
		id: int,
		title: str,
		description: str="",
		technicaldescription: str="",
		impact: str="",
		recommendation: str="",
		threatlevel: str="Unknown",
		type: str="Unknown",
		status: str="none"
	):
		super().__init__(id, title)
		self.description = description
		self.technicaldescription = technicaldescription
		self.impact = impact
		self.recommendation = recommendation
		self.threatlevel = threatlevel
		self.type = type
		self.status = status

	@property
	def doc(self):
		doc = xml.dom.minidom.Document()

		root = doc.createElement("finding");
		root.setAttribute("id", self.slug)
		root.setAttribute("number", str(self.id))
		root.setAttribute("threatLevel", self.threatlevel)
		root.setAttribute("type", self.type)
		root.setAttribute("status", self.status)

		title = doc.createElement("title");
		title.appendChild(doc.createTextNode(self.title))
		root.appendChild(title)

		self.__append_section(root, "description")
		self.__append_section(root, "technicaldescription")
		self.__append_section(root, "impact")
		self.__append_section(root, "recommendation")

		doc.appendChild(root)
		return doc

	def __append_section(self, parentNode, name):
		section = xml.dom.minidom.Element(name)
		markdown_text = self.__getattribute__(name)
		section_nodes = self._markdown_to_dom(markdown_text)
		for node in section_nodes:
			section.appendChild(node)
		parentNode.appendChild(section)

	@property
	def relative_path(self):
		return f"findings/{self.filename}"


class NonFinding(ReportAsset):

	def __init__(
		self,
		id: int,
		title: str,
		description: str=""
	):
		super().__init__(id, title)
		self.description = description

	@property
	def doc(self):
		doc = xml.dom.minidom.Document()
		root = doc.createElement("non-finding");
		root.setAttribute("id", self.slug)
		root.setAttribute("number", str(self.id))

		title = doc.createElement("title");
		title.appendChild(doc.createTextNode(self.title))
		root.appendChild(title)

		content_nodes = self._markdown_to_dom(self.description)
		for node in content_nodes:
			root.appendChild(node)
		doc.appendChild(root)
		return doc

	@property
	def relative_path(self):
		return f"non-findings/{self.filename}"


class Report:

	def __init__(
		self,
		path: str="source/report.xml"
	) -> None:
		self.path = path
		self.doc = None
		self.read()

	def read(self):
		self.doc = xml.dom.minidom.parse(self.path)

	def write(self, dest=None):
		if dest is None:
			dest = self.path
		with open(dest, "w", encoding="UTF-8") as file:
			print(f"writing report to {dest}")
			file.write(self.doc.toprettyxml(indent="\t"))

	def get_section(self, section_name):
		for section in self.doc.documentElement.getElementsByTagName("section"):
			if section.getAttribute("id") == section_name:
				return section

	@property
	def findings(self):
		return self.get_section("findings")

	@property
	def non_findings(self):
		return self.get_section("non-findings")

	def add(self, section_name, item):
		el = self.doc.createElement("xi:include")
		el.setAttribute("xmlns:xi", "http://www.w3.org/2001/XInclude")
		el.setAttribute("href", os.path.join("..", item.relative_path))
		section = self.get_section(section_name)
		section.appendChild(el)

	def add_finding(self, finding: Finding) -> None:
		self.add("findings", finding)

	def add_non_finding(self, non_finding: NonFinding) -> None:
		self.add("nonFindings", non_finding)



def readFindingFromIssue(issue):
	technicaldescription = ""
	impact = ""
	recommendation = ""
	threatlevel = "Unknown"
	type = "Unknown"
	status = "none"

	i = 0
	for discussion in issue.discussions.list():
		comment = discussion.attributes["notes"][0]["body"]
		i += 1

		# the first comment is the technical description
		if i == 1:
			technicaldescription = comment
			continue
		
		# other comments can have a meaning as well 
		lines = comment.splitlines()
		first_line = lines.pop(0)
		if first_line.lower().strip().endswith("recommendation"):
			recommendation = "\n".join(lines)
		elif first_line.lower().strip().endswith("impact"):
			impact = "\n".join(lines)
		elif first_line.lower().strip().endswith("type"):
			type = lines[0].strip()

	for label in issue.labels:
		if label.lower().startswith("threatlevel:") is True:
			threatlevel = label.split(":", maxsplit=1)[1]
		if label.lower().startswith("status:") is True:
			status = label.split(":", maxsplit=1)[1]


	return Finding(
		id=issue.id,
		title=issue.title,
		description=issue.description,
		technicaldescription=technicaldescription,
		impact=impact,
		recommendation=recommendation,
		threatlevel=threatlevel,
		type=type,
		status=status
	)


class ROSProject:

	def __init__(self, project_id: int) -> None:
		self.gitlab_project = gitlab.projects.get(project_id)
		self._findings = None
		self._non_findings = None
		self.report = Report()

	@property
	def findings(self):
		if self._findings is None:
			self._findings = list(map(
				readFindingFromIssue,
				self.gitlab_project.issues.list(labels=["finding"])
			))
		return self._findings

	@property
	def non_findings(self):
		if self._non_findings is None:
			self._non_findings = list(map(
				lambda issue: NonFinding(issue.id, issue.title, issue.description),
				self.gitlab_project.issues.list(labels=["non-finding"])
			))
		return self._non_findings

	def write(self):
		for finding in self.findings:
			finding.write();
			self.report.add_finding(finding)
		for non_finding in self.non_findings:
			non_finding.write();
			self.report.add_non_finding(non_finding)
		self.report.write()
		print("ROS Project written")


project = ROSProject(os.environ["CI_PROJECT_ID"])
project.write()