"""Contract gate between the desktop settings registry and DaxConfig."""

from __future__ import annotations

import json
from collections.abc import Mapping
from pathlib import Path
from typing import get_origin

from pydantic import BaseModel

from dax.core.config import DaxConfig

ROOT = Path(__file__).parents[2]
REGISTRY = ROOT / "desktop/src/screens/settings/registry.json"


def _model_leaves(model: type[BaseModel], prefix: str = "") -> set[str]:
    leaves: set[str] = set()
    for name, field in model.model_fields.items():
        key = f"{prefix}.{name}" if prefix else name
        annotation = field.annotation
        if isinstance(annotation, type) and issubclass(annotation, BaseModel):
            leaves.update(_model_leaves(annotation, key))
        elif get_origin(annotation) is dict or get_origin(annotation) is Mapping:
            # Dynamic map entries are managed by a custom collection editor.
            leaves.add(key)
        else:
            leaves.add(key)
    return leaves


def test_registry_covers_every_dax_config_leaf() -> None:
    data = json.loads(REGISTRY.read_text(encoding="utf-8"))
    registry_keys = {
        field["key"]
        for section in data["sections"]
        for group in section["groups"]
        for field in group["fields"]
        if "key" in field
    }

    expected = _model_leaves(DaxConfig)
    assert registry_keys == expected, (
        f"Missing from settings: {sorted(expected - registry_keys)}; "
        f"unknown registry keys: {sorted(registry_keys - expected)}"
    )
