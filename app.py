
from copy import deepcopy
import math

from flask import Flask, jsonify, request
import requests

OPENFOODFACTS_PRODUCTS = [
    {
        "id": 1,
        "code": "0123456789012",
        "product_name": "Organic Almond Milk",
        "brands": "Silk",
        "ingredients_text": "Filtered water, almonds, cane sugar",
        "quantity": "1 L",
    },
    {
        "id": 2,
        "code": "0987654321098",
        "product_name": "Rolled Oats",
        "brands": "Example Farms",
        "ingredients_text": "Whole grain oats",
        "quantity": "500 g",
    },
    {
        "id": 3,
        "code": "0012345678905",
        "product_name": "Apple Juice",
        "brands": "Fresh Farm",
        "ingredients_text": "Water, apple juice concentrate",
        "quantity": "1 L",
    },
]

OPENFOODFACTS_API_PREFIX = "/openfoodfacts-server/api"
OPENFOODFACTS_API_URL = "https://world.openfoodfacts.org"


def create_app(test_config=None):
    """Create the Flask app and its in-memory product list."""
    app = Flask(__name__)
    app.config["PRODUCTS"] = []
    app.config["OPENFOODFACTS_PRODUCTS"] = deepcopy(OPENFOODFACTS_PRODUCTS)

    if test_config:
        app.config.update(test_config)

    def find_product(product_id):
        for product in app.config["PRODUCTS"]:
            if product["id"] == product_id:
                return product
        return None

    def validate_product(data, is_update=False):
        """Check product fields and return cleaned values or an error."""
        allowed_fields = {
            "name",
            "description",
            "quantity",
            "price",
            "barcode",
            "brand",
            "ingredients",
            "package_size",
        }
        unknown_fields = set(data) - allowed_fields
        if unknown_fields:
            return None, f"Unknown field: {sorted(unknown_fields)[0]}"

        if not is_update and "name" not in data and "barcode" not in data:
            return None, "Provide a product name or barcode."

        cleaned = {}
        if "name" in data:
            if not isinstance(data["name"], str) or not data["name"].strip():
                return None, "Name must be a non-empty string."
            cleaned["name"] = data["name"].strip()

        if "description" in data:
            if not isinstance(data["description"], str):
                return None, "Description must be a string."
            cleaned["description"] = data["description"].strip()

        if "quantity" in data:
            quantity = data["quantity"]
            if not isinstance(quantity, int) or isinstance(quantity, bool) or quantity < 0:
                return None, "Quantity must be a non-negative whole number."
            cleaned["quantity"] = quantity

        if "price" in data:
            price = data["price"]
            if (
                not isinstance(price, (int, float))
                or isinstance(price, bool)
                or not math.isfinite(price)
                or price < 0
            ):
                return None, "Price must be a non-negative number."
            cleaned["price"] = float(price)

        if "barcode" in data:
            barcode = data["barcode"]
            if barcode is not None and not isinstance(barcode, str):
                return None, "Barcode must be a string or null."
            cleaned["barcode"] = barcode.strip() if barcode else None

        for field in ("brand", "ingredients", "package_size"):
            if field in data:
                if not isinstance(data[field], str):
                    return None, f"{field.replace('_', ' ').capitalize()} must be a string."
                cleaned[field] = data[field].strip()

        return cleaned, None

    @app.get("/")
    def home():
        return jsonify({"message": "Inventory API is running."})

    @app.get("/inventory")
    @app.get("/products")
    def get_products():
        return jsonify(app.config["PRODUCTS"])

    @app.post("/inventory")
    @app.post("/products")
    def add_product():
        data = request.get_json(silent=True)
        if not isinstance(data, dict):
            return jsonify({"error": "Send product data as a JSON object."}), 400

        product_data, error = validate_product(data)
        if error:
            return jsonify({"error": error}), 400

        food_details = {}
        if product_data.get("barcode"):
            try:
                food_details = fetch_product_details(
                    barcode=product_data["barcode"]
                )
            except LookupError as error:
                return jsonify({"error": str(error)}), 404
            except requests.RequestException:
                return jsonify({"error": "Could not contact OpenFoodFacts."}), 502
            except ValueError:
                return jsonify({"error": "OpenFoodFacts returned invalid data."}), 502

        name = product_data.get("name") or food_details.get("name")
        if not name:
            return jsonify({"error": "A product name is required."}), 400

        products = app.config["PRODUCTS"]
        next_id = max((product["id"] for product in products), default=0) + 1
        product = {
            "id": next_id,
            "name": name,
            "description": product_data.get("description", ""),
            "quantity": product_data.get("quantity", 0),
            "price": product_data.get("price", 0.0),
            "barcode": product_data.get("barcode") or food_details.get("barcode"),
            "brand": product_data.get("brand") or food_details.get("brand", ""),
            "ingredients": product_data.get("ingredients")
            or food_details.get("ingredients", ""),
            "package_size": product_data.get("package_size")
            or food_details.get("package_size", ""),
        }
        products.append(product)
        return jsonify(product), 201

    @app.get("/inventory/lookup")
    @app.get("/products/lookup")
    def lookup_product():
        barcode = request.args.get("barcode", "").strip()
        name = request.args.get("name", "").strip()

        if bool(barcode) == bool(name):
            return jsonify({"error": "Provide either a barcode or a name."}), 400

        try:
            if barcode:
                product = fetch_product_details(barcode=barcode)
                return jsonify({"product": product})

            products = fetch_product_details(name=name, multiple=True)
            return jsonify({"products": products})
        except LookupError as error:
            return jsonify({"error": str(error)}), 404
        except requests.RequestException:
            return jsonify({"error": "Could not contact OpenFoodFacts."}), 502
        except ValueError:
            return jsonify({"error": "OpenFoodFacts returned invalid data."}), 502

    @app.get(OPENFOODFACTS_API_PREFIX)
    @app.get(f"{OPENFOODFACTS_API_PREFIX}/")
    def openfoodfacts_api_home():
        return jsonify(
            {
                "message": "Local OpenFoodFacts mock API",
                "routes": [
                    f"{OPENFOODFACTS_API_PREFIX}/product/<barcode>",
                    f"{OPENFOODFACTS_API_PREFIX}/search?name=<name>",
                ],
            }
        )

    @app.get(f"{OPENFOODFACTS_API_PREFIX}/product/<barcode>")
    def get_mock_food_product(barcode):
        product = find_food_product_by_barcode(barcode)
        if product is None:
            return jsonify({"status": 0, "error": "Product not found."}), 404
        return jsonify({"status": 1, "product": product})

    @app.get(f"{OPENFOODFACTS_API_PREFIX}/search")
    def search_mock_food_products():
        name = request.args.get("name", "").strip()
        if not name:
            return jsonify({"error": "The name query parameter is required."}), 400
        return jsonify({"products": search_food_products(name)})

    @app.get("/products/<int:product_id>")
    @app.get("/inventory/<int:product_id>")
    def get_product(product_id):
        product = find_product(product_id)
        if product is None:
            return jsonify({"error": "Product not found."}), 404
        return jsonify(product)

    @app.put("/products/<int:product_id>")
    @app.patch("/products/<int:product_id>")
    @app.put("/inventory/<int:product_id>")
    @app.patch("/inventory/<int:product_id>")
    def update_product(product_id):
        product = find_product(product_id)
        if product is None:
            return jsonify({"error": "Product not found."}), 404

        data = request.get_json(silent=True)
        if not isinstance(data, dict) or not data:
            return jsonify({"error": "Send at least one field as a JSON object."}), 400

        product_data, error = validate_product(data, is_update=True)
        if error:
            return jsonify({"error": error}), 400

        product.update(product_data)
        return jsonify(product)

    @app.delete("/products/<int:product_id>")
    @app.delete("/inventory/<int:product_id>")
    def delete_product(product_id):
        product = find_product(product_id)
        if product is None:
            return jsonify({"error": "Product not found."}), 404
        app.config["PRODUCTS"].remove(product)
        return jsonify({"message": "Product deleted."})

    def find_food_product_by_barcode(barcode):
        for product in app.config["OPENFOODFACTS_PRODUCTS"]:
            if product["code"] == barcode:
                return product
        return None

    def search_food_products(name):
        search_text = name.casefold()
        return [
            product
            for product in app.config["OPENFOODFACTS_PRODUCTS"]
            if search_text in product["product_name"].casefold()
            or search_text in product["brands"].casefold()
        ]

    return app


