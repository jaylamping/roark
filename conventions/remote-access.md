# Remote access (Tailscale)

**Status:** proposed for Joey's review, 2026-11-08.

How people and agents reach the robot's computers (the Pi now, the Jetson later). Everything goes over **Tailscale**, a private
network between our own devices, with a plain local fallback for when the internet is down. Who may move the robot is set by
PLAN ([Real hardware rule](../PLAN.md#real-hardware-rule) and [item 3a](../PLAN.md#3a-the-runtime-interface-api), "Motion
authority"); this page makes the network and accounts enforce it.

**The principle:** Tailscale decides **who can reach** the Pi; accounts and socket permissions on the Pi decide **what they can
do** there. Neither is trusted alone.

## 1. Devices and tags

| Device | Kind | Tag |
|---|---|---|
| Robot Pi, later the Jetson | Server | `tag:robot` |
| Cloud coding agents (Claude Code, Cursor) | Short-lived | `tag:agent` (ephemeral) |
| CI, if it ever needs the robot | Short-lived | `tag:ci` (ephemeral) |
| Joey's Mac, Windows PC, phone | Personal | none: they stay Joey's own devices |

- **Servers and agents are tagged; personal devices are not.** Tailscale's docs say not to use tags for laptops and phones. A
  tagged device belongs to the tailnet, not to a person, so it keeps working if accounts change, and its key doesn't expire.
- Machine names say what they are without revealing anything sensitive (names end up in public certificate logs if HTTPS is
  turned on).

## 2. The access policy lives in git

- The Tailscale policy file is kept in a repo and applied by the `tailscale/gitops-acl-action` GitHub Action: checked on every
  PR, applied on merge. Edits in the admin console are locked, with "edit anyway" kept for emergencies. **Why:** access rules
  are as safety-relevant as code; they get the same review and history.
- **Use `grants`** (Tailscale's current syntax; the older `acls` are called legacy).
- **The shape of the policy:**
  - Joey to `tag:robot`: SSH, and HTTPS (443) for the UI.
  - `tag:agent` to `tag:robot`: SSH (22) only. No UI port.
  - `tag:robot` to anything: nothing. The robot doesn't start connections into the tailnet.
  - No `*` rules, no hostname-based rules, no subnet routes, no exit node, no `funnel` attribute (so Funnel, which exposes a
    service to the public internet, can't be turned on).
- **The policy file has tests,** and Tailscale refuses a policy whose tests fail:
  - `tests`: an agent is accepted on `tag:robot:22` and denied on `tag:robot:443`; Joey is accepted on 443.
  - `sshTests`: agents are accepted as user `agent` and denied as `root` or Joey's user.

## 3. SSH

- **Tailscale SSH** for everyone on the tailnet. Joey to `tag:robot` uses **check mode** (re-authenticate through the identity
  provider every few hours) when logging in as his own user. Agents use `accept` as the `agent` user. (Tailscale doesn't allow
  check mode for tagged sources.)
- **Explicit users only.** No `root`, no `autogroup:nonroot` for tagged sources.
- **Restarting `tailscaled` drops Tailscale SSH sessions,** so Tailscale updates happen by hand, with the drives disabled
  (section 6).
- **Audit is on the Pi:** journald records logins, and the runtime records every `api` request with its client (logging.md).
  Don't build on Tailscale's session recorder; it's deprecated.

## 4. Accounts on the Pi

| Account | Who | Can |
|---|---|---|
| Joey's user | Joey | Everything an operator can: `enable`, `clear`, start plans, stop, deploy, `sudo` |
| `agent` | Cloud agents | Read logs and recordings, deploy, run anything on `vcan`, start approved plans, stop. No `sudo`, no `enable` or `clear` |
| Service user for the runtime | systemd | Run the runtime with the realtime and network capabilities it needs; no login |

- **Motion authority is enforced by the `api` socket,** not by trust: the socket's permissions and the runtime's per-client
  rules let only Joey's user `enable` and `clear` (PLAN item 3a). An agent that somehow gets a shell still can't enable a drive.
- **Agents never get Joey's SSH key** and never log in as Joey.

## 5. Keys for cloud agents

- **Ephemeral, pre-approved, tagged `tag:agent`.** An ephemeral node disappears from the tailnet soon after it goes idle; run it
  with in-memory state (`tailscaled --state=mem:`) so nothing persists in the container.
- **Prefer workload identity** (an OIDC token from the agent platform) if the platform provides one, so there's no long-lived
  secret at all. Otherwise an **OAuth client** restricted to creating `tag:agent` keys, stored as a secret in the agent
  environment. Never a reusable plain auth key, and never in an environment variable everyone with access can read without
  knowing it.
- **Containers use userspace networking** (`--tun=userspace-networking`, with a local SOCKS5 or HTTP proxy for SSH). Cursor's
  cloud agents need this; the legacy repo's setup shows it working.
- **Claude Code cloud sessions are untested.** All their traffic goes through an HTTPS proxy, so Tailscale may only work in
  userspace mode relayed over DERP, if at all. Test it before relying on it. The fallback is Remote Control on Joey's machine.

## 6. The robot's Tailscale install

- Installed from Tailscale's apt repository, with **auto-update off** for the robot. Updated by hand, drives disabled, like any
  other system change ([deploy.md](deploy.md)).
- **The runtime doesn't depend on Tailscale.** No systemd ordering on `tailscaled`; the robot runs, stops and records the same
  with Tailscale down.
- **Firewall:** `ufw` denies incoming by default and allows the `tailscale0` interface and SSH from the home LAN. Tailnet
  traffic is filtered by the Tailscale policy, not `ufw` (Tailscale's own firewall rules accept `tailscale0` traffic first).

## 7. The UI over the tailnet

- The UI bridge listens only on localhost (or a Unix socket). **`tailscale serve`** publishes it on HTTPS 443 to the tailnet
  only, with Tailscale's own certificate.
- `serve` adds the caller's identity in request headers (`Tailscale-User-Login`). The bridge allows actions that move the robot
  only when that header is Joey's login, and treats a missing header (tagged devices, unknown callers) as **read-only**. This
  is the "no unauthenticated remote motion endpoint" rule in PLAN item 3a.
- **Never Funnel.** The robot's UI is never on the public internet.

## 8. When the internet is down

- Tailscale keeps working between devices that already know each other: traffic never goes through Tailscale's servers, and
  peers on the same LAN talk directly. New devices can't join, and check-mode SSH may fail because it needs the identity
  provider.
- **Fallbacks, in order:** plain OpenSSH to the Pi's LAN address with Joey's key; a keyboard and screen on the Pi; and always the
  physical E-stop. Agents have no LAN path.
- Robot software never needs the internet to run. ROS-style multicast discovery wouldn't cross Tailscale anyway; our `api` is a
  local socket, so nothing depends on it.

## 9. Locking the tailnet down

- MFA on the identity provider Joey signs in with.
- Either **device approval** (new devices need an admin's OK) or **Tailnet Lock** (new devices must be signed by trusted nodes);
  Tailscale says they can't be used together. Tailnet Lock is the stronger choice once there are two signing devices.
- Review the device list at each milestone and remove what's no longer used.

## Checklist for a change to access

- Is it a policy PR with updated `tests` and `sshTests`?
- Does any new rule use `*`, a hostname, `root`, or a port beyond what that tag needs?
- Can an agent reach anything that lets it `enable` or `clear`?
- Does anything make the robot depend on Tailscale to run or stop?

## Sources

- Tailscale docs: tags (https://tailscale.com/kb/1068/tags), grants (https://tailscale.com/kb/1324/grants), policy tests
  (https://tailscale.com/kb/1337/policy-syntax), GitOps for the policy (https://tailscale.com/kb/1306/gitops-acls-github),
  Tailscale SSH (https://tailscale.com/kb/1193/tailscale-ssh), session recording deprecation
  (https://tailscale.com/kb/1246/tailscale-ssh-session-recording), auth keys (https://tailscale.com/kb/1085/auth-keys),
  ephemeral nodes (https://tailscale.com/kb/1111/ephemeral-nodes), OAuth clients (https://tailscale.com/kb/1215/oauth-clients),
  workload identity (https://tailscale.com/docs/features/workload-identity-federation), serve
  (https://tailscale.com/kb/1312/serve), Funnel (https://tailscale.com/kb/1223/funnel), HTTPS
  (https://tailscale.com/kb/1153/enabling-https), coordination server outages
  (https://tailscale.com/docs/reference/coordination-server-down), updates (https://tailscale.com/kb/1067/update), securing a
  server with ufw (https://tailscale.com/kb/1077/secure-server), device approval (https://tailscale.com/kb/1099/device-approval),
  Tailnet Lock (https://tailscale.com/kb/1226/tailnet-lock)
- Cursor cloud agents and Tailscale: https://cursor.com/docs/cloud-agent/setup
- Legacy setup (what to improve on: reusable key, shared SSH key, hostname rules):
  https://github.com/jaylamping/marengo/blob/main/docs/cloud-pi-tailscale.md
