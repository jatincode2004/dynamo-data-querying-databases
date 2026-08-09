The source data is stored under /app/data:

- /app/data/customers.json
- /app/data/products.json
- /app/data/orders.json

Generate exactly one file:

/app/report.json

The report must contain exactly these top-level fields:

- total_revenue
- active_customers
- cancelled_orders
- top_customer
- top_product
- category_revenue

The three collections represent a small commerce system whose documents have changed over time. Treat the collections as historical document records rather than assuming that one physical document represents one permanent entity.

Produce a business report from the order history. The report should reflect the state of the relevant customer and product information at the time each order was placed. Repeated documents may therefore represent different historical states of the same logical entity.

Identifiers may use different casing and may appear under either an `*_id` field or a generic `id` field. Treat logically identical identifiers consistently.

For each order, use its order date when determining which historical customer or product information applies to that transaction. A historical document is applicable to a transaction when its effective period covers the transaction date. If several records for the same logical entity could apply, use the most recent applicable version.

Order line items contain quantity and unit price information. Some lines can contain discounts and line-level cancellation information. Cancelled lines must not contribute to sales or quantities. An order containing cancelled lines is counted as a cancelled order even when it also contains active lines.

Revenue for an active line is based on its quantity, unit price, and any applicable monetary discount. Revenue must not become negative.

Customer activity and customer spending are based on active order lines.

Product quantities are summed from active lines.

Product category revenue must use the product information applicable to the order date rather than blindly trusting a category copied into an order line. Missing or blank categories belong to `Uncategorized`.

`total_revenue` is the total net revenue from active order lines, rounded to two decimal places.

`active_customers` is the number of distinct customers associated with active order lines.

`cancelled_orders` is the number of logical orders containing at least one cancelled line.

`top_customer` must contain exactly:

{
  "customer_id": "...",
  "total_spend": 0.00
}

It identifies the customer with the greatest total net spend. Customer identifiers in the output must be uppercase. If there is a tie, use the uppercase identifier that comes first lexicographically.

`top_product` must contain exactly:

{
  "product_id": "...",
  "quantity_sold": 0
}

It identifies the product with the greatest number of units sold on active lines. Product identifiers in the output must be uppercase. If there is a tie, use the uppercase identifier that comes first lexicographically.

`category_revenue` must contain every category having positive rounded revenue, with values rounded to two decimal places.

The output must be valid UTF-8 JSON and must not contain any additional top-level fields.
