from cinfer import Agent, depends, tool

from .data import SALES_COLUMNS, SALES_DF

cinfer_tool_calls = []


@tool
@depends(column=SALES_COLUMNS)
def filter_sales_cinfer(column: str, value: str) -> str:
    result = SALES_DF[SALES_DF[column].astype(str).str.contains(value, case=False, na=False, regex=False)]
    cinfer_tool_calls.append({"column": column, "value": value})
    return f"Found {len(result)} orders where {column} contains '{value}'"


async def run_cinfer(scenarios, server_url):
    agent = Agent(
        system_prompt="You are a sales data analyst. Use filter_sales_cinfer to query sales data.",
        server_url=server_url,
        max_iterations=1,
        temperature=0.1,
        reasoning_tokens=30,
    )
    results = []
    valid = 0
    hallucinations = 0

    for scenario in scenarios:
        cinfer_tool_calls.clear()
        try:
            await agent.run(scenario.user_message)
            if cinfer_tool_calls:
                used = cinfer_tool_calls[0]["column"]
                is_valid = used in SALES_COLUMNS
                valid += int(is_valid)
                hallucinations += int(not is_valid)
                results.append(
                    {
                        "scenario": scenario.name,
                        "expected_column": scenario.expected_column,
                        "used_column": used,
                        "column_is_valid": is_valid,
                        "should_exist": scenario.column_exists,
                    }
                )
            else:
                results.append({"scenario": scenario.name, "no_tool_call": True})
        except Exception as exc:
            results.append({"scenario": scenario.name, "error": str(exc)})

    return {
        "results": results,
        "valid_columns": valid,
        "hallucinations": hallucinations,
        "total": len(scenarios),
    }
