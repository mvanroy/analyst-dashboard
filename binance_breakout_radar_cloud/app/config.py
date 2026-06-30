from __future__ import annotations

from copy import deepcopy
from pathlib import Path
from typing import Any

try:
    import yaml
except ModuleNotFoundError:  # Local smoke tests can run before dependencies are installed.
    yaml = None


def load_config(path: str | Path = "config/balanced.yml") -> dict[str, Any]:
    path = Path(path)
    data = _read_yaml(path)
    parent = data.pop("extends", None)
    if parent:
        base = load_config(parent)
        return _deep_merge(base, data)
    return data


def _read_yaml(path: Path) -> dict[str, Any]:
    with path.open("r") as f:
        text = f.read()
    if yaml is not None:
        return yaml.safe_load(text) or {}
    return _read_simple_yaml(text)


def _deep_merge(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
    merged = deepcopy(base)
    for key, value in override.items():
        if isinstance(value, dict) and isinstance(merged.get(key), dict):
            merged[key] = _deep_merge(merged[key], value)
        else:
            merged[key] = value
    return merged


def score_points(config: dict[str, Any]) -> dict[str, float]:
    return config.get("scores", {"strong": 100, "moderate": 75, "weak": 50, "negative": 0})


def _read_simple_yaml(text: str) -> dict[str, Any]:
    root: dict[str, Any] = {}
    stack: list[tuple[int, Any]] = [(-1, root)]
    pending_key: tuple[int, dict[str, Any], str] | None = None
    for raw_line in text.splitlines():
        if not raw_line.strip() or raw_line.lstrip().startswith("#"):
            continue
        indent = len(raw_line) - len(raw_line.lstrip(" "))
        line = raw_line.strip()
        while stack and indent <= stack[-1][0]:
            stack.pop()
        parent = stack[-1][1]
        if line.startswith("- "):
            value = _coerce(line[2:].strip())
            if not isinstance(parent, list):
                if pending_key is None:
                    continue
                _, dict_parent, key = pending_key
                parent = []
                dict_parent[key] = parent
                stack.append((indent - 2, parent))
            parent.append(value)
            continue
        key, value = line.split(":", 1)
        key = key.strip()
        value = value.strip()
        if value == "":
            child: dict[str, Any] = {}
            parent[key] = child
            pending_key = (indent, parent, key)
            stack.append((indent, child))
        else:
            parent[key] = _coerce(value)
            pending_key = (indent, parent, key)
    return root


def _coerce(value: str) -> Any:
    if value.lower() == "true":
        return True
    if value.lower() == "false":
        return False
    if value.lower() in {"null", "none"}:
        return None
    try:
        if "." in value:
            return float(value)
        return int(value)
    except ValueError:
        return value.strip('"').strip("'")
