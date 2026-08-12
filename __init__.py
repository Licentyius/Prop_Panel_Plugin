"""
Prop Studio & Stage Wing Expansion Tool
Official decoupled standalone workspace environment suite for MakeHuman 2.
"""
__version__ = "2.0.0"
__author__ = "Elvaerwyn_MH2"

import sys
import os

# FORCE LOCAL PACKAGE OVERRIDES PRIOR TO INTERPRETER INTERCEPT
# Explicitly steps over the dynamic background checker to lock in your local module namespaces
_root = os.path.dirname(os.path.abspath(__file__))
if _root not in sys.path:
    sys.path.insert(0, _root)

from .gui.prop_module import initialize_prop_studio

def initialize_extension(app_reference, glob_reference):
    """
    Fires automatically when the extension loader hooks the plugin checkbox.
    Routes system variables safely through verified local package directories.
    """
    print("[Prop Studio Core] Executing native decoupled plugin initialization sequence...")
    return initialize_prop_studio(app_reference, glob_reference)

__all__ = [
    "initialize_prop_studio",
    "initialize_extension",
    "__version__",
    "__author__"
]
