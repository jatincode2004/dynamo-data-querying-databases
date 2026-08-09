import json
import os

import pytest


REPORT_PATH = "/app/report.json"
DATA_DIR = "/app/data"


def normalize_id(value):
    return str(value or "").strip().upper()


def latest_versions(records, id_fields):
    selected = {}

    for record in records:
        raw_id = ""

        for field in id_fields:
            if record.get(field):
                raw_id = record[field]
                break

        entity_id = normalize_id(raw_id)

        if not entity_id:
            continue

        version = int(record.get("schema_version", 1))

        if (
            entity_id not in selected
            or version > int(selected[entity_id].get("schema_version", 1))
        ):
            selected[entity_id] = record

    return selected


def load_data():
    with open(os.path.join(DATA_DIR, "customers.json"), encoding="utf-8") as f:
        customers = json.load(f)

    with open(os.path.join(DATA_DIR, "products.json"), encoding="utf-8") as f:
        products = json.load(f)

    with open(os.path.join(DATA_DIR, "orders.json"), encoding="utf-8") as f:
        orders = json.load(f)

    return customers, products, orders


def test_report_file_exists():
    """The required report artifact must be created."""
    assert os.path.exists(REPORT_PATH)


def test_no_extra_json_files():
    """The application root may contain only report.json as an output JSON file."""
    for item in os.listdir("/app"):
        if item.endswith(".json") and item != "report.json":
            pytest.fail(f"Unauthorized extra JSON file found: {item}")


def test_report_schema_and_types():
    """The report must contain exactly the documented schema and JSON types."""
    with open(REPORT_PATH, encoding="utf-8") as f:
        report = json.load(f)

    expected = {
        "total_revenue",
        "active_customers",
        "cancelled_orders",
        "top_customer",
        "top_product",
        "category_revenue",
    }

    assert set(report) == expected

    assert isinstance(report["total_revenue"], (int, float))
    assert isinstance(report["active_customers"], int)
    assert isinstance(report["cancelled_orders"], int)

    assert set(report["top_customer"]) == {
        "customer_id",
        "total_spend",
    }

    assert set(report["top_product"]) == {
        "product_id",
        "quantity_sold",
    }

    assert isinstance(report["top_customer"]["customer_id"], str)
    assert isinstance(report["top_customer"]["total_spend"], (int, float))
    assert isinstance(report["top_product"]["product_id"], str)
    assert isinstance(report["top_product"]["quantity_sold"], int)
    assert isinstance(report["category_revenue"], dict)


def test_report_matches_independent_reconciliation():
    """Recompute all metrics after version reconciliation and line-level filtering."""
    customers, products, orders = load_data()

    customer_map = latest_versions(customers, ["customer_id", "id"])
    product_map = latest_versions(products, ["product_id", "id"])
    order_map = latest_versions(orders, ["order_id", "id"])

    # Ensure versioned logical entities are actually being reconciled.
    assert len(customer_map) < len(customers)
    assert len(product_map) < len(products)
    assert len(order_map) < len(orders)

    product_categories = {}

    for pid, product in product_map.items():
        category = product.get("category")

        if category is None or not str(category).strip():
            category = "Uncategorized"
        else:
            category = str(category).strip()

        product_categories[pid] = category

    total_revenue = 0.0
    cancelled_orders = 0
    active_customers = set()

    customer_spend = {}
    product_quantities = {}
    category_revenue = {}

    for order in order_map.values():
        customer_id = normalize_id(order.get("customer_id"))
        has_cancelled_line = False

        for item in order.get("items", []):
            status = str(
                item.get("line_status", "active")
            ).strip().lower()

            if status == "cancelled":
                has_cancelled_line = True
                continue

            quantity = int(item.get("quantity", 0))
            unit_price = float(item.get("unit_price", 0.0))
            discount = float(item.get("discount", 0.0))

            net = max(
                0.0,
                quantity * unit_price - discount
            )

            if customer_id:
                active_customers.add(customer_id)
                customer_spend[customer_id] = (
                    customer_spend.get(customer_id, 0.0) + net
                )

            product_id = normalize_id(item.get("product_id"))

            if product_id:
                product_quantities[product_id] = (
                    product_quantities.get(product_id, 0) + quantity
                )

            category = product_categories.get(
                product_id,
                "Uncategorized"
            )

            category_revenue[category] = (
                category_revenue.get(category, 0.0) + net
            )

            total_revenue += net

        if has_cancelled_line:
            cancelled_orders += 1

    top_customer_id = min(
        customer_spend,
        key=lambda cid: (-round(customer_spend[cid], 2), cid)
    )

    top_product_id = min(
        product_quantities,
        key=lambda pid: (-product_quantities[pid], pid)
    )

    with open(REPORT_PATH, encoding="utf-8") as f:
        report = json.load(f)

    assert report["total_revenue"] == pytest.approx(
        round(total_revenue, 2),
        abs=1e-6,
    )

    assert report["active_customers"] == len(active_customers)

    assert report["cancelled_orders"] == cancelled_orders

    assert report["top_customer"]["customer_id"] == top_customer_id

    assert report["top_customer"]["total_spend"] == pytest.approx(
        round(customer_spend[top_customer_id], 2),
        abs=1e-6,
    )

    assert report["top_product"]["product_id"] == top_product_id

    assert report["top_product"]["quantity_sold"] == (
        product_quantities[top_product_id]
    )

    expected_categories = {
        category: round(value, 2)
        for category, value in category_revenue.items()
        if round(value, 2) > 0
    }

    assert report["category_revenue"] == expected_categories
