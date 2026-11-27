#!/usr/bin/env python3
"""Generates the deploy plan (plan.json) for the 3-year Reposilite instance.
Deterministic: same seed -> same plan."""
import json, random, datetime as dt, sys

R = random.Random(20231204)
START = dt.datetime(2023, 12, 4, 9, 0)
END = dt.datetime(2026, 11, 20, 18, 0)
# keep a quiet band around "now - 180 days" so the policy result does not depend on the exact day it runs
QUIET = (dt.datetime(2026, 5, 1), dt.datetime(2026, 6, 25))

def d(s): return dt.datetime.fromisoformat(s)

def dates(n, start, end):
    start, end = d(start), d(end)
    out = set()
    while len(out) < n:
        t = start + dt.timedelta(seconds=R.randrange(int((end - start).total_seconds())))
        if QUIET[0] <= t <= QUIET[1]: continue
        if t.weekday() >= 5 and R.random() < 0.8: continue
        t = t.replace(hour=R.randrange(8, 19), minute=R.randrange(60), second=R.randrange(60))
        out.add(t)
    return sorted(out)

def semver(n, major=1, minor=0, patch_every=(3, 9)):
    vs, mi, pa = [], minor, 0
    nxt = R.randint(*patch_every)
    for i in range(n):
        vs.append(f"{major}.{mi}.{pa}")
        pa += 1
        if pa >= nxt:
            mi += 1; pa = 0; nxt = R.randint(*patch_every)
    return vs

ART = {}  # key "g:a" -> dict(repo, tool, packaging, versions[(v, date)], ...)
def art(ga, repo, tool, packaging, versions, ds, **kw):
    assert len(versions) == len(ds), ga
    ART[ga] = dict(ga=ga, repo=repo, tool=tool, packaging=packaging, versions=list(zip(versions, ds)), **kw)

A = "com.acme:"
def first_at(ds, iso):
    ds[0] = d(iso); return ds
# --- POMs
art(A+"acme-parent", "releases", "mvn", "pom", [str(i) for i in range(1, 26)], first_at(dates(25, "2023-12-04", "2026-10-30"), "2023-12-01T10:12:00"))
art(A+"acme-java-parent", "releases", "mvn", "pom", [f"1.{i}" for i in range(30)], first_at(dates(30, "2023-12-05", "2026-11-05"), "2023-12-01T10:40:00"))
art(A+"acme-bom", "releases", "mvn", "pom", [f"1.{i}" for i in range(60)], first_at(dates(60, "2023-12-06", "2026-11-18"), "2023-12-01T11:05:00"))
# --- core libs (maven)
core_v = [f"1.9.{i}" for i in range(14)] + [f"1.10.{i}" for i in range(30)] + semver(66, 1, 11)
art(A+"acme-core", "releases", "mvn", "jar", core_v, dates(len(core_v), "2023-12-04", "2026-11-19"))
art(A+"acme-log", "releases", "mvn", "jar", semver(50), dates(50, "2023-12-04", "2026-11-10"))
json_v = [f"2.{i}" for i in range(10)] + ["3.0.0-RC1", "3.0.0-RC2", "3.0.0"] + semver(32, 3, 0, (4, 9))[1:]
json_d = dates(10, "2023-12-04", "2024-09-20") + dates(3, "2024-10-01", "2024-11-15") + dates(len(json_v) - 13, "2024-11-20", "2026-11-15")
art(A+"acme-json", "releases", "mvn", "jar", json_v, json_d)
art(A+"acme-driver-shim", "releases", "mvn", "jar", semver(10), first_at(dates(10, "2023-12-08", "2025-09-10"), "2023-12-04T15:20:00"))
art(A+"acme-jaxb-shim", "releases", "mvn", "jar", semver(10), first_at(dates(10, "2023-12-08", "2025-09-10"), "2023-12-04T15:40:00"))
for name, n, s, e in [("acme-http", 110, "2023-12-04", "2026-11-19"), ("acme-db", 80, "2023-12-10", "2026-11-12"),
                      ("acme-cache", 50, "2023-12-10", "2026-10-20"), ("acme-metrics", 75, "2023-12-10", "2026-11-14"),
                      ("acme-auth", 50, "2024-01-10", "2026-11-01"), ("acme-test-support", 30, "2023-12-10", "2026-09-01"),
                      ("acme-contract-tests", 20, "2024-01-10", "2026-08-01"), ("acme-native", 25, "2023-12-10", "2026-10-01"),
                      ("acme-web", 70, "2024-01-10", "2026-11-10"), ("acme-grpc", 30, "2024-02-10", "2026-10-10"),
                      ("acme-security", 35, "2024-02-10", "2026-11-10"), ("acme-i18n", 20, "2024-01-10", "2026-07-10"),
                      ("acme-mail", 25, "2024-01-10", "2026-09-10"), ("acme-pdf", 20, "2023-12-10", "2026-04-10"),
                      ("acme-scheduler", 30, "2024-03-10", "2026-11-10"), ("acme-storage", 60, "2024-01-10", "2026-11-10"),
                      ("acme-queue", 55, "2024-02-10", "2026-11-10"), ("acme-flags", 25, "2024-04-10", "2026-10-10"),
                      ("acme-legacy-db", 14, "2023-12-10", "2025-06-10")]:
    art(A+name, "releases", "mvn", "jar", semver(n), dates(n, s, e))
