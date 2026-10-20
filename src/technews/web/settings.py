"""Read and write the few config.yaml values the web app exposes, keeping the file's comments."""

from __future__ import annotations

import copy
import os
from pathlib import Path
from typing import Any

from ruamel.yaml import YAML
from ruamel.yaml.comments import CommentedMap, CommentedSeq
from ruamel.yaml.representer import RoundTripRepresenter
from ruamel.yaml.scalarstring import DoubleQuotedScalarString

from ..config import CONFIG_DIR, AppConfig, load_config


class _Representer(RoundTripRepresenter):
    """Writes ``null`` as null (ruamel leaves the value blank), so untouched keys read as they did."""


_Representer.add_representer(type(None), lambda r, _: r.represent_scalar("tag:yaml.org,2002:null", "null"))

# Dotted config paths the settings page may change.
EDITABLE = {
    "render.style",
    "render.captions.enabled",
    "voice.voice",
    "voice.speed",
    "llm.tasks.script.provider",
    "llm.tasks.script.model",
    "llm.tasks.script.effort",
    "brand.name",
    "news.feeds",
    "news.hacker_news.enabled",
}


def config_path() -> Path:
    return Path(os.environ.get("TECHNEWS_CONFIG", CONFIG_DIR / "config.yaml"))


def _plain(node: Any) -> Any:
    if isinstance(node, dict):
        return {k: _plain(v) for k, v in node.items()}
    if isinstance(node, list):
        return [_plain(v) for v in node]
    return node


def _node(value: Any, old: Any) -> Any:
    """Lists of mappings (feeds) go in one line per item like the hand-written file, keeping the blank line after."""
    if not isinstance(value, list) or not all(isinstance(v, dict) for v in value):
        return value
    items = []
    for v in value:
        item = CommentedMap({k: DoubleQuotedScalarString(x) if isinstance(x, str) and "://" in x else x for k, x in v.items()})
        item.fa.set_flow_style()
        items.append(item)
    seq = old if isinstance(old, CommentedSeq) else CommentedSeq()  # refilled in place: its trailing blank line stays
    seq.clear()
    seq.extend(items)
    return seq


def update_config(changes: dict[str, Any]) -> AppConfig:
    """Apply ``{"voice.speed": 1.1, ...}`` to config.yaml. Validates the result before writing."""
    unknown = set(changes) - EDITABLE
    if unknown:
        raise ValueError(f"Not editable here: {', '.join(sorted(unknown))}")
    path = config_path()
    yaml = YAML()
    yaml.Representer = _Representer
    yaml.preserve_quotes = True
    yaml.indent(mapping=2, sequence=4, offset=2)  # "  feeds:\n    - {...}", as config.example.yaml writes lists
    yaml.width = 4096  # never re-wrap long strings
    newline = "\r\n" if path.exists() and b"\r\n" in path.read_bytes() else "\n"
    data = (yaml.load(path.read_text(encoding="utf-8")) if path.exists() else None) or CommentedMap()
    for dotted, value in changes.items():
        node = data
        *parents, leaf = dotted.split(".")
        for key in parents:
            if not isinstance(node.get(key), dict):
                node[key] = CommentedMap()
            node = node[key]
        if value is None:
            node.pop(leaf, None)
        else:
            node[leaf] = _node(value, node.get(leaf))
    cfg = AppConfig.model_validate(copy.deepcopy(_plain(data)))  # raises on a bad value; nothing written
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".yaml.tmp")
    with tmp.open("w", encoding="utf-8", newline=newline) as fh:
        yaml.dump(data, fh)
    tmp.replace(path)
    load_config.cache_clear()
    return cfg
