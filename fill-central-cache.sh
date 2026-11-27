#!/bin/bash
# fill-central-cache.sh <kit-workdir> : runs ordinary CI builds with an empty local repo so central-proxy caches the plugins
set -e
W=$1/central-fill; rm -rf $W; mkdir -p $W/p/src/main/resources; cd $W/p
echo x=1 > src/main/resources/x.properties
cat > pom.xml <<'P'
<project><modelVersion>4.0.0</modelVersion><groupId>ci</groupId><artifactId>warm</artifactId><version>1</version>
<properties><maven.compiler.release>17</maven.compiler.release></properties>
<build><plugins>
<plugin><groupId>org.apache.maven.plugins</groupId><artifactId>maven-jar-plugin</artifactId><version>3.4.2</version></plugin>
<plugin><groupId>org.apache.maven.plugins</groupId><artifactId>maven-resources-plugin</artifactId><version>3.3.1</version></plugin>
<plugin><groupId>org.apache.maven.plugins</groupId><artifactId>maven-compiler-plugin</artifactId><version>3.13.0</version></plugin>
<plugin><groupId>org.apache.maven.plugins</groupId><artifactId>maven-surefire-plugin</artifactId><version>3.5.2</version></plugin>
<plugin><groupId>org.apache.maven.plugins</groupId><artifactId>maven-install-plugin</artifactId><version>3.1.3</version></plugin>
<plugin><groupId>org.apache.maven.plugins</groupId><artifactId>maven-deploy-plugin</artifactId><version>3.1.3</version></plugin>
</plugins></build></project>
P
for i in $(seq 1 3); do
  mvn -B -ntp -U -s $1/settings.xml -Dmaven.repo.local=$W/repo install org.apache.maven.plugins:maven-dependency-plugin:3.8.1:list org.apache.maven.plugins:maven-dependency-plugin:3.8.1:tree > $W/log 2>&1 && break
  sleep 30
done
grep -q "BUILD SUCCESS" $W/log && echo central-cache-filled
