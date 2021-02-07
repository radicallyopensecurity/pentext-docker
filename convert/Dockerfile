FROM python:3.8-alpine

#RUN apk add --no-cache python3 libxml2-dev libxslt-dev cython
#RUN apk add --no-cache build-base enchant2-dev libxml2-dev libxslt-dev cython
#RUN python3 -m pip install python-gitlab requests lxml pyenchant titlecase
RUN python3 -m pip install python-gitlab markdown python-slugify

# ADD scripts/gitlab_to_pentext.py /scripts/gitlab_to_pentext.py
# ADD scripts/gl2pentext_postprocess.py /scripts/gl2pentext_postprocess.py
# ADD scripts/validate_report.py /scripts/validate_report.py

# RUN apk add --no-cache curl
# RUN python3 -m pip install markdown
ARG GITLAB_TOKEN
ENV GITLAB_TOKEN=${GITLAB_TOKEN}

ADD scripts/entrypoint.sh /scripts/entrypoint.sh
ADD scripts/convert.py /scripts/convert.py
ENTRYPOINT /scripts/entrypoint.sh

