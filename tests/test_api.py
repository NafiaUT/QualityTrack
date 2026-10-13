"""
tests/test_api.py
-----------------
Tests d integration pour les endpoints de l API FastAPI QualityTrack.
"""

import pytest
from fastapi.testclient import TestClient
from api.main import app


@pytest.fixture(scope="module")
def client():
    return TestClient(app)


def test_api_health(client):
    """Verifie le endpoint de sante /api/v1/health."""
    response = client.get("/api/v1/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert data["app"] == "QualityTrack"


def test_api_list_products(client):
    """Verifie la recuperation de la liste des produits."""
    response = client.get("/api/v1/products")
    assert response.status_code == 200
    products = response.json()
    assert isinstance(products, list)
    assert len(products) >= 2


def test_api_create_invalid_product(client):
    """Verifie qu un produit avec LSL >= USL est refuse (code 400)."""
    payload = {
        "name": "Produit Invalide",
        "unit": "mm",
        "lsl": 25.0,
        "usl": 20.0,  # Erreur : LSL > USL
    }
    response = client.post("/api/v1/products", json=payload)
    assert response.status_code == 400


def test_api_batch_spc_analysis(client):
    """Verifie le calcul SPC complet pour le premier lot."""
    # Recupere les produits puis le premier lot
    products = client.get("/api/v1/products").json()
    product_id = products[0]["id"]

    batches = client.get(f"/api/v1/products/{product_id}/batches").json()
    assert len(batches) > 0
    batch_id = batches[0]["id"]

    # Appel de l endpoint SPC
    response = client.get(f"/api/v1/batches/{batch_id}/spc?subgroup_size=5")
    assert response.status_code == 200
    data = response.json()

    assert "capabilities" in data
    assert "control_charts" in data
    assert "nelson_violations" in data

    cap = data["capabilities"]
    assert "cp" in cap
    assert "cpk" in cap
    assert "is_capable" in cap
    assert cap["cp"] > 0


def test_api_plant_summary(client):
    """Verifie la synthese des indicateurs de l usine."""
    response = client.get("/api/v1/kpi/plant-summary")
    assert response.status_code == 200
    kpi = response.json()

    assert kpi["total_parts"] > 0
    assert 0 <= kpi["first_pass_yield_pct"] <= 100.0
