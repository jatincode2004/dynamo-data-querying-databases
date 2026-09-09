import json
import os
from datetime import datetime

import pytest

REPORT_PATH = "/app/report.json"
DATA_DIR = "/app/data"


def normalize_id(value):
    if value is None:
        return ""
    return str(value).strip().upper()


def parse_date(value):
    if not value:
        return datetime.min

    try:
        return datetime.strptime(
            str(value).strip()[:10],
            "%Y-%m-%d",
        )
    except (TypeError, ValueError):
        return datetime.min


def entity_id(record):
    for field in ("customer_id", "product_id", "id"):
        value = record.get(field)
        if value is not None and str(value).strip():
            return normalize_id(value)
    return ""


def applicable_record(records, target_date):
    candidates = []

    for record in records:
        effective_from = parse_date(
            record.get("effective_from", "1900-01-01")
        )

        if effective_from <= target_date:
            try:
                version = int(record.get("schema_version", 1))
            except (TypeError, ValueError):
                version = 1

            candidates.append(
                (effective_from, version, record)
            )

    if not candidates:
        return None

    candidates.sort(
        key=lambda x: (x[0], x[1]),
        reverse=True,
    )

    return candidates[0][2]

def reconcile_orders(orders):
    """Retain only the highest schema_version per logical order ID."""
    retained = {}

    for order in orders:
        order_id = normalize_id(
            order.get("order_id") or order.get("id")
        )

        if not order_id:
            continue

        try:
            version = int(order.get("schema_version", 1))
        except (TypeError, ValueError):
            version = 1

        current = retained.get(order_id)

        if current is None or version > current[0]:
            retained[order_id] = (version, order)

    return [order for _, order in retained.values()]
def is_cancelled_line(item):
    return (
        str(item.get("line_status", ""))
        .strip()
        .lower()
        == "cancelled"
    )


def discount_value(item):
    for field in (
        "discount",
        "discount_amount",
        "line_discount",
    ):
        value = item.get(field)

        if value is None or value == "":
            continue

        try:
            return float(value)
        except (TypeError, ValueError):
            return 0.0

    return 0.0


def compute_expected_metrics():
    """Recompute all six requested report metrics from the source collections."""

    with open(
        os.path.join(DATA_DIR, "customers.json"),
        "r",
        encoding="utf-8",
    ) as f:
        customers = json.load(f)

    with open(
        os.path.join(DATA_DIR, "products.json"),
        "r",
        encoding="utf-8",
    ) as f:
        products = json.load(f)

    with open(
        os.path.join(DATA_DIR, "orders.json"),
        "r",
        encoding="utf-8",
    ) as f:
        orders = json.load(f)

    orders = reconcile_orders(orders)

    total_revenue = 0.0
    cancelled_orders = 0
    active_customers = set()
    customer_spend = {}
    product_quantities = {}
    category_revenue = {}

    for order in orders:
        order_date = parse_date(
            order.get("order_date")
        )

        items = order.get("items", [])

        if not isinstance(items, list):
            items = []

        has_cancelled_line = any(
            is_cancelled_line(item)
            for item in items
        )

        if has_cancelled_line:
            cancelled_orders += 1

        order_customer_id = normalize_id(
            order.get("customer_id")
        )

        customer_records = [
            customer
            for customer in customers
            if entity_id(customer) == order_customer_id
        ]

        customer = applicable_record(
            customer_records,
            order_date,
        )

        if customer is not None:
            customer_id = entity_id(customer)
        else:
            customer_id = order_customer_id

        order_spend = 0.0
        has_active_line = False

        for item in items:
            if is_cancelled_line(item):
                continue

            has_active_line = True

            product_id = normalize_id(
                item.get("product_id")
                or item.get("id")
            )

            quantity = int(
                item.get("quantity", 0)
            )

            unit_price = float(
                item.get("unit_price", 0.0)
            )

            discount = discount_value(item)

            line_revenue = max(
                0.0,
                quantity * unit_price - discount,
            )

            order_spend += line_revenue

            if product_id:
                product_quantities[product_id] = (
                    product_quantities.get(product_id, 0)
                    + quantity
                )

            product_records = [
                product
                for product in products
                if entity_id(product) == product_id
            ]

            product = applicable_record(
                product_records,
                order_date,
            )

            if product is None:
                category = "Uncategorized"
            else:
                raw_category = product.get("category")

                if (
                    raw_category is None
                    or not str(raw_category).strip()
                ):
                    category = "Uncategorized"
                else:
                    category = str(
                        raw_category
                    ).strip()

            category_revenue[category] = (
                category_revenue.get(category, 0.0)
                + line_revenue
            )

        total_revenue += order_spend

        if has_active_line and customer_id:
            active_customers.add(customer_id)

            customer_spend[customer_id] = (
                customer_spend.get(customer_id, 0.0)
                + order_spend
            )

    best_customer = sorted(
        customer_spend.items(),
        key=lambda x: (
            -round(x[1], 2),
            x[0],
        ),
    )[0]

    best_product = sorted(
        product_quantities.items(),
        key=lambda x: (
            -x[1],
            x[0],
        ),
    )[0]

    expected_categories = {
        category: round(revenue, 2)
        for category, revenue in category_revenue.items()
        if round(revenue, 2) > 0
    }

    return {
        "total_revenue": round(total_revenue, 2),
        "active_customers": len(active_customers),
        "cancelled_orders": cancelled_orders,
        "top_customer": {
            "customer_id": best_customer[0],
            "total_spend": round(best_customer[1], 2),
        },
        "top_product": {
            "product_id": best_product[0],
            "quantity_sold": best_product[1],
        },
        "category_revenue": expected_categories,
    }


