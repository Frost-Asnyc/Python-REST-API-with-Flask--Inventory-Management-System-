"""A beginner-friendly command-line client for the Inventory API."""

import argparse
import json

import requests


DEFAULT_API_URL = "http://127.0.0.1:5000"


def call_api(method, url, **kwargs):
    """Send one request and show either the JSON result or an error."""
    try:
        response = requests.request(method, url, timeout=5, **kwargs)
        response.raise_for_status()
        if response.content:
            print(json.dumps(response.json(), indent=2))
    except requests.RequestException as error:
        print(f"API request failed: {error}")
    except ValueError:
        print("The API returned invalid JSON.")


def run_menu(api_url):
    """Show the menu until the user chooses to quit."""
    products_url = f"{api_url}/inventory"

    while True:
        print(
            "\nInventory Menu\n"
            "1. List products\n"
            "2. View one product\n"
            "3. Add a product\n"
            "4. Update a product\n"
            "5. Delete a product\n"
            "6. Find product details online\n"
            "0. Quit"
        )
        choice = input("Choose an option: ").strip()

        if choice == "1":
            call_api("GET", products_url)
        elif choice == "2":
            product_id = input("Product ID: ").strip()
            call_api("GET", f"{products_url}/{product_id}")
        elif choice == "3":
            add_product(products_url)
        elif choice == "4":
            update_product(products_url)
        elif choice == "5":
            product_id = input("Product ID: ").strip()
            call_api("DELETE", f"{products_url}/{product_id}")
        elif choice == "6":
            lookup_product(products_url)
        elif choice == "0":
            print("Goodbye!")
            break
        else:
            print("Please choose one of the menu options.")


def add_product(products_url):
    name = input("Name (or leave blank and enter a barcode): ").strip()
    product = {
        "description": input("Description: ").strip(),
        "quantity": read_number("Quantity: ", int),
        "price": read_number("Price: ", float),
        "barcode": input("Barcode (optional): ").strip() or None,
    }
    if name:
        product["name"] = name
    call_api("POST", products_url, json=product)


def update_product(products_url):
    product_id = input("Product ID: ").strip()
    name = input("New name (leave blank to keep current): ").strip()
    quantity = input("New quantity (leave blank to keep current): ").strip()
    price = input("New price (leave blank to keep current): ").strip()

    changes = {}
    if name:
        changes["name"] = name
    if quantity:
        try:
            changes["quantity"] = int(quantity)
        except ValueError:
            print("Quantity must be a whole number.")
            return
    if price:
        try:
            changes["price"] = float(price)
        except ValueError:
            print("Price must be a number.")
            return

    if not changes:
        print("No changes entered.")
        return
    call_api("PATCH", f"{products_url}/{product_id}", json=changes)


def lookup_product(products_url):
    search_type = input("Search by barcode or name? ").strip().lower()
    if search_type == "barcode":
        value = input("Barcode: ").strip()
        params = {"barcode": value}
    elif search_type == "name":
        value = input("Product name: ").strip()
        params = {"name": value}
    else:
        print("Enter 'barcode' or 'name'.")
        return

    call_api("GET", f"{products_url}/lookup", params=params)


def read_number(prompt, number_type):
    """Ask until a valid integer or decimal number is entered."""
    while True:
        try:
            return number_type(input(prompt).strip())
        except ValueError:
            print("Please enter a valid number.")


def main():
    parser = argparse.ArgumentParser(description="Manage products in the Inventory API.")
    parser.add_argument("--url", default=DEFAULT_API_URL, help="Base URL for the API.")
    args = parser.parse_args()
    run_menu(args.url.rstrip("/"))


if __name__ == "__main__":
    main()