def format_food_product(product):
    """Convert OpenFoodFacts fields into inventory-friendly names."""
    return {
        "barcode": product.get("code"),
        "name": product.get("product_name"),
        "brand": product.get("brands"),
        "ingredients": product.get("ingredients_text"),
        "package_size": product.get("quantity"),
    }


def fetch_product_details(barcode=None, name=None, multiple=False):
    """Fetch product details from OpenFoodFacts using a barcode or name."""
    if bool(barcode) == bool(name):
        raise ValueError("Provide either a barcode or a product name.")

    if barcode:
        response = requests.get(
            f"{OPENFOODFACTS_API_URL}/api/v2/product/{barcode}.json",
            params={"fields": "code,product_name,brands,ingredients_text,quantity"},
            timeout=5,
        )
        response.raise_for_status()
        result = response.json()
        if not isinstance(result, dict):
            raise ValueError("OpenFoodFacts returned invalid data.")
        product = result.get("product") if result.get("status") == 1 else None
        if not isinstance(product, dict):
            raise LookupError("Product not found.")
        return format_food_product(product)

    response = requests.get(
        f"{OPENFOODFACTS_API_URL}/cgi/search.pl",
        params={
            "search_terms": name,
            "search_simple": 1,
            "action": "process",
            "json": 1,
            "page_size": 10,
            "fields": "code,product_name,brands,ingredients_text,quantity",
        },
        timeout=5,
    )
    response.raise_for_status()
    result = response.json()
    if not isinstance(result, dict) or not isinstance(result.get("products"), list):
        raise ValueError("OpenFoodFacts returned invalid data.")

    products = result["products"]
    if not all(isinstance(product, dict) for product in products):
        raise ValueError("OpenFoodFacts returned invalid data.")
    formatted_products = [format_food_product(product) for product in products]
    if multiple:
        return formatted_products
    if not formatted_products:
        raise LookupError("Product not found.")
    return formatted_products[0]


if __name__ == "__main__":
    create_app().run(debug=True)
