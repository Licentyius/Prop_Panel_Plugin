"""
Core structural logic initialization for the Prop Studio engine. Elvaerwyn_MH2 2026
Cleaned
"""

from .prop import PropMesh
from .emitter_prop import MH2LiveEmitterProp
from .json_io import save_prop_changes_to_json

__all__ = [
    "PropMesh",
    "MH2LiveEmitterProp",
    "save_prop_changes_to_json"
]
