from cinfer import depends, tool

from .data_frame import SALES_COLUMNS, SALES_DF

cinfer_tool_calls = []


@tool
@depends(column=SALES_COLUMNS)
def filter_sales_cinfer(column: str, value: str) -> str:
    result = SALES_DF[SALES_DF[column].astype(str).str.contains(value, case=False, na=False, regex=False)]
    cinfer_tool_calls.append({"column": column, "value": value})
    return f"Found {len(result)} orders where {column} contains '{value}'"
