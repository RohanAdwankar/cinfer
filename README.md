# Cinfer

Cinfer is a Python library designed to force AI Agents to be more deterministic to enable effective tool calling capabilities in SLMs. 

It works by constraining generation at inference time to obey grammers generated from tool definitions.

## Benchmarks

Performance is benchmarked with (Gemma 3)[https://huggingface.co/ggml-org/gemma-3-1b-it-GGUF] a model around 1/100 to 1/1000 the size of the leading models being used for modern agents.

### Python Tasks (./benchmark/python_sandbox)
All agents are implemented in ~100 lines and are given a tool to run python. 

They are then asked to perform data analysis tasks that require it to write pandas code to solve the problem on the fly. 

The cinfer agent performs with 100% accuracy, while the langraph agent had a 25% accuracy, and the cinfer agent without grammaer constrainsts (@depends_language(code="python")) also has a 25% accuracy.

### Dataframe Querying (./benchmark/dataframe)
Both agents are given a specialized tool to conduct the querying.

The cinfer agent (~50 lines) performs with 100% accuracy, while the langraph agent (~100 lines) had a 14% accuracy.

## Usage

### Basic Tool Definition

Decorate your functions with `@tool`. 

```python
from cinfer import tool, Agent
from typing import List

@tool
def search_database(query: str, limit: int):
    return f"Searching for {query} with limit {limit}"

agent = Agent(
    system_prompt="You are a helpful assistant.",
    server_url="http://localhost:8080")

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

### Language Constrains

For on the fly code generation users can supply a specific programming language.
```python
@tool
@depends_language(code="python")
def new_py_file(code: str) -> str:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    OUTPUT_FILE.write_text(code.strip() + "\n")
    return f"Wrote {OUTPUT_FILE}"
```

Alternatively, they can also supply a specific GBNF grammer.
```python
@tool
@depends_grammar_file(content="grammar/gbnf_grammar/json.gbnf")
def write_json(content: str) -> str:
```

## Examples
The goal of the project can be consisely understood by running the samples in /examples. 

## Problem / Motivation
AI agents work effectively for large models (in the order of 100B to 1T parameters) however they quickly fail for smaller models drastically decreasing their utility.
Small models typically fail due to hallucination, getting stuck in loops, and an inability to comply with a schema, making it difficult to perform reliable structured output generation, which is necessary to have the AI agent do things in the real world.
The model I am targetting is Gemma 3 1B, and the goal is to build a library that makes it ergonomic to develop useful agents.

## Solution
Agent libraries are typically decoupled from the inference engine, the goal of this library is to explore how re-coupling them can enable improved performance for SLMs.

Cinfer does this by taking the tool definition and then generating a formal grammer [GBNF](https://github.com/ggml-org/llama.cpp/blob/master/grammars/README.md) for the tool call. Then when the agent attempts to make a tool call, the inference engine masks the tokens which are not permitted for the grammer. This ensures that if a function requires an integer, the model physically cannot generate a non-integer token. If a tool requires a specific DataFrame column, the model can only select from the list of valid columns.

This differs from other approaches which generate a response, then validate against a schema, then loop till a valid schema is formed because here it is litterally impossible for a syntactically invalid output.

## Roadmap
The aim of the project is not just to show promising results on benchmark but push the frontier of what is 