art("com.acme.util:util", "releases", "mvn", "jar", [f"1.{i}" for i in range(9)], first_at(dates(9, "2023-12-08", "2025-11-10"), "2023-12-04T16:00:00"))
art(A+"old-util", "releases", "mvn", "jar", ["1.0", "1.1", "1.2", "1.3", "1.4"],
    [d("2023-12-04T16:30"), d("2023-12-20T10:00"), d("2024-01-10T10:00"), d("2024-02-01T10:00"), d("2024-03-04T10:00")])
# --- gradle published
art(A+"acme-kafka-shim", "releases", "gradle", "jar", semver(20), dates(20, "2024-01-10", "2026-10-10"))
art(A+"acme-events", "releases", "gradle", "jar", semver(40, 2), dates(40, "2024-02-10", "2026-10-30"))
art(A+"acme-kotlin-ext", "releases", "gradle", "jar", semver(35), dates(35, "2024-02-10", "2026-11-10"))
art(A+"events-gateway", "releases", "gradle", "jar", semver(30), dates(30, "2024-06-10", "2025-03-10"))
# --- services (maven)
for name, n, s, e in [("billing-svc", 170, "2023-12-11", "2026-11-20"), ("orders-svc", 45, "2023-12-11", "2024-10-25"),
                      ("inventory-svc", 90, "2024-01-11", "2026-08-20"), ("reporting-svc", 35, "2023-12-11", "2024-06-20"),
                      ("shipping-svc", 90, "2024-02-11", "2026-11-18"), ("notify-svc", 40, "2024-03-11", "2025-02-20"),
                      ("search-svc", 80, "2024-03-11", "2026-11-18"), ("analytics-svc", 60, "2024-05-11", "2026-11-18"),
                      ("admin-svc", 55, "2024-01-11", "2025-12-18"), ("pricing-svc", 35, "2024-04-11", "2026-03-18"),
                      ("catalog-svc", 90, "2024-02-11", "2026-11-17"), ("auth-svc", 70, "2024-01-11", "2026-11-17")]:
    art(A+name, "releases", "mvn", "jar", semver(n), dates(n, s, e))
# --- thirdparty
art("com.vendor:fastcodec", "thirdparty", "deployfile", "jar",
    ["1.8", "1.9", "1.10", "1.11", "2.0.0-RC1", "2.0.0.Final", "2.0.0", "2.1.0"],
    [d("2023-12-04T09:30"), d("2023-12-04T09:31"), d("2024-01-15T11:00"), d("2024-02-20T11:00"), d("2024-04-02T11:00"), d("2024-05-06T11:00"), d("2024-05-07T09:00"), d("2024-07-01T11:00")])
art("com.vendor:jdbc-shim", "thirdparty", "hand", "jar", ["11.2.0.4", "12.1.0.2", "19.3", "21.1", "23.4"],
    [d("2023-12-04T09:10"), d("2023-12-04T09:12"), d("2023-12-04T09:15"), d("2024-06-11T14:02"), d("2025-08-01T10:30")])
art("com.vendor:geo-db", "thirdparty", "deployfile", "jar",
    ["2.0", "20231204", "20240105", "20240612", "20250301", "20250915", "20260110"],
    [d("2023-12-04T10:00"), d("2023-12-05T10:00"), d("2024-01-08T10:00"), d("2024-06-14T10:00"), d("2025-03-03T10:00"), d("2025-09-16T10:00"), d("2026-01-12T10:00")])
art("org.legacy:soap-client", "thirdparty", "hand", "jar", ["3.0", "3.1", "3.2", "3.3"],
    [d("2023-12-04T09:20"), d("2023-12-04T09:21"), d("2023-12-04T09:22"), d("2025-01-08T16:40")],
    fake_metadata=["2.8", "2.9", "3.0", "3.1"])
