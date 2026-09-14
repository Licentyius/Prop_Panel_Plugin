######
## Multi-Prop V2.1 Module Bridge Tracker(zombie atm)
## Part of the MakeHuman 2 Project contributed by Elvaerwyn_MH2 2026
######
from .prop_manager import MultiPropManager

# FIXED: Standard class bridge routes the old JSON-manifest imports 
# straight into the now working MultiPropManager pipeline seamlessly!
class Multi_Prop(MultiPropManager):
    """
    Decoupled interface bridge redirects legacy file allocations 
    straight to the active master MultiPropManager wrapper.
    """
    def __init__(self, shaders, glob):
        super().__init__(shaders, glob)
        print("[Prop Studio Core] Legacy multi_prop class bridge initialized successfully.")
