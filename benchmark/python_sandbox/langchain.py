import asyncio

from langchain_core.messages import HumanMessage, SystemMessage, ToolMessage
from langchain_core.tools import tool
from langchain_openai import ChatOpenAI

from .data import DATA_DIR, REGIONS_COLUMNS, SALES_COLUMNS, SCENARIOS
from .report import evaluate_output
from .sandbox import run_python_in_container, wrap_benchmark_code

langchain_tool_calls = []
ALLOWED_SERVER_URL = "http://127.0.0.1:8080"


def _message_to_dict(message) -> dict:
    return {
        "type": getattr(message, "type", message.__class__.__name__),
        "content": getattr(message, "content", ""),
        "tool_calls": getattr(message, "tool_calls", None),
        "tool_call_id": getattr(message, "tool_call_id", None),
    }


@tool
def run_python(code: str) -> str:
    """Run python code inside the sandbox container and return stdout."""
    wrapped = wrap_benchmark_code(code)
    output = run_python_in_container(wrapped, DATA_DIR)
    langchain_tool_calls.append({"code": code, "output": output})
    return output


def _build_llm(server_url: str) -> ChatOpenAI:
    if server_url.rstrip("/") != ALLOWED_SERVER_URL:
        raise ValueError(f"Only {ALLOWED_SERVER_URL} is allowed; got {server_url}")

    return ChatOpenAI(
        base_url=f"{server_url}/v1",
        api_key="not-needed",
        model="local-model",
        temperature=0.1,
        max_tokens=256,
    )


async def run_langchain(server_url: str) -> dict:
    llm = _build_llm(server_url)
    llm_with_tools = llm.bind_tools([run_python], tool_choice="required")

    results = []
    for scenario in SCENARIOS:
        langchain_tool_calls.clear()
        message_trace = []
        messages = [
            SystemMessage(
                content=(
                    "You are a Python data analyst in a Docker sandbox. "
                    "Always call run_python exactly once. "
                    "Send only valid Python code to run_python (no markdown, no explanation). "
                    "sales_df and regions_df are already loaded pandas DataFrames. "
                    "Do not read files. Do not print. "
                    "Put the final JSON-serializable answer in RESULT. "
                    f"sales_df columns: {', '.join(SALES_COLUMNS)}. "
                    f"regions_df columns: {', '.join(REGIONS_COLUMNS)}." 
                )
            ),
            HumanMessage(content=scenario.user_message),
        ]
        message_trace += [_message_to_dict(msg) for msg in messages]

        try:
            response = await llm_with_tools.ainvoke(messages)
            messages.append(response)
            message_trace.append(_message_to_dict(response))

            if getattr(response, "tool_calls", None):
                for call in response.tool_calls:
                    tool_result = run_python.invoke(call["args"])
                    messages.append(ToolMessage(tool_call_id=call["id"], content=str(tool_result)))
                    message_trace.append(_message_to_dict(messages[-1]))
        except Exception as exc:
            results.append(
                {
                    "scenario": scenario.name,
                    "ok": False,
                    "error": str(exc),
                    "tool_calls": langchain_tool_calls.copy(),
                    "messages": message_trace,
                }
            )
            continue

        if not langchain_tool_calls:
            results.append(
                {
                    "scenario": scenario.name,
                    "ok": False,
                    "error": "no_tool_call",
                    "tool_calls": langchain_tool_calls.copy(),
                    "messages": message_trace,
                }
            )
            continue

        output = langchain_tool_calls[-1]["output"]
        verdict = evaluate_output(output, scenario.expected)
        results.append(
            {
                "scenario": scenario.name,
                **verdict,
                "tool_calls": langchain_tool_calls.copy(),
                "messages": message_trace,
            }
        )

    return {"results": results}
