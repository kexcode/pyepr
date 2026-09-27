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
        "nPoints": 50
    }
    response = client.post("/api/simulate/levels", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert len(data["B"]) == 50
    assert len(data["E"]) > 0
