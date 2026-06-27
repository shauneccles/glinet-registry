# glinet-registry

Community device-profile registry for GL.iNet routers — firmware API capability data, fully decoupled from the `glinet-profiler` package.

## What this is

`registry/devices/` holds one sanitized JSON profile per device+firmware combination. `registry/index.json` is a generated manifest summarising available method counts per device, kept in sync by `scripts/build_manifest.py`.

## How to contribute

**Option 1 — the launcher (recommended):** Run [`glinet-profiler`](https://github.com/shauneccles/glinet-profiler) against your device. It captures a **sanitized** profile (no MAC addresses, no serials, no credentials, no response values), tells you whether the device is already here, and opens a prefilled submission for you.

```bash
uvx glinet-profiler              # local web UI
uvx glinet-profiler 192.168.8.1  # headless; prints the submission link
```

**Option 2 — the issue form:** Open a [Device Profile submission](../../issues/new?template=profile-submission.yml) issue and **drag-and-drop** the `<id>.json` the launcher saved (don't paste its contents). A bot validates it and opens a pull request.

**Option 3 — a manual pull request:** Add the sanitized file under `registry/devices/<id>.json`, run `python scripts/build_manifest.py`, and open a PR.

## Keeping `index.json` in sync

After adding or editing a device profile, regenerate the manifest:

```bash
python scripts/build_manifest.py
```

CI enforces that `index.json` matches the device files (`python scripts/build_manifest.py --check`). Pull requests that add a device file without regenerating the manifest will fail CI.

## Tooling

- `tools/registry_lib.py` — pure stdlib helpers: `device_id`, `validate_profile`, `build_manifest`
- `scripts/build_manifest.py` — rebuild or `--check` the manifest
- `scripts/ingest.py` — validate a submission file, write it, and rebuild the manifest
- `tests/` — `uvx pytest -q`
