ARG FOP_VERSION=2.5
ARG SAXON_VERSION=10.3

FROM openjdk:alpine as download-and-extract-tools
ARG FOP_VERSION
ARG SAXON_VERSION

RUN apk add --no-cache gnupg
# safely download https://downloads.apache.org/xmlgraphics/fop/KEYS and verify the keys in it once, outside the docker.
ADD KEYS .
RUN gpg --import KEYS
RUN wget https://downloads.apache.org/xmlgraphics/fop/binaries/fop-${FOP_VERSION}-bin.tar.gz
RUN wget https://downloads.apache.org/xmlgraphics/fop/binaries/fop-${FOP_VERSION}-bin.tar.gz.asc
RUN wget https://repo1.maven.org/maven2/net/sf/saxon/Saxon-HE/${SAXON_VERSION}/Saxon-HE-${SAXON_VERSION}.jar
RUN gpg --verify fop-${FOP_VERSION}-bin.tar.gz.asc fop-${FOP_VERSION}-bin.tar.gz
RUN tar -xf fop-${FOP_VERSION}-bin.tar.gz
RUN jarsigner -verify Saxon-HE-${SAXON_VERSION}.jar

FROM java:openjdk-8-jre-alpine
ARG FOP_VERSION
ARG SAXON_VERSION

COPY --from=download-and-extract-tools /fop-${FOP_VERSION}/fop /fop
COPY --from=download-and-extract-tools /Saxon-HE-${SAXON_VERSION}.jar /saxon.jar
ENV PATH=/fop:${PATH}

RUN apk add --no-cache fontconfig ttf-dejavu


# add dummy fontconfig.properties to fix NPE -- https://github.com/AdoptOpenJDK/openjdk-build/issues/693
ADD configs/fontconfig.properties /usr/lib/jvm/java-1.8-openjdk/jre/lib/fontconfig.properties
ADD configs/rosfop.xconf /fop/conf/rosfop.xconf
ADD fonts/* /fop/fonts/
ADD scripts/build-document.sh /scripts/build-document.sh


ENTRYPOINT /scripts/build-document.sh

