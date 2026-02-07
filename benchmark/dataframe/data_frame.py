import pandas as pd


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
