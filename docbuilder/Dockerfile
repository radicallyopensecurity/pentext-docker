ARG FOP_VERSION=2.9
ARG SAXON_VERSION=11.6

# build container, used for downloading and checking non-packaged software
FROM eclipse-temurin:22-alpine as download-and-extract-tools
ARG FOP_VERSION
ARG SAXON_VERSION

WORKDIR /tmp

RUN apk add --no-cache gnupg

# "-D" Don't assign a password
RUN adduser builder -D

USER builder

# The KEYS file is a variation of https://downloads.apache.org/xmlgraphics/fop/KEYS 
# Since many of the included keys in the upstream KEYS file are weak or old, our
# local copy focuses on a single, reasonably trustworthy signing key
#
# pub   rsa4096 2015-05-20 [SC]
#       5C9A30FF22B2C02F30261C305B93F1DF7CDB6DEA
# uid           [ unknown] Simon Steiner (CODE SIGNING KEY) <ssteiner@apache.org>
# sub   rsa4096 2015-05-20 [E]

ADD KEYS .
RUN gpg --import KEYS

# the apache project apparently only makes the latest version available for download on the main server
# under https://downloads.apache.org/xmlgraphics/fop/binaries/
# 
# as soon as a new version gets released, downloading the pinned version start failing with 404s
# therefore use the https://archive.apache.org/dist/xmlgraphics/fop/binaries/ location which has old + new
RUN wget https://archive.apache.org/dist/xmlgraphics/fop/binaries/fop-${FOP_VERSION}-bin.tar.gz -O fop-bin.tar.gz
RUN wget https://archive.apache.org/dist/xmlgraphics/fop/binaries/fop-${FOP_VERSION}-bin.tar.gz.asc -O fop-bin.tar.gz.asc

# sha512sum of Saxon ZIP archive of version SAXON_VERSION
# reminder: update this line when switching to a new Saxon version
RUN echo "2370a0aebc85007106f030a7aa95eee8a909542d9a80da56a0cf43fa4ff405f5a7f7804edf3755ca82e718a13032fbe9935f928257327dc2f4725b0c21dba692 SaxonHE-J.zip" > SHA512SUM.txt

# the download URL needs the version number with a dash instead of dot separator
# generate this string dynamically and avoid the need for a separate ARG variable
RUN SAXON_VERSION_DASH=$(echo ${SAXON_VERSION} | sed "s/\./\-/") && \
    wget https://github.com/Saxonica/Saxon-HE/raw/main/11/Java/SaxonHE${SAXON_VERSION_DASH}J.zip -O SaxonHE-J.zip

# check file integrity or correct signature
RUN sha512sum -c SHA512SUM.txt

# the gpg lockfile is stuck for some reason on newer OS eclipse-temurin versions >= 21
# manually remove the lockfile to work around the issue
RUN rm -f ~/.gnupg/public-keys.d/pubring.db.lock
RUN gpg --keyring ~/.gnupg/trustdb.gpg --verify fop-bin.tar.gz.asc fop-bin.tar.gz

# unpack archives
RUN tar -xf fop-bin.tar.gz
RUN unzip SaxonHE-J.zip

# main container
FROM eclipse-temurin:22-alpine
ARG FOP_VERSION
ARG SAXON_VERSION

COPY --from=download-and-extract-tools /tmp/fop-${FOP_VERSION}/fop /opt/fop
COPY --from=download-and-extract-tools /tmp/saxon-he-${SAXON_VERSION}.jar /opt/saxon/saxon.jar
COPY --from=download-and-extract-tools /tmp/lib/* /opt/saxon/lib/

# TODO check if this path is necessary
ENV PATH=/opt/fop:/opt/saxon:${PATH}

# install font* packages for the required font groups
RUN apk add --no-cache fontconfig ttf-dejavu exiftool qpdf font-liberation-sans-narrow font-opensans font-liberation

# add dummy fontconfig.properties to fix NPE
# https://github.com/AdoptOpenJDK/openjdk-build/issues/693
COPY configs/fontconfig.properties /usr/lib/jvm/java-1.9-openjdk/jre/lib/fontconfig.properties
COPY configs/rosfop.xconf /opt/fop/conf/rosfop.xconf
COPY scripts/build-document.sh /opt/build-document.sh

# some of the hardening steps are dependent on the
# container being run by a host user with a specific UID and GID
# one well-known workaround is laid out below
#
# note that this requires the targeted IDs to be set at container build time (!)
# adapted from https://github.com/mhart/alpine-node/issues/48#issuecomment-430902787 
#
# ARG UID
# ARG GID
# RUN apk add --no-cache shadow && \
#     if [ -z "`getent group $GID`" ]; then \
#       addgroup -S -g $GID pentext; \
#     else \
#       groupmod -n pentext `getent group $GID | cut -d: -f1`; \
#     fi && \
#     if [ -z "`getent passwd $UID`" ]; then \
#       adduser -S -u $UID -G pentext -s /bin/sh pentext; \
#     else \
#       usermod -l pentext -g $GID -d /home/pentext -m `getent passwd $UID | cut -d: -f1`; \
#     fi
#
# WORKDIR /home/pentext
#
# this should now have the desired UID:GID values
# USER pentext

# defaults to uid 1000, gid 1000
# "-D" Don't assign a password
RUN adduser pentext -D

USER pentext

ENTRYPOINT /opt/build-document.sh
