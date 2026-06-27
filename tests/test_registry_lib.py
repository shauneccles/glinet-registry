"""Tests for the self-contained registry tooling."""
# pylint: disable=missing-function-docstring

import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from tools.registry_lib import build_manifest, device_id, validate_profile  # noqa: E402

CLEAN = {
    "id": "x", "model": "mt6000", "firmware_version": "4.9.0",
    "services": {"system": {"get_info": {"status": "available", "covered_by": "router_info"}}},
}


def test_device_id_slug():
    assert device_id("MT6000", "4.9.0") == "mt6000_4.9.0"


def test_validate_clean_and_rejections():
    assert validate_profile(CLEAN) is None
    assert "identifier" in validate_profile({**CLEAN, "mac": "94:83:C4:AA:BB:CC"})
    bad = {**CLEAN, "services": {"s": {"m": {"status": "available", "value": {"x": 1}}}}}
    assert "response value" in validate_profile(bad)
    assert "MAC" in validate_profile({**CLEAN, "services": {"s": {"m": {"schema": {"a": "94:83:C4:AA:BB:CC"}}}}})
    assert "JSON object" in validate_profile("not a dict")
    assert "missing required key" in validate_profile({"model": "x", "firmware_version": "1"})
    assert "non-empty string" in validate_profile({"model": "", "firmware_version": "1", "services": {}})
    assert "must be an object" in validate_profile({"model": "x", "firmware_version": "1", "services": []})
    assert "must be an object" in validate_profile(
        {"model": "x", "firmware_version": "1", "services": {"s": {"m": "notdict"}}}
    )


def test_build_manifest_counts():
    entry = build_manifest([{**CLEAN, "id": "mt6000_4.9.0"}])["devices"][0]
    assert entry["available_count"] == 1 and entry["service_count"] == 1


def test_committed_index_matches_devices():
    reg = Path(__file__).resolve().parent.parent / "registry"
    profiles = [json.loads(p.read_text(encoding="utf-8")) for p in sorted((reg / "devices").glob("*.json"))]
    committed = json.loads((reg / "index.json").read_text(encoding="utf-8"))
    assert committed == build_manifest(profiles)
    mac = re.compile(r"(?:[0-9A-Fa-f]{2}:){5}[0-9A-Fa-f]{2}")
    for p in (reg / "devices").glob("*.json"):
        assert validate_profile(json.loads(p.read_text(encoding="utf-8"))) is None
        assert not mac.search(p.read_text(encoding="utf-8"))
