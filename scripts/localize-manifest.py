#!/usr/bin/env python3
"""Point a built release manifest at artifacts on disk, for a local install.

``install.sh --manifest`` verifies every artifact against the digests inside the
manifest, but resolves each artifact's ``url`` — which ``release.py build``
writes as a GitHub download link. Installing a release that was never published
therefore fails on a 404 even though the files are sitting right there.

Rewriting the urls to absolute paths is enough: ``fetch()`` accepts local paths,
and the per-artifact digests still authenticate the payload. SHA256SUMS is
regenerated for the manifest alone so its self-check keeps passing.
"""

from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path


def main() -> int:
    directory = Path(sys.argv[1] if len(sys.argv) > 1 else "dist/release").resolve()
    manifest_path = directory / "release-manifest.json"
    if not manifest_path.is_file():
        print(f"no release manifest in {directory}", file=sys.stderr)
        return 1

    manifest = json.loads(manifest_path.read_text())
    for artifact in manifest["artifacts"]:
        artifact["url"] = str(directory / artifact["name"])
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n")

    checksums = directory / "SHA256SUMS"
    lines = []
    for line in checksums.read_text().splitlines():
        digest, name = line.split(None, 1)
        name = name.strip()
        if name == manifest_path.name:
            digest = hashlib.sha256(manifest_path.read_bytes()).hexdigest()
        lines.append(f"{digest}  {name}")
    checksums.write_text("\n".join(lines) + "\n")

    print(f"{len(manifest['artifacts'])} artifacts pointed at {directory}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
