#!/usr/bin/env python3

import json
import os

DATA_DIR = "/app/data"
OUTPUT_PATH = "/app/report.json"


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

        current = selected.get(entity_id)
        if current is None or version > int(current.get("schema_version", 1)):
            selected[entity_id] = record

    return selected


def main():
    with open(os.path.join(DATA_DIR, "customers.json"), encoding="utf-8") as f:
        customers = json.load(f)

    with open(os.path.join(DATA_DIR, "products.json"), encoding="utf-8") as f:
        products = json.load(f)

    with open(os.path.join(DATA_DIR, "orders.json"), encoding="utf-8") as f:
        orders = json.load(f)

    # Reconcile document versions before aggregation.
    customer_map = latest_versions(customers, ["customer_id", "id"])
    product_map = latest_versions(products, ["product_id", "id"])
    order_map = latest_versions(orders, ["order_id", "id"])

    # Customer map is intentionally built because customer documents are
    # part of the reconciled document collections.
    valid_customers = set(customer_map)

    product_categories = {}

    for product_id, product in product_map.items():
        category = product.get("category")

        if category is None or not str(category).strip():
            category = "Uncategorized"
        else:
            category = str(category).strip()

        product_categories[product_id] = category

    total_revenue = 0.0
    cancelled_orders = 0

    active_customers = set()
    customer_spend = {}
    product_quantities = {}
    category_revenue = {}

    for order_id, order in order_map.items():
        customer_id = normalize_id(order.get("customer_id"))

        order_has_cancelled_line = False

        for item in order.get("items", []):
            line_status = str(item.get("line_status", "active")).strip().lower()

            if line_status == "cancelled":
                order_has_cancelled_line = True
                continue

            product_id = normalize_id(item.get("product_id"))

            quantity = int(item.get("quantity", 0))
            unit_price = float(item.get("unit_price", 0.0))
            discount = float(item.get("discount", 0.0))

            net_revenue = max(
                0.0,
                quantity * unit_price - discount
            )

            if customer_id:
                active_customers.add(customer_id)
                customer_spend[customer_id] = (
                    customer_spend.get(customer_id, 0.0)
                    + net_revenue
                )

            if product_id:
                product_quantities[product_id] = (
                    product_quantities.get(product_id, 0)
                    + quantity
                )

            category = product_categories.get(
                product_id,
                "Uncategorized"
            )

            category_revenue[category] = (
                category_revenue.get(category, 0.0)
                + net_revenue
            )

            total_revenue += net_revenue

        if order_has_cancelled_line:
            cancelled_orders += 1

    if customer_spend:
        top_customer_id = min(
            customer_spend,
            key=lambda cid: (
                -round(customer_spend[cid], 2),
                cid
            )
        )

        top_customer = {
            "customer_id": top_customer_id,
            "total_spend": round(
                customer_spend[top_customer_id], 2
            ),
        }
    else:
        top_customer = {
            "customer_id": "",
            "total_spend": 0.0,
        }

    if product_quantities:
        top_product_id = min(
            product_quantities,
            key=lambda pid: (
                -product_quantities[pid],
                pid
            )
        )

        top_product = {
            "product_id": top_product_id,
            "quantity_sold": product_quantities[top_product_id],
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
        "total_revenue": round(total_revenue, 2),
        "active_customers": len(active_customers),
        "cancelled_orders": cancelled_orders,
        "top_customer": top_customer,
        "top_product": top_product,
        "category_revenue": category_revenue,
    }

    os.makedirs(os.path.dirname(OUTPUT_PATH), exist_ok=True)

    with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2)


if __name__ == "__main__":
    main()
