ARG SAXON_VERSION=10.3

FROM eclipse-temurin:20-alpine as download-and-extract-tools
ARG SAXON_VERSION

RUN wget https://repo1.maven.org/maven2/net/sf/saxon/Saxon-HE/${SAXON_VERSION}/Saxon-HE-${SAXON_VERSION}.jar
# use strict to force error exit code when jar is unsigned
RUN jarsigner -verify -strict Saxon-HE-${SAXON_VERSION}.jar

FROM eclipse-temurin:20-alpine
ARG SAXON_VERSION

COPY --from=download-and-extract-tools /Saxon-HE-${SAXON_VERSION}.jar /saxon.jar

RUN apk add --no-cache git

# add dummy fontconfig.properties to fix NPE -- https://github.com/AdoptOpenJDK/openjdk-build/issues/693
ADD scripts/off2rep.sh /scripts/off2rep.sh

ENTRYPOINT /scripts/off2rep.sh