art("org.legacy:xml-tools", "thirdparty", "hand", "jar", ["1.0", "1.1", "1.2", "1.3", "1.5"], dates(5, "2023-12-04", "2025-05-01"))
art("com.vendor:license-check", "thirdparty", "deployfile", "jar", ["4.0", "4.1", "4.2", "5.0", "5.1"], dates(5, "2023-12-04", "2026-02-01"))

# ---------------------------------------------------------------- dependency rules
def latest(ga, t, pred=lambda v: True):
    best = None
    for v, dd in ART[ga]["versions"]:
        if dd < t and pred(v): best = v
    return best

def nth_latest(ga, t, k):
    vs = [v for v, dd in ART[ga]["versions"] if dd < t]
    return vs[max(0, len(vs) - 1 - k)] if vs else None

def no_rc(v): return "RC" not in v

def dep(ga, v=None, **kw):
    g, a = ga.split(":")
    x = dict(g=g, a=a)
    if v: x["v"] = v
    x.update(kw)
    return x

LIBS_IN_BOM = ["acme-core", "acme-log", "acme-http", "acme-db", "acme-cache", "acme-metrics", "acme-auth", "acme-web",
               "acme-grpc", "acme-security", "acme-i18n", "acme-mail", "acme-pdf", "acme-scheduler", "acme-storage",
               "acme-queue", "acme-flags", "acme-test-support", "acme-native"]
PINNED_PARENT = {"acme-cache": "1.2", "acme-native": "1.4", "acme-pdf": "1.3", "reporting-svc": "1.1", "acme-legacy-db": "1.2"}

