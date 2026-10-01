import pytest
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)

def test_spa_root():
    response = client.get("/")
    assert response.status_code == 200
    assert "html" in response.headers.get("content-type", "").lower()

def test_get_spin_system():
    response = client.get("/api/system")
    assert response.status_code == 200
    data = response.json()
    assert "S" in data
    assert "g" in data
    assert "nuclei" in data

def test_update_spin_system():
    payload = {
        "S": 0.5,
        "g": [2.005, 2.005, 2.002],
        "D": [],
        "lw": [0.4],
        "tcorr": None
    }
    response = client.put("/api/system", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["S"] == [0.5]
    assert data["lw"] == [0.4]

def test_nuclei_lifecycle():
    # Clear nuclei first
    client.delete("/api/system/nuclei")

    # Add 14N
    add_resp = client.post("/api/system/nuclei", json={"symbol": "14N", "A": 35.0, "Q": 0.0})
    assert add_resp.status_code == 200
    data = add_resp.json()
    assert len(data["nuclei"]) == 1
    assert data["nuclei"][0]["symbol"] == "14N"

    # Add 1H
    add_resp2 = client.post("/api/system/nuclei", json={"symbol": "1H", "A": 12.0})
    assert add_resp2.status_code == 200
    data2 = add_resp2.json()
    assert len(data2["nuclei"]) == 2

    # Remove 1H (index 1)
    del_resp = client.delete("/api/system/nuclei/1")
    assert del_resp.status_code == 200
    data3 = del_resp.json()
    assert len(data3["nuclei"]) == 1
    assert data3["nuclei"][0]["symbol"] == "14N"

def test_get_isotopes():
    response = client.get("/api/isotopes")
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)
    assert any(iso["symbol"] == "14N" for iso in data)

def test_validate_simulator():
    resp_garlic = client.get("/api/validate/garlic")
    assert resp_garlic.status_code == 200
    assert "valid" in resp_garlic.json()

    resp_pepper = client.get("/api/validate/pepper")
    assert resp_pepper.status_code == 200
    assert "valid" in resp_pepper.json()

