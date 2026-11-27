#!/usr/bin/env python3
"""Replays plan.json against a running Reposilite with real mvn / gradle / deploy-file / curl uploads.
usage: deploy.py plan.json workdir [--base http://localhost:8080] [--limit N]"""
import json, os, sys, subprocess, shutil, time, hashlib, argparse
from xml.sax.saxutils import escape

ap = argparse.ArgumentParser()
ap.add_argument("plan"); ap.add_argument("work")
ap.add_argument("--base", default="http://localhost:8080")
ap.add_argument("--limit", type=int, default=0)
ap.add_argument("--start", type=int, default=0, help="resume from batch number")
args = ap.parse_args()
P = json.load(open(args.plan))
BASE = args.base
WORK = os.path.abspath(args.work); os.makedirs(WORK, exist_ok=True)
CI = ("ci-deployer", "ci-deploy-41xK")
M2 = os.environ.get("SEED_M2") or os.path.join(WORK, "m2")
SETTINGS = os.path.join(WORK, "settings.xml")
PLUGINS = dict(jar="3.4.2", deploy="3.1.3", install="3.1.3", resources="3.3.1", compiler="3.13.0", surefire="3.5.2")

open(SETTINGS, "w").write(f"""<settings>
 <servers>
  <server><id>releases</id><username>{CI[0]}</username><password>{CI[1]}</password></server>
  <server><id>thirdparty</id><username>{CI[0]}</username><password>{CI[1]}</password></server>
  <server><id>snapshots</id><username>{CI[0]}</username><password>{CI[1]}</password></server>
 </servers>
 <mirrors><mirror><id>central-proxy</id><mirrorOf>central</mirrorOf><url>{BASE}/central-proxy</url></mirror></mirrors>
 <profiles><profile><id>acme</id>
  <repositories>
   <repository><id>releases</id><url>{BASE}/releases</url><snapshots><enabled>false</enabled></snapshots></repository>
   <repository><id>thirdparty</id><url>{BASE}/thirdparty</url><snapshots><enabled>false</enabled></snapshots></repository>
   <repository><id>snapshots</id><url>{BASE}/snapshots</url><releases><enabled>false</enabled></releases></repository>
  </repositories>
 </profile></profiles>
 <activeProfiles><activeProfile>acme</activeProfile></activeProfiles>
</settings>
""")

def gav_xml(x, tag="dependency", ind="   "):
    s = f"{ind}<{tag}><groupId>{x['g']}</groupId><artifactId>{x['a']}</artifactId>"
    if x.get("v"): s += f"<version>{escape(x['v'])}</version>"
    if x.get("type"): s += f"<type>{x['type']}</type>"
    if x.get("classifier"): s += f"<classifier>{x['classifier']}</classifier>"
    if x.get("scope"): s += f"<scope>{x['scope']}</scope>"
    return s + f"</{tag}>\n"

