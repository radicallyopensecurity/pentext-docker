#!/bin/sh
set -e

TARGET_DIR_FULL="$CI_PROJECT_DIR/target"
SOURCE_DIR_FULL="$CI_PROJECT_DIR/source"

# TODO rewrite to better deal with spaces and special characters?
PROJECT_NAME="$(echo ${CI_PROJECT_NAME} | sed s/^off-// | sed s/^pen-//)"

set -x

# note: the target directory creation has to be done on the container host side

# note: working in temporary directory would be preferable since it 
# avoids creating and deleting the fop .fo intermediary file in place 
# in the "target/" folder, but the pentext system relies on relative paths,
# which makes out-of-tree builds more difficult
cd "$CI_PROJECT_DIR"

to_csv()
{
        DOC_TYPE="${1:-report}"
        echo "Building ${TARGET_DIR_FULL}/${DOC_TYPE}_${PROJECT_NAME}.csv"
        java -jar /opt/saxon/saxon.jar \
                "-s:$SOURCE_DIR_FULL/${DOC_TYPE}.xml" \
                "-xsl:$CI_PROJECT_DIR/xslt/findings2csv.xsl" \
                "-o:${TARGET_DIR_FULL}/${DOC_TYPE}_${PROJECT_NAME}.csv" \
                -xi
}


to_html()
{
	DOC_TYPE="${1:-report}"
	echo "Building ${TARGET_DIR}/${DOC_TYPE}_${PROJECT_NAME}.html"
	time java -jar /opt/saxon/saxon.jar \
		"-s:$SOURCE_DIR_FULL/${DOC_TYPE}.xml" \
		"-xsl:$CI_PROJECT_DIR/xslt/generate_html_report.xsl" \
		"-o:${TARGET_DIR_FULL}/${DOC_TYPE}_${PROJECT_NAME}.html" \
		-xi
}

to_fo()
{
	DOC_TYPE="${1:-report}"
	echo "Building ${DOC_TYPE}_${PROJECT_NAME}.fo"
	java -jar /opt/saxon/saxon.jar \
		"-s:$SOURCE_DIR_FULL/${DOC_TYPE}.xml" \
		"-xsl:$CI_PROJECT_DIR/xslt/generate_${DOC_TYPE}.xsl" \
		"-o:$TARGET_DIR_FULL/${DOC_TYPE}_${PROJECT_NAME}.fo" \
		-xi
}

to_pdf()
{
	DOC_TYPE="${1:-report}"
	to_fo "$DOC_TYPE"
	echo "Building ${DOC_TYPE}_${PROJECT_NAME}.pdf"
	/opt/fop/fop \
		-c /opt/fop/conf/rosfop.xconf \
		"$TARGET_DIR_FULL/${DOC_TYPE}_${PROJECT_NAME}.fo" \
		"${TARGET_DIR_FULL}/${DOC_TYPE}_${PROJECT_NAME}.pdf" \
		-v \
		-noassembledoc \
		-noedit \
		-o "$PDF_PASSWORD" \
		-u "$PDF_PASSWORD"

	# delete *.fo file to clean the output directory
	rm $TARGET_DIR_FULL/${DOC_TYPE}_${PROJECT_NAME}.fo

	if [[ -z "$SKIP_METADATA_REMOVAL" ]]; then 
		# remove metadata
		exiftool -all= -overwrite_original_in_place "${TARGET_DIR_FULL}/${DOC_TYPE}_${PROJECT_NAME}.pdf"

		# restructure PDF to make metadata changes permanent
		qpdf --linearize --replace-input "${TARGET_DIR_FULL}/${DOC_TYPE}_${PROJECT_NAME}.pdf"
	fi

}

if [[ -z "$SKIP_REPORT_PDF_GENERATION" ]] && [ -f "/$CI_PROJECT_DIR/source/report.xml" ]; then
	to_pdf report
fi
if [[ -z "$SKIP_REPORT_CSV_GENERATION" ]] && [ -f "/$CI_PROJECT_DIR/source/report.xml" ]; then
	to_csv report
fi
if [[ -z "$SKIP_REPORT_HTML_GENERATION" ]] && [ -f "/$CI_PROJECT_DIR/source/report.xml" ]; then
        to_html report
fi


if [[ -z "$SKIP_OFFERTE_GENERATION" ]] && [ -f "/$CI_PROJECT_DIR/source/offerte.xml" ]; then
	to_pdf offerte
fi

if [[ -z "$SKIP_EXTRA_DOCUMENT_GENERATION" ]] && [ -f "/$CI_PROJECT_DIR/source/document.xml" ]; then
	to_pdf document
fi

ls -al $TARGET_DIR_FULL
