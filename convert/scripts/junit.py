import os
import os.path
import re
import xml.dom.minidom

import logging
logging.basicConfig(level=os.environ.get("LOGLEVEL", "INFO"))

# ToDo: duplicate from convert.py
def to_prettyxml(doc):
	output = doc.toprettyxml(encoding="UTF-8").decode("UTF-8")
	# force newline after XML declaration
	output = re.sub(r"^(<\?xml[^>\n]*>)", r"\1\n", output, count=1)
	# end file with newline
	output = re.sub(r"\n*$", "\n", output)
	return output

class PentextUnit:

	relative_path = "./target/junit.xml";

	def __init__(self):
		super().__init__()
		self.doc = xml.dom.minidom.Document()
		self.doc.appendChild(self.doc.createElement("testsuites"))	

	@property
	def testsuites(self):
		return self.doc.childNodes[0]

	def get_or_add_testsuite(self, name):
		for testsuite in self.testsuites.childNodes:
			if testsuite.getAttribute("name") != str(name):
				continue
			return testsuite
		testsuite = self.doc.createElement("testsuite")
		testsuite.setAttribute("name", str(name))
		self.testsuites.appendChild(testsuite)
		return testsuite

	def add_testcase(self, testsuite_name, name, filename, status=None):
		testsuite = self.get_or_add_testsuite(testsuite_name);
		testcase = self.doc.createElement("testcase")
		testcase.setAttribute("name", str(name))
		testcase.setAttribute("classname", str(testsuite_name))
		testcase.setAttribute("file", str(filename))
		if status is not None:
			testcase.appendChild(status)
		testsuite.appendChild(testcase)
		return testcase

	def write(self) -> None:
		prettyxml = to_prettyxml(self.doc)
		os.makedirs(os.path.dirname(self.relative_path), exist_ok=True)
		with open(self.relative_path, "w", encoding="UTF-8") as file:
			logging.info(f"writing {self.relative_path}")
			file.write(prettyxml)