def test_simulate_spectrum():
    payload = {
        "simulator": "garlic",
        "mwFreq": 9.5,
        "B_min": 330.0,
        "B_max": 345.0,
        "nPoints": 256,
        "Harmonic": 0,
        "nKnots": 10
    }
    response = client.post("/api/simulate/spectrum", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert len(data["B"]) == 256
    assert len(data["spc"]) == 256

def test_simulate_levels():
    payload = {
        "B_min": 0.0,
        "B_max": 350.0,
        "nPoints": 50,
        "method": "matrix",
        "mwFreq": 9.5
    }
    response = client.post("/api/simulate/levels", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert len(data["B"]) == 50
    assert len(data["E"]) > 0
    assert "transitions" in data
    # At 9.5 GHz and 0-350 mT for free electron / standard system, transition is present
    if len(data["transitions"]) > 0:
        t = data["transitions"][0]
        assert "B_res" in t
        assert "E_lower" in t
        assert "E_upper" in t
        assert "intensity" in t
        assert 0.0 <= t["intensity"] <= 1.0


def test_simulation_methods():
    for method in ["matrix", "perturb1", "perturb2"]:
        # Spectrum
        spc_resp = client.post("/api/simulate/spectrum", json={
            "simulator": "garlic",
            "mwFreq": 9.5,
            "B_min": 330.0,
            "B_max": 345.0,
            "nPoints": 128,
            "Harmonic": 0,
            "method": method
        })
        assert spc_resp.status_code == 200, f"Method {method} failed for spectrum"
        assert len(spc_resp.json()["spc"]) == 128

        # Levels
        lvl_resp = client.post("/api/simulate/levels", json={
            "B_min": 0.0,
            "B_max": 400.0,
            "nPoints": 50,
            "method": method,
            "mwFreq": 9.5
        })
        assert lvl_resp.status_code == 200, f"Method {method} failed for levels"
        assert len(lvl_resp.json()["E"]) > 0


def test_orientation_simulation_api():
    # Test pepper single orientation via API
    resp = client.post("/api/simulate/spectrum", json={
        "simulator": "pepper",
        "mwFreq": 9.5,
        "B_min": 300.0,
        "B_max": 350.0,
        "nPoints": 128,
        "Harmonic": 1,
        "method": "matrix",
        "singleOrientation": True,
        "orientation": [90.0, 0.0]
    })
    assert resp.status_code == 200
    data = resp.json()
    assert len(data["spc"]) == 128

    # Test levels with orientation via API
    lvl_resp = client.post("/api/simulate/levels", json={
        "B_min": 0.0,
        "B_max": 400.0,
        "nPoints": 50,
        "method": "matrix",
        "mwFreq": 9.5,
        "orientation": [90.0, 90.0]
    })
    assert lvl_resp.status_code == 200
    lvl_data = lvl_resp.json()
    assert len(lvl_data["E"]) > 0
    assert "transitions" in lvl_data


def test_nucleus_tensor_update_and_perturb2_api():
    # Reset system
    client.put("/api/system", json={
        "S": 0.5,
        "g": [2.0083, 2.0061, 2.0022],
        "D": [],
        "lw": [0.5],
        "tcorr": None
    })
    client.delete("/api/system/nuclei")

    # Add 14N
    add_resp = client.post("/api/system/nuclei", json={
        "symbol": "14N",
        "A": 38.27,
        "A_aniso": [11.2, 11.2, 92.4],
        "Q": 0.0,
        "Q_aniso": [0.0, 0.0, 0.0]
    })
    assert add_resp.status_code == 200
    nucs = add_resp.json()["nuclei"]
    assert len(nucs) == 1
    assert nucs[0]["A_aniso"] == [11.2, 11.2, 92.4]

    # Update via PUT /api/system/nuclei/0
    put_resp = client.put("/api/system/nuclei/0", json={
        "symbol": "14N",
        "A": 38.27,
        "A_aniso": [11.5, 11.5, 93.0],
        "Q": 1.0,
        "Q_aniso": [-0.5, -0.5, 1.0]
    })
    assert put_resp.status_code == 200
    updated_nucs = put_resp.json()["nuclei"]
    assert updated_nucs[0]["A_aniso"] == [11.5, 11.5, 93.0]
    assert updated_nucs[0]["Q_aniso"] == [-0.5, -0.5, 1.0]

    # Run pepper with perturb2 method
    sim_resp = client.post("/api/simulate/spectrum", json={
        "simulator": "pepper",
        "mwFreq": 9.4,
        "B_min": 328.0,
        "B_max": 342.0,
        "nPoints": 256,
        "Harmonic": 1,
        "method": "perturb2",
        "singleOrientation": False
    })
    assert sim_resp.status_code == 200
    sim_data = sim_resp.json()
    assert len(sim_data["spc"]) == 256
    assert "spc_abs" in sim_data and sim_data["spc_abs"] is not None
    assert "spc_deriv" in sim_data and sim_data["spc_deriv"] is not None
    assert len(sim_data["spc_abs"]) == 256
    assert len(sim_data["spc_deriv"]) == 256
    import numpy as np
    assert np.max(np.abs(sim_data["spc"])) > 0, "Perturbation theory produced zero spectrum"
    assert np.max(np.abs(sim_data["spc_abs"])) > 0, "Absorption spectrum is zero"
    assert np.max(np.abs(sim_data["spc_deriv"])) > 0, "Derivative spectrum is zero"


def test_garlic_dual_harmonic_simulation():
    # Test garlic returns both spc_abs and spc_deriv simultaneously
    resp = client.post("/api/simulate/spectrum", json={
        "simulator": "garlic",
        "mwFreq": 9.5,
        "B_min": 330.0,
        "B_max": 345.0,
        "nPoints": 501,
        "Harmonic": 1,
        "method": "matrix"
    })
    assert resp.status_code == 200
    data = resp.json()
    assert len(data["B"]) == 501
    assert len(data["spc"]) == 501
    assert len(data["spc_abs"]) == 501
    assert len(data["spc_deriv"]) == 501
    import numpy as np
    assert np.max(np.abs(data["spc_abs"])) > 0
    assert np.max(np.abs(data["spc_deriv"])) > 0


def test_preset_cache_content():
    import json
    import os

    cache_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "app", "static", "preset_cache.json")
    assert os.path.exists(cache_path), "preset_cache.json must exist"

    with open(cache_path, "r", encoding="utf-8") as f:
        cache = json.load(f)

    assert len(cache) == 10
    for idx in range(10):
        key = str(idx)
        assert key in cache, f"Preset {idx} missing from cache"
        item = cache[key]
        assert "spectrum" in item and "levels" in item
        assert len(item["spectrum"]["B"]) > 0
        assert len(item["levels"]["B"]) > 0
        assert len(item["levels"]["E"]) > 0

    # Ensure last 4 presets have gridSize 193
    for idx in [6, 7, 8, 9]:
        assert cache[str(idx)]["gridSize"] == 193, f"Preset {idx} should have gridSize 193"

    # Verify static route serves the file
    resp = client.get("/static/preset_cache.json")
    assert resp.status_code == 200
    assert "application/json" in resp.headers.get("content-type", "")




