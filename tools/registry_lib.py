"""Self-contained registry helpers (stdlib only): id slug, validation, manifest."""

import json
import re
from typing import Any

_SLUG = re.compile(r"[^a-z0-9.]+")
_MAC_RE = re.compile(r"(?:[0-9A-Fa-f]{2}:){5}[0-9A-Fa-f]{2}")
_PRESENT = ("available", "needs_params")
_REQUIRED = ("model", "firmware_version", "services")
_IDENTIFIERS = ("mac", "sn", "sn_bak")


def device_id(model: str, firmware: str) -> str:
    """Slug `model_firmware`."""
    model_slug = _SLUG.sub("-", model.lower()).strip("-")
    firmware_slug = _SLUG.sub("-", firmware.lower()).strip("-")
    return f"{model_slug}_{firmware_slug}"


def validate_profile(data: Any) -> str | None:  # pylint: disable=too-many-return-statements
    """Return an error message if `data` is not a clean sanitized profile, else None."""
    if not isinstance(data, dict):
        return "submission is not a JSON object"
    for key in _REQUIRED:
        if key not in data:
            return f"missing required key: {key}"
    for key in ("model", "firmware_version"):
        if not isinstance(data[key], str) or not data[key].strip():
            return f"'{key}' must be a non-empty string"
    if not isinstance(data["services"], dict):
        return "'services' must be an object"
    for ident in _IDENTIFIERS:
        if ident in data:
            return f"profile contains a device identifier ({ident}); submit a sanitized profile, not a raw report"
    for service, methods in data["services"].items():
        if not isinstance(methods, dict):
            return f"service '{service}' must be an object"
        for method, rec in methods.items():
            if not isinstance(rec, dict):
                return f"method '{service}.{method}' must be an object"
            if "value" in rec:
                return f"method '{service}.{method}' contains a response value; submit a sanitized profile"
    if _MAC_RE.search(json.dumps(data)):
        return "profile contains a MAC-address-like value; submit a sanitized profile"
    return None


def build_manifest(profiles: list[dict[str, Any]]) -> dict[str, Any]:
    """Build the manifest (per-device id/model/firmware + present-method counts)."""
    entries: list[dict[str, Any]] = []
    for dev in profiles:
        present = [
            rec
            for methods in dev["services"].values()
            for rec in methods.values()
            if rec.get("status") in _PRESENT
        ]
        service_count = sum(
            1
            for methods in dev["services"].values()
            if any(rec.get("status") in _PRESENT for rec in methods.values())
        )
        discovered_count = sum(
            1
            for methods in dev["services"].values()
            for rec in methods.values()
            if rec.get("status") == "discovered"
        )
        entries.append(
            {
                "id": dev["id"],
                "model": dev.get("model", "unknown"),
                "firmware_version": dev.get("firmware_version", "unknown"),
                "country_code": dev.get("capabilities", {}).get("country_code"),
                "service_count": service_count,
                "available_count": len(present),
                "discovered_count": discovered_count,
                "not_wrapped_count": sum(1 for rec in present if rec.get("covered_by") is None),
            }
        )
    entries.sort(key=lambda entry: (entry["model"], entry["firmware_version"]))
    return {"devices": entries}


# OpenRPC export ------------------------------------------------------------------
# A device profile is a superset of an API spec (it carries probe status/risk/provenance),
# but the "exists" methods + their captured schemas map cleanly onto OpenRPC (the JSON-RPC
# analog of OpenAPI), which unlocks codegen + standard tooling. Registry-only metadata is
# preserved in `x-` specification extensions.

_OPENRPC_EXISTS = ("available", "needs_params", "error", "discovered")
_SCALAR_TO_JSON = {
    "str": "string",
    "int": "integer",
    "float": "number",
    "bool": "boolean",
    "null": "null",
    "list": "array",
    "dict": "object",
}


def _to_json_schema(shape: Any) -> dict[str, Any]:
    """Convert a captured type-erased shape (e.g. {'n': 'int'}) into a JSON Schema fragment."""
    if isinstance(shape, dict):
        return {
            "type": "object",
            "properties": {k: _to_json_schema(v) for k, v in shape.items()},
        }
    if isinstance(shape, list):
        return {"type": "array", "items": _to_json_schema(shape[0]) if shape else {}}
    if isinstance(shape, str):
        json_type = _SCALAR_TO_JSON.get(shape)
        return {"type": json_type} if json_type else {}
    return {}


def to_openrpc(profile: dict[str, Any]) -> dict[str, Any]:
    """Render a device profile as an OpenRPC 1.x document (the exists-methods + their schemas)."""
    model = profile.get("model", "unknown")
    firmware = profile.get("firmware_version", "unknown")
    methods = []
    for service in sorted(profile.get("services", {})):
        for method in sorted(profile["services"][service]):
            rec = profile["services"][service][method]
            if rec.get("status") not in _OPENRPC_EXISTS:
                continue  # absent / unreachable / other aren't part of the surface
            schema = rec.get("schema")
            entry: dict[str, Any] = {
                "name": f"{service}.{method}",
                "params": [{"name": p, "schema": {}} for p in (rec.get("params") or [])],
                "result": {"name": "result", "schema": _to_json_schema(schema) if schema else {}},
                "x-status": rec.get("status"),
                "x-risk": rec.get("risk"),
                "x-discovered-by": rec.get("discovered_by"),
            }
            if rec.get("covered_by"):
                entry["x-gli4py"] = rec["covered_by"]
            methods.append(entry)
    return {
        "openrpc": "1.2.6",
        "info": {
            "title": f"GL.iNet {model} RPC API",
            "version": str(firmware),
            "description": (
                f"Auto-generated from a sanitized glinet-profiler capture of a GL.iNet {model} "
                f"on firmware {firmware}. Calls are JSON-RPC 2.0 over POST /rpc. The `x-status`, "
                "`x-risk`, `x-discovered-by` and `x-gli4py` extensions carry registry metadata. "
                "Empirical observation, not an official vendor contract."
            ),
            "license": {"name": "GPL-3.0-or-later"},
        },
        "x-capabilities": profile.get("capabilities", {}),
        "methods": methods,
    }
