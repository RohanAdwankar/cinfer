import asyncio
from pathlib import Path

from .cinfer_impl import run_cinfer
from .data import SCENARIOS
from .langgraph_impl import run_langgraph
from .report import summarize_run, write_report


async def main() -> None:
    server_url = "http://127.0.0.1:8080"
    report_path = Path(__file__).resolve().parent / "report.txt"

    langgraph_data = await run_langgraph(SCENARIOS, server_url)
    cinfer_data = await run_cinfer(SCENARIOS, server_url)

    raw = {"langgraph": langgraph_data, "cinfer": cinfer_data}
    runs = [summarize_run("LangGraph", langgraph_data), summarize_run("Cinfer", cinfer_data)]
    write_report(str(report_path), runs, raw)
    print(f"Report written to {report_path}")


if __name__ == "__main__":
    asyncio.run(main())
