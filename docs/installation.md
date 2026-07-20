# Installing Dax

Dax is four pieces, and only the first is required:

| Piece | What it is | How it is configured |
| --- | --- | --- |
| **Backend** | The single authority: SQLite, configuration, conversations, LLM routing, policy, approvals | Commands, on the machine it runs on |
| **Desktop** | A client, and the machine that can also be a capability node | Its own UI |
| **Android** | A client | Its own UI |
| **Capability node** | An optional laptop daemon that lends tools to the backend | Enrolled by command, governed from the desktop or web UI |

The ordering matters: everything else needs a backend to talk to, and a node or
phone can only be enrolled by a client that is already authenticated. Install in
the order below and nothing will ask you for something you do not have yet.

## 1. Backend

Follow the verified install path in the [README](../README.md#production-install)
— pin a release, verify its attestation, then run the installer. The operational
runbook, backups, and upgrades live in [`deployment.md`](deployment.md).

The backend is the one piece with no configuration UI of its own, by design. It
is configured by command on the machine it runs on:

```bash
systemctl --user status dax-assistant
journalctl --user -u dax-assistant -f
```

Its bind address and port come from the encrypted configuration; every other
setting is editable from any authenticated client. It binds `127.0.0.1` by
default — see [Remote access](../README.md#remote-access) before exposing it.

## 2. Desktop

Install with `bash install.sh --version "$VERSION" --desktop-only`, or `--both`
alongside the backend.

First launch runs setup in two halves, split by a login:

**Before login — connection.** Choose whether the authority is a backend on this
machine or your server, give its URL, and verify it responds. There is nothing
to log into until this is settled, which is why it comes first. Re-openable from
**Settings → Desktop → Open onboarding**.

**After login — everything else.** Pick a model and enter its API key, enrol this
laptop as a capability node, and pair your phone. All three call an authenticated
backend, so none of them can run any earlier. Every step is skippable and the
flow is re-openable from **Settings → Desktop → Run setup again**.

Nothing in the desktop app stores an API key locally; keys go to the backend's
encrypted secret store. Session credentials are kept per origin in the system
keyring and are never copied between servers.

## 3. Android

The APK is a separate signed release asset. The installer never downloads it —
fetch it from the release page and verify it the same way:

```bash
VERSION=0.1.0
curl --proto '=https' --tlsv1.2 --fail --location --remote-name \
  "https://github.com/daxrpm/dax-assistant/releases/download/v$VERSION/dax-assistant.apk"
gh attestation verify dax-assistant.apk --repo daxrpm/dax-assistant
```

First run walks four steps:

1. **Backend address** — HTTPS, or a private-network address.
2. **Pairing code** — generated on an already-authenticated desktop or web
   client under **Settings → Access → Devices**, or during desktop first-run
   setup. Scan the QR or type the eight characters. The phone never learns your
   password: it redeems the code once for its own device credential and then
   exchanges that for short-lived tokens.
3. **Permissions** — microphone, Bluetooth, and notifications. The microphone is
   opened only while a turn is live.
4. **Assistant role** — select Dax under Android's *Digital assistant app*.

That last step is worth understanding, because it is the one thing the app
cannot do for you. `RoleManager` has no request flow for the assistant role, so
the app can only send you to the right settings page. Granting it does two
things: the gesture your phone already maps to an assistant starts opening the
Dax voice orb, and Android's foreground-service rules begin exempting the app,
which is what makes a trigger legal while the app is not visible.

**No app can bind the power button.** `KEYCODE_POWER` is not delivered to
applications. Which gesture invokes an assistant is a system setting, and on
most phones a long power press of several seconds is a forced restart, not an
assist gesture. Dax answers whichever gesture your phone assigns; it cannot
choose that gesture.

## 4. Capability node

A node lets the backend use tools on a laptop without moving the backend there.
Full behaviour, safety model, and revocation are in
[`capability-nodes.md`](capability-nodes.md). The short path:

```bash
# Installs the unit but deliberately does not enable or start it.
bash install.sh --version "$VERSION" --with-node

# Enrol first: the unit refuses to start without a credential file.
dax edge enroll --server https://dax.example --code CODE --name "$(hostname)"
dax edge status

systemctl --user enable --now dax-assistant-node.service
journalctl --user -u dax-assistant-node.service -f
```

Generate `CODE` from the desktop or web UI under **Settings → Access → Devices →
Add laptop capability**, or from desktop first-run setup, which prints the whole
command ready to paste.

Once enrolled, what the node is asked to do is configured from a UI, not from
the laptop's config file:

* **Desktop and web** — **Settings → Capabilities → Capability nodes**. One card
  per laptop, showing whether it is connected right now, with per-node control
  over processing, inference, and speech.
* **Android** — **Settings → Local node**. The phone gets the two fleet switches
  and whether a node is currently up. It deliberately cannot enumerate or
  re-policy the fleet: an enrolled device may not list its siblings.

Leave **inference** on `auto`. It pins the model to the laptop only when the
model is itself local — Ollama on the laptop's GPU. A cloud provider is
dominated by the round trip to that provider, so routing the call through a
laptop adds a hop and removes none. **Speech** is where a node genuinely wins:
audio is bulky, and keeping transcription next to the microphone avoids sending
it across the network twice.

## Verifying the whole chain

```bash
systemctl --user status dax-assistant            # backend up
systemctl --user status dax-assistant-node       # node up, if enrolled
dax edge status                                  # node knows its server
```

In the desktop UI, **Settings → Capabilities → Capability nodes** shows a live
presence dot per node, taken from the open socket rather than from the last time
the node asked for a token. On the phone, **Settings → Local node** says whether
a laptop is up and which one would serve it.