def pom(e):
    o = ['<?xml version="1.0" encoding="UTF-8"?>\n<project xmlns="http://maven.apache.org/POM/4.0.0" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" xsi:schemaLocation="http://maven.apache.org/POM/4.0.0 https://maven.apache.org/xsd/maven-4.0.0.xsd">\n <modelVersion>4.0.0</modelVersion>\n']
    if e.get("parent"):
        p = e["parent"]; o.append(f" <parent><groupId>{p['g']}</groupId><artifactId>{p['a']}</artifactId><version>{p['v']}</version><relativePath/></parent>\n")
    o.append(f" <groupId>{e['g']}</groupId>\n <artifactId>{e['a']}</artifactId>\n <version>{e['v']}</version>\n <packaging>{e['packaging']}</packaging>\n")
    props = dict(e.get("props", {}) or {})
    props = {k: v for k, v in props.items() if v}
    if e["a"] == "acme-parent":
        props.update({"maven.compiler.release": "17", "project.build.sourceEncoding": "UTF-8"})
    props["project.build.outputTimestamp"] = e["t"] + "Z"
    o.append(" <properties>\n" + "".join(f"  <{k}>{escape(v)}</{k}>\n" for k, v in props.items()) + " </properties>\n")
    dm = list(e.get("dm", []))
    imps = list(e.get("dm_import", [])) + ([e["own_bom"]] if e.get("own_bom") else [])
    if dm or imps:
        o.append(" <dependencyManagement><dependencies>\n")
        for x in dm: o.append(gav_xml(x))
        for x in imps: o.append(gav_xml(dict(x, type="pom", scope="import")))
        o.append(" </dependencies></dependencyManagement>\n")
    if e.get("deps"):
        o.append(" <dependencies>\n" + "".join(gav_xml(x) for x in e["deps"]) + " </dependencies>\n")
    if e.get("profiles"):
        o.append(" <profiles>\n")
        for pr in e["profiles"]:
            act = "<activeByDefault>true</activeByDefault>" if pr.get("activeByDefault") else f"<jdk>{pr['jdk']}</jdk>"
            o.append(f"  <profile><id>{pr['id']}</id><activation>{act}</activation><dependencies>\n" + "".join(gav_xml(x, ind='    ') for x in pr["deps"]) + "  </dependencies></profile>\n")
        o.append(" </profiles>\n")
    if e["a"] == "acme-parent":
        o.append(" <build><pluginManagement><plugins>\n" + "".join(
            f"  <plugin><groupId>org.apache.maven.plugins</groupId><artifactId>maven-{k}-plugin</artifactId><version>{v}</version></plugin>\n" for k, v in PLUGINS.items())
                 + " </plugins></pluginManagement></build>\n")
        o.append(" <distributionManagement>\n  <repository><id>releases</id><url>https://repo.acme.internal/releases</url></repository>\n  <snapshotRepository><id>snapshots</id><url>https://repo.acme.internal/snapshots</url></snapshotRepository>\n </distributionManagement>\n")
    execs = []
    if e.get("classifiers"):
        for c in e["classifiers"]:
            execs.append(f"<execution><id>{c}</id><goals><goal>jar</goal></goals><configuration><classifier>{c}</classifier></configuration></execution>")
    if e["a"] == "acme-test-support":
        execs.append("<execution><id>tests</id><goals><goal>test-jar</goal></goals></execution>")
    if execs:
        o.append(" <build><plugins><plugin><groupId>org.apache.maven.plugins</groupId><artifactId>maven-jar-plugin</artifactId><executions>" + "".join(execs) + "</executions></plugin></plugins></build>\n")
    if e.get("relocation"):
        r = e["relocation"]; o.append(f" <distributionManagement><relocation><groupId>{r['g']}</groupId><artifactId>{r['a']}</artifactId><version>{r['v']}</version><message>old-util moved to com.acme.util:util</message></relocation></distributionManagement>\n")
    o.append("</project>\n")
    return "".join(o)

def write_module(d, e):
    os.makedirs(d, exist_ok=True)
    open(os.path.join(d, "pom.xml"), "w").write(pom(e))
    if e["packaging"] == "jar":
        r = os.path.join(d, "src/main/resources/META-INF/acme"); os.makedirs(r, exist_ok=True)
        open(os.path.join(r, e["a"] + ".properties"), "w").write(f"artifact={e['a']}\nversion={e['v']}\n")
        if e["a"] == "acme-test-support":
            t = os.path.join(d, "src/test/resources"); os.makedirs(t, exist_ok=True)
            open(os.path.join(t, "fixtures.properties"), "w").write(f"v={e['v']}\n")

def run(cmd, cwd, log, tries=8):
    for i in range(tries):
        with open(log, "a") as f:
            f.write(f"\n### try {i} {' '.join(cmd)}\n"); f.flush()
            r = subprocess.run(cmd, cwd=cwd, stdout=f, stderr=subprocess.STDOUT)
        if r.returncode == 0: return
        time.sleep(15 + 10 * i)
    raise SystemExit(f"FAILED: {cmd} in {cwd}, see {log}")

MVN = ["mvn", "-B", "-ntp", "-U", "-s", SETTINGS, f"-Dmaven.repo.local={M2}", "-DskipTests", "-Daether.connector.http.retryHandler.count=5"]

