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


def test_inventory_routes_accept_products_aliases():
    client = make_client()

    created = client.post("/products", json={"name": "Pears"})

    assert created.status_code == 201
    assert client.get("/products").json == client.get("/inventory").json
    assert client.get("/products/1").json["name"] == "Pears"


def test_home_route_reports_api_status():
    response = make_client().get("/")

    assert response.status_code == 200
    assert response.json == {"message": "Inventory API is running."}


def test_create_rejects_non_object_json_and_unknown_fields():
    client = make_client()

    non_object = client.post("/inventory", json=["Apples"])
    unknown_field = client.post(
        "/inventory", json={"name": "Apples", "stock": 2}
    )

    assert non_object.status_code == 400
    assert unknown_field.status_code == 400
    assert client.get("/inventory").json == []


def test_create_validates_optional_product_field_types():
    invalid_products = [
        {"name": ""},
        {"name": "Apples", "description": 1},
        {"name": "Apples", "quantity": True},
        {"name": "Apples", "quantity": 1.5},
        {"name": "Apples", "price": True},
        {"name": "Apples", "price": float("nan")},
        {"name": "Apples", "barcode": 123},
        {"name": "Apples", "brand": None},
        {"name": "Apples", "ingredients": 1},
        {"name": "Apples", "package_size": 1},
    ]

    for product in invalid_products:
        response = make_client().post("/inventory", json=product)
        assert response.status_code == 400, product


def test_get_missing_product_returns_404():
    client = make_client()

    response = client.get("/inventory/99")

    assert response.status_code == 404
    assert response.json["error"] == "Product not found."


def test_update_supports_put_and_rejects_empty_or_invalid_updates():
    client = make_client()
    client.post("/inventory", json={"name": "Apples", "quantity": 3})

    updated = client.put("/inventory/1", json={"name": "Green apples"})
    empty = client.patch("/inventory/1", json={})
    invalid = client.patch("/inventory/1", json={"price": -1})
    missing = client.put("/inventory/99", json={"name": "Missing"})

    assert updated.status_code == 200
    assert updated.json["name"] == "Green apples"
    assert updated.json["quantity"] == 3
    assert empty.status_code == 400
    assert invalid.status_code == 400
    assert missing.status_code == 404


def test_delete_missing_product_returns_404():
    response = make_client().delete("/inventory/99")

    assert response.status_code == 404


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


@patch("app.requests.get")
def test_create_with_name_does_not_call_external_api(mock_get):
    client = make_client()

    response = client.post("/inventory", json={"name": "Apples"})

    assert response.status_code == 201
    mock_get.assert_not_called()


@patch("app.requests.get")
def test_create_with_unknown_barcode_returns_404_without_creating_product(mock_get):
    mock_get.return_value = mock_response({"status": 0})
    client = make_client()

    response = client.post(
        "/inventory", json={"barcode": "12345", "quantity": 2}
    )

    assert response.status_code == 404
    assert client.get("/inventory").json == []


@patch("app.requests.get")
def test_lookup_returns_404_when_barcode_is_not_found(mock_get):
    mock_get.return_value = mock_response({"status": 0})

    response = make_client().get("/inventory/lookup?barcode=12345")

    assert response.status_code == 404


@patch("app.requests.get")
def test_lookup_returns_502_when_external_data_is_invalid(mock_get):
    mock_get.return_value = mock_response([])

    response = make_client().get("/inventory/lookup?barcode=12345")

    assert response.status_code == 502


@patch("app.requests.get")
def test_name_lookup_returns_empty_list_when_no_products_match(mock_get):
    mock_get.return_value = mock_response({"products": []})

    response = make_client().get("/inventory/lookup?name=not-found")

    assert response.status_code == 200
    assert response.json == {"products": []}


def test_lookup_needs_either_barcode_or_name():
    client = make_client()

    response = client.get("/inventory/lookup")

    assert response.status_code == 400


def test_lookup_rejects_both_barcode_and_name():
    response = make_client().get(
        "/inventory/lookup?barcode=12345&name=apples"
    )

    assert response.status_code == 400


def test_namespaced_home_route_lists_mock_api_routes():
    response = make_client().get("/openfoodfacts-server/api/")

    assert response.status_code == 200
    assert response.json["routes"] == [
        "/openfoodfacts-server/api/product/<barcode>",
        "/openfoodfacts-server/api/search?name=<name>",
    ]


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


def test_namespaced_barcode_route_returns_404_for_unknown_product():
    response = make_client().get(
        "/openfoodfacts-server/api/product/9999999999999"
    )

    assert response.status_code == 404
    assert response.json["status"] == 0


def test_namespaced_search_route_finds_products_by_name():
    client = make_client()

    response = client.get(
        "/openfoodfacts-server/api/search?name=almond"
    )

    assert response.status_code == 200
    assert len(response.json["products"]) == 1
    assert response.json["products"][0]["product_name"] == "Organic Almond Milk"


def test_namespaced_search_matches_brands_without_case_sensitivity():
    response = make_client().get(
        "/openfoodfacts-server/api/search?name=sIlK"
    )

    assert response.status_code == 200
    assert response.json["products"][0]["brands"] == "Silk"


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


@patch("app.requests.get", side_effect=requests.Timeout)
def test_name_lookup_reports_openfoodfacts_connection_errors(_mock_get):
    response = make_client().get("/inventory/lookup?name=apples")

    assert response.status_code == 502
