#!/usr/bin/env python3
import json
import os

DATA_DIR = "/app/data"
OUTPUT_PATH = "/app/report.json"

def main():
    # Load JSON document collections
    with open(os.path.join(DATA_DIR, "customers.json"), "r", encoding="utf-8") as f:
        customers_data = json.load(f)
    with open(os.path.join(DATA_DIR, "products.json"), "r", encoding="utf-8") as f:
        products_data = json.load(f)
    with open(os.path.join(DATA_DIR, "orders.json"), "r", encoding="utf-8") as f:
        orders_data = json.load(f)

    # Build valid uppercase customer set
    valid_customers = set()
    for c in customers_data:
        cid = (c.get("customer_id") or c.get("id") or "").strip().upper()
        if cid:
            valid_customers.add(cid)

    # Build authoritative product-to-category map (case-insensitive keys)
    product_category_map = {}
    for p in products_data:
        p_id = (p.get("product_id") or p.get("id") or "").strip().upper()
        cat = p.get("category")
        if not cat or not str(cat).strip():
            cat_name = "Uncategorized"
        else:
            cat_name = str(cat).strip()
        if p_id:
            product_category_map[p_id] = cat_name

    total_revenue = 0.0
    cancelled_orders = 0
    active_customers = set()
    customer_spend = {}
    product_quantities = {}
    category_revenue = {}

    for order in orders_data:
        status = (order.get("status") or "").strip().lower()
        
        if status == "cancelled":
            cancelled_orders += 1
            continue

        if status != "completed":
            continue

        raw_cust_id = order.get("customer_id") or ""
        cust_id = str(raw_cust_id).strip().upper()
        if cust_id:
            active_customers.add(cust_id)

        order_spend = 0.0
        items = order.get("items", [])
        
        for item in items:
            p_id = str(item.get("product_id") or "").strip().upper()
            qty = int(item.get("quantity", 0))
            price = float(item.get("unit_price", 0.0))
            
            line_total = qty * price
            order_spend += line_total

            # Track quantity sold per product
            if p_id:
                product_quantities[p_id] = product_quantities.get(p_id, 0) + qty

            # Category revenue derived authoritatively from product catalog
            cat_name = product_category_map.get(p_id, "Uncategorized")
            category_revenue[cat_name] = category_revenue.get(cat_name, 0.0) + line_total

        total_revenue += order_spend
        if cust_id:
            customer_spend[cust_id] = customer_spend.get(cust_id, 0.0) + order_spend

    # Top Customer Determination (Spend desc, Lexicographical customer_id asc)
    top_customer = {"customer_id": "", "total_spend": 0.0}
    if customer_spend:
        best_cust = sorted(
            customer_spend.items(),
            key=lambda x: (-round(x[1], 2), x[0])
        )[0]
        top_customer = {
            "customer_id": best_cust[0],
            "total_spend": round(best_cust[1], 2)
        }

    # Top Product Determination (Quantity desc, Lexicographical product_id asc)
    top_product = {"product_id": "", "quantity_sold": 0}
    if product_quantities:
        best_prod = sorted(
            product_quantities.items(),
            key=lambda x: (-x[1], x[0])
        )[0]
        top_product = {
            "product_id": best_prod[0],
            "quantity_sold": best_prod[1]
        }

    # Format category revenue map
    formatted_category_revenue = {
        cat: round(rev, 2) for cat, rev in category_revenue.items() if round(rev, 2) > 0
    }

    report = {
        "total_revenue": round(total_revenue, 2),
        "active_customers": len(active_customers),
        "cancelled_orders": cancelled_orders,
        "top_customer": top_customer,
        "top_product": top_product,
        "category_revenue": formatted_category_revenue
    }

    # Ensure parent directory exists
    os.makedirs(os.path.dirname(OUTPUT_PATH), exist_ok=True)
    with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2)

if __name__ == "__main__":
    main()