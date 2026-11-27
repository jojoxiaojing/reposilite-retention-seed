# reposilite-retention-seed

Starting data for the Reposilite retention task: a Reposilite working directory that looks like three years of use as the Maven repository for about 40 JVM projects.

- `releases`: about 2,160 release versions of 51 artifacts (libraries, parent POMs, BOMs, services), deployed with real `mvn deploy` and `gradle publish`
- `thirdparty`: jars uploaded by hand, some without `maven-metadata.xml`
- `snapshots`: a few snapshot builds
- `central-proxy`: proxy of Maven Central with the plugins and libraries the builds pulled

File dates and `maven-metadata.xml` timestamps are spread from 2023-12 to 2026-11.

Tokens in the database: `ops-admin` (manager), `ci-deployer` (rw on releases, thirdparty, snapshots), `developers` (read only).

## Use the prepared data

The release `world-v1` has `reposilite-data.tar.gz` (sha256 `962492e031266e1e87091f0f2f0a4787a1b7962712bac0cb53e6af321f9410bc`). It unpacks to `reposilite-data/`:

```
curl -fsSL https://github.com/jojoxiaojing/reposilite-retention-seed/releases/download/world-v1/reposilite-data.tar.gz | tar xz -C /home/lane
```

Start Reposilite against it with `--working-directory /home/lane/reposilite-data`.

## Build the data from scratch

Needs JDK 21, Maven 3.9, Gradle 8, curl and python3, and network access to Maven Central. Build the Reposilite jar from dzikoysk/reposilite at 488caacbcd194631d652d6c6c10b5f63f20a15fd first (`./gradlew :reposilite-backend:shadowJar`).

```
./build-world.sh <reposilite.jar> /home/lane/reposilite-data /var/tmp/seed-m2
```

It starts a temporary Reposilite on port 8080, replays the deploy history in `plan.py` with real Maven and Gradle builds, fills the central proxy, sets file dates (`backdate.py`), and stops the server. A full run takes about 40 minutes.