def exists(repo, e, ext="pom"):
    gp = e["g"].replace(".", "/")
    if e["v"].endswith("SNAPSHOT"): return False
    url = f"{BASE}/{repo}/{gp}/{e['a']}/{e['v']}/{e['a']}-{e['v']}.{ext}"
    r = subprocess.run(["curl", "-s", "-o", "/dev/null", "-w", "%{http_code}", "-I", url], capture_output=True, text=True)
    return r.stdout == "200"

def mvn_batch(n, evs, repo="releases"):
    d = os.path.join(WORK, f"b{n:04d}")
    log = os.path.join(WORK, f"b{n:04d}.log")
    for i in range(8):
        todo = [e for e in evs if not exists(repo, e)]
        if not todo: break
        shutil.rmtree(d, ignore_errors=True); os.makedirs(d)
        mods = []
        for j, e in enumerate(todo):
            m = f"m{j:02d}-{e['a']}"; write_module(os.path.join(d, m), e); mods.append(m)
        open(os.path.join(d, "pom.xml"), "w").write(
            "<project><modelVersion>4.0.0</modelVersion><groupId>seed.batch</groupId><artifactId>b</artifactId><version>1</version><packaging>pom</packaging>"
            "<properties><maven.deploy.skip>true</maven.deploy.skip><maven.install.skip>true</maven.install.skip></properties>"
            "<modules>" + "".join(f"<module>{m}</module>" for m in mods) + "</modules></project>\n")
        with open(log, "a") as f:
            f.write(f"\n### try {i}\n"); f.flush()
            r = subprocess.run(MVN + ["-T", "4", f"-DaltDeploymentRepository={repo}::{BASE}/{repo}", "deploy"], cwd=d, stdout=f, stderr=subprocess.STDOUT)
        if r.returncode == 0: break
        time.sleep(10 + 10 * i)
    else:
        raise SystemExit(f"FAILED batch {n}, see {log}")
    shutil.rmtree(d, ignore_errors=True)
    if os.path.exists(log) and "### try 1" not in open(log).read(): os.remove(log)

def gradle_dep(x):
    return f'"{x["g"]}:{x["a"]}' + (f':{x["v"]}' if x.get("v") else "") + '"'

def gradle_batch(n, evs):
    for i in range(6):
        todo = [e for e in evs if not exists("releases", e)]
        if not todo: return
        try:
            gradle_batch1(n, todo); return
        except SystemExit:
            time.sleep(10)
    raise SystemExit(f"FAILED gradle batch {n}")

