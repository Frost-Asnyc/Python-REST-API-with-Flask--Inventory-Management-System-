"""Tests for the command-line API client."""

from unittest.mock import Mock, patch

import requests

import cli
from cli import call_api


@patch("cli.requests.request")
def test_call_api_sends_request_and_prints_response(mock_request, capsys):
    response = Mock()
    response.raise_for_status.return_value = None
    response.content = b'{"message": "ok"}'
    response.json.return_value = {"message": "ok"}
    mock_request.return_value = response

    call_api("GET", "http://localhost:5000/products")

    mock_request.assert_called_once_with(
        "GET", "http://localhost:5000/products", timeout=5
    )
    assert '"message": "ok"' in capsys.readouterr().out


@patch("cli.requests.request")
def test_call_api_explains_when_inventory_is_empty(mock_request, capsys):
    response = Mock()
    response.raise_for_status.return_value = None
    response.content = b"[]\n"
    response.json.return_value = []
    mock_request.return_value = response

    call_api("GET", "http://localhost:5000/inventory")

    assert "Inventory is empty" in capsys.readouterr().out


@patch("cli.requests.request", side_effect=requests.ConnectionError("offline"))
def test_call_api_reports_request_failures(_mock_request, capsys):
    call_api("GET", "http://localhost:5000/inventory")

    assert "API request failed" in capsys.readouterr().out


@patch("cli.requests.request")
def test_call_api_reports_invalid_json(mock_request, capsys):
    response = Mock()
    response.raise_for_status.return_value = None
    response.content = b"not-json"
    response.json.side_effect = ValueError
    mock_request.return_value = response

    call_api("GET", "http://localhost:5000/inventory")

    assert "The API returned invalid JSON." in capsys.readouterr().out


@patch("cli.call_api")
@patch("builtins.input", side_effect=[
    "1",
    "2", "5",
    "3", "", "Almond milk", "3", "2.75", "0123456789012",
    "4", "5", "", "8", "",
    "5", "5",
    "6", "barcode", "0123456789012",
    "0",
])
def test_menu_runs_inventory_commands(mock_input, mock_call_api):
    cli.run_menu("http://localhost:5000")

    assert mock_call_api.call_args_list == [
        (( "GET", "http://localhost:5000/inventory"),),
        (( "GET", "http://localhost:5000/inventory/5"),),
        (
            ("POST", "http://localhost:5000/inventory"),
            {
                "json": {
                    "description": "Almond milk",
                    "quantity": 3,
                    "price": 2.75,
                    "barcode": "0123456789012",
                }
            },
        ),
        (
            ("PATCH", "http://localhost:5000/inventory/5"),
            {"json": {"quantity": 8}},
        ),
        (( "DELETE", "http://localhost:5000/inventory/5"),),
        (
            ("GET", "http://localhost:5000/inventory/lookup"),
            {"params": {"barcode": "0123456789012"}},
        ),
    ]


@patch("cli.call_api")
@patch("builtins.input", side_effect=["", "Almond milk", "3", "2.75", "0123"])
def test_add_product_leaves_blank_name_out_when_using_barcode(
    _mock_input, mock_call_api
):
    cli.add_product("http://localhost:5000/inventory")

    product = mock_call_api.call_args.kwargs["json"]
    assert "name" not in product
    assert product["barcode"] == "0123"


@patch("cli.call_api")
@patch("builtins.input", side_effect=["Apples", "Fresh fruit", "5", "1.25", ""])
def test_add_product_includes_a_provided_name(_mock_input, mock_call_api):
    cli.add_product("http://localhost:5000/inventory")

    assert mock_call_api.call_args.kwargs["json"] == {
        "description": "Fresh fruit",
        "quantity": 5,
        "price": 1.25,
        "barcode": None,
        "name": "Apples",
    }


@patch("cli.call_api")
@patch("builtins.input", side_effect=["name", "almond milk"])
def test_lookup_product_can_search_by_name(_mock_input, mock_call_api):
    cli.lookup_product("http://localhost:5000/inventory")

    mock_call_api.assert_called_once_with(
        "GET",
        "http://localhost:5000/inventory/lookup",
        params={"name": "almond milk"},
    )


@patch("builtins.input", side_effect=["not-a-number", "4"])
def test_read_number_retries_until_input_is_valid(_mock_input, capsys):
    assert cli.read_number("Quantity: ", int) == 4
    assert "Please enter a valid number." in capsys.readouterr().out
