"""
Precompute spectra and energy levels for all pyEPR presets.
Outputs:
  - app/static/preset_cache.json (for frontend instant loading)
  - app/preset_cache.json (for backend cache lookup)
"""

import sys
import os
import time
import json
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from easyspin_py.core.spin_system import SpinSystem, Nucleus
from easyspin_py.simulation.garlic import garlic
from easyspin_py.simulation.pepper import pepper
from easyspin_py.simulation.levels import levels


PRESETS = [
    {
        "name": "Free electron",
        "S": 0.5, "g": [2.0023, 2.0023, 2.0023], "D": [], "lw": [0.3, 0.0],
        "nuclei": [],
        "simulator": "garlic", "method": "matrix", "gridSize": 23,
        "exp": {"mwFreq": 9.4, "Bmin": 330.0, "Bmax": 340.0, "nPoints": 501, "temperature": None},
        "levels": {"Bmin": 0.0, "Bmax": 340.0, "nPoints": 200},
    },
    {
        "name": "1 Proton",
        "S": 0.5, "g": [2.0029, 2.0029, 2.0029], "D": [], "lw": [1.0, 0.0],
        "nuclei": [
            {"symbol": "1H", "A": 1430.0, "A_aniso": [1430.0, 1430.0, 1430.0], "Q": 0.0}
        ],
        "simulator": "garlic", "method": "perturb2", "gridSize": 23,
        "exp": {"mwFreq": 9.4, "Bmin": 200.0, "Bmax": 450.0, "nPoints": 5001, "temperature": None},
        "levels": {"Bmin": 0.0, "Bmax": 450.0, "nPoints": 200},
    },
    {
        "name": "2 Protons",
        "S": 0.5, "g": [2.0029, 2.0029, 2.0029], "D": [], "lw": [1.0, 0.0],
        "nuclei": [
            {"symbol": "1H", "A": 1430.0, "A_aniso": [1430.0, 1430.0, 1430.0], "Q": 0.0},
            {"symbol": "1H", "A": 1430.0, "A_aniso": [1430.0, 1430.0, 1430.0], "Q": 0.0}
        ],
        "simulator": "garlic", "method": "matrix", "gridSize": 23,
        "exp": {"mwFreq": 9.4, "Bmin": 200.0, "Bmax": 450.0, "nPoints": 5001, "temperature": None},
        "levels": {"Bmin": 0.0, "Bmax": 450.0, "nPoints": 200},
    },
    {
        "name": "Nitroxide radical",
        "S": 0.5, "g": [2.0083, 2.0061, 2.0022], "D": [], "lw": [0.5, 0.0],
        "nuclei": [
            {"symbol": "14N", "A": 38.27, "A_aniso": [11.2, 11.2, 92.4], "Q": 0.0}
        ],
        "simulator": "pepper", "method": "perturb2", "gridSize": 23,
        "exp": {"mwFreq": 9.4, "Bmin": 328.0, "Bmax": 342.0, "nPoints": 501, "temperature": None},
        "levels": {"Bmin": 0.0, "Bmax": 342.0, "nPoints": 200},
    },
    {
        "name": "Methyl radical",
        "S": 0.5, "g": [2.0026, 2.0026, 2.0026], "D": [], "lw": [0.2, 0.0],
        "nuclei": [
            {"symbol": "1H", "A": -70.0, "A_aniso": [-70.0, -70.0, -70.0], "Q": 0.0},
            {"symbol": "1H", "A": -70.0, "A_aniso": [-70.0, -70.0, -70.0], "Q": 0.0},
            {"symbol": "1H", "A": -70.0, "A_aniso": [-70.0, -70.0, -70.0], "Q": 0.0},
            {"symbol": "13C", "A": 105.0, "A_aniso": [105.0, 105.0, 105.0], "Q": 0.0},
        ],
        "simulator": "garlic", "method": "perturb2", "gridSize": 23,
        "exp": {"mwFreq": 9.4, "Bmin": 325.0, "Bmax": 345.0, "nPoints": 501, "temperature": None},
        "levels": {"Bmin": 0.0, "Bmax": 345.0, "nPoints": 200},
    },
    {
        "name": "Spin triplet",
        "S": 1.0, "g": [2.0000, 2.0000, 2.0000], "D": [4496.88, 749.48], "lw": [10.0, 0.0],
        "nuclei": [],
        "simulator": "pepper", "method": "matrix", "gridSize": 23,
        "exp": {"mwFreq": 9.4, "Bmin": 0.0, "Bmax": 600.0, "nPoints": 2501, "temperature": None},
        "levels": {"Bmin": 0.0, "Bmax": 600.0, "nPoints": 200},
    },
    {
        "name": "Triplet nitrene",
        "S": 1.0, "g": [2.0033, 2.0033, 2.0033], "D": [41041.59, 2788.07], "lw": [30.0, 0.0],
        "nuclei": [],
        "simulator": "pepper", "method": "matrix", "gridSize": 193,
        "exp": {"mwFreq": 94.0, "Bmin": 0.0, "Bmax": 6000.0, "nPoints": 5001, "temperature": None},
        "levels": {"Bmin": 0.0, "Bmax": 6000.0, "nPoints": 200},
    },
    {
        "name": "Triplet carbene",
        "S": 1.0, "g": [2.0033, 2.0033, 2.0033], "D": [12258.51, 2788.07], "lw": [10.0, 0.0],
        "nuclei": [],
        "simulator": "pepper", "method": "matrix", "gridSize": 193,
        "exp": {"mwFreq": 9.4, "Bmin": 0.0, "Bmax": 1400.0, "nPoints": 5001, "temperature": None},
        "levels": {"Bmin": 0.0, "Bmax": 1400.0, "nPoints": 200},
    },
    {
        "name": "Mn(III) ion",
        "S": 2.0, "g": [2.0000, 2.0000, 2.0000], "D": [-119317.40, 0.0], "lw": [80.0, 0.0],
        "nuclei": [],
        "simulator": "pepper", "method": "matrix", "gridSize": 193,
        "exp": {"mwFreq": 240.0, "Bmin": 0.0, "Bmax": 12000.0, "nPoints": 2501, "temperature": 5.0},
        "levels": {"Bmin": 0.0, "Bmax": 12000.0, "nPoints": 200},
    },
    {
        "name": "Fe(III) ion",
        "S": 2.5, "g": [2.0000, 2.0000, 2.0000], "D": [149896.23, 0.0], "lw": [20.0, 0.0],
        "nuclei": [],
        "simulator": "pepper", "method": "matrix", "gridSize": 193,
        "exp": {"mwFreq": 9.4, "Bmin": 0.0, "Bmax": 400.0, "nPoints": 2501, "temperature": 5.0},
        "levels": {"Bmin": 0.0, "Bmax": 400.0, "nPoints": 200},
    }
]


