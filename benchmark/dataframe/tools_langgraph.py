from langchain_core.tools import tool

from .data_frame import SALES_DF

langgraph_tool_calls = []
langgraph_schema_tool_calls = []


@tool
def filter_sales_langgraph(column: str, value: str) -> str:
    """Filter sales data by column value."""
    if column not in SALES_DF.columns:
        langgraph_tool_calls.append({"column": column, "value": value, "error": "missing_column"})
        return f"Error: column '{column}' does not exist"
    result = SALES_DF[SALES_DF[column].astype(str).str.contains(value, case=False, na=False, regex=False)]
    langgraph_tool_calls.append({"column": column, "value": value})
    return f"Found {len(result)} orders where {column} contains '{value}'"


@tool
def get_available_columns() -> str:
    """Return the available column names."""
    return ", ".join(SALES_DF.columns)


@tool
def filter_sales_langgraph_schema(column: str, value: str) -> str:
    """Filter sales data by column value after checking available columns."""
    if column not in SALES_DF.columns:
        langgraph_schema_tool_calls.append({"column": column, "value": value, "error": "missing_column"})
        return f"Error: column '{column}' does not exist"
    result = SALES_DF[SALES_DF[column].astype(str).str.contains(value, case=False, na=False, regex=False)]
    langgraph_schema_tool_calls.append({"column": column, "value": value})
    return f"Found {len(result)} orders where {column} contains '{value}'"
