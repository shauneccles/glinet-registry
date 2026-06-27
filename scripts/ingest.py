"""Validate a submitted profile, write registry/devices/<id>.json, rebuild the manifest."""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from tools.registry_lib import build_manifest, device_id, validate_profile  # noqa: E402

_REG = Path(__file__).resolve().parent.parent / "registry"


def main(argv: list[str] | None = None) -> int:
    """Ingest the given submission file; print the id (ok) or the error (fail)."""
    if not argv:
        argv = sys.argv[1:]
    data = json.loads(Path(argv[0]).read_text(encoding="utf-8"))
    error = validate_profile(data)
    if error:
        print(error, file=sys.stderr)
        return 1
    new_id = device_id(data["model"], data["firmware_version"])
    data["id"] = new_id
    (_REG / "devices").mkdir(parents=True, exist_ok=True)
    (_REG / "devices" / f"{new_id}.json").write_text(
        json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    profiles = [
        json.loads(p.read_text(encoding="utf-8")) for p in sorted((_REG / "devices").glob("*.json"))
    ]
    (_REG / "index.json").write_text(
        json.dumps(build_manifest(profiles), indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(new_id)
    return 0


if __name__ == "__main__":
    sys.exit(main())
