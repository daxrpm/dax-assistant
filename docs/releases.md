# Release And Installation

Dax releases coordinate compatible components without combining their trust or
installation boundaries. `release.json` records API compatibility for the
backend, desktop, Android, and capability-node protocol. A tagged release
publishes separate backend wheel/dependency lock/service assets, desktop RPM and
deb packages, a signed Android APK, the optional node service, the Linux
installer, and a release manifest.

## Verified Linux Install

Download the installer as data and verify its GitHub artifact attestation before
executing it. The installer resolves the newest published release on its own:

```bash
curl --proto '=https' --tlsv1.2 --fail --location --remote-name \
  "https://github.com/daxrpm/dax-assistant/releases/latest/download/install.sh"
gh attestation verify install.sh --repo daxrpm/dax-assistant
bash install.sh --both
```

Pin an immutable tag when an install must be reproducible or must downgrade:

```bash
VERSION=0.1.2
curl --proto '=https' --tlsv1.2 --fail --location --remote-name \
  "https://github.com/daxrpm/dax-assistant/releases/download/v$VERSION/install.sh"
gh attestation verify install.sh --repo daxrpm/dax-assistant
bash install.sh --version "$VERSION" --both
```

`release.json` is the single source of truth for the version.
`scripts/release.py sync X.Y.Z` propagates it to every product manifest and to
the pinned example on this page; `scripts/release.py check` fails the build when
any of them disagree, which is what keeps documented install commands from
naming a release that is no longer current.

The installer then downloads the attested release manifest, verifies its tag,
commit, compatibility metadata, and attestation, and verifies attestation,
SHA256, and size for every selected artifact. It fails closed when verification
is unavailable or invalid. `--insecure-skip-attestation` is an explicit emergency
bypass, not a verified installation path. `--dry-run` performs selection,
download, and verification without installation.

Use `--backend-only`, `--desktop-only`, `--node-only`, or `--both`. The host receives the
release's RPM or deb; those packages do not install the backend unless it was
selected, and no Linux option installs Android. `--node-only` installs a separate
verified capability runtime and canonical node unit without installing or
starting an authority. It remains disabled until enrollment. See
[`capability-nodes.md`](capability-nodes.md).

The Android APK is a separate signed asset. Release construction requires the
Android keystore variables and expected `DAX_ANDROID_CERT_SHA256`; the pipeline
uses `apksigner` to validate both the signature and exact signer identity before
publication. Installing and launching that APK on a clean physical device, just
like clean RPM/deb installation and platform signing acceptance, remains an
external release gate rather than a claim made by build tests.

## Source Development Mode

For development only:

```bash
bash scripts/install.sh --source "$PWD" --backend-only
```

Source mode uses the existing checkout with `uv sync --frozen`. It does not
clone or execute `main`, use release artifacts, install a desktop package, or
claim release attestation. Build desktop and Android independently with the
commands in their README files.

For production upgrades, rollback, backup, disaster recovery, and server
replacement, follow [`deployment.md`](deployment.md).
