FROM ubuntu

RUN apt-get update
RUN apt-get install -y python3 python3-pip pandoc

RUN python3 -m pip install pypandoc python-gitlab python-slugify

# ADD scripts/gitlab_to_pentext.py /scripts/gitlab_to_pentext.py
# ADD scripts/gl2pentext_postprocess.py /scripts/gl2pentext_postprocess.py
# ADD scripts/validate_report.py /scripts/validate_report.py

COPY scripts/ /scripts/
ENTRYPOINT /scripts/entrypoint.sh
