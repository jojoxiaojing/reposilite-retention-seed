#!/usr/bin/env python3
"""Moves file times and maven-metadata lastUpdated back to the dates in plan.json (server must be STOPPED).
usage: backdate.py plan.json datadir"""
import json, os, sys, re, hashlib, datetime as dt
P = json.load(open(sys.argv[1])); DATA = sys.argv[2]
R = os.path.join(DATA, "repositories")
def ts(t): return dt.datetime.fromisoformat(t).replace(tzinfo=dt.timezone.utc).timestamp()
last = {}
n = 0
for e in P["events"]:
    d = os.path.join(R, e["repo"], *e["g"].split("."), e["a"], e["v"])
    if not os.path.isdir(d): print("missing", d); continue
    t = ts(e["t"])
    for i, f in enumerate(sorted(os.listdir(d), key=lambda f: (not f.endswith(".pom"), f))):
        os.utime(os.path.join(d, f), (t + i * 0.37, t + i * 0.37)); n += 1
    os.utime(d, (t + 3, t + 3))
    k = (e["repo"], e["g"], e["a"]); last[k] = max(last.get(k, 0), t + 4)
for (repo, g, a), t in last.items():
    ad = os.path.join(R, repo, *g.split("."), a)
    m = os.path.join(ad, "maven-metadata.xml")
    if os.path.exists(m) and not (g == "org.legacy" and a == "soap-client"):
        x = open(m).read()
        stamp = dt.datetime.fromtimestamp(t, dt.timezone.utc).strftime("%Y%m%d%H%M%S")
        x2 = re.sub(r"<lastUpdated>\d+</lastUpdated>", f"<lastUpdated>{stamp}</lastUpdated>", x)
        open(m, "w").write(x2)
        b = x2.encode()
        for algo in ("md5", "sha1", "sha256", "sha512"):
            if os.path.exists(m + "." + algo):
                open(m + "." + algo, "w").write(hashlib.new(algo, b).hexdigest())
    elif os.path.exists(m):
        t = ts("2024-02-19T11:45:02")
    for f in os.listdir(ad):
        p = os.path.join(ad, f)
        if os.path.isfile(p): os.utime(p, (t, t))
    os.utime(ad, (t, t))
print("files", n, "artifacts", len(last))
