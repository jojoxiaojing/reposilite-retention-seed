#!/bin/bash
# build-world.sh <reposilite.jar> <datadir> <m2-with-plugins>
# Full rebuild of the 3-year instance: real deploys, central-proxy cache, final config, backdating. Server is left STOPPED.
set -e
KIT=$(cd "$(dirname "$0")" && pwd); JAR=$(readlink -f "$1"); DATA=$2; M2=$3
export SEED_WORK=${SEED_WORK:-/var/tmp/seed-work} SEED_M2=$M2
"$KIT/seed.sh" "$JAR" "$DATA"
# cache what developers' builds pulled through central-proxy (Central rate-limits the proxy in some networks)
"$KIT/fill-central-cache.sh" "$SEED_WORK" || python3 "$KIT/fill-central-from-m2.py" "$M2" "$DATA"
sed "s|HTTPPROXY||" "$KIT/repos.json" > "$SEED_WORK/repos-final.json"
curl -sf -u seed:seed-secret-1 -X PUT -H 'Content-Type: application/json' --data @"$SEED_WORK/repos-final.json" localhost:8080/api/settings/domain/maven -o /dev/null
sleep 2; pkill -f -- "--working-directory $DATA"; sleep 3
python3 "$KIT/backdate.py" "$SEED_WORK/plan.json" "$DATA"
rm -rf "$DATA/logs" "$DATA/latest.log"
echo WORLD-READY
