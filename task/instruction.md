The input data is located under /app/data and contains the following JSON collections:
- customers.json
- products.json
- orders.json

Your goal is to inspect the provided document collections and generate exactly one output file:
/app/report.json

The output must be valid UTF-8 encoded JSON with no additional top-level fields. The report must contain only the following top-level fields:
- total_revenue
- active_customers
- cancelled_orders
- top_customer
- top_product
- category_revenue

Metric Definitions & Requirements:
- total_revenue (number): The net revenue generated across all non-cancelled orders. Floating-point values in the output must be rounded to exactly two decimal places.
- active_customers (integer): The total count of unique customers who have placed at least one non-cancelled order. Customer identifiers are case-insensitive (e.g., "CUST1" and "cust1" represent the same customer).
- cancelled_orders (integer): The total count of order records marked with status "cancelled".
- top_customer (object): Must contain exactly the following structure for the customer with the highest total net spend on non-cancelled orders:
  {
    "customer_id": "...",
    "total_spend": ...
  }
  where customer_id is a string converted to uppercase, and total_spend is a number rounded to exactly two decimal places.
- top_product (object): Must contain exactly the following structure for the product with the highest total units sold across non-cancelled orders:
  {
    "product_id": "...",
    "quantity_sold": ...
  }
  where product_id is a string converted to uppercase, and quantity_sold is an integer.
- category_revenue (object): A key-value map where keys are category names (string) and values are total net revenue (number, rounded to exactly two decimal places) for non-cancelled orders. All categories with non-zero revenue present in the dataset must appear. Orders with missing or blank categories must be grouped under key "Uncategorized".

Tie-Breaking Rules:
- top_customer: If multiple customers tie for highest spend, select the customer whose uppercase customer_id comes first lexicographically (ASCII order).
- top_product: If multiple products tie for highest total quantity sold, select the product whose uppercase product_id comes first lexicographically (ASCII order).

Do not generate any files other than /app/report.json.