# Flask Inventory Management API

Created by Lerionka Olentiki

A beginner-friendly inventory manager built with Flask. A command-line client
sends HTTP requests to the API. Inventory is stored in a Python list, so it
resets when the server restarts.

Product details can be looked up through the OpenFoodFacts API by barcode or
name. The project also includes a small local OpenFoodFacts-style mock catalog
for learning and testing; this mock catalog is separate from live lookups.

## Project files

```text
.
├── app.py              # Flask routes, inventory list, and product lookup
├── cli.py              # Interactive command-line client
├── tests/
│   ├── test_app.py     # API and OpenFoodFacts tests
│   └── test_cli.py     # CLI tests
├── Pipfile             # Project dependencies
├── Pipfile.lock        # Locked dependency versions
└── README.md
```

## Installation

Install Python 3.12 and Pipenv, then install the project and test dependencies:

```bash
pipenv install --dev
```

## Run the application

Start the Flask API:

```bash
pipenv run python app.py
```

The API is available at `http://127.0.0.1:5000`. Keep this terminal open.
Open another terminal and start the CLI:

```bash
pipenv run python cli.py
```

To connect the CLI to a different API address:

```bash
pipenv run python cli.py --url http://127.0.0.1:5000
```

The CLI displays a menu. Choose an option by number, then enter the requested
product details or ID:

| Menu option | Action |
| --- | --- |
| `1` | List all inventory items |
| `2` | View one item by its ID |
| `3` | Add an item; enter a name or leave it blank and provide a barcode |
| `4` | Update an item's name, price, or stock quantity |
| `5` | Delete an item by its ID |
| `6` | Look up product details by barcode or name |
| `0` | Exit the CLI |

For example, choose `3`, enter a product name (or leave it blank to use the
barcode), then provide a description, stock quantity, price, and optional
barcode. When a barcode is provided, the API tries to retrieve product details
from OpenFoodFacts. The inventory quantity and price are the values you enter.

## API endpoints

Use `http://127.0.0.1:5000` as the base URL. Routes accept and return JSON where
appropriate.

| Method | Endpoint | Input | Result |
| --- | --- | --- | --- |
| `GET` | `/inventory` | — | List of inventory items |
| `POST` | `/inventory` | JSON product object | Creates an item; returns `201` and the item |
| `GET` | `/inventory/<id>` | Item ID in URL | One item |
| `PATCH` | `/inventory/<id>` | JSON fields to change | Updated item |
| `DELETE` | `/inventory/<id>` | Item ID in URL | Deletion confirmation |
| `GET` | `/inventory/lookup?barcode=<code>` | Barcode query parameter | Matching OpenFoodFacts product details |
| `GET` | `/inventory/lookup?name=<name>` | Name query parameter | Matching OpenFoodFacts product details |

The `/products` routes are compatibility aliases for the corresponding
`/inventory` routes.

### Add an inventory item

Send a `name` or a `barcode`. The other fields are optional; stock quantity
defaults to `0`, price defaults to `0.0`, and descriptive fields default to
empty strings.

```json
{
  "barcode": "0123456789012",
  "description": "Almond milk",
  "quantity": 12,
  "price": 3.99
}
```

The API uses the barcode to fetch the product name, brand, ingredients, and
package size from OpenFoodFacts. You can provide the name directly instead:

```json
{
  "name": "Apples",
  "quantity": 5,
  "price": 1.5
}
```

### Update an inventory item

Send only the fields to change:

```json
{
  "quantity": 8,
  "price": 4.25
}
```

### Response and errors

- `200`: request succeeded.
- `201`: inventory item was created.
- `400`: invalid input, such as missing product name and barcode.
- `404`: inventory item or requested OpenFoodFacts product was not found.
- `502`: OpenFoodFacts could not be reached or returned invalid data.

Inventory changes are held in memory and are lost when the server stops. Live
barcode and name searches require an internet connection.

## Local mock OpenFoodFacts catalog

The mock catalog has sample products in `app.py`, each with an `id`, barcode
`code`, `product_name`, `brands`, `ingredients_text`, and `quantity`. Its
routes return sample data and do not contact the external service or change
inventory:

| Method | Endpoint | Result |
| --- | --- | --- |
| `GET` | `/openfoodfacts-server/api/` | Mock API route information |
| `GET` | `/openfoodfacts-server/api/product/<barcode>` | Mock product by barcode |
| `GET` | `/openfoodfacts-server/api/search?name=<name>` | Mock products by name or brand |

Example:

```text
http://127.0.0.1:5000/openfoodfacts-server/api/product/0123456789012
```

## Tests

Run the full test suite:

```bash
pipenv run pytest
```

Tests use `pytest` and `unittest.mock` to simulate external API responses, so
the automated tests do not need internet access.

## Manual testing with Postman

Start the server, then create Postman requests using
`http://127.0.0.1:5000` as the base URL. For `POST` and `PATCH`, choose
**Body → raw → JSON**:

| Action | Method and URL | Example JSON body |
| --- | --- | --- |
| List items | `GET /inventory` | — |
| Add item | `POST /inventory` | `{"name":"Apples","quantity":5,"price":1.5}` |
| View item | `GET /inventory/1` | — |
| Update item | `PATCH /inventory/1` | `{"quantity":8}` |
| Delete item | `DELETE /inventory/1` | — |
| Look up a barcode | `GET /inventory/lookup?barcode=0123456789012` | — |
| Search by name | `GET /inventory/lookup?name=almond%20milk` | — |

Flask debug mode is enabled by the local `app.py` run command for development.
Do not use the debug server in production.
