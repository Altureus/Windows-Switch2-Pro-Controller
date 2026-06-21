#!/usr/bin/env python3
r"""
_fetch_vigem.py -- obtain ViGEmClient.dll without installing vgamepad.

vgamepad ships no wheel (only an sdist whose setup.py runs an interactive
ViGEmBus driver installer). The ViGEmBus *driver* is already installed on this
machine, so all we actually need is the user-mode client DLL that vgamepad
bundles. This script downloads the vgamepad sdist straight from PyPI and
extracts only ViGEmClient.dll (x64 + x86) into this vendor/ folder. It never
executes any packaged code.

Run:  python procon2/vendor/_fetch_vigem.py
"""
import hashlib
import io
import json
import os
import sys
import tarfile
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
PYPI = "https://pypi.org/pypi/vgamepad/json"


def main():
    print(f"[fetch] querying {PYPI}")
    with urllib.request.urlopen(PYPI, timeout=30) as r:
        meta = json.load(r)

    # newest version's sdist
    ver = meta["info"]["version"]
    sdist = None
    for f in meta["releases"].get(ver, []):
        if f["packagetype"] == "sdist":
            sdist = f
            break
    if sdist is None:
        # fall back: scan all releases for any sdist
        for rel in meta["releases"].values():
            for f in rel:
                if f["packagetype"] == "sdist":
                    sdist = f
                    break
            if sdist:
                break
    if sdist is None:
        sys.exit("[fetch] no sdist found for vgamepad on PyPI")

    url = sdist["url"]
    print(f"[fetch] vgamepad {ver} sdist: {url}")
    with urllib.request.urlopen(url, timeout=60) as r:
        blob = r.read()
    print(f"[fetch] downloaded {len(blob)} bytes")

    extracted = []
    with tarfile.open(fileobj=io.BytesIO(blob), mode="r:gz") as tf:
        for m in tf.getmembers():
            if m.isfile() and m.name.lower().endswith("vigemclient.dll"):
                # classify arch by path component
                low = m.name.lower()
                arch = "x64" if "/x64/" in low or "\\x64\\" in low else \
                       "x86" if "/x86/" in low or "\\x86\\" in low else "unknown"
                data = tf.extractfile(m).read()
                out = os.path.join(HERE, f"ViGEmClient.{arch}.dll")
                with open(out, "wb") as o:
                    o.write(data)
                sha = hashlib.sha256(data).hexdigest()[:16]
                extracted.append((m.name, arch, len(data), sha, out))

    if not extracted:
        sys.exit("[fetch] no ViGEmClient.dll inside the sdist (layout changed?)")

    print("[fetch] extracted:")
    for name, arch, size, sha, out in extracted:
        print(f"   {arch:7} {size:>8} bytes  sha256:{sha}..  <- {name}")
        print(f"           -> {out}")

    # convenience: the x64 one as the canonical name we'll load
    x64 = [e for e in extracted if e[1] == "x64"]
    if x64:
        canon = os.path.join(HERE, "ViGEmClient.dll")
        with open(x64[0][4], "rb") as src, open(canon, "wb") as dst:
            dst.write(src.read())
        print(f"[fetch] canonical x64 copy -> {canon}")
    print("[fetch] done.")


if __name__ == "__main__":
    main()
