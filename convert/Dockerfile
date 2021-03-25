FROM pandoc/core:latest

RUN apk add --update --no-cache python3 py3-pip
RUN pip3 install pypandoc

RUN python3 -m pip install python-gitlab python-slugify

# ADD scripts/gitlab_to_pentext.py /scripts/gitlab_to_pentext.py
# ADD scripts/gl2pentext_postprocess.py /scripts/gl2pentext_postprocess.py
# ADD scripts/validate_report.py /scripts/validate_report.py

ADD scripts/entrypoint.sh /scripts/entrypoint.sh
ADD scripts/convert.py /scripts/convert.py
ENTRYPOINT /scripts/entrypoint.sh
