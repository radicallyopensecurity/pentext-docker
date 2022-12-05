ARG FOP_VERSION=2.7
ARG SAXON_VERSION=10.5

FROM eclipse-temurin:19 as download-and-extract-tools
ARG FOP_VERSION
ARG SAXON_VERSION

RUN apt-get update
RUN apt-get upgrade -y
RUN apt-get install -y gnupg wget
# safely download https://downloads.apache.org/xmlgraphics/fop/KEYS and verify the keys in it once, outside the docker.
ADD KEYS .
RUN gpg --import KEYS
RUN wget https://archive.apache.org/dist/xmlgraphics/fop/binaries/fop-${FOP_VERSION}-bin.tar.gz
RUN wget https://archive.apache.org/dist/xmlgraphics/fop/binaries/fop-${FOP_VERSION}-bin.tar.gz.asc

RUN wget https://repo1.maven.org/maven2/net/sf/saxon/Saxon-HE/${SAXON_VERSION}/Saxon-HE-${SAXON_VERSION}.jar
RUN gpg --verify fop-${FOP_VERSION}-bin.tar.gz.asc fop-${FOP_VERSION}-bin.tar.gz
RUN tar -xf fop-${FOP_VERSION}-bin.tar.gz
# use strict to force error exit code when jar is unsigned
RUN jarsigner -verify -strict Saxon-HE-${SAXON_VERSION}.jar

FROM eclipse-temurin:19
ARG FOP_VERSION
ARG SAXON_VERSION

COPY --from=download-and-extract-tools /fop-${FOP_VERSION}/fop /fop
COPY --from=download-and-extract-tools /Saxon-HE-${SAXON_VERSION}.jar /saxon.jar
ENV PATH=/fop:${PATH}

RUN apt-get update
RUN apt-get upgrade -y
RUN apt-get install -y fontconfig fonts-dejavu

# add dummy fontconfig.properties to fix NPE -- https://github.com/AdoptOpenJDK/openjdk-build/issues/693
COPY configs/fontconfig.properties /usr/lib/jvm/java-1.9-openjdk/jre/lib/fontconfig.properties
COPY configs/rosfop.xconf /fop/conf/rosfop.xconf
COPY fonts/* /fop/fonts/
COPY scripts/build-document.sh /scripts/build-document.sh

ENTRYPOINT /scripts/build-document.sh