events = []
for ga, spec in ART.items():
    g, a = ga.split(":")
    for idx, (v, t) in enumerate(spec["versions"]):
        e = dict(g=g, a=a, v=v, t=t.isoformat(), repo=spec["repo"], tool=spec["tool"], packaging=spec["packaging"], deps=[])
        if spec["tool"] in ("hand", "deployfile"):
            if ga == "org.legacy:xml-tools" and v == "1.3": e["no_pom"] = True
            events.append(e); continue
        if a == "acme-parent":
            e["props"] = {"acme-log.version": latest(A+"acme-log", t),
                          "acme-json.version": latest(A+"acme-json", t, no_rc),
                          "codec.version": "1.9" if t < d("2024-03-01") else ("1.11" if t < d("2024-08-01") else "2.0.0")}
        elif a == "acme-java-parent":
            e["parent"] = dep(A+"acme-parent", latest(A+"acme-parent", t))
            e["props"] = {"acme-bom.version": latest(A+"acme-bom", t) or None}
            if e["props"]["acme-bom.version"]:
                e["dm_import"] = [dep(A+"acme-bom", "${acme-bom.version}")]
        elif a == "acme-bom":
            e["dm"] = [dep(A+x, latest(A+x, t)) for x in LIBS_IN_BOM if latest(A+x, t)]
        elif a == "old-util" and v == "1.4":
            e["parent"] = dep(A+"acme-java-parent", latest(A+"acme-java-parent", t))
            e["relocation"] = dict(g="com.acme.util", a="util", v=latest("com.acme.util:util", t)); e["packaging"] = "pom"
        else:
            if spec["tool"] == "mvn":
                pv = PINNED_PARENT.get(a)
                if pv and dt.datetime.fromisoformat(ART[A+"acme-java-parent"]["versions"][int(pv.split(".")[1])][1].isoformat()) >= t: pv = None
                e["parent"] = dep(A+"acme-java-parent", pv or latest(A+"acme-java-parent", t))
            D = e["deps"]
            managed = lambda x: D.append(dep(A+x)) if latest(A+x, t) else None
            explicit = lambda ga2, k=0: D.append(dep(ga2, nth_latest(ga2, t, k))) if nth_latest(ga2, t, k) else None
            if a == "acme-core": D.append(dep(A+"acme-log", "${acme-log.version}"))
            elif a == "acme-json" and v.startswith("3"): D.append(dep(A+"acme-log", "${acme-log.version}"))
            elif a == "acme-http": managed("acme-core"); D.append(dep(A+"acme-json", "${acme-json.version}"))
            elif a == "acme-db":
                managed("acme-core")
                D.append(dep("org.legacy:soap-client", "3.2" if t < d("2025-02-01") else "3.3"))
                D.append(dep("com.vendor:jdbc-shim", "19.3" if t < d("2025-09-01") else "23.4"))
            elif a in ("acme-cache", "acme-i18n", "acme-mail", "acme-storage", "acme-test-support"): managed("acme-core")
            elif a == "acme-metrics": managed("acme-core"); D.append(dep("com.vendor:fastcodec", "${codec.version}"))
            elif a == "acme-auth": managed("acme-http"); D.append(dep(A+"acme-json", "${acme-json.version}"))
            elif a == "acme-contract-tests":
                explicit(A+"acme-test-support"); D.append(dep(A+"acme-test-support", nth_latest(A+"acme-test-support", t, 0), type="test-jar"))
            elif a == "acme-native": e["classifiers"] = ["linux-x86_64", "osx-aarch_64"]
            elif a == "acme-test-support": pass
            elif a == "acme-web": managed("acme-http")
            elif a == "acme-grpc": managed("acme-core"); D.append(dep(A+"acme-json", "${acme-json.version}"))
            elif a == "acme-security": managed("acme-auth")
            elif a == "acme-pdf": managed("acme-core"); D.append(dep("com.vendor:geo-db", "20231204"))
            elif a == "acme-scheduler": managed("acme-core"); managed("acme-db")
            elif a == "acme-queue": managed("acme-core"); D.append(dep(A+"acme-json", "${acme-json.version}"))
            elif a == "acme-flags": managed("acme-cache")
            elif a == "acme-legacy-db":
                e["profiles"] = [dict(id="default-driver", activeByDefault=True, deps=[dep(A+"acme-driver-shim", latest(A+"acme-driver-shim", t))]),
                                 dict(id="jdk11-jaxb", jdk="[11,)", deps=[dep(A+"acme-jaxb-shim", latest(A+"acme-jaxb-shim", t))])]
            # gradle libs
            elif a == "acme-kafka-shim": pass
            elif a == "acme-events":
                e["gradle"] = dict(platform=dep(A+"acme-bom", latest(A+"acme-bom", t)), impl=[dep(A+"acme-core")],
                                   feature=dict(name="kafka", deps=[dep(A+"acme-kafka-shim", latest(A+"acme-kafka-shim", t))]))
            elif a == "acme-kotlin-ext":
                e["gradle"] = dict(api=[dep(A+"acme-core", latest(A+"acme-core", t))])
            elif a == "events-gateway":
                e["gradle"] = dict(impl=[dep(A+"acme-events", latest(A+"acme-events", t), capability="com.acme:acme-events-kafka"),
                                         dep(A+"acme-kotlin-ext", latest(A+"acme-kotlin-ext", t))])
            # services
            elif a == "billing-svc":
                managed("acme-http"); managed("acme-db"); managed("acme-metrics")
                if latest(A+"acme-events", t): explicit(A+"acme-events")
                if latest(A+"acme-kotlin-ext", t): explicit(A+"acme-kotlin-ext")
            elif a == "orders-svc":
                D.append(dep(A+"acme-json", "[2.0,3.0)")) if latest(A+"acme-json", t) else None; explicit(A+"acme-legacy-db"); managed("acme-cache")
            elif a == "inventory-svc":
                e["own_bom"] = dep(A+"acme-bom", latest(A+"acme-bom", t))
                managed("acme-db"); managed("acme-cache"); managed("acme-storage")
            elif a == "reporting-svc":
                D.append(dep(A+"old-util", latest(A+"old-util", t)))
                D.append(dep(A+"acme-native", nth_latest(A+"acme-native", t, 0), classifier="linux-x86_64"))
                if latest(A+"acme-contract-tests", t): explicit(A+"acme-contract-tests")
                managed("acme-pdf")
            elif a == "shipping-svc":
                D.append(dep("com.vendor:geo-db", "[20240101,20260101)")) if t > d("2024-01-09") else None; managed("acme-http")
            elif a == "notify-svc":
                D.append(dep("com.vendor:fastcodec", "[1.0,2.0)")); managed("acme-mail")
            elif a == "search-svc": managed("acme-http"); D.append(dep(A+"acme-json", "${acme-json.version}")); managed("acme-queue")
            elif a == "analytics-svc": managed("acme-metrics"); managed("acme-storage")
            elif a == "admin-svc": managed("acme-auth"); managed("acme-web"); managed("acme-flags")
            elif a == "pricing-svc": managed("acme-cache"); managed("acme-i18n"); explicit(A+"acme-legacy-db", 2)
            elif a == "catalog-svc": managed("acme-web"); managed("acme-storage"); managed("acme-scheduler"); managed("acme-grpc")
            elif a == "auth-svc": managed("acme-security"); managed("acme-db")
            elif a == "com.acme.util" or ga == "com.acme.util:util": pass
        events.append(e)

