#!/usr/bin/env python3

import glob
import codecs
import argparse
from lxml import etree
import os
import subprocess
from subprocess import PIPE
import textwrap
import sys


def parse_arguments():
    """
    Parses command line arguments.
    """
    parser = argparse.ArgumentParser(
        formatter_class=argparse.RawDescriptionHelpFormatter,
        description=textwrap.dedent('''\
Takes findings & non-findings converted from Gitlab, cleans them up, puts them in the report and downloads all referenced images

Copyright (C) 2015-2017  Radically Open Security (Peter Mosmans)

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.'''))
    parser.add_argument('--project', action='store',
                        help='project name')
    parser.add_argument('--saxon', action='store',
                        default='/Users/patje/Workspace/ROS/tools/SaxonHE10/saxon-he-10.2.jar',
                        help="""saxon JAR file (default
                        /Users/patje/Workspace/ROS/tools/SaxonHE10/saxon-he-10.2.jar)""")
    parser.add_argument('--glclean', action='store',
                        default='xslt/gitlab_export_cleanup.xsl',
                        help="""xslt for cleaning findings (default
                        /xslt/gitlab_export_cleanup.xsl)""")
    parser.add_argument('--glsplit', action='store',
                        default='xslt/gitlab_export_splitter.xsl',
                        help="""xslt for splitting images out of paragraphs (default
                        /xslt/gitlab_export_splitter.xsl)""")
    parser.add_argument('--prettyprint', action='store',
                        default='xslt/indent.xsl',
                        help="""basic identity transformation for pretty-printing (default
                        /xslt/gitlab_export_splitter.xsl)""")
    return vars(parser.parse_args())


def print_line(text, error=False):
    """
    Prints text, and flushes stdout and stdin.
    When @error, prints text to stderr instead of stdout.
    """
    if not error:
        print(text)
    else:
        print(text, file=sys.stderr)
    sys.stdout.flush()
    sys.stderr.flush()


def main():
    """
    The main program.
    """

    # list of xml files in findings:
    options = parse_arguments()
    reportXML = "source/report.xml"
    findings = glob.glob("findings/*.xml")
    nonfindings = glob.glob("non-findings/*.xml")
    threatLevelDict = {}

    for doc in findings + nonfindings:
        tree = etree.parse(doc)
        root = tree.getroot()
        # find all referred images in doc and download them
        imgs = root.iter('img')
        for img in imgs:
            srcAttr = img.get("src")
            # if doc has been cleaned up before, its img src has had an "../" added. If so, remove it when forming the img url:
            if srcAttr.startswith("../uploads"):
                srcAttr = srcAttr[3:]
            image_path = srcAttr.split("/")
            image_file = image_path.pop()
            image_path = "/".join(image_path)
            image_url = "http://localhost:8081/ros/{0}/{1}".format(options['project'], srcAttr)
            if not os.path.exists("./" + image_path):
                os.makedirs("./" + image_path)
            cmd = ["curl", image_url, "--output", "./" + srcAttr]
            print_line("   - Downloading image `{0}`".format(image_file))
            process = subprocess.Popen(cmd, stdout=PIPE, stderr=PIPE)
            stdout, stderr = process.communicate()

        print_line("[+] Auto-cleaning '{0}'".format(doc))

        # clean doc
        cmd = ['java', '-jar', options['saxon'], '-s:' + doc, '-xsl:' + options['glclean'], '-o:' + doc]
        process = subprocess.Popen(cmd, stdout=PIPE, stderr=PIPE)
        stdout, stderr = process.communicate()

        # split <img> out of <p> in doc
        cmd = ['java', '-jar', options['saxon'], '-s:' + doc, '-xsl:' + options['glsplit'], '-o:' + doc]
        process = subprocess.Popen(cmd, stdout=PIPE, stderr=PIPE)
        stdout, stderr = process.communicate()

        # add finding & threatLevel to dict
        if doc in findings:
            threatLevelDict[doc] = root.get("threatLevel")

    threatLevelOrder = ["Extreme", "High", "Elevated", "Moderate", "Low", "N/A", "Unknown"]

    reporttree = etree.parse(reportXML)
    reportroot = reporttree.getroot()
    etree.register_namespace("xi", "http://www.w3.org/2001/XInclude")
    xmlns_uri = {'xi': 'http://www.w3.org/2001/XInclude'}

    print_line("[+] Adding findings to report")
    # find section with findings
    findingSection = reportroot.findall(".//section[@id = 'findings']")[0]
    # remove all children except first (title) and second (introductory para)
    for child in findingSection.getchildren()[2:]:
        findingSection.remove(child)

    # add in xincludes for findings (by threatLevel)
    for threatLevel in threatLevelOrder:
        comment = etree.Comment(threatLevel)
        findingSection.append(comment)
        for filename in sorted([k for k, v in threatLevelDict.items() if v == threatLevel]):
            findingSection.append(etree.Element('{%s}include' % xmlns_uri['xi'], {'href': '../{}'.format(filename)}))

    print_line("[+] Adding non-findings to report")
    # find section with non-findings
    nonfindingSection = reportroot.findall(".//section[@id = 'nonFindings']")[0]
    # remove all children except first (title) and second (introductory para)
    for child in nonfindingSection.getchildren()[2:]:
        nonfindingSection.remove(child)

    # add in xincludes for non-findings
    for filename in sorted(nonfindings):
        nonfindingSection.append(etree.Element('{%s}include' % xmlns_uri['xi'], {'href': '../{}'.format(filename)}))

    expfile = codecs.open(reportXML, "w", "utf-8")
    etree.ElementTree(reportroot).write(reportXML, encoding="UTF-8", xml_declaration=True, pretty_print=True)
    expfile.close()

    print_line("[+] Indenting report")
    # pretty-print report
    cmd = ['java', '-jar', options['saxon'], '-s:' + reportXML, '-xsl:' + options['prettyprint'], '-o:' + reportXML]
    process = subprocess.Popen(cmd, stdout=PIPE, stderr=PIPE)
    stdout, stderr = process.communicate()


if __name__ == "__main__":
    main()
