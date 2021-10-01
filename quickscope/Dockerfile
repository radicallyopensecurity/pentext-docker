ARG SAXON_VERSION=10.3

FROM openjdk:18-alpine as download-and-extract-tools
ARG SAXON_VERSION

RUN wget https://repo1.maven.org/maven2/net/sf/saxon/Saxon-HE/${SAXON_VERSION}/Saxon-HE-${SAXON_VERSION}.jar
RUN jarsigner -verify Saxon-HE-${SAXON_VERSION}.jar

FROM openjdk:18-alpine
ARG SAXON_VERSION

COPY --from=download-and-extract-tools /Saxon-HE-${SAXON_VERSION}.jar /saxon.jar

RUN apk add --no-cache git

# add dummy fontconfig.properties to fix NPE -- https://github.com/AdoptOpenJDK/openjdk-build/issues/693
ADD scripts/quickscope2off.sh /scripts/quickscope2off.sh

ENTRYPOINT /scripts/quickscope2off.sh
