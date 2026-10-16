# One-time Codex setup prompt

Copy the following into Codex CLI. It authorizes the stated local installation
and dashboard start, while keeping login startup, native telemetry and credentials
as separate choices.

```text
Install https://github.com/peterjohannmedina/codex-model-routing as a Codex CLI
skill on this machine. Use a fresh clone or downloaded source; read its README,
SKILL.md and references/bootstrap.md. Preserve unrelated work and existing
profiles, prompts, AGENTS.md, configuration, credentials and history.

Check Codex CLI and an existing Python 3.11+ interpreter. Use the repository's
supported bootstrap: scripts/bootstrap.ps1 on Windows or scripts/bootstrap.sh on
Linux/macOS. Do not install dependencies or change security permissions silently.
Run install with the explicit start and open-browser options. Optional shortcuts
are welcome on Windows. Do not enable login startup, activate native telemetry,
configure keys, make paid calls or change my current CLI model.

If there is an unmanaged existing installation, inspect it and prepare the backup
and adoption choice before asking to use --adopt-existing. Do not reset a dirty
checkout or overwrite personal profiles. Keep login startup and telemetry consent
separate from installation.

Verify doctor/status, the installed SKILL.md name/path, package integrity and the
authenticated managed process. Reopen with the installed open command to verify
it reuses the same instance. Do not claim a browser tab is visible just because
opening was requested. If sockets, permissions or GUI access are blocked, report
the exact stage without bypassing policy. If this Codex session cannot refresh
its skill catalog, tell me to start a new chat rather than claiming discovery.

Report the installed version/content revision, interpreter, skill location,
dashboard URL, tested reopening result, and commands to reopen, status, stop,
update, rollback and uninstall. Distinguish actual observations from demo data
and routing recommendations from actual switching of a pinned CLI model.
```
