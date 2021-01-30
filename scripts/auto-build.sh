#!/bin/sh
if [ -f "source/report.xml" ]; then
	echo "Building Report"
	/usr/bin/python3 /scripts/docbuilder -c --input "source/report.xml"
elif [ -f "source/offerte.xml" ]; then
	echo "Building Offerte"
	/usr/bin/python3 /scripts/docbuilder -c --input "source/offerte.xml"
fi
