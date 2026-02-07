from cinfer import Agent, depends_language, tool

from .data import DATA_DIR, SCENARIOS
from .report import evaluate_output
from .sandbox import run_python_in_container

cinfer_tool_calls = []


@tool
@depends_language(code="python")
def run_python(code: str) -> str:
    output = run_python_in_container(code, DATA_DIR)
    cinfer_tool_calls.append({"code": code, "output": output})
    return output


async def run_cinfer(server_url: str) -> dict:
    agent = Agent(
        system_prompt=(
            "You are a Python data analyst running in a sandbox. "
            "Always call run_python with valid Python code. "
            "The code must read CSVs from /input and print JSON only."
        ),
        server_url=server_url,
        max_iterations=1,
        temperature=0.1,
        reasoning_tokens=60,
    )

    results = []
    for scenario in SCENARIOS:
        cinfer_tool_calls.clear()
        try:
            await agent.run(scenario.user_message)
        except Exception as exc:
            results.append({"scenario": scenario.name, "ok": False, "error": str(exc)})
            continue

        if not cinfer_tool_calls:
            results.append({"scenario": scenario.name, "ok": False, "error": "no_tool_call"})
            continue

        output = cinfer_tool_calls[-1]["output"]
        verdict = evaluate_output(output, scenario.expected)
        results.append({"scenario": scenario.name, **verdict})

    return {"results": results}