def precompute_all():
    cache = {}
    total_t0 = time.time()
    print(f"Starting precomputation for {len(PRESETS)} presets...")

    for idx, p in enumerate(PRESETS):
        t0 = time.time()
        print(f"\n[{idx + 1}/{len(PRESETS)}] Computing '{p['name']}' ({p['simulator']}, method={p['method']}, gridSize={p['gridSize']})...")

        # Build spin system
        sys_obj = SpinSystem(
            S=p["S"],
            g=p["g"],
            D=p["D"],
            lw=p["lw"]
        )
        for n in p["nuclei"]:
            sys_obj.add_nucleus(
                symbol=n["symbol"],
                A=n["A"],
                A_aniso=n["A_aniso"],
                Q=n.get("Q", 0.0),
                Q_aniso=n.get("Q_aniso", [0.0, 0.0, 0.0])
            )

        # Simulation options
        exp_dict = {
            "mwFreq": p["exp"]["mwFreq"],
            "Range": [p["exp"]["Bmin"], p["exp"]["Bmax"]],
            "nPoints": p["exp"]["nPoints"],
            "Harmonic": 1,
            "method": p["method"],
            "Temperature": p["exp"]["temperature"]
        }
        opt_dict = {
            "nKnots": p["gridSize"],
            "GridSize": p["gridSize"],
            "method": p["method"],
            "return_both": True
        }

        # 1. Run Spectrum
        if p["simulator"] == "garlic":
            B, spc_abs, spc_deriv = garlic(sys_obj, exp_dict, opt_dict)
        else:
            B, spc_abs, spc_deriv = pepper(sys_obj, exp_dict, opt_dict)

        spc = spc_deriv  # Default harmonic is 1 (derivative)

        # 2. Run Levels
        E, B_lvl, transitions = levels(
            sys_obj,
            [p["levels"]["Bmin"], p["levels"]["Bmax"]],
            n_points=p["levels"]["nPoints"],
            method=p["method"],
            mw_freq_GHz=p["exp"]["mwFreq"],
            return_transitions=True
        )

        dt = round(time.time() - t0, 2)
        print(f"  -> Done in {dt}s. Spectrum points: {len(B)}, Levels shape: {E.shape}, Transitions: {len(transitions)}")

        cache[str(idx)] = {
            "name": p["name"],
            "gridSize": p["gridSize"],
            "spectrum": {
                "B": np.round(B, 4).tolist(),
                "spc": np.round(spc, 6).tolist(),
                "spc_abs": np.round(spc_abs, 6).tolist(),
                "spc_deriv": np.round(spc_deriv, 6).tolist(),
                "simulator": p["simulator"],
                "mwFreq": p["exp"]["mwFreq"],
                "Harmonic": 1,
                "validation": {"messages": [], "has_errors": False, "has_warnings": False}
            },
            "levels": {
                "B": np.round(B_lvl, 4).tolist(),
                "E": np.round(E, 6).tolist(),
                "transitions": transitions,
                "validation": {"messages": [], "has_errors": False, "has_warnings": False}
            }
        }

    total_time = round(time.time() - total_t0, 2)
    print(f"\nAll presets computed in {total_time}s!")

    # Write output files
    out_static = os.path.join("app", "static", "preset_cache.json")
    out_backend = os.path.join("app", "preset_cache.json")

    json_str = json.dumps(cache, separators=(',', ':'))
    with open(out_static, "w", encoding="utf-8") as f:
        f.write(json_str)
    print(f"Saved {out_static} ({round(len(json_str)/1024, 1)} KB)")

    with open(out_backend, "w", encoding="utf-8") as f:
        f.write(json_str)
    print(f"Saved {out_backend} ({round(len(json_str)/1024, 1)} KB)")


if __name__ == "__main__":
    precompute_all()
