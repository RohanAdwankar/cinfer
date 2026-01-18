Examples shows 3 examples of how cinfer can appraoch grammer generation.
The examples force the LLM to generate something it would not like to generate, thereby proving how the grammer constraints can control generation.
## Default Type Enforcement 
In `default_types.py` we force the LLM into a corner where the answer is purple but that is impossible to return as an int so it returns an arbitrary number proving cinfer can pick up the type of the tool parameter and enforce it grammatically in generation.
```bash
uv run examples/default_types.py
>> Result: 13070542024352831774881710906182510298611141220208
```
## Depends Type Enforcement 
In `depends.py` we force the LLM to use the options in a list when none of the options in the list are the answer.
```bash
uv run examples/depends.py
>> Result: pink
```
Here the model wants to output purple but the grammer forces it to output pink.
If you add purple as one of the options, it will then output purple.
