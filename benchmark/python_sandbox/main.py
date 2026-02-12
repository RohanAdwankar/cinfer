import asyncio
from pathlib import Path

from .cinfer import run_cinfer
from .cinfer_no_language_dependency import run_cinfer_no_language_dependency
from .langchain import run_langchain
from .report import summarize_run, write_report


ALLOWED_SERVER_URL = "http://127.0.0.1:8080"


def _validate_server_url(server_url: str) -> None:
    if server_url.rstrip("/") != ALLOWED_SERVER_URL:
        raise ValueError(
            f"Only {ALLOWED_SERVER_URL} is allowed for this benchmark; got {server_url}"
        )


async def main() -> None:
    server_url = ALLOWED_SERVER_URL
    _validate_server_url(server_url)
    report_path = Path(__file__).resolve().parent / "report.txt"

    langchain_data = await run_langchain(server_url)
    cinfer_data = await run_cinfer(server_url)
    cinfer_no_language_dependency_data = await run_cinfer_no_language_dependency(
        server_url
    )

    raw = {
        "langchain": langchain_data,
        "cinfer": cinfer_data,
        "cinfer_no_language_dependency": cinfer_no_language_dependency_data,
    }
    runs = [
        summarize_run("LangChain", langchain_data["results"]),
        summarize_run("Cinfer", cinfer_data["results"]),
        summarize_run(
            "Cinfer (no depends_language)",
            cinfer_no_language_dependency_data["results"],
        ),
    ]
    write_report(str(report_path), runs, raw)
    print(f"Report written to {report_path}")


if __name__ == "__main__":
    asyncio.run(main())
