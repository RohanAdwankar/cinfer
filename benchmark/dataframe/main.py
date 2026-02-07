import asyncio
from pathlib import Path

from .scenarios import SCENARIOS
from .report import summarize_run, write_report
from .runner_cinfer import run_cinfer
from .runner_langgraph import run_langgraph


async def main() -> None:
    server_url = "http://127.0.0.1:8080"
    base_dir = Path(__file__).resolve().parent
    report_path = base_dir / "report.txt"

    langgraph_data = await run_langgraph(SCENARIOS, server_url, use_schema=False)
    langgraph_schema_data = await run_langgraph(SCENARIOS, server_url, use_schema=True)
    cinfer_data = await run_cinfer(SCENARIOS, server_url)

    raw = {
        "langgraph_baseline": langgraph_data,
        "langgraph_schema": langgraph_schema_data,
        "cinfer": cinfer_data,
    }
    runs = [
        summarize_run("LangGraph baseline", langgraph_data),
        summarize_run("LangGraph + schema", langgraph_schema_data),
        summarize_run("Cinfer", cinfer_data),
    ]
    write_report(str(report_path), server_url, runs, raw)
    print(f"Report written to {report_path}")


if __name__ == "__main__":
    asyncio.run(main())
