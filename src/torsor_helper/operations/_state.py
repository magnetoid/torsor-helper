"""Where non-derivable state lives. Delegates to store.state_file, which also
migrates a file written before .torsor/state/ existed and keeps it git-ignored."""
from __future__ import annotations

from torsor_helper import store as _store_mod


def _state_file(store, name: str):
    return _store_mod.state_file(store.paths, name)

def _coach_state_path(store):
    return _state_file(store, "coach_state.json")
