#!/usr/bin/env python3
"""Fallback when Maven Central rate-limits the proxy: copies plugin artifacts from a local Maven repo into the
central-proxy store exactly as Reposilite stores proxied files (file + .sha1). usage: fill-central-from-m2.py <m2repo> <datadir>"""
import os, sys, shutil, hashlib
src, data = sys.argv[1], sys.argv[2]
dst = os.path.join(data, "repositories", "central-proxy"); n = 0
for dp, dns, fns in os.walk(src):
    rel = os.path.relpath(dp, src)
    if rel.split(os.sep)[0] in ("seed", "consumer") or rel.startswith(("com/acme", "com/vendor", "org/legacy")): continue
    for f in fns:
        if not f.endswith((".jar", ".pom")): continue
        os.makedirs(os.path.join(dst, rel), exist_ok=True)
        p = os.path.join(dst, rel, f); shutil.copy2(os.path.join(dp, f), p)
        open(p + ".sha1", "w").write(hashlib.sha1(open(p, "rb").read()).hexdigest()); n += 1
print("copied", n)
