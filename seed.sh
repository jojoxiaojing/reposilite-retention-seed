#!/bin/bash
# seed.sh <reposilite.jar> <datadir> : builds the 3-year instance from scratch (wipes datadir)
set -e
KIT=$(cd "$(dirname "$0")" && pwd)
JAR=$(readlink -f "$1"); DATA=$2; PORT=8080; WORK=${SEED_WORK:-/var/tmp/seed-work}
pkill -f -- "--working-directory $DATA" || true; sleep 1
rm -rf "$DATA" "$WORK"; mkdir -p "$DATA" "$WORK"
"$KIT/start-seed-server.sh" "$JAR" "$DATA" $PORT
S="-u seed:seed-secret-1"
PROXY=${SEED_HTTP_PROXY:-}
sed "s|HTTPPROXY|${PROXY}|" "$KIT/repos.json" > "$WORK/repos.json"
curl -sf $S -X PUT -H 'Content-Type: application/json' --data @"$WORK/repos.json" localhost:$PORT/api/settings/domain/maven -o /dev/null
X(){ curl -sf $S -X POST --data "$1" localhost:$PORT/api/console/execute -o /dev/null; }
X "token-generate --secret=ops-admin-7Qe2 ops-admin m"
X "token-generate --secret=ci-deploy-41xK ci-deployer"
for r in releases thirdparty snapshots; do X "route-add ci-deployer /$r rw"; done
X "token-generate --secret=dev-readonly-9 developers"
for r in releases thirdparty snapshots; do X "route-add developers /$r r"; done
python3 "$KIT/plan.py" "$WORK/plan.json"
python3 "$KIT/deploy.py" "$WORK/plan.json" "$WORK" --base http://localhost:$PORT
echo SEED-DEPLOYED
