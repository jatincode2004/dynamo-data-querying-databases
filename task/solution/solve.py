#!/usr/bin/env python3

import json
import os
from datetime import datetime

DATA_DIR = "/app/data"
OUTPUT_PATH = "/app/report.json"


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


def get_entity_id(record):
    for field in ("customer_id", "product_id", "id"):
        value = record.get(field)

        if value is not None and str(value).strip():
            return normalize_id(value)

    return ""


def applicable_record(records, entity_id, target_date):
    entity_id = normalize_id(entity_id)

    candidates = []

    for record in records:
        if get_entity_id(record) != entity_id:
            continue

        effective_from = parse_date(
            record.get("effective_from", "1900-01-01")
        )

        if effective_from <= target_date:
            try:
                schema_version = int(
                    record.get("schema_version", 1)
                )
            except (TypeError, ValueError):
                schema_version = 1

            candidates.append(
                (
                    effective_from,
                    schema_version,
                    record,
                )
            )

    if not candidates:
        return None

    candidates.sort(
        key=lambda x: (x[0], x[1]),
        reverse=True,
    )

    return candidates[0][2]


def is_cancelled_line(item):
    line_status = str(
        item.get("line_status", "")
    ).strip().lower()

    return line_status == "cancelled"


def get_discount(item):
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


def main():
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
            if get_entity_id(customer)
            == order_customer_id
        ]

        customer = applicable_record(
            customer_records,
            order_customer_id,
            order_date,
        )

        if customer is not None:
            customer_id = get_entity_id(customer)
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

            try:
                quantity = int(
                    item.get("quantity", 0)
                )
            except (TypeError, ValueError):
                quantity = 0

            try:
                unit_price = float(
                    item.get("unit_price", 0.0)
                )
            except (TypeError, ValueError):
                unit_price = 0.0

            discount = get_discount(item)

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
                if get_entity_id(product)
                == product_id
            ]

            product = applicable_record(
                product_records,
                product_id,
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

    if customer_spend:
        best_customer = sorted(
            customer_spend.items(),
            key=lambda x: (
                -round(x[1], 2),
                x[0],
            ),
        )[0]

        top_customer = {
            "customer_id": best_customer[0],
            "total_spend": round(
                best_customer[1],
                2,
            ),
        }
    else:
        top_customer = {
            "customer_id": "",
            "total_spend": 0.0,
        }

    if product_quantities:
        best_product = sorted(
            product_quantities.items(),
            key=lambda x: (
                -x[1],
                x[0],
            ),
        )[0]

        top_product = {
            "product_id": best_product[0],
            "quantity_sold": best_product[1],
        }
    else:
        top_product = {
            "product_id": "",
            "quantity_sold": 0,
        }

    category_revenue = {
        category: round(revenue, 2)
        for category, revenue in category_revenue.items()
        if round(revenue, 2) > 0
    }

    report = {
        "total_revenue": round(
            total_revenue,
            2,
        ),
        "active_customers": len(
            active_customers
        ),
        "cancelled_orders": cancelled_orders,
        "top_customer": top_customer,
        "top_product": top_product,
        "category_revenue": category_revenue,
    }

    os.makedirs(
        os.path.dirname(OUTPUT_PATH),
        exist_ok=True,
    )

    with open(
        OUTPUT_PATH,
        "w",
        encoding="utf-8",
    ) as f:
        json.dump(
            report,
            f,
            indent=2,
        )


if __name__ == "__main__":
    main()
