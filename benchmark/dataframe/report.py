import json


def summarize_run(name, data):
    results = data["results"]
    total = data["total"]
    valid = data["valid_columns"]
    hallucinations = data["hallucinations"]
    no_tool = sum(1 for r in results if r.get("no_tool_call"))
    errors = sum(1 for r in results if r.get("error"))
    issues = []
    for r in results:
        if r.get("error"):
            issues.append(f"{r['scenario']}: error")
        elif r.get("no_tool_call"):
            issues.append(f"{r['scenario']}: no tool call")
        elif not r.get("column_is_valid", True):
            issues.append(f"{r['scenario']}: used {r.get('used_column')} expected {r.get('expected_column')}")
    return {
        "name": name,
        "total": total,
        "valid": valid,
        "hallucinations": hallucinations,
        "no_tool": no_tool,
        "errors": errors,
        "issues": issues[:5],
    }


def write_report(path, runs, raw):
    lines = ["Dataframe column hallucination benchmark", "", "Summary"]
    for run in runs:
        rate = (run["valid"] / run["total"] * 100) if run["total"] else 0
        lines.append(
            f"- {run['name']}: valid {run['valid']}/{run['total']} ({rate:.0f}%), "
            f"hallucinations {run['hallucinations']}, no_tool {run['no_tool']}, errors {run['errors']}"
        )
    lines += ["", "Examples (first 5 issues per run)"]
    for run in runs:
        lines.append(f"{run['name']}:")
        lines += [f"- {issue}" for issue in run["issues"] or ["(no issues)"]]

    with open(path, "w") as handle:
        handle.write("\n".join(lines) + "\n")

    with open(path.replace(".txt", ".json"), "w") as handle:
        json.dump(raw, handle, indent=2)
