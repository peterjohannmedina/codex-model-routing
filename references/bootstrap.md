# Skill bootstrap and dashboard lifecycle

This package installs a Codex CLI skill plus its supporting runtime. It is not a
desktop application or EXE. Python 3.11+ and an installed Codex CLI are prerequisites;
the bootstrap uses the standard library and installs no SDK, server dependency,
OAuth connection or model. Git is optional when using a downloaded source archive.
Use an existing interpreter through `CODEX_ROUTING_PYTHON`, Windows `-PythonPath`,
or invoke `python3 -B scripts/routing_bootstrap.py` directly.

## Separate actions and permissions

| Action | What it changes |
| --- | --- |
| `install` | Versioned skill files, missing native profile/prompt templates, private install receipt and rollback backup |
| `--start` or `start` | Starts one user-owned background Python process; it needs no interactive terminal |
| `open` | Starts if needed, then obtains a fresh expiring browser authorization file from the authenticated running instance |
| `--shortcuts` | Optional user launcher: Windows desktop/Start menu, macOS Desktop command, Linux application-menu entry |
| `--login-startup` | Explicitly adds a per-user next-login launcher; no system service, privilege change or immediate telemetry activation |
| `start --otel-receiver` | Enables ingestion only for a separately approved existing private OTel setup; does not edit Codex config |

Installing a skill does not imply starting a process, enabling login startup or
collecting native-session telemetry. A server process is still required while the
dashboard is available. Without login startup it must be started again after
logout/reboot. This manager detaches that process from the interactive shell;
there is no terminal to keep open. It does not restart active Codex sessions.

The bootstrap resolves `$CODEX_HOME` or `~/.codex`. Explicit `--user-root` uses an
isolated user root, ignoring inherited `CODEX_HOME` unless `--codex-home` is given.
No machine-specific installation path is embedded. Shortcuts point at the installed
runtime; the original clone/download can be moved after a successful install.

## Install, update, repair and rollback

Run `sh scripts/bootstrap.sh install --start --open-browser` on Linux/macOS, or
`powershell.exe -NoProfile -File .\scripts\bootstrap.ps1 -Command install -Start -OpenBrowser`
on Windows. Windows can add `-Shortcuts`; Unix can add `--shortcuts`.

Existing profiles, slash prompts, global `AGENTS.md`, user configuration, credentials
and history are preserved. Missing native profiles and a routing slash prompt are
created as user-owned templates; later updates and uninstall leave them alone.
The legacy copy installers remain available, but the bootstrap is the supported
route for managed lifecycle. Do not mix installers without inspecting ownership.

An existing unmanaged skill is not silently adopted. Review its changes and choose
`install --adopt-existing` (Windows `-AdoptExisting`) explicitly. Known package
files are backed up before adoption; unrelated files remain untouched. Updating
refuses modified owned package files. `repair` is an explicit restoration of owned
files from the reviewed source, with a private recovery copy of existing bytes.

For an update, fetch/review the source without discarding unrelated work, then run
its bootstrap with `update`. Source archives work too. A SHA-256 content revision
and version are recorded, and status compares installed files with the receipt.
An unchanged install/update does not replace the running instance. A changed
update stops only the capability-authenticated managed receiver, updates files,
then restarts it if it was running. An occupied unmanaged port is left alone.
`rollback` restores the previous package snapshot after checking current ownership
and backup hashes. It preserves profiles, prompts, history and credentials.

Backups are stored under `routing/dashboard-service/backups` with flat blob names
to reduce Windows path-length pressure. No registry/long-path policy is changed.
Backups are retained after uninstall. Only exact owned files are removed; modified
or unknown files are retained. `uninstall` stops only the authenticated managed
instance and removes unchanged owned skill/launcher files. It does not remove a
Codex OTel exporter: use the separately approved telemetry undo workflow before
uninstall if that is desired. Later config edits require the documented manual
undo review; they are not overwritten.

## Reopen and bookmark

Use the installed `bootstrap.sh open` / `bootstrap.ps1 -Command open`, or the
optional launcher. This reuses the same running instance and renews a one-use,
five-minute handoff file. Existing authorized tabs remain valid. No capability is
put on a command line or written to browser profiles. The URL is normally
`http://127.0.0.1:8765`; an explicitly chosen different port is recorded.

After authorization, bookmark that plain URL with the browser's own bookmark UI.
Never bookmark the temporary authorization fragment or private handoff file. If a
bookmark opens an unauthorized page after a browser restart, use `open` again.
Headless environments can use `open --no-browser`; it returns a private handoff
path to open manually. Browser launch failure is reported and never equated with
a verified visible tab. No CUA/GUI automation or browser-profile editing is used.

## Login startup and platform adapters

Login startup defaults off. Explicitly choose `install/update --login-startup`
(Windows `-LoginStartup`). Remove it with `update --no-login-startup` (Windows
`-LoginStartup:$false`). This writes only the user's Startup shortcut on Windows,
an XDG autostart entry on Linux, or a LaunchAgent plist on macOS. It takes effect
at the next login; the bootstrap does not invoke a system service manager or alter
security permissions. User-edited launcher files are preserved.

Linux entries follow the [Desktop Entry Exec rules](https://specifications.freedesktop.org/desktop-entry/latest/exec-variables.html)
and [XDG autostart specification](https://specifications.freedesktop.org/autostart/latest/).
Desktop trust prompts, GUI activation and actual next-login behavior depend on the
host and must be checked separately; rendering or writing a fixture is not proof
of those interactions. Native Linux/macOS login jobs keep a foreground worker
inside the OS job instead of daemonizing out of it. A macOS Desktop command may
briefly open Terminal; that command returns and the terminal is not a server
dependency. No EXE is needed for this
skill-first scope; a future signed bundle would mainly remove the Python prerequisite.

## Security and bounded control

Managed control is disabled on the ordinary foreground dashboard. The manager
creates an owner-private control capability only on explicit background start.
`/api/lifecycle` accepts status/open/stop on loopback with exact Host, one control
header, no browser Origin/Fetch headers, uncompressed JSON and a 512-byte limit.
Browser and OTel capabilities grant no control access; control grants no data API
access. Reopening rotates only browser bootstrap state, not the running process.
Stop never trusts a PID alone and never force-kills an unrelated listener.

Startup validates private state permissions and fails closed rather than repairing
ACLs, changing a firewall or bypassing blocked sockets. Windows uses the shipped
read-only ACL probe. Unix uses current-user ownership and restrictive modes.
No API key is needed. Credential fields contain environment-variable names such
as `OPENAI_API_KEY`, not secret values. No provider or metered request is made by
install, status, open or stop.

Native recommendations do not switch a pinned CLI model or execute a candidate.
The parent still chooses/dispatches work through supported controls. Actual
observations require the instrumented runtime, exec stream or separately approved
native exporter. Demo screenshots are not evidence of personal activity. For
telemetry activation/retention and unsupported surfaces, read
[automatic-telemetry.md](automatic-telemetry.md).