def gradle_batch1(n, evs):
    d = os.path.join(WORK, f"g{n:04d}"); shutil.rmtree(d, ignore_errors=True); os.makedirs(d)
    names = []
    for i, e in enumerate(evs):
        m = f"p{i:02d}"; names.append(m); pd = os.path.join(d, m)
        os.makedirs(os.path.join(pd, "src/main/resources/META-INF/acme"))
        open(os.path.join(pd, "src/main/resources/META-INF/acme", e["a"] + ".properties"), "w").write(f"artifact={e['a']}\nversion={e['v']}\n")
        G = e.get("gradle", {})
        deps = []
        if G.get("platform"): deps.append(f'    api(platform({gradle_dep(G["platform"])}))')
        for x in G.get("api", []): deps.append(f'    api({gradle_dep(x)})')
        for x in G.get("impl", []):
            if x.get("capability"):
                deps.append(f'    implementation({gradle_dep(x)}) {{ capabilities {{ requireCapability("{x["capability"]}") }} }}')
            else:
                deps.append(f'    implementation({gradle_dep(x)})')
        feat = ""
        if G.get("feature"):
            f = G["feature"]
            feat = f'java {{ registerFeature("{f["name"]}") {{ usingSourceSet(sourceSets["main"]) }} }}\n'
            for x in f["deps"]: deps.append(f'    "{f["name"]}Implementation"({gradle_dep(x)})')
        open(os.path.join(pd, "build.gradle.kts"), "w").write(f'''plugins {{ `java-library`; `maven-publish` }}
group = "{e['g']}"
version = "{e['v']}"
java {{ toolchain {{ }} }}
{feat}dependencies {{
{chr(10).join(deps)}
}}
tasks.withType<AbstractArchiveTask>().configureEach {{ isPreserveFileTimestamps = false; isReproducibleFileOrder = true }}
publishing {{
  publications {{ create<MavenPublication>("maven") {{ artifactId = "{e['a']}"; from(components["java"]); suppressAllPomMetadataWarnings() }} }}
  repositories {{ maven {{ name = "releases"; url = uri("{BASE}/releases"); isAllowInsecureProtocol = true; credentials {{ username = "{CI[0]}"; password = "{CI[1]}" }} }} }}
}}
''')
    open(os.path.join(d, "settings.gradle.kts"), "w").write(
        'rootProject.name = "seed-batch"\n' + "".join(f'include(":{e["a"]}")\nproject(":{e["a"]}").projectDir = file("{m}")\n' for m, e in zip(names, evs)) +
        f'''dependencyResolutionManagement {{
  repositories {{
    maven {{ url = uri("{BASE}/releases"); isAllowInsecureProtocol = true }}
    maven {{ url = uri("{BASE}/thirdparty"); isAllowInsecureProtocol = true }}
    maven {{ url = uri("{BASE}/central-proxy"); isAllowInsecureProtocol = true }}
  }}
}}
''')
    run(["gradle", "--console=plain", "-q", "--no-configuration-cache", "-g", os.path.join(WORK, "gradle-home"), "publish"], d, os.path.join(WORK, f"g{n:04d}.log"), tries=1)
    shutil.rmtree(d)

def sha(data, algo): return hashlib.new(algo, data).hexdigest()

def put(path, data):
    for i in range(5):
        r = subprocess.run(["curl", "-s", "-o", "/dev/null", "-w", "%{http_code}", "-u", f"{CI[0]}:{CI[1]}", "-X", "PUT", "--data-binary", "@-", f"{BASE}/{path}"], input=data, capture_output=True)
        if r.stdout.decode() in ("200", "201", "204"): return
        time.sleep(2)
    raise SystemExit(f"PUT {path} -> {r.stdout}")

def tiny_jar(e):
    d = os.path.join(WORK, "jar-src", e["a"], e["v"]); os.makedirs(os.path.join(d, "META-INF"), exist_ok=True)
    open(os.path.join(d, "META-INF", "vendor.txt"), "w").write(f"{e['g']}:{e['a']}:{e['v']}\n")
    out = os.path.join(WORK, "jar-src", f"{e['a']}-{e['v']}.jar")
    subprocess.run(["jar", "--create", "--file", out, "--date", e["t"] + "Z", "-C", d, "."], check=True)
    return out

def thirdparty(e):
    if exists("thirdparty", e, "jar"): return
    j = tiny_jar(e)
    gp = e["g"].replace(".", "/")
    base = f"thirdparty/{gp}/{e['a']}/{e['v']}/{e['a']}-{e['v']}"
    if e["tool"] == "deployfile":
        d = os.path.join(WORK, "deployfile"); os.makedirs(d, exist_ok=True)
        run(["mvn", "-B", "-ntp", "-s", SETTINGS, f"-Dmaven.repo.local={M2}", "org.apache.maven.plugins:maven-deploy-plugin:3.1.3:deploy-file",
             f"-Durl={BASE}/thirdparty", "-DrepositoryId=thirdparty", f"-Dfile={j}", f"-DgroupId={e['g']}", f"-DartifactId={e['a']}",
             f"-Dversion={e['v']}", "-Dpackaging=jar", "-DgeneratePom=true"], d, os.path.join(d, "deploy.log"))
    else:  # uploaded by hand from the vendor zip: jar + pom (+ sha1), no maven-metadata.xml
        data = open(j, "rb").read()
        put(base + ".jar", data); put(base + ".jar.sha1", sha(data, "sha1").encode())
        if not e.get("no_pom"):
            p = f'<?xml version="1.0" encoding="UTF-8"?>\n<project xmlns="http://maven.apache.org/POM/4.0.0">\n  <modelVersion>4.0.0</modelVersion>\n  <groupId>{e["g"]}</groupId>\n  <artifactId>{e["a"]}</artifactId>\n  <version>{e["v"]}</version>\n  <description>Vendor distribution, uploaded manually</description>\n</project>\n'.encode()
            put(base + ".pom", p); put(base + ".pom.sha1", sha(p, "sha1").encode())