def load_report():
    """Load the generated report for the individual metric tests."""

    with open(
        REPORT_PATH,
        "r",
        encoding="utf-8",
    ) as f:
        return json.load(f)


def test_report_file_exists():
    """Verify that the required report.json artifact is produced."""

    assert os.path.exists(REPORT_PATH)


def test_no_extra_json_files():
    """Verify that no unauthorized JSON artifacts are created in /app."""

    for item in os.listdir("/app"):
        if item.endswith(".json") and item != "report.json":
            pytest.fail(
                f"Unauthorized extra JSON file found in /app: {item}"
            )


def test_report_schema_and_types():
    """Verify the required report fields, nested fields, and value types."""

    report = load_report()

    expected_keys = {
        "total_revenue",
        "active_customers",
        "cancelled_orders",
        "top_customer",
        "top_product",
        "category_revenue",
    }

    assert set(report.keys()) == expected_keys

    assert isinstance(
        report["total_revenue"],
        (int, float),
    )

    assert isinstance(
        report["active_customers"],
        int,
    )

    assert isinstance(
        report["cancelled_orders"],
        int,
    )

    assert isinstance(
        report["top_customer"],
        dict,
    )

    assert isinstance(
        report["top_product"],
        dict,
    )

    assert isinstance(
        report["category_revenue"],
        dict,
    )

    assert set(report["top_customer"].keys()) == {
        "customer_id",
        "total_spend",
    }

    assert set(report["top_product"].keys()) == {
        "product_id",
        "quantity_sold",
    }

    assert isinstance(
        report["top_customer"]["customer_id"],
        str,
    )

    assert isinstance(
        report["top_customer"]["total_spend"],
        (int, float),
    )

    assert isinstance(
        report["top_product"]["product_id"],
        str,
    )

    assert isinstance(
        report["top_product"]["quantity_sold"],
        int,
    )


def test_total_revenue():
    """Verify total_revenue matches the independently reconciled active-line revenue."""

    report = load_report()
    expected = compute_expected_metrics()

    assert report["total_revenue"] == pytest.approx(
        expected["total_revenue"],
        abs=1e-2,
    )


def test_active_customers():
    """Verify active_customers counts customers with at least one active order line."""

    report = load_report()
    expected = compute_expected_metrics()

    assert report["active_customers"] == (
        expected["active_customers"]
    )


def test_cancelled_orders():
    """Verify cancelled_orders counts orders containing at least one cancelled line."""

    report = load_report()
    expected = compute_expected_metrics()

    assert report["cancelled_orders"] == (
        expected["cancelled_orders"]
    )


def test_top_customer():
    """Verify top_customer ID and spend using reconciled customer totals and tie-breaking."""

    report = load_report()
    expected = compute_expected_metrics()

    assert report["top_customer"]["customer_id"] == (
        expected["top_customer"]["customer_id"]
    )

    assert report["top_customer"]["total_spend"] == (
        pytest.approx(
            expected["top_customer"]["total_spend"],
            abs=1e-2,
        )
    )


def test_top_product():
    """Verify top_product ID and quantity using active product quantities and tie-breaking."""

    report = load_report()
    expected = compute_expected_metrics()

    assert report["top_product"]["product_id"] == (
        expected["top_product"]["product_id"]
    )

    assert report["top_product"]["quantity_sold"] == (
        expected["top_product"]["quantity_sold"]
    )


def test_category_revenue():
    """Verify category_revenue matches independently reconciled active-line category totals."""

    report = load_report()
    expected = compute_expected_metrics()

    assert report["category_revenue"] == (
        expected["category_revenue"]
    )
