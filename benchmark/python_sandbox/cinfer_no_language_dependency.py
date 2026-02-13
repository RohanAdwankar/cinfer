from pathlib import Path

from cinfer import Agent, sanitize_python_tool_code, tool
from cinfer.registry import registry

from .data import DATA_DIR, REGIONS_COLUMNS, SALES_COLUMNS, SCENARIOS
from .report import evaluate_output
from .sandbox import run_python_in_container, wrap_benchmark_code

TRACE_DIR = Path(__file__).resolve().parent / "traces"
ALLOWED_SERVER_URL = "http://127.0.0.1:8080"
cinfer_no_language_dependency_tool_calls = []


def _snapshot_registry_state() -> tuple[dict, dict]:
    return registry._tools.copy(), {
        name: deps.copy() for name, deps in registry._pending_dependencies.items()
    }


def _restore_registry_state(tools: dict, pending_dependencies: dict) -> None:
    registry._tools = tools
    registry._pending_dependencies = pending_dependencies


def _register_run_python_tool() -> None:
    @tool
    def run_python(code: str) -> str:
        sanitized = sanitize_python_tool_code(code)
        wrapped = wrap_benchmark_code(sanitized)
        output = run_python_in_container(wrapped, DATA_DIR)
        cinfer_no_language_dependency_tool_calls.append({"code": code, "output": output})
        return output


async def run_cinfer_no_language_dependency(server_url: str) -> dict:
    if server_url.rstrip("/") != ALLOWED_SERVER_URL:
        raise ValueError(f"Only {ALLOWED_SERVER_URL} is allowed; got {server_url}")

    original_tools, original_pending_dependencies = _snapshot_registry_state()
    registry.clear()
    _register_run_python_tool()

    results = []
    try:
        for scenario in SCENARIOS:
            TRACE_DIR.mkdir(parents=True, exist_ok=True)
            trace_path = TRACE_DIR / f"cinfer_no_language_dependency_{scenario.name}.log"
            agent = Agent(
                system_prompt=(
                    "You are a Python data analyst in a Docker sandbox. "
                    "Always call run_python exactly once. "
                    "Send only valid Python code to run_python (no markdown, no explanation). "
                    "sales_df and regions_df are already loaded pandas DataFrames. "
                    "Do not read files. Do not print. "
                    "Put the final JSON-serializable answer in RESULT. "
                    f"sales_df columns: {', '.join(SALES_COLUMNS)}. "
                    f"regions_df columns: {', '.join(REGIONS_COLUMNS)}."
                ),
                server_url=server_url,
                max_iterations=1,
                temperature=0.0,
                reasoning_tokens=0,
                trace_file=str(trace_path),
            )
            cinfer_no_language_dependency_tool_calls.clear()
            try:
                await agent.run(scenario.user_message)
            except Exception as exc:
                trace_text = trace_path.read_text(encoding="utf-8") if trace_path.exists() else ""
                results.append(
                    {
                        "scenario": scenario.name,
                        "ok": False,
                        "error": str(exc),
                        "tool_calls": cinfer_no_language_dependency_tool_calls.copy(),
                        "trace_file": str(trace_path),
                        "trace": trace_text,
                        "conversation": agent.conversation_history,
                    }
                )
                continue

            if not cinfer_no_language_dependency_tool_calls:
                trace_text = trace_path.read_text(encoding="utf-8") if trace_path.exists() else ""
                results.append(
                    {
                        "scenario": scenario.name,
                        "ok": False,
                        "error": "no_tool_call",
                        "tool_calls": cinfer_no_language_dependency_tool_calls.copy(),
                        "trace_file": str(trace_path),
                        "trace": trace_text,
                        "conversation": agent.conversation_history,
                    }
                )
                continue

            output = cinfer_no_language_dependency_tool_calls[-1]["output"]
            verdict = evaluate_output(output, scenario.expected)
            trace_text = trace_path.read_text(encoding="utf-8") if trace_path.exists() else ""
            results.append(
                {
                    "scenario": scenario.name,
                    **verdict,
                    "tool_calls": cinfer_no_language_dependency_tool_calls.copy(),
                    "trace_file": str(trace_path),
                    "trace": trace_text,
                    "conversation": agent.conversation_history,
                }
            )
    finally:
        _restore_registry_state(original_tools, original_pending_dependencies)

    return {"results": results}