def fake_metadata(ga, versions, last):
    g, a = ga.split(":")
    x = (f'<?xml version="1.0" encoding="UTF-8"?>\n<metadata>\n  <groupId>{g}</groupId>\n  <artifactId>{a}</artifactId>\n  <versioning>\n'
         f'    <latest>{versions[-1]}</latest>\n    <release>{versions[-1]}</release>\n    <versions>\n' +
         "".join(f"      <version>{v}</version>\n" for v in versions) + f'    </versions>\n    <lastUpdated>{last}</lastUpdated>\n  </versioning>\n</metadata>\n').encode()
    p = f"thirdparty/{g.replace('.', '/')}/{a}/maven-metadata.xml"
    put(p, x); put(p + ".sha1", sha(x, "sha1").encode()); put(p + ".md5", sha(x, "md5").encode())

def refs(e):
    out = []
    for x in e.get("deps", []) + ([e["parent"]] if e.get("parent") else []) + e.get("dm_import", []) + ([e["own_bom"]] if e.get("own_bom") else []):
        out.append(x["g"] + ":" + x["a"])
    for pr in e.get("profiles", []): out += [x["g"] + ":" + x["a"] for x in pr["deps"]]
    G = e.get("gradle", {})
    for x in G.get("api", []) + G.get("impl", []) + ([G["platform"]] if G.get("platform") else []) + G.get("feature", {}).get("deps", []):
        out.append(x["g"] + ":" + x["a"])
    if e.get("relocation"): out.append(e["relocation"]["g"] + ":" + e["relocation"]["a"])
    # managed deps resolve through the BOM, which itself references everything: depend on the bom GA too
    return set(out) | ({"com.acme:acme-bom"} if any("v" not in x for x in e.get("deps", []) + G.get("impl", [])) else set())

# ---- build batches
batches, cur, kind = [], [], None
ORDERED = [e for e in P["events"] if e["tool"] in ("hand", "deployfile")] + [e for e in P["events"] if e["tool"] not in ("hand", "deployfile")]
for e in ORDERED:
    k = "gradle" if e["tool"] == "gradle" else ("mvn" if e["tool"] == "mvn" else "tp")
    gas = {x["g"] + ":" + x["a"] for x in cur}
    if cur and (k != kind or k == "tp" or e["g"] + ":" + e["a"] in gas or refs(e) & gas or len(cur) >= 60):
        batches.append((kind, cur)); cur = []
    cur.append(e); kind = k
if cur: batches.append((kind, cur))
print(len(batches), "batches", flush=True)
fake = {}
t0 = time.time()
for n, (k, evs) in enumerate(batches):
    if n < args.start: continue
    if args.limit and n >= args.start + args.limit: break
    s = time.time()
    if k == "mvn": mvn_batch(n, evs)
    elif k == "gradle": gradle_batch(n, evs)
    else:
        for e in evs: thirdparty(e)
    print(f"batch {n} {k} {len(evs)} {evs[0]['t'][:10]} {time.time()-s:.1f}s total {time.time()-t0:.0f}s", flush=True)
if not args.limit:
    # vendor metadata that a previous admin wrote by hand and never kept up to date
    for ga in ["org.legacy:soap-client"]:
        fake_metadata(ga, ["2.8", "2.9", "3.0", "3.1"], "20240219114502")
    # snapshots: real builds of feature branches
    for s in P["snapshots"]:
        for b in range(s["builds"]):
            e = dict(s, t="2026-11-26T00:00:00")
            mvn_batch(9000 + b, [e], "snapshots")
    print("DONE", flush=True)
