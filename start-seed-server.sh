#!/bin/bash
# start-seed-server.sh <jar> <datadir> [port]
JAR=$1; DATA=$2; PORT=${3:-8080}
mkdir -p "$DATA"
cd "$DATA"
nohup java -Xmx1g -jar "$JAR" --working-directory "$DATA" --port $PORT --token seed:seed-secret-1 --disable-interactive-console >> "$DATA/../seed-server.log" 2>&1 &
for i in $(seq 120); do curl -s -o /dev/null -u seed:seed-secret-1 localhost:$PORT/api/status/instance && exit 0; sleep 0.5; done
echo "server did not start"; exit 1
