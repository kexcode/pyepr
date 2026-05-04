"""
In-memory session state for the EPR Simulator.

For local single-user use this is a global singleton.
For multi-user remote deployment each session should have its own state
(managed via session tokens — future enhancement).
"""
from easyspin_py.core.spin_system import SpinSystem

# Global default spin system — starts as a simple nitroxide-like radical
_spin_system: SpinSystem = SpinSystem(
    S=0.5,
    g=[2.0060, 2.0050, 2.0023],
    lw=[0.3],
)

def get_spin_system() -> SpinSystem:
    return _spin_system

def set_spin_system(sys: SpinSystem):
    global _spin_system
    _spin_system = sys
