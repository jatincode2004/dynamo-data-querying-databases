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
            str(value)[:10],
            "%Y-%m-%d",
        )
    except ValueError:
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
            candidates.append(
                (
                    effective_from,
                    int(record.get("schema_version", 1)),
                    record,
                )
            )

    if not candidates:
        return None

    candidates.sort(
        key=lambda value: (value[0], value[1]),
        reverse=True,
    )

    return candidates[0][2]


def is_cancelled_line(item, order):
    status = str(
        item.get("status", "")
    ).strip().lower()

    if status == "cancelled":
        return True

    if item.get("cancelled") is True:
        return True

    if item.get("is_cancelled") is True:
        return True

    return (
        str(order.get("status", "")).strip().lower()
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


def test_report_file_exists():
    assert os.path.exists(REPORT_PATH), (
        f"Output file '{REPORT_PATH}' does not exist."
    )


def test_no_extra_json_files():
    for item in os.listdir("/app"):
        if item.endswith(".json") and item != "report.json":
            pytest.fail(
                f"Unauthorized extra JSON file found in /app: {item}"
            )


def test_report_schema_and_types():
    with open(
        REPORT_PATH,
        "r",
        encoding="utf-8",
    ) as f:
        report = json.load(f)

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


def test_report_matches_temporal_reconciliation():
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
            is_cancelled_line(item, order)
            for item in items
        )

        if (
            str(order.get("status", "")).strip().lower()
            == "cancelled"
            or has_cancelled_line
        ):
            cancelled_orders += 1

        customer_records = [
            customer
            for customer in customers
            if entity_id(customer)
            == normalize_id(order.get("customer_id"))
        ]

        customer = applicable_record(
            customer_records,
            order_date,
        )

        if customer:
            customer_id = entity_id(customer)
        else:
            customer_id = normalize_id(
                order.get("customer_id")
            )

        order_spend = 0.0

        for item in items:
            if is_cancelled_line(item, order):
                continue

            product_id = normalize_id(
                item.get("product_id") or item.get("id")
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

        if order_spend > 0 and customer_id:
            active_customers.add(customer_id)

            customer_spend[customer_id] = (
                customer_spend.get(customer_id, 0.0)
                + order_spend
            )

    report = json.load(
        open(
            REPORT_PATH,
            "r",
            encoding="utf-8",
        )
    )

    assert report["total_revenue"] == pytest.approx(
        round(total_revenue, 2),
        abs=1e-6,
    )

    assert report["active_customers"] == len(
        active_customers
    )

    assert report["cancelled_orders"] == cancelled_orders

    if customer_spend:
        best_customer = sorted(
            customer_spend.items(),
            key=lambda pair: (
                -round(pair[1], 2),
                pair[0],
            ),
        )[0]

        assert (
            report["top_customer"]["customer_id"]
            == best_customer[0]
        )

        assert report["top_customer"]["total_spend"] == pytest.approx(
            round(best_customer[1], 2),
            abs=1e-6,
        )

    if product_quantities:
        best_product = sorted(
            product_quantities.items(),
            key=lambda pair: (
                -pair[1],
                pair[0],
            ),
        )[0]

        assert (
            report["top_product"]["product_id"]
            == best_product[0]
        )

        assert (
            report["top_product"]["quantity_sold"]
            == best_product[1]
        )

    expected_categories = {
        category: round(revenue, 2)
        for category, revenue in category_revenue.items()
        if round(revenue, 2) > 0
    }

    assert report["category_revenue"] == expected_categories