events.sort(key=lambda e: e["t"])
# ---- post-pass: a versionless dependency must be managed by the BOM the event really sees, otherwise pin it
IDX = {(e["g"]+":"+e["a"], e["v"]): e for e in events}
def eff_bom(e):
    if e.get("own_bom"): return e["own_bom"]["v"]
    if e.get("gradle", {}).get("platform"): return e["gradle"]["platform"]["v"]
    p = e.get("parent")
    if p and p["a"] == "acme-java-parent":
        return IDX[(A+"acme-java-parent", p["v"])].get("props", {}).get("acme-bom.version")
    return None
for e in events:
    lst = e["deps"] + e.get("gradle", {}).get("impl", []) + e.get("gradle", {}).get("api", [])
    bv = eff_bom(e)
    managed = {x["g"]+":"+x["a"] for x in IDX[(A+"acme-bom", bv)]["dm"]} if bv else set()
    for x in lst:
        if "v" not in x and x["g"]+":"+x["a"] not in managed:
            x["v"] = latest(x["g"]+":"+x["a"], dt.datetime.fromisoformat(e["t"]))
    # property versions: resolve through parent chain; pin explicitly when the parent does not define it yet
    def chain_prop(e, name):
        p = e.get("parent")
        while p:
            pe = IDX[(p["g"]+":"+p["a"], p["v"])]
            if pe.get("props", {}).get(name): return pe["props"][name]
            p = pe.get("parent")
        return None
    for x in e["deps"]:
        if (x.get("v") or "").startswith("${"):
            if not chain_prop(e, x["v"][2:-1]):
                x["v"] = latest(x["g"]+":"+x["a"], dt.datetime.fromisoformat(e["t"]))
    for pr in e.get("profiles", []): assert all(x.get("v") for x in pr["deps"]), e
    if "feature" in e.get("gradle", {}): e["gradle"]["feature"]["deps"] = [x for x in e["gradle"]["feature"]["deps"] if x.get("v")]
    if e.get("gradle", {}).get("platform") and not e["gradle"]["platform"].get("v"): del e["gradle"]["platform"]
    for key in ("deps",):
        e[key] = [x for x in e[key] if not ("v" in x and x["v"] is None)]
    for gk in ("impl", "api"):
        if gk in e.get("gradle", {}): e["gradle"][gk] = [x for x in e["gradle"][gk] if x.get("v", 1) is not None]

# snapshots (deployed last, dated "now")
snaps = [dict(g="com.acme", a="billing-svc", v="4.0.0-SNAPSHOT", builds=3,
              deps=[dep(A+"acme-db", ART[A+"acme-db"]["versions"][20][0]), dep(A+"acme-http")]),
         dict(g="com.acme", a="reporting-svc", v="2.1-SNAPSHOT", builds=2,
              deps=[dep(A+"acme-json", "2.3"), dep(A+"old-util", "1.2")]),
         dict(g="com.acme", a="acme-core", v="2.0.0-SNAPSHOT", builds=4, deps=[dep(A+"acme-log", "${acme-log.version}")])]
for s in snaps:
    s.update(repo="snapshots", tool="mvn", packaging="jar", parent=dep(A+"acme-java-parent", ART[A+"acme-java-parent"]["versions"][-1][0]))

# ---- validate: every explicit reference exists before the event
WHEN = {(e["g"]+":"+e["a"], e["v"]): e["t"] for e in events}
bad = 0
for e in events:
    refs = list(e["deps"]) + ([e["parent"]] if e.get("parent") else []) + e.get("dm_import", []) + ([e["own_bom"]] if e.get("own_bom") else [])
    refs += [x for pr in e.get("profiles", []) for x in pr["deps"]]
    G = e.get("gradle", {}); refs += G.get("api", []) + G.get("impl", []) + ([G["platform"]] if G.get("platform") else []) + G.get("feature", {}).get("deps", [])
    if e.get("relocation"): refs.append(e["relocation"])
    for x in refs:
        v = x.get("v")
        if not v or v.startswith("${") or v.startswith("["): continue
        w = WHEN.get((x["g"]+":"+x["a"], v))
        if not w or w >= e["t"]: bad += 1; print("BAD", e["a"], e["v"], x, w)
assert not bad
for e in events:
    if e.get("relocation"): assert e["relocation"]["v"], e
json.dump(dict(events=events, snapshots=snaps, now="2026-11-26T00:00:00"), open(sys.argv[1] if len(sys.argv) > 1 else "plan.json", "w"), indent=1)
print(len(events), "events;", sum(1 for e in events if e["repo"] == "releases"), "releases;",
      sum(1 for e in events if e["repo"] == "thirdparty"), "thirdparty;", len(ART), "artifacts")
