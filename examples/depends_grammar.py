import asyncio
from pathlib import Path

from cinfer import Agent, depends_grammar_file, tool

OUTPUT_DIR = Path(__file__).resolve().parent / "json_agent_output"
OUTPUT_FILE = OUTPUT_DIR / "result.json"


@tool
@depends_grammar_file(content="grammar/gbnf_grammar/json.gbnf")
def write_json(content: str) -> str:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    OUTPUT_FILE.write_text(content.strip() + "\n")
    return f"Wrote {OUTPUT_FILE}"


async def main() -> None:
    agent = Agent(
        system_prompt=(
            "You are a JSON generator. Always call write_json with a single JSON value. "
            "Return only JSON without markdown or commentary."
        ),
        server_url="http://127.0.0.1:8080",
        max_iterations=1,
        temperature=0.1,
    )

    await agent.run(
        "Create a JSON object with keys name and age, where name is Alice and age is 30. "
        "Return only JSON."
    )


if __name__ == "__main__":
    asyncio.run(main())
