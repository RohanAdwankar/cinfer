import asyncio
import logging
import sys
from typing import List
from cinfer import tool, Agent, depends

@tool
def mix_colors(result: int):
    print(f"Result: {result}")

async def main():
    agent = Agent(
        system_prompt="You are a color mixer.",
        server_url="http://localhost:8080",
        max_iterations=1,
    )
    await agent.run("When red and blue are mixed, what is the resulting color? Call mix_colors_int to output the answer.")
    
if __name__ == "__main__":
    asyncio.run(main())
