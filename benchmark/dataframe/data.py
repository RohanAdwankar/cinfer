from dataclasses import dataclass

import pandas as pd


@dataclass
class Scenario:
    name: str
    user_message: str
    expected_column: str
    column_exists: bool


SALES_DF = pd.DataFrame(
    {
        "customer_id": ["C001", "C002", "C001", "C003", "C002", "C004", "C001", "C003"],
        "customer_name": [
            "Alice Corp",
            "Bob Industries",
            "Alice Corp",
            "Charlie Ltd",
            "Bob Industries",
            "Delta Inc",
            "Alice Corp",
            "Charlie Ltd",
        ],
        "customer_email": [
            "alice@corp.com",
            "bob@ind.com",
            "alice@corp.com",
            "charlie@ltd.com",
            "bob@ind.com",
            "delta@inc.com",
            "alice@corp.com",
            "charlie@ltd.com",
        ],
        "customer_segment": [
            "Enterprise",
            "SMB",
            "Enterprise",
            "Mid-Market",
            "SMB",
            "Enterprise",
            "Enterprise",
            "Mid-Market",
        ],
        "order_id": ["ORD1001", "ORD1002", "ORD1003", "ORD1004", "ORD1005", "ORD1006", "ORD1007", "ORD1008"],
        "order_date": ["2024-01-15", "2024-01-16", "2024-01-17", "2024-01-18", "2024-01-19", "2024-01-20", "2024-01-21", "2024-01-22"],
        "order_status": ["completed", "completed", "pending", "completed", "completed", "shipped", "completed", "processing"],
        "product_id": ["P100", "P200", "P300", "P400", "P100", "P500", "P300", "P400"],
        "product_name": ["Laptop Pro", "Mouse Wireless", "Keyboard Mech", "Monitor 4K", "Laptop Pro", "Headphones", "Keyboard Mech", "Monitor 4K"],
        "product_sku": ["SKU-LP-001", "SKU-MW-002", "SKU-KM-003", "SKU-M4-004", "SKU-LP-001", "SKU-HP-005", "SKU-KM-003", "SKU-M4-004"],
        "product_category": ["Computers", "Accessories", "Accessories", "Displays", "Computers", "Audio", "Accessories", "Displays"],
        "price_usd": [1200.0, 25.0, 75.0, 350.0, 1200.0, 89.0, 75.0, 350.0],
        "price_base": [1000.0, 20.0, 60.0, 300.0, 1000.0, 70.0, 60.0, 300.0],
        "tax_amount": [120.0, 2.5, 7.5, 35.0, 120.0, 8.9, 7.5, 35.0],
        "shipping_cost": [0.0, 5.0, 5.0, 15.0, 0.0, 10.0, 5.0, 15.0],
        "region": ["West", "East", "West", "North", "East", "South", "West", "North"],
        "sales_office": ["SF", "NYC", "SF", "CHI", "NYC", "ATL", "SF", "CHI"],
        "sales_rep_id": ["REP01", "REP02", "REP01", "REP03", "REP02", "REP04", "REP01", "REP03"],
        "sales_rep_name": ["John Smith", "Jane Doe", "John Smith", "Bob Wilson", "Jane Doe", "Sarah Chen", "John Smith", "Bob Wilson"],
        "quarter": ["Q1", "Q1", "Q1", "Q1", "Q1", "Q1", "Q1", "Q1"],
    }
)

SALES_COLUMNS = list(SALES_DF.columns)

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
