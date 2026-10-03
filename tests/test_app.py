"""Tests for the inventory API and its OpenFoodFacts integration."""

from unittest.mock import Mock, patch

import requests

from app import create_app


def make_client():
    app = create_app({"TESTING": True, "PRODUCTS": []})
    return app.test_client()


def test_create_list_update_and_delete_product():
    client = make_client()
    new_product = {
        "name": "Apples",
        "description": "Green apples",
        "quantity": 12,
        "price": 1.5,
    }

    created = client.post("/inventory", json=new_product)
    assert created.status_code == 201
    assert created.json["id"] == 1
    assert created.json["name"] == "Apples"

    product_list = client.get("/inventory")
    assert product_list.status_code == 200
    assert len(product_list.json) == 1

    updated = client.patch("/inventory/1", json={"quantity": 8})
    assert updated.status_code == 200
    assert updated.json["quantity"] == 8

    deleted = client.delete("/inventory/1")
    assert deleted.status_code == 200
    assert client.get("/inventory/1").status_code == 404


def test_create_requires_a_name_and_valid_quantity():
    client = make_client()

    missing_name = client.post("/inventory", json={"quantity": 2})
    bad_quantity = client.post("/inventory", json={"name": "Pears", "quantity": -1})

    assert missing_name.status_code == 400
    assert bad_quantity.status_code == 400


def test_get_missing_product_returns_404():
    client = make_client()

    response = client.get("/inventory/99")

    assert response.status_code == 404
    assert response.json["error"] == "Product not found."


def mock_response(result):
    response = Mock()
    response.raise_for_status.return_value = None
    response.json.return_value = result
    return response


@patch("app.requests.get")
def test_lookup_by_barcode_uses_openfoodfacts(mock_get):
    client = make_client()
    mock_get.return_value = mock_response(
        {
            "status": 1,
            "product": {
                "code": "0012345678905",
                "product_name": "Apple Juice",
                "brands": "Fresh Farm",
                "ingredients_text": "Water and apples",
                "quantity": "1 L",
            },
        }
    )

    response = client.get("/inventory/lookup?barcode=0012345678905")

    assert response.status_code == 200
    assert response.json["product"]["name"] == "Apple Juice"
    assert response.json["product"]["barcode"] == "0012345678905"
    assert response.json["product"]["ingredients"] == "Water and apples"
    assert mock_get.call_args.kwargs["timeout"] == 5


@patch("app.requests.get")
def test_lookup_by_name_uses_openfoodfacts(mock_get):
    client = make_client()
    mock_get.return_value = mock_response(
        {
            "products": [
                {
                    "code": "0012345678905",
                    "product_name": "Apple Juice",
                    "brands": "Fresh Farm",
                    "ingredients_text": "Water and apples",
                    "quantity": "1 L",
                }
            ]
        }
    )

    response = client.get("/inventory/lookup?name=apple%20juice")

    assert response.status_code == 200
    assert response.json["products"][0]["brand"] == "Fresh Farm"
    assert response.json["products"][0]["barcode"] == "0012345678905"
    assert mock_get.call_args.kwargs["params"]["search_terms"] == "apple juice"


@patch("app.requests.get")
def test_add_inventory_item_enriches_from_barcode(mock_get):
    client = make_client()
    mock_get.return_value = mock_response(
        {
            "status": 1,
            "product": {
                "code": "0123456789012",
                "product_name": "Organic Almond Milk",
                "brands": "Silk",
                "ingredients_text": "Water, almonds",
                "quantity": "1 L",
            },
        }
    )

    response = client.post(
        "/inventory",
        json={"barcode": "0123456789012", "quantity": 4, "price": 3.5},
    )

    assert response.status_code == 201
    assert response.json["name"] == "Organic Almond Milk"
    assert response.json["brand"] == "Silk"
    assert response.json["ingredients"] == "Water, almonds"
    assert response.json["package_size"] == "1 L"
    assert response.json["quantity"] == 4


@patch("app.requests.get", side_effect=requests.Timeout)
def test_add_inventory_item_reports_external_api_failure(_mock_get):
    client = make_client()

    response = client.post(
        "/inventory",
        json={"barcode": "0123456789012", "quantity": 4, "price": 3.5},
    )

    assert response.status_code == 502
    assert client.get("/inventory").json == []


def test_lookup_needs_either_barcode_or_name():
    client = make_client()

    response = client.get("/inventory/lookup")

    assert response.status_code == 400


def test_namespaced_barcode_route_returns_mock_openfoodfacts_data():
    client = make_client()

    response = client.get(
        "/openfoodfacts-server/api/product/0123456789012"
    )

    assert response.status_code == 200
    assert response.json["status"] == 1
    assert response.json["product"]["product_name"] == "Organic Almond Milk"
    assert response.json["product"]["brands"] == "Silk"
    assert "id" in response.json["product"]


def test_namespaced_search_route_finds_products_by_name():
    client = make_client()

    response = client.get(
        "/openfoodfacts-server/api/search?name=almond"
    )

    assert response.status_code == 200
    assert len(response.json["products"]) == 1
    assert response.json["products"][0]["product_name"] == "Organic Almond Milk"


def test_namespaced_search_requires_a_name():
    client = make_client()

    response = client.get("/openfoodfacts-server/api/search")

    assert response.status_code == 400


def test_mock_food_lookup_does_not_add_to_inventory():
    client = make_client()

    client.get("/openfoodfacts-server/api/product/0123456789012")

    assert client.get("/inventory").json == []


@patch("app.requests.get", side_effect=requests.Timeout)
def test_lookup_reports_openfoodfacts_connection_errors(_mock_get):
    client = make_client()

    response = client.get("/inventory/lookup?barcode=12345")

    assert response.status_code == 502
