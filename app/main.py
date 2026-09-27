"""
FastAPI application — EPR Simulator REST API.

Endpoints
---------
GET  /                          Serve the SPA (index.html)
GET  /api/system                Get current spin system state
PUT  /api/system                Update electron spin parameters
POST /api/system/nuclei         Add a nucleus
DELETE /api/system/nuclei/{idx} Remove nucleus by index
GET  /api/isotopes              List all available isotopes
GET  /api/validate/{simulator}  Validate system for a simulator
POST /api/simulate/spectrum     Run garlic() or pepper()
POST /api/simulate/levels       Run levels()
"""

from __future__ import annotations

import sys
import os
import numpy as np

# Ensure the project root is on the path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from fastapi import FastAPI, HTTPException, Path
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

from easyspin_py.core.spin_system import SpinSystem
from easyspin_py.core.isotopes import IsotopeDatabase
from easyspin_py.simulation.garlic import garlic
from easyspin_py.simulation.pepper import pepper
from easyspin_py.simulation.levels import levels
from easyspin_py.simulation.validator import (
    validate_garlic, validate_pepper, validate_levels
)

from app.models import (
    SpinSystemRequest, SpinSystemState, NucleusRequest, NucleusResponse,
    ExperimentParams, LevelsParams, SpectrumResponse, LevelsResponse,
    ValidationResponse, IsotopeInfo,
)
from app.state import get_spin_system, set_spin_system

# ---------------------------------------------------------------------------
# App
# ---------------------------------------------------------------------------

app = FastAPI(
    title="EPR Simulator",
    description="Python port of EasySpin EPR simulation functions",
    version="0.1.0",
)

# Serve static files
STATIC_DIR = os.path.join(os.path.dirname(__file__), "static")
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_isotope_db = IsotopeDatabase()


def _sys_to_state(sys: SpinSystem) -> SpinSystemState:
    return SpinSystemState(
        S=sys.S.tolist(),
        g=sys.g.tolist(),
        D=sys.D.tolist(),
        lw=sys.lw.tolist(),
        tcorr=sys.tcorr,
        nuclei=[
            NucleusResponse(
                symbol=n.symbol,
                A=n.A,
                A_aniso=n.A_aniso,
                Q=n.Q,
                label=n.label,
                I=n.I,
                gn=n.gn,
            )
            for n in sys.nuclei
        ],
        hsdim=sys.hsdim(),
        nElectrons=sys.nElectrons,
        nNuclei=sys.nNuclei,
    )


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@app.get("/", include_in_schema=False)
def serve_spa():
    return FileResponse(os.path.join(STATIC_DIR, "index.html"))


# --- Spin System ---

@app.get("/api/system", response_model=SpinSystemState, tags=["Spin System"])
def get_system():
    """Return the current spin system state."""
    return _sys_to_state(get_spin_system())


@app.put("/api/system", response_model=SpinSystemState, tags=["Spin System"])
def update_system(req: SpinSystemRequest):
    """Update electron spin parameters (S, g, D, lw). Nuclei are preserved."""
    sys = get_spin_system()
    sys.S = np.atleast_1d(np.array([req.S], dtype=float))
    sys.g = np.atleast_1d(np.array(req.g, dtype=float))
    sys.D = np.atleast_1d(np.array(req.D, dtype=float))
    sys.lw = np.atleast_1d(np.array(req.lw, dtype=float))
    sys.tcorr = req.tcorr
    return _sys_to_state(sys)


# --- Nuclei ---

@app.post("/api/system/nuclei", response_model=SpinSystemState, tags=["Nuclei"])
def add_nucleus(req: NucleusRequest):
    """Add a nucleus to the spin system."""
    sys = get_spin_system()
    try:
        sys.add_nucleus(
            symbol=req.symbol,
            A=req.A,
            A_aniso=req.A_aniso,
            Q=req.Q,
            label=req.label,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return _sys_to_state(sys)


@app.delete("/api/system/nuclei/{idx}", response_model=SpinSystemState, tags=["Nuclei"])
def remove_nucleus(idx: int = Path(..., ge=0)):
    """Remove nucleus at index idx (0-based)."""
    sys = get_spin_system()
    try:
        sys.remove_nucleus(idx)
    except IndexError as e:
        raise HTTPException(status_code=404, detail=str(e))
    return _sys_to_state(sys)


@app.delete("/api/system/nuclei", response_model=SpinSystemState, tags=["Nuclei"])
def clear_nuclei():
    """Remove all nuclei from the spin system."""
    sys = get_spin_system()
    sys.clear_nuclei()
    return _sys_to_state(sys)


# --- Isotope database ---

@app.get("/api/isotopes", response_model=list[IsotopeInfo], tags=["Database"])
def list_isotopes(element: str | None = None):
    """List all isotopes in the database, optionally filtered by element symbol."""
    results = []
    for sym, iso in _isotope_db.isotopes.items():
        if element and iso.element.lower() != element.lower():
            continue
        results.append(IsotopeInfo(
            symbol=sym,
            element=iso.element,
            nucleons=iso.nucleons,
            I=iso.spin,
            gn=iso.gn,
            abundance=iso.abundance,
            qm=iso.qm,
        ))
    results.sort(key=lambda x: (x.element, x.nucleons))
    return results


# --- Validation ---

@app.get("/api/validate/{simulator}", response_model=ValidationResponse, tags=["Validation"])
def validate(simulator: str):
    """Validate the current spin system for a given simulator."""
    sys = get_spin_system()
    validators = {
        "garlic": validate_garlic,
        "pepper": validate_pepper,
        "levels": validate_levels,
    }
    if simulator not in validators:
        raise HTTPException(status_code=400, detail=f"Unknown simulator '{simulator}'")
    result = validators[simulator](sys)
    return ValidationResponse(**result.to_dict())


# --- Simulation ---

@app.post("/api/simulate/spectrum", response_model=SpectrumResponse, tags=["Simulation"])
def simulate_spectrum(params: ExperimentParams):
    """Run garlic() or pepper() and return the spectrum."""
    sys = get_spin_system()
    exp = {
        "mwFreq": params.mwFreq,
        "Range": [params.B_min, params.B_max],
        "nPoints": params.nPoints,
        "Harmonic": params.Harmonic,
    }
    opt = {"nKnots": params.nKnots}

    # Run validation first (collect messages without stopping)
    if params.simulator == "garlic":
        val_result = validate_garlic(sys)
    else:
        val_result = validate_pepper(sys)

    if val_result.has_errors:
        raise HTTPException(status_code=422, detail=val_result.to_dict())

    try:
        import warnings
        with warnings.catch_warnings(record=True):
            warnings.simplefilter("always")
            if params.simulator == "garlic":
                B, spc = garlic(sys, exp)
            else:
                B, spc = pepper(sys, exp, opt)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

    return SpectrumResponse(
        B=B.tolist(),
        spc=spc.tolist(),
        simulator=params.simulator,
        mwFreq=params.mwFreq,
        validation=val_result.to_dict(),
    )


@app.post("/api/simulate/levels", response_model=LevelsResponse, tags=["Simulation"])
def simulate_levels(params: LevelsParams):
    """Run levels() and return energy level data."""
    sys = get_spin_system()
    val_result = validate_levels(sys)

    if val_result.has_errors:
        raise HTTPException(status_code=422, detail=val_result.to_dict())

    try:
        E, B = levels(sys, [params.B_min, params.B_max], n_points=params.nPoints)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

    return LevelsResponse(
        B=B.tolist(),
        E=E.tolist(),
        validation=val_result.to_dict(),
    )
