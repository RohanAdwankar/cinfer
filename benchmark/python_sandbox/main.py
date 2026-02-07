import asyncio
from pathlib import Path

from .cinfer import run_cinfer
from .langchain import run_langchain
from .report import summarize_run, write_report


async def main() -> None:
    server_url = "http://127.0.0.1:8080"
    report_path = Path(__file__).resolve().parent / "report.txt"

    langchain_data = await run_langchain(server_url)
    cinfer_data = await run_cinfer(server_url)

    raw = {"langchain": langchain_data, "cinfer": cinfer_data}
    runs = [
        summarize_run("LangChain", langchain_data["results"]),
        summarize_run("Cinfer", cinfer_data["results"]),
    ]
    write_report(str(report_path), runs, raw)
    print(f"Report written to {report_path}")


if __name__ == "__main__":
    asyncio.run(main())
