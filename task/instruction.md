The input data is stored under /app/data as three JSON document collections:

- /app/data/customers.json
- /app/data/products.json
- /app/data/orders.json

Generate exactly one file:

/app/report.json

Do not create any other files under /app. The output must be valid UTF-8 JSON and must contain exactly these top-level fields:

- total_revenue
- active_customers
- cancelled_orders
- top_customer
- top_product
- category_revenue

Data reconciliation:

1. Every customer, product, and order document has a logical identifier. The identifier may appear as `customer_id`/`id`, `product_id`/`id`, or `order_id`.
2. Identifiers are case-insensitive. Normalize them by converting the selected identifier to a stripped uppercase string.
3. Documents may contain multiple versions of the same logical entity. Each version has an integer `schema_version`. For every logical customer, product, or order, retain only the document having the highest `schema_version` before performing any aggregation.
4. Product categories must come from the retained product document. If its category is missing, null, or blank, use `Uncategorized`.
5. Order line-item fields are authoritative for line-level processing. Each item has `product_id`, `quantity`, `unit_price`, optional numeric `discount`, and optional `line_status`. A missing discount is zero and a missing line status is treated as active.
6. A line whose `line_status` is `cancelled` contributes nothing to revenue, customer spend, product quantity, or category revenue.
7. An order is counted in `cancelled_orders` when its retained document contains at least one cancelled line item. Other active lines in that same order are still included in the revenue and aggregation metrics.
8. For an active line, net line revenue is:
   quantity * unit_price - discount
   where `discount` is a monetary amount for the entire line, not a percentage. Net revenue is never negative; if the computed value is below zero, use zero.
9. Order-level status fields, when present, do not replace the line-level cancellation rule.

Metrics:

`total_revenue` is the sum of net revenue from every active line in every retained order. Round the final value to two decimal places.

`active_customers` is the number of distinct normalized customer identifiers appearing on at least one active line in a retained order.

`cancelled_orders` is the number of retained logical orders containing at least one cancelled line.

`top_customer` must contain exactly:
{
  "customer_id": "...",
  "total_spend": 0.00
}
It is the customer with the greatest net spend across active lines. Customer IDs are uppercase. Ties are resolved by uppercase customer ID in ASCII lexicographic order.

`top_product` must contain exactly:
{
  "product_id": "...",
  "quantity_sold": 0
}
It is the product with the greatest quantity across active lines. Product IDs are uppercase. Ties are resolved by uppercase product ID in ASCII lexicographic order.

`category_revenue` maps every category having positive rounded revenue to its total net revenue. Categories come from the retained product catalog. Missing or blank product categories use `Uncategorized`. Values are rounded to two decimal places.

The report must contain no additional top-level fields.
