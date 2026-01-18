# Cinfer

Cinfer is a Python library designed to force AI Agents to be more deterministic to enable effective tool calling capabilities in SLMs. 

It works by constraining generation at inference time to obey grammers generated from tool definitions.

This project is a work in progress, if benchmarks show strong performance I will put it on pypi to install.

## Problem / Motivation

AI agents work effectively for large models (in the order of 100B to 1T parameters) however they quickly fail for smaller models drastically decreasing their utility.
Small models typically fail due to hallucination, getting stuck in loops, and an inability to comply with a schema, making it difficult to perform reliable structured output generation, which is necessary to have the AI agent do things in the real world.
The model I am targetting is Gemma 3 1B, and the goal is to build a library that makes it ergonomic to develop useful agents.

## Solution

Agent libraries are typically decoupled from the inference engine, the goal of this library is to explore how re-coupling them can enable improved performance for SLMs.

Cinfer does this by taking the tool definition and then generating a formal grammer [GBNF](https://github.com/ggml-org/llama.cpp/blob/master/grammars/README.md) for the tool call. Then when the agent attempts to make a tool call, the inference engine masks the tokens which are not permitted for the grammer. This ensures that if a function requires an integer, the model physically cannot generate a non-integer token. If a tool requires a specific DataFrame column, the model can only select from the list of valid columns.

This differs from other approaches which generate a response, then validate against a schema, then loop till a valid schema is formed because here it is litterally impossible for a syntactically invalid output.

## Usage

### Basic Tool Definition

Decorate your functions with `@tool`. 

```python
from cinfer import tool, Agent
from typing import List

@tool
def search_database(query: str, limit: int):
    """Search the database for items."""
    return f"Searching for {query} with limit {limit}"

# Initialize agent pointing to your local server
agent = Agent(
    system_prompt="You are a helpful assistant.",
    server_url="http://localhost:8080"
)

# Run the agent
result = await agent.run("Find top 5 laptop results")
```
Cinfer will see that query is a string and limit is an int, generate a grammer, then enforce it on an inference engine level.

### Explicit Constraints

Cinfer can restrict model outputs to only generate the options from a list using `@depends`.
In this case, cinfer ensures only valid column names can be generated:

```python
import pandas as pd
from cinfer import tool, depends

df = pd.DataFrame({"product_id": [1, 2], "price_usd": [100, 200]})
valid_columns = list(df.columns)

@tool
@depends(column=valid_columns)
def filter_data(column: str, value: int):
    return df[df[column] == value]
```
The model will be constrained to generate either "product_id" or "price_usd" for the 'column' argument. It cannot hallucinate "price" or "id".

## Examples
The goal of the project can be consisely understood by running the samples in /examples. 
