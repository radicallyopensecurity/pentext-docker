# there are newer 11.x and 12.x Saxon versions available
ARG SAXON_VERSION=10.9

# eclipse-temurin:21 tracks JDK 21, which is LTS
FROM eclipse-temurin:21-alpine AS download-and-extract-tools
ARG SAXON_VERSION

RUN wget https://repo1.maven.org/maven2/net/sf/saxon/Saxon-HE/${SAXON_VERSION}/Saxon-HE-${SAXON_VERSION}.jar

# use strict to force error exit code when jar is unsigned
RUN jarsigner -verify -strict Saxon-HE-${SAXON_VERSION}.jar

FROM eclipse-temurin:21-alpine
ARG SAXON_VERSION

COPY --from=download-and-extract-tools /Saxon-HE-${SAXON_VERSION}.jar /saxon.jar

RUN apk add --no-cache git

ADD src/quickscope2off.sh /usr/local/src/quickscope2off/quickscope2off.sh

ENTRYPOINT ["/usr/local/src/quickscope2off/quickscope2off.sh"]
