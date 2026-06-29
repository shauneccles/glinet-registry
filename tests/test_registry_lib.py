"""Tests for the self-contained registry tooling."""
# pylint: disable=missing-function-docstring

import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from tools.registry_lib import (  # noqa: E402
    _to_json_schema,
    build_manifest,
    device_id,
    to_openrpc,
    validate_profile,
)

CLEAN = {
    "id": "x",
    "model": "mt6000",
    "firmware_version": "4.9.0",
    "services": {"system": {"get_info": {"status": "available", "covered_by": "router_info"}}},
}


def test_device_id_slug():
    assert device_id("MT6000", "4.9.0") == "mt6000_4.9.0"


def test_validate_clean_and_rejections():
    assert validate_profile(CLEAN) is None
    assert "identifier" in validate_profile({**CLEAN, "mac": "94:83:C4:AA:BB:CC"})
    bad = {**CLEAN, "services": {"s": {"m": {"status": "available", "value": {"x": 1}}}}}
    assert "response value" in validate_profile(bad)
    assert "MAC" in validate_profile(
        {**CLEAN, "services": {"s": {"m": {"schema": {"a": "94:83:C4:AA:BB:CC"}}}}}
    )
    assert "JSON object" in validate_profile("not a dict")
    assert "missing required key" in validate_profile({"model": "x", "firmware_version": "1"})
    assert "non-empty string" in validate_profile(
        {"model": "", "firmware_version": "1", "services": {}}
    )
    assert "must be an object" in validate_profile(
        {"model": "x", "firmware_version": "1", "services": []}
    )
    assert "must be an object" in validate_profile(
        {"model": "x", "firmware_version": "1", "services": {"s": {"m": "notdict"}}}
    )


def test_build_manifest_counts():
    entry = build_manifest([{**CLEAN, "id": "mt6000_4.9.0"}])["devices"][0]
    assert entry["available_count"] == 1 and entry["service_count"] == 1
    assert entry["discovered_count"] == 0


def test_build_manifest_counts_discovered_writes():
    prof = {
        "id": "x",
        "model": "m",
        "firmware_version": "1",
        "services": {
            "acl": {
                "get_x": {"status": "available", "covered_by": None},
                "set_x": {"status": "discovered", "covered_by": None},
            }
        },
    }
    entry = build_manifest([prof])["devices"][0]
    assert entry["available_count"] == 1
    assert entry["discovered_count"] == 1


def test_to_json_schema_shapes():
    assert _to_json_schema("str") == {"type": "string"}
    assert _to_json_schema("int") == {"type": "integer"}
    assert _to_json_schema({"a": "bool"}) == {
        "type": "object",
        "properties": {"a": {"type": "boolean"}},
    }
    assert _to_json_schema(["str"]) == {"type": "array", "items": {"type": "string"}}
    assert _to_json_schema("mystery") == {}  # unknown type -> permissive


def test_to_openrpc_exports_exists_methods_with_extensions():
    profile = {
        "id": "mt6000_4.9.0",
        "model": "mt6000",
        "firmware_version": "4.9.0",
        "services": {
            "system": {
                "get_info": {
                    "status": "available",
                    "risk": "read",
                    "discovered_by": "catalog",
                    "covered_by": "router_info",
                    "params": None,
                    "schema": {"model": "str", "n": "int"},
                },
                "gone": {
                    "status": "absent",
                    "risk": "read",
                    "discovered_by": "catalog",
                    "covered_by": None,
                    "params": None,
                    "schema": None,
                },
            },
            "acl": {
                "add_user": {
                    "status": "discovered",
                    "risk": "write",
                    "discovered_by": "ssh",
                    "covered_by": None,
                    "params": ["name"],
                    "schema": None,
                },
            },
        },
    }
    doc = to_openrpc(profile)
    assert doc["openrpc"] == "1.2.6"
    assert doc["info"]["version"] == "4.9.0" and "mt6000" in doc["info"]["title"]
    by_name = {m["name"]: m for m in doc["methods"]}
    assert "system.get_info" in by_name and "acl.add_user" in by_name
    assert "system.gone" not in by_name  # absent is excluded from the surface
    # captured shape -> real JSON Schema on the result
    assert by_name["system.get_info"]["result"]["schema"] == {
        "type": "object",
        "properties": {"model": {"type": "string"}, "n": {"type": "integer"}},
    }
    # registry metadata preserved as x- extensions
    assert by_name["system.get_info"]["x-status"] == "available"
    assert by_name["system.get_info"]["x-gli4py"] == "router_info"
    # discovered write: named params, empty result schema (never called)
    assert by_name["acl.add_user"]["params"] == [{"name": "name", "schema": {}}]
    assert by_name["acl.add_user"]["result"]["schema"] == {}


def test_manifest_and_openrpc_carry_capabilities():
    prof = {
        "id": "x_1",
        "model": "x",
        "firmware_version": "1",
        "capabilities": {
            "country_code": "US",
            "software_feature": {"vpn": True},
            "hardware_feature": {"simo": False},
        },
        "services": {"system": {"get_info": {"status": "available", "covered_by": None}}},
    }
    assert build_manifest([prof])["devices"][0]["country_code"] == "US"
    doc = to_openrpc(prof)
    assert doc["x-capabilities"]["country_code"] == "US"
    assert doc["x-capabilities"]["hardware_feature"]["simo"] is False


def test_to_openrpc_uses_signature_for_schema_and_examples():
    profile = {
        "id": "x_1", "model": "x", "firmware_version": "1",
        "services": {"wifi": {"get_status": {
            "status": "available", "risk": "read", "discovered_by": "catalog",
            "covered_by": None, "params": None,
            "signature": {"band": "5g", "channel": 36, "gateway": "<ipv4>"},
        }}},
    }
    m = {x["name"]: x for x in to_openrpc(profile)["methods"]}["wifi.get_status"]
    schema = m["result"]["schema"]
    assert schema["type"] == "object"
    assert schema["properties"]["channel"] == {"type": "integer", "examples": [36]}
    assert schema["properties"]["band"] == {"type": "string", "examples": ["5g"]}
    assert schema["properties"]["gateway"] == {"type": "string", "format": "ipv4"}


def test_to_openrpc_pairs_write_request_shape_from_get_sibling():
    profile = {
        "id": "x_1", "model": "x", "firmware_version": "1",
        "services": {"tor": {
            "get_config": {"status": "available", "risk": "read", "covered_by": None,
                           "signature": {"enable": False, "manual": True}},
            "set_config": {"status": "discovered", "risk": "write", "covered_by": None,
                           "params": [], "signature": None},
        }},
    }
    m = {x["name"]: x for x in to_openrpc(profile)["methods"]}["tor.set_config"]
    names = {p["name"] for p in m["params"]}
    assert names == {"enable", "manual"}
    assert m["x-inferred-from"] == "tor.get_config"
    assert m["params"][0]["schema"]  # has a JSON-schema fragment from the read


def test_committed_index_matches_devices():
    reg = Path(__file__).resolve().parent.parent / "registry"
    profiles = [
        json.loads(p.read_text(encoding="utf-8")) for p in sorted((reg / "devices").glob("*.json"))
    ]
    committed = json.loads((reg / "index.json").read_text(encoding="utf-8"))
    assert committed == build_manifest(profiles)
    mac = re.compile(r"(?:[0-9A-Fa-f]{2}:){5}[0-9A-Fa-f]{2}")
    for p in (reg / "devices").glob("*.json"):
        assert validate_profile(json.loads(p.read_text(encoding="utf-8"))) is None
        assert not mac.search(p.read_text(encoding="utf-8"))
