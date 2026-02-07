import asyncio
from pathlib import Path

from cinfer import Agent, depends_language, tool

OUTPUT_DIR = Path(__file__).resolve().parent / "python_agent_output"
OUTPUT_FILE = OUTPUT_DIR / "generated.py"


@tool
@depends_language(code="python")
def new_py_file(code: str) -> str:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    OUTPUT_FILE.write_text(code.strip() + "\n")
    return f"Wrote {OUTPUT_FILE}"


async def main() -> None:
    agent = Agent(
        system_prompt=(
            "You are a Python file generator. Always call new_py_file with the full file contents. "
            "Output only valid Python source code. Do not add markdown or commentary."
        ),
        server_url="http://127.0.0.1:8080",
        max_iterations=1,
        temperature=0.1,
    )

    await agent.run(
        "Create a Python file that defines a function add(a, b). "
        "After the function definition, include a top-level line: print(add(2, 3)). "
        "Return only the file contents."
    )


if __name__ == "__main__":
    asyncio.run(main())
