from typing import Annotated, TypedDict
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_core.tools import tool
from langchain_openai import ChatOpenAI
from langgraph.graph import END, StateGraph
from langgraph.graph.message import add_messages
from langgraph.prebuilt import ToolNode

from .data import SALES_COLUMNS, SALES_DF
langgraph_tool_calls = []


@tool
def filter_sales_langgraph(column: str, value: str) -> str:
    """Filter sales data by column value."""
    if column not in SALES_DF.columns:
        langgraph_tool_calls.append({"column": column, "value": value, "error": "missing_column"})
        return f"Error: column '{column}' does not exist"
    result = SALES_DF[SALES_DF[column].astype(str).str.contains(value, case=False, na=False, regex=False)]
    langgraph_tool_calls.append({"column": column, "value": value})
    return f"Found {len(result)} orders where {column} contains '{value}'"


class AgentState(TypedDict):
    messages: Annotated[list, add_messages]


async def run_langgraph(scenarios, server_url):
    llm = ChatOpenAI(
        base_url=f"{server_url}/v1",
        api_key="not-needed",
        model="local-model",
        temperature=0.1,
        max_tokens=256,
    )
    llm_with_tools = llm.bind_tools([filter_sales_langgraph])

    def should_continue(state):
        last = state["messages"][-1]
        return "tools" if getattr(last, "tool_calls", None) else "final"

    def call_model(state):
        return {"messages": [llm_with_tools.invoke(state["messages"])]}

    def call_model_final(state):
        return {"messages": [llm.invoke(state["messages"])]}

    workflow = StateGraph(AgentState)
    workflow.add_node("agent", call_model)
    workflow.add_node("tools", ToolNode([filter_sales_langgraph]))
    workflow.add_node("agent_final", call_model_final)
    workflow.set_entry_point("agent")
    workflow.add_conditional_edges("agent", should_continue, {"tools": "tools", "final": "agent_final"})
    workflow.add_edge("tools", "agent_final")
    workflow.add_edge("agent_final", END)
    graph = workflow.compile()

    results = []
    valid = 0
    hallucinations = 0

    for scenario in scenarios:
        langgraph_tool_calls.clear()
        try:
            await graph.ainvoke(
                {
                    "messages": [
                        SystemMessage(content="You are a sales data analyst. Use filter_sales_langgraph to query sales data."),
                        HumanMessage(content=scenario.user_message),
                    ]
                },
                {"recursion_limit": 12},
            )
            if langgraph_tool_calls:
                used = langgraph_tool_calls[0]["column"]
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
                        "had_error": "error" in langgraph_tool_calls[0],
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
