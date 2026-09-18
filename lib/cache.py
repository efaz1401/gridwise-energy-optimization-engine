"""Per-note memo so repeats and paraphrase drills cost nothing."""
from __future__ import annotations

import hashlib
from collections import OrderedDict
from typing import Any

_MAX = 2048
_store: "OrderedDict[str, dict[str, Any]]" = OrderedDict()


def key(note: str, capacity: float) -> str:
    return hashlib.sha256(f"{note.strip()}|{capacity}".encode()).hexdigest()


def get(k: str) -> dict[str, Any] | None:
    if k in _store:
        _store.move_to_end(k)
        return dict(_store[k])
    return None


def put(k: str, entry: dict[str, Any]) -> None:
    _store[k] = {x: y for x, y in entry.items() if x != "note_index"}
    _store.move_to_end(k)
    while len(_store) > _MAX:
        _store.popitem(last=False)


def size() -> int:
    return len(_store)
