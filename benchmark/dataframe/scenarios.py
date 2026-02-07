from .types import Scenario


SCENARIOS = [
    Scenario("filter_by_customer_name", "Show me orders from Alice Corp", "customer_name", True),
    Scenario("filter_by_product_category", "Show me Computers category", "product_category", True),
    Scenario("filter_by_order_status", "Show me completed orders", "order_status", True),
    Scenario("filter_by_sales_rep_name", "Show me orders from John Smith", "sales_rep_name", True),
    Scenario("filter_by_customer_segment", "Show me Enterprise customers", "customer_segment", True),
    Scenario("filter_by_customer_type", "Show me customer type Enterprise", "customer_type", False),
    Scenario("filter_by_customer_company", "Show me orders from Alice company", "customer_company", False),
    Scenario("filter_by_product_type", "Show me product type Computers", "product_type", False),
    Scenario("filter_by_product_description", "Show me product description for Laptop", "product_description", False),
    Scenario("filter_by_price", "Show me orders with price 1200", "price", False),
    Scenario("filter_by_total_price", "Show me orders with total price over 1000", "total_price", False),
    Scenario("filter_by_discount_amount", "Show me orders with discount applied", "discount_amount", False),
    Scenario("filter_by_discount_percent", "Show me 10% discount orders", "discount_percent", False),
    Scenario("filter_by_profit_margin", "Show me high profit margin orders", "profit_margin", False),
    Scenario("filter_by_revenue", "Show me revenue over 1000", "revenue", False),
    Scenario("filter_by_sales_rep_email", "Show me orders from rep email john@company.com", "sales_rep_email", False),
    Scenario("filter_by_order_number", "Show me order number 1001", "order_number", False),
    Scenario("filter_by_invoice_id", "Show me invoice INV1001", "invoice_id", False),
    Scenario("filter_by_payment_status", "Show me paid orders", "payment_status", False),
    Scenario("filter_by_country", "Show me orders from USA", "country", False),
    Scenario("filter_by_state", "Show me orders from California", "state", False),
    Scenario("filter_by_city", "Show me orders from San Francisco", "city", False),
]
