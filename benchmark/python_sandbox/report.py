import json
from typing import Any, Tuple


def _extract_json(text: str) -> Tuple[Any, str | None]:
    cleaned = text.strip()
    start = cleaned.find("{")
    alt_start = cleaned.find("[")
    if start == -1 or (alt_start != -1 and alt_start < start):
        start = alt_start

    if start == -1:
        return None, "no_json"

    decoder = json.JSONDecoder()
    try:
        obj, _ = decoder.raw_decode(cleaned[start:])
        return obj, None
    except json.JSONDecodeError as exc:
        return None, f"json_error: {exc}"


def _compare(expected: Any, actual: Any, tol: float = 1e-2) -> bool:
    if isinstance(expected, float) and isinstance(actual, (float, int)):
        return abs(expected - float(actual)) <= tol
    if isinstance(expected, int) and isinstance(actual, int):
        return expected == actual
    if isinstance(expected, dict) and isinstance(actual, dict):
        if expected.keys() != actual.keys():
            return False
        for key, exp_val in expected.items():
            if not _compare(exp_val, actual[key], tol=tol):
                return False
        return True
    if isinstance(expected, list) and isinstance(actual, list):
        if len(expected) != len(actual):
            return False
        return all(_compare(e, a, tol=tol) for e, a in zip(expected, actual))
    return expected == actual


def evaluate_output(output: str, expected: Any) -> dict:
    raw = output.strip()
    parsed, error = _extract_json(output)
    if error:
        return {"ok": False, "error": error, "raw": raw}

    ok = _compare(expected, parsed)
    return {"ok": ok, "parsed": parsed, "raw": raw}


def summarize_run(name: str, results: list[dict]) -> dict:
    total = len(results)
    ok = sum(1 for r in results if r.get("ok"))
    errors = sum(1 for r in results if r.get("error"))
    return {
        "name": name,
        "total": total,
        "ok": ok,
        "errors": errors,
        "issues": [r for r in results if not r.get("ok")][:5],
    }


def write_report(path: str, runs: list[dict], raw: dict) -> None:
    lines = [
        "Python sandbox benchmark",
        "",
        "Summary",
    ]
    for run in runs:
        rate = (run["ok"] / run["total"] * 100) if run["total"] else 0
        lines.append(
            f"- {run['name']}: ok {run['ok']}/{run['total']} ({rate:.0f}%), errors {run['errors']}"
        )

    lines += ["", "Examples (first 5 issues per run)"]
    for run in runs:
        lines.append(f"{run['name']}:")
        if run["issues"]:
            for issue in run["issues"]:
                lines.append(f"- {issue}")
        else:
            lines.append("- (no issues)")

    with open(path, "w", encoding="utf-8") as handle:
        handle.write("\n".join(lines) + "\n")

    with open(path.replace(".txt", ".json"), "w", encoding="utf-8") as handle:
        json.dump(raw, handle, indent=2)
