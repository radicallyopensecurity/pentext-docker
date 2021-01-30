#!/bin/sh
cd "$CI_PROJECT_DIR"
TARGET_DIR="target"

mkdir -p $TARGET_DIR

to_fo()
{
	DOC_TYPE="${1:-report}"
	echo "Building ${TARGET_DIR}/${DOC_TYPE}.fo"
	java -jar /saxon.jar \
		"-s:source/${DOC_TYPE}.xml" \
		"-xsl:xslt/generate_${DOC_TYPE}.xsl" \
		"-o:${TARGET_DIR}/${DOC_TYPE}.fo" \
		-xi
}

to_pdf()
{
	DOC_TYPE="${1:-report}"
	to_fo "$DOC_TYPE"
	echo "Building ${TARGET_DIR}/${DOC_TYPE}.pdf"
	/fop/fop \
		-c /fop/conf/rosfop.xconf \
		"${TARGET_DIR}/${DOC_TYPE}.fo" \
		"${TARGET_DIR}/${DOC_TYPE}.pdf" \
		-v \
		-nocopy \
		-noaccesscontent \
		-noassembledoc \
		-noedit \
		-noannotations \
		-o "$PDF_PASSWORD" \
		-u "$PDF_PASSWORD" 
}

if [ -f "source/report.xml" ]; then
	to_pdf report
elif [ -f "source/offerte.xml" ]; then
	to_pdf offerte
fi
