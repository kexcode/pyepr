"""
Pydantic request/response models for the EPR Simulator REST API.
"""
from __future__ import annotations
from typing import List, Optional, Any, Dict
from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Nucleus
# ---------------------------------------------------------------------------

class NucleusRequest(BaseModel):
    symbol: str = Field(..., examples=["14N"], description="Isotope symbol, e.g. '14N', '1H', '63Cu'")
    A: float = Field(0.0, description="Isotropic HFI coupling in MHz")
    A_aniso: Optional[List[float]] = Field(None, description="Anisotropic [Axx,Ayy,Azz] in MHz")
    Q: float = Field(0.0, description="Nuclear quadrupole coupling in MHz")
    Q_aniso: Optional[List[float]] = Field(None, description="Anisotropic [Qxx,Qyy,Qzz] in MHz")
    label: Optional[str] = Field(None, description="User label, e.g. 'alpha-H'")


class NucleusResponse(NucleusRequest):
    I: float = Field(..., description="Nuclear spin quantum number (from isotope DB)")
    gn: float = Field(..., description="Nuclear g-value (from isotope DB)")


# ---------------------------------------------------------------------------
# Spin System
# ---------------------------------------------------------------------------

class SpinSystemRequest(BaseModel):
    S: float = Field(0.5, description="Electron spin quantum number")
    g: List[float] = Field([2.0023], description="g-tensor: scalar, [g1,g2,g3], or 9-element flat 3x3")
    D: List[float] = Field([], description="ZFS in MHz: [D], [D,E], or [Dxx,Dyy,Dzz]")
    lw: List[float] = Field([0.3], description="Linewidth in mT: [lG] or [lG, lL]")
    tcorr: Optional[float] = Field(None, description="Rotational correlation time in seconds")


class SpinSystemState(BaseModel):
    S: List[float]
    g: List[float]
    D: List[float]
    lw: List[float]
    tcorr: Optional[float]
    nuclei: List[NucleusResponse]
    hsdim: int
    nElectrons: int
    nNuclei: int


# ---------------------------------------------------------------------------
# Experiment Parameters
# ---------------------------------------------------------------------------

class ExperimentParams(BaseModel):
    mwFreq: float = Field(9.5, description="Microwave frequency in GHz")
    B_min: float = Field(300.0, description="Minimum field in mT")
    B_max: float = Field(400.0, description="Maximum field in mT")
    nPoints: int = Field(1024, description="Number of spectrum points")
    Harmonic: int = Field(1, description="0 = absorption, 1 = first derivative")
    simulator: str = Field("garlic", description="'garlic' or 'pepper'")
    method: str = Field("matrix", description="Simulation model: 'matrix' or 'perturb2'")
    # pepper-specific
    nKnots: int = Field(20, description="Powder averaging knots (pepper only)")
    gridSize: Optional[int] = Field(None, description="Grid size / powder averaging knots (Opt.GridSize)")
    Temperature: Optional[float] = Field(None, description="Sample temperature in Kelvin (Exp.Temperature)")
    singleOrientation: bool = Field(False, description="Whether to simulate single orientation instead of powder")
    orientation: List[float] = Field([0.0, 0.0], description="Orientation angles [theta, phi] in degrees")


class LevelsParams(BaseModel):
    B_min: float = Field(0.0, description="Minimum field in mT")
    B_max: float = Field(400.0, description="Maximum field in mT")
    nPoints: int = Field(200, description="Number of field points")
    method: str = Field("matrix", description="Simulation model: 'matrix' or 'perturb2'")
    mwFreq: Optional[float] = Field(9.5, description="Microwave frequency in GHz for transition calculation")
    orientation: Optional[List[float]] = Field([0.0, 0.0], description="Field direction [theta, phi] in degrees")


# ---------------------------------------------------------------------------
# Responses
# ---------------------------------------------------------------------------

class TransitionInfo(BaseModel):
    B_res: float = Field(..., description="Resonance field in mT")
    E_lower: float = Field(..., description="Energy of lower state in MHz")
    E_upper: float = Field(..., description="Energy of upper state in MHz")
    lower_idx: int = Field(..., description="Index of lower state (0-based)")
    upper_idx: int = Field(..., description="Index of upper state (0-based)")
    intensity: float = Field(..., description="Relative transition probability (0 to 1)")


class SpectrumResponse(BaseModel):
    B: List[float]
    spc: List[float]
    spc_abs: Optional[List[float]] = None
    spc_deriv: Optional[List[float]] = None
    simulator: str
    mwFreq: float
    validation: Dict[str, Any]


class LevelsResponse(BaseModel):
    B: List[float]
    E: List[List[float]]       # shape: [n_states][n_points]
    transitions: List[TransitionInfo] = Field(default_factory=list)
    validation: Dict[str, Any]


class ValidationResponse(BaseModel):
    valid: bool
    messages: List[Dict[str, str]]


class IsotopeInfo(BaseModel):
    symbol: str
    element: str
    nucleons: int
    I: float
    gn: float
    abundance: float
    qm: float
