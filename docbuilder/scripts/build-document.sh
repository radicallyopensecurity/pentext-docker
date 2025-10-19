#!/bin/sh
set -e

cd "$CI_PROJECT_DIR"
TARGET_DIR="${TARGET_DIR:-${CI_PROJECT_DIR}/target}"
if [ "$CI_PROJECT_NAME" != "" ]; then
	FILENAME_SUFFIX="_$(echo ${CI_PROJECT_NAME} | sed s/^off-// | sed s/^pen-//)"
fi

SOURCE_DOCUMENTS=${SOURCE_DOCUMENTS-offerte document}
SOURCE_REPORTS=${SOURCE_REPORTS-report}
FOP_CONFIG_FILE=${FOP_CONFIG_FILE:-/fop/conf/rosfop.xconf}

set -x
mkdir -p "$TARGET_DIR"

to_csv()
{
	SOURCE_FILE="$1"
	echo "Building ${TARGET_DIR}/${SOURCE_FILE}${FILENAME_SUFFIX}.csv"
	java -jar /saxon.jar \
		"-s:source/${SOURCE_FILE}.xml" \
		"-xsl:xslt/findings2csv.xsl" \
		"-o:${TARGET_DIR}/${SOURCE_FILE}${FILENAME_SUFFIX}.csv" \
		-xi
}

to_html()
{
	SOURCE_FILE="$1"
	echo "Building ${TARGET_DIR}/${SOURCE_FILE}${FILENAME_SUFFIX}.html"
	java -jar /saxon.jar \
		"-s:source/${SOURCE_FILE}.xml" \
		"-xsl:xslt/generate_html_report.xsl" \
		"-o:${TARGET_DIR}/${SOURCE_FILE}${FILENAME_SUFFIX}.html" \
		-xi
}

to_fo()
{
	DOC_TYPE="$1"
	SOURCE_FILE="$2"
	echo "Building ${TARGET_DIR}/${SOURCE_FILE}${FILENAME_SUFFIX}.fo"
	java -jar /saxon.jar \
		"-s:source/${SOURCE_FILE}.xml" \
		"-xsl:xslt/generate_${DOC_TYPE}.xsl" \
		"-o:${TARGET_DIR}/${SOURCE_FILE}${FILENAME_SUFFIX}.fo" \
		-xi
}

to_pdf()
{
	DOC_TYPE="$1"
	SOURCE_FILE="$2"
	to_fo "${DOC_TYPE}" "${SOURCE_FILE}"
	echo "Building ${TARGET_DIR}/${SOURCE_FILE}${FILENAME_SUFFIX}.pdf"
	/fop/fop \
		-c "${FOP_CONFIG_FILE}" \
		"${TARGET_DIR}/${SOURCE_FILE}${FILENAME_SUFFIX}.fo" \
		"${TARGET_DIR}/${SOURCE_FILE}${FILENAME_SUFFIX}.pdf" \
		-v \
		-noassembledoc \
		-noedit \
		-o "$PDF_PASSWORD" \
		-u "$PDF_PASSWORD" 
}

for SOURCE_FILE in ${SOURCE_DOCUMENTS}
do
	if [ "$SOURCE_FILE" = "offerte" ]; then
		DOC_TYPE="offerte"
	else
		DOC_TYPE="document"
	fi
	if [ -f "source/${SOURCE_FILE}.xml" ]; then
		to_pdf "$DOC_TYPE" "$SOURCE_FILE"
	fi
done

for SOURCE_FILE in ${SOURCE_REPORTS}
do
	if [ -f "source/${SOURCE_FILE}.xml" ]; then
		to_pdf report "$SOURCE_FILE"
		to_csv "$SOURCE_FILE"
		to_html "$SOURCE_FILE"
	fi
done

exit 0

ls -al $TARGET_DIR
