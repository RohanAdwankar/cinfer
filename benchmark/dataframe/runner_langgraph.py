from typing import Annotated, TypedDict
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI
from langgraph.graph import END, StateGraph
from langgraph.graph.message import add_messages
from langgraph.prebuilt import ToolNode

from .data_frame import SALES_COLUMNS
from .tools_langgraph import (
    filter_sales_langgraph,
    filter_sales_langgraph_schema,
    get_available_columns,
    langgraph_schema_tool_calls,
    langgraph_tool_calls,
)


class AgentState(TypedDict):
    messages: Annotated[list, add_messages]


async def run_langgraph(scenarios, server_url, use_schema):
    tools = [get_available_columns, filter_sales_langgraph_schema] if use_schema else [filter_sales_langgraph]
    tool_calls = langgraph_schema_tool_calls if use_schema else langgraph_tool_calls
    system_prompt = (
        "You are a sales data analyst. Call get_available_columns first, then "
        "filter_sales_langgraph_schema to query sales data."
        if use_schema
        else "You are a sales data analyst. Use filter_sales_langgraph to query sales data."
    )
    llm = ChatOpenAI(
        base_url=f"{server_url}/v1",
        api_key="not-needed",
        model="local-model",
        temperature=0.1,
        max_tokens=512 if use_schema else 256,
    )
    llm_with_tools = llm.bind_tools(tools)

    def should_continue(state):
        last = state["messages"][-1]
        return "tools" if getattr(last, "tool_calls", None) else "final"

    def call_model(state):
        return {"messages": [llm_with_tools.invoke(state["messages"])]}

    def call_model_final(state):
        return {"messages": [llm.invoke(state["messages"])]}

    workflow = StateGraph(AgentState)
    workflow.add_node("agent", call_model); workflow.add_node("tools", ToolNode(tools))
    workflow.add_node("agent_final", call_model_final); workflow.set_entry_point("agent")
    workflow.add_conditional_edges("agent", should_continue, {"tools": "tools", "final": "agent_final"})
    workflow.add_edge("tools", "agent_final"); workflow.add_edge("agent_final", END)
    graph = workflow.compile()

    results = []; valid = 0; hallucinations = 0; schema_checks = 0
    for scenario in scenarios:
        tool_calls.clear(); used_schema_tool = False
        try:
            result = await graph.ainvoke(
                {"messages": [SystemMessage(content=system_prompt), HumanMessage(content=scenario.user_message)]},
                {"recursion_limit": 12},
            )
            if use_schema:
                for msg in result["messages"]:
                    for tc in getattr(msg, "tool_calls", []) or []:
                        if tc.get("name") == "get_available_columns":
                            used_schema_tool = True; schema_checks += 1
            if tool_calls:
                used = tool_calls[0]["column"]; is_valid = used in SALES_COLUMNS
                valid += int(is_valid); hallucinations += int(not is_valid)
                results.append(
                    {
                        "scenario": scenario.name,
                        "expected_column": scenario.expected_column,
                        "used_column": used,
                        "column_is_valid": is_valid,
                        "should_exist": scenario.column_exists,
                        "had_error": "error" in tool_calls[0],
                        "used_schema_tool": used_schema_tool,
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
        "schema_checks": schema_checks,
        "total": len(scenarios),
    }
