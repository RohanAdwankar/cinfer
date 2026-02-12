from pathlib import Path
import ast
import re

from cinfer import Agent, depends_language, tool

from .data import DATA_DIR, REGIONS_COLUMNS, SALES_COLUMNS, SCENARIOS
from .report import evaluate_output
from .sandbox import run_python_in_container, wrap_benchmark_code

TRACE_DIR = Path(__file__).resolve().parent / "traces"
cinfer_tool_calls = []
ALLOWED_SERVER_URL = "http://127.0.0.1:8080"


def _extract_fenced_code(text: str) -> str:
    def score_block(block: str) -> int:
        value = block.strip()
        score = 0
        if not value:
            return -100
        if "RESULT" in value:
            score += 10
        if "=" in value:
            score += 4
        if "print(" in value:
            score += 2
        if "def run_python" in value:
            score -= 8
        return score

    blocks = re.findall(r"```\s*python\s*\n(.*?)```", text, re.DOTALL | re.IGNORECASE)
    if not blocks:
        blocks = re.findall(r"```\s*\w*\s*\n(.*?)```", text, re.DOTALL)

    if blocks:
        return max(blocks, key=score_block).strip()

    return text.strip()


def _unwrap_run_python_call(text: str) -> str:
    match = re.search(r"run_python\s*\(\s*([\s\S]+?)\s*\)", text)
    if not match:
        return text

    inner = match.group(1).strip()
    try:
        return ast.literal_eval(inner)
    except Exception:
        return text


def _sanitize_code(code: str) -> str:
    cleaned = _extract_fenced_code(code)
    cleaned = _unwrap_run_python_call(cleaned)
    cleaned = cleaned.strip()

    if not cleaned:
        return "RESULT = None"

    if cleaned.startswith("RESULT\n"):
        rest = cleaned.split("\n", 1)[1].strip()
        if rest:
            cleaned = f"RESULT = {rest}"

    lines = cleaned.splitlines()
    if len(lines) >= 2 and lines[0].strip() == "RESULT":
        rhs = "\n".join(lines[1:]).strip()
        if rhs:
            cleaned = f"RESULT = {rhs}"

    # Convert simple helper function outputs into direct RESULT assignments
    fn_match = re.search(r"def\s+run_python\s*\([^)]*\)\s*:\s*\n(?:\s+.*\n)*?\s+return\s+(.+)", cleaned)
    if fn_match and "RESULT" not in cleaned:
        cleaned = f"RESULT = {fn_match.group(1).strip()}"

    # Convert `print(expr)` when RESULT is missing
    if "RESULT" not in cleaned:
        print_match = re.fullmatch(r"print\((.+)\)\s*", cleaned, re.DOTALL)
        if print_match:
            cleaned = f"RESULT = {print_match.group(1).strip()}"

    # If it's a single expression, treat it as the final result
    if "RESULT" not in cleaned:
        try:
            parsed = ast.parse(cleaned)
            if len(parsed.body) == 1 and isinstance(parsed.body[0], ast.Expr):
                cleaned = f"RESULT = {cleaned}"
        except Exception:
            pass

    # Normalize lowercase result variable
    if "RESULT" not in cleaned:
        cleaned = re.sub(r"\bresult\s*=", "RESULT =", cleaned)

    # If code is just a JSON literal, assign it to RESULT
    if "RESULT" not in cleaned:
        stripped = cleaned.strip()
        if (stripped.startswith("{") and stripped.endswith("}")) or (stripped.startswith("[") and stripped.endswith("]")):
            cleaned = f"RESULT = {stripped}"

    return cleaned.strip()


@tool
@depends_language(code="python")
def run_python(code: str) -> str:
    sanitized = _sanitize_code(code)
    wrapped = wrap_benchmark_code(sanitized)
    output = run_python_in_container(wrapped, DATA_DIR)
    cinfer_tool_calls.append({"code": code, "output": output})
    return output


async def run_cinfer(server_url: str) -> dict:
    if server_url.rstrip("/") != ALLOWED_SERVER_URL:
        raise ValueError(f"Only {ALLOWED_SERVER_URL} is allowed; got {server_url}")

    results = []
    for scenario in SCENARIOS:
        TRACE_DIR.mkdir(parents=True, exist_ok=True)
        trace_path = TRACE_DIR / f"cinfer_{scenario.name}.log"
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
        cinfer_tool_calls.clear()
        try:
            await agent.run(scenario.user_message)
        except Exception as exc:
            trace_text = trace_path.read_text(encoding="utf-8") if trace_path.exists() else ""
            results.append(
                {
                    "scenario": scenario.name,
                    "ok": False,
                    "error": str(exc),
                    "tool_calls": cinfer_tool_calls.copy(),
                    "trace_file": str(trace_path),
                    "trace": trace_text,
                    "conversation": agent.conversation_history,
                }
            )
            continue

        if not cinfer_tool_calls:
            trace_text = trace_path.read_text(encoding="utf-8") if trace_path.exists() else ""
            results.append(
                {
                    "scenario": scenario.name,
                    "ok": False,
                    "error": "no_tool_call",
                    "tool_calls": cinfer_tool_calls.copy(),
                    "trace_file": str(trace_path),
                    "trace": trace_text,
                    "conversation": agent.conversation_history,
                }
            )
            continue

        output = cinfer_tool_calls[-1]["output"]
        verdict = evaluate_output(output, scenario.expected)
        trace_text = trace_path.read_text(encoding="utf-8") if trace_path.exists() else ""
        results.append(
            {
                "scenario": scenario.name,
                **verdict,
                "tool_calls": cinfer_tool_calls.copy(),
                "trace_file": str(trace_path),
                "trace": trace_text,
                "conversation": agent.conversation_history,
            }
        )

    return {"results": results}
