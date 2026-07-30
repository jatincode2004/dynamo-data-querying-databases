import json
import os
import pytest

REPORT_PATH = "/app/report.json"
DATA_DIR = "/app/data"

def test_report_file_exists():
    assert os.path.exists(REPORT_PATH), f"Output file '{REPORT_PATH}' does not exist."

def test_no_extra_json_files():
    for item in os.listdir("/app"):
        if item.endswith(".json") and item != "report.json":
            pytest.fail(f"Unauthorized extra JSON file found in /app: {item}")

def test_report_schema_and_types():
    with open(REPORT_PATH, "r", encoding="utf-8") as f:
        report = json.load(f)

    expected_keys = {
        "total_revenue",
        "active_customers",
        "cancelled_orders",
        "top_customer",
        "top_product",
        "category_revenue"
    }
    assert set(report.keys()) == expected_keys, f"Key mismatch. Expected {expected_keys}, got {set(report.keys())}"

    assert isinstance(report["total_revenue"], (int, float))
    assert isinstance(report["active_customers"], int)
    assert isinstance(report["cancelled_orders"], int)
    assert isinstance(report["top_customer"], dict)
    assert isinstance(report["top_product"], dict)
    assert isinstance(report["category_revenue"], dict)

    assert set(report["top_customer"].keys()) == {"customer_id", "total_spend"}
    assert set(report["top_product"].keys()) == {"product_id", "quantity_sold"}

    assert isinstance(report["top_customer"]["customer_id"], str)
    assert isinstance(report["top_customer"]["total_spend"], (int, float))
    assert isinstance(report["top_product"]["product_id"], str)
    assert isinstance(report["top_product"]["quantity_sold"], int)

def test_report_values_dynamically():
    """Independently computes expected values from /app/data to avoid hardcoding answer literals."""
    with open(os.path.join(DATA_DIR, "products.json"), "r", encoding="utf-8") as f:
        products_data = json.load(f)
    with open(os.path.join(DATA_DIR, "orders.json"), "r", encoding="utf-8") as f:
        orders_data = json.load(f)

    product_category_map = {}
    for p in products_data:
        p_id = (p.get("product_id") or p.get("id") or "").strip().upper()
        cat = p.get("category")
        cat_name = str(cat).strip() if (cat and str(cat).strip()) else "Uncategorized"
        if p_id:
            product_category_map[p_id] = cat_name

    expected_rev = 0.0
    expected_cancelled = 0
    expected_active_cust = set()
    cust_spend = {}
    prod_qty = {}
    cat_rev = {}

    for order in orders_data:
        status = (order.get("status") or "").strip().lower()
        if status == "cancelled":
            expected_cancelled += 1
            continue
        if status != "completed":
            continue

        cid = str(order.get("customer_id") or "").strip().upper()
        if cid:
            expected_active_cust.add(cid)

        order_spend = 0.0
        for item in order.get("items", []):
            pid = str(item.get("product_id") or "").strip().upper()
            qty = int(item.get("quantity", 0))
            price = float(item.get("unit_price", 0.0))
            line = qty * price
            order_spend += line

            if pid:
                prod_qty[pid] = prod_qty.get(pid, 0) + qty
            cat = product_category_map.get(pid, "Uncategorized")
            cat_rev[cat] = cat_rev.get(cat, 0.0) + line

        expected_rev += order_spend
        if cid:
            cust_spend[cid] = cust_spend.get(cid, 0.0) + order_spend

    best_cust = sorted(cust_spend.items(), key=lambda x: (-round(x[1], 2), x[0]))[0]
    best_prod = sorted(prod_qty.items(), key=lambda x: (-x[1], x[0]))[0]

    with open(REPORT_PATH, "r", encoding="utf-8") as f:
        report = json.load(f)

    # Validate with float tolerance
    assert report["total_revenue"] == pytest.approx(round(expected_rev, 2), abs=1e-2)
    assert report["active_customers"] == len(expected_active_cust)
    assert report["cancelled_orders"] == expected_cancelled
    
    assert report["top_customer"]["customer_id"] == best_cust[0]
    assert report["top_customer"]["total_spend"] == pytest.approx(round(best_cust[1], 2), abs=1e-2)
    
    assert report["top_product"]["product_id"] == best_prod[0]
    assert report["top_product"]["quantity_sold"] == best_prod[1]

    for cat, rev in cat_rev.items():
        if round(rev, 2) > 0:
            assert cat in report["category_revenue"]
            assert report["category_revenue"][cat] == pytest.approx(round(rev, 2), abs=1e-2)