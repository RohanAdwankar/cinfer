"""
Agent class for running inference with grammar constraints
"""

import asyncio
import json
import logging
import re
from typing import Any, Dict, List, Optional
import httpx

from .registry import registry, ToolMetadata
from .grammar import grammar_generator

logger = logging.getLogger(__name__)


class Agent:
    """
    Agent that uses inference-time grammars for constrained generation.
    """

    def __init__(
        self,
        system_prompt: str,
        server_url: str = "http://localhost:8080",
        max_iterations: int = 10,
        temperature: float = 0.7,
        allow_no_tool: bool = False,
        reasoning_tokens: int = 50,
        trace_file: Optional[str] = None,
    ):
        """
        Initialize the agent.

        Args:
            system_prompt: System prompt defining agent behavior
            server_url: URL of the llama.cpp server
            max_iterations: Maximum number of reasoning/tool call iterations
            temperature: Sampling temperature
            allow_no_tool: Whether to allow the agent to choose not to use any tool
            reasoning_tokens: Max tokens for reasoning step (default 50, ~80% reduction from 256)
            trace_file: Optional file path to write detailed trace logs
        """
        self.system_prompt = system_prompt
        self.server_url = server_url
        self.max_iterations = max_iterations
        self.temperature = temperature
        self.allow_no_tool = allow_no_tool
        self.reasoning_tokens = reasoning_tokens
        self.conversation_history: List[Dict[str, str]] = []
        self.trace_file = trace_file
        if self.trace_file:
            with open(self.trace_file, 'w') as f:
                f.write("=== CINFER AGENT TRACE ===\n\n")

    async def _complete(
        self,
        prompt: str,
        grammar: Optional[str] = None,
        n_predict: int = 512,
        stop: Optional[List[str]] = None,
    ) -> str:
        """
        Make a completion request to llama.cpp server.

        Args:
            prompt: The prompt to complete
            grammar: Optional GBNF grammar to constrain output
            n_predict: Maximum tokens to predict
            stop: Stop sequences

        Returns:
            Generated text
        """
        payload = {
            "prompt": prompt,
            "n_predict": n_predict,
            "temperature": self.temperature,
        }

        if grammar:
            payload["grammar"] = grammar
            logger.debug(f"Using grammar:\n{grammar}")

        if stop:
            payload["stop"] = stop

        logger.debug(f"Making completion request with prompt length: {len(prompt)}")

        # Write trace if enabled
        if self.trace_file:
            with open(self.trace_file, 'a') as f:
                f.write(f"\n{'='*80}\n")
                f.write(f"PROMPT (length={len(prompt)}, n_predict={n_predict}):\n")
                f.write(f"{'='*80}\n")
                f.write(prompt)
                f.write(f"\n{'='*80}\n")
                if grammar:
                    f.write(f"GRAMMAR:\n{grammar}\n")
                    f.write(f"{'='*80}\n")

        async with httpx.AsyncClient(timeout=60.0) as client:
            try:
                response = await client.post(
                    f"{self.server_url}/completion",
                    json=payload,
                )
                response.raise_for_status()
                result = response.json()
                content = result.get("content", "")
                logger.debug(f"Generated: {content}")

                # Write trace if enabled
                if self.trace_file:
                    with open(self.trace_file, 'a') as f:
                        f.write(f"GENERATED:\n{content}\n")
                        f.write(f"{'='*80}\n\n")

                return content
            except Exception as e:
                logger.error(f"Completion request failed: {e}")
                raise

    def _build_prompt(self, user_message: str, include_history: bool = True) -> str:
        """
        Build a prompt from system prompt, history, and user message.

        Args:
            user_message: The user's message
            include_history: Whether to include conversation history

        Returns:
            Complete prompt string
        """
        parts = [self.system_prompt]

        if include_history and self.conversation_history:
            for msg in self.conversation_history:
                role = msg.get("role", "")
                content = msg.get("content", "")
                parts.append(f"{role}: {content}")

        parts.append(f"User: {user_message}")
        parts.append("Assistant:")

        return "\n\n".join(parts)

    async def _reason(self, user_message: str) -> str:
        """
        Let the agent reason about what to do (unconstrained generation).

        Args:
            user_message: The user's message

        Returns:
            Agent's reasoning
        """
        if self.reasoning_tokens <= 0:
            return ""

        logger.info("Agent reasoning (unconstrained)...")
        prompt = self._build_prompt(user_message)

        # Add tool information to help the agent understand what's available
        tools = registry.get_all_tools()
        if tools:
            tool_desc = "\n".join([f"- {name}: {meta.description}" for name, meta in tools.items()])
            prompt += f"\n\nAvailable tools:\n{tool_desc}"

            if self.allow_no_tool:
                prompt += "\nNote: You may choose to use none of the tools if that is the rational decision."

            prompt += "\n\nThinking: To process the request, I need to"

        reasoning = await self._complete(prompt, n_predict=self.reasoning_tokens, stop=["Action:", "User:"])
        logger.info(f"< {reasoning.strip()}")
        return reasoning.strip()

    async def _select_tool(self) -> Optional[str]:
        """
        Have the agent select which tool to use (grammar-constrained).

        Returns:
            Tool name or None
        """
        logger.info("Selecting tool (grammar-constrained)...")

        # Generate grammar for available tools
        tools_grammar = grammar_generator.generate_tools_grammar(allow_none=self.allow_no_tool)

        tools = registry.get_all_tools()
        if not tools:
            logger.warning("No tools available")
            return None

        # Calculate tool count
        tool_results = [h for h in self.conversation_history if h.get("role") == "ToolResult"]
        tool_count = len(tool_results)

        # Build prompt with conversation history for better context
        prompt = self._build_prompt("", include_history=True)
        prompt += f"\n\n[System] History: {tool_count} tools executed so far.\nAction: "

        tool_name = await self._complete(prompt, grammar=tools_grammar, n_predict=50)
        tool_name = tool_name.strip().strip('"')

        # Check if "NONE" was selected
        if tool_name == "NONE":
            logger.info(f"> Action: NONE (no tool selected)")
            return None

        logger.info(f"> Action: {tool_name}")
        return tool_name

    async def _get_parameter_value(self, tool_name: str, param_name: str, user_message: str, reasoning: str = "", custom_grammar: Optional[str] = None, extracted_params: Optional[Dict[str, Any]] = None) -> Any:
        """
        Get a parameter value with grammar constraints if available.

        Args:
            tool_name: Name of the tool
            param_name: Name of the parameter
            user_message: The original user message for context
            reasoning: The reasoning from the agent (provides additional context)
            custom_grammar: Optional custom grammar to use for this parameter
            extracted_params: Parameters already extracted in this tool call

        Returns:
            Parameter value (converted to correct type)
        """
        logger.info(f"Getting parameter {param_name} for {tool_name}...")

        # Use custom grammar if provided, otherwise try to get one from registry
        param_grammar = custom_grammar or grammar_generator.generate_parameter_grammar(tool_name, param_name)

        # If no dependency grammar, generate native type grammar
        if not param_grammar:
            tool = registry.get_tool(tool_name)
            if tool and param_name in tool.parameters:
                param = tool.parameters[param_name]
                param_type = param.annotation if hasattr(param, 'annotation') else str
                type_name = str(param_type)
                
                if 'int' in type_name.lower():
                    param_grammar = 'root ::= "-"? [0-9]+'
                elif 'float' in type_name.lower():
                    param_grammar = 'root ::= "-"? [0-9]+ ("." [0-9]+)?'
                elif 'bool' in type_name.lower():
                    param_grammar = 'root ::= "true" | "false"'

        # Include system context for parameter extraction
        # Get parameter type to determine extraction strategy
        tool = registry.get_tool(tool_name)
        param_type_str = ""
        is_complex = False
        if tool and param_name in tool.parameters:
            param = tool.parameters[param_name]
            param_type = param.annotation if hasattr(param, 'annotation') else str
            param_type_str = str(param_type)
            is_complex = 'list' in param_type_str.lower() or 'dict' in param_type_str.lower()
        dependency = tool.get_dependency(param_name) if tool else None

        # Build prompt for parameter extraction WITH conversation history
        # Track how many times this tool has been called to handle multi-entity extraction
        tool_call_count = 0
        if self.conversation_history:
            tool_results = [h for h in self.conversation_history if h.get("role") == "ToolResult"]
            tool_call_count = len(tool_results)

        # Calculate extraction hint for ALL parameter types
        tool_call_count = 0
        if self.conversation_history:
            tool_results = [h for h in self.conversation_history if h.get("role") == "ToolResult"]
            tool_call_count = len(tool_results)

        n = tool_call_count + 1
        suffix = {1: 'st', 2: 'nd', 3: 'rd'}.get(n if (n < 20) else n % 10, 'th')
        ord_str = f"{n}{suffix}"
        extraction_hint = f"for the {ord_str} patient"

        # Prepare context string from extracted params
        param_context = ""
        if extracted_params:
            context_items = [f"{k}='{v}'" for k, v in extracted_params.items() if isinstance(v, (str, int, float, bool))]
            if context_items:
                param_context = f"Current Entity Context: {', '.join(context_items)}.\n"

        if param_name in ["content", "code"]:
            # Full context for code generation
            prompt = (
                f"{self.system_prompt}\n\n"
                f"User request: {user_message}\n"
                "Write ONLY executable Python statements for the tool parameter.\n"
                "Do not define functions or classes.\n"
                "Do not include markdown fences or explanations.\n"
                "Use existing variables if provided by the tool context.\n"
                "Set RESULT to the final JSON-serializable value.\n"
            )
        elif is_complex:
            # For complex types (lists, dicts), be very explicit about JSON format
            # Check if this is a List of Pydantic models to provide structure guidance
            from typing import get_args
            inner_type = None
            if hasattr(param_type, '__args__') and get_args(param_type):
                inner_type = get_args(param_type)[0]

            # Build example structure based on inner type
            focus_str = f"Focus ONLY on the entity described by: {param_context}\n" if param_context else ""
            
            if inner_type and hasattr(inner_type, '__annotations__'):
                # Pydantic model - show expected structure
                fields = list(inner_type.__annotations__.keys())
                example_item = '{' + ', '.join([f'"{f}": ...' for f in fields]) + '}'
                prompt = f"{focus_str}From the text below, extract {param_name} as an array of objects with these fields: {', '.join(fields)}.\nExample format: [{example_item}]\n\n{user_message}\n\nAnswer:\n"
            elif 'list' in param_type_str.lower():
                prompt = f"{focus_str}From the text below, extract {param_name} as an array like [\"item1\", \"item2\"]:\n\n{user_message}\n\nAnswer:\n"
            else:
                prompt = f"{focus_str}From the text below, extract {param_name} as an object:\n\n{user_message}\n\nAnswer:\n"
        else:
            # For simple parameters, extract the raw value
            # If there's a grammar constraint, mention it in the prompt
            if param_grammar:
                # Get the valid values from the tool's dependency
                tool = registry.get_tool(tool_name)
                dependency = tool.get_dependency(param_name) if tool else None
                if dependency and not dependency.is_grammar:
                    try:
                        valid_values = list(dependency.source_object)
                        prompt = f"{param_context}List every occurrence of {param_name} found in the text, one per line. Do not number the lines. Do not combine values for different entities. Values must be one of: {', '.join(str(v) for v in valid_values)}.\n\n{user_message}\n\n{param_name} list:"
                    except:
                        prompt = f"{param_context}List every occurrence of {param_name} found in the text, one per line. Do not number the lines. Do not combine values for different entities. Do not include any other text.\n\n{user_message}\n\n{param_name} list:"
                else:
                    prompt = f"{param_context}List every occurrence of {param_name} found in the text, one per line. Do not number the lines. Do not combine values for different entities. Do not include any other text.\n\n{user_message}\n\n{param_name} list:"
            else:
                # Unconstrained simple parameter
                prompt = f"{param_context}List every occurrence of {param_name} found in the text, one per line. Do not number the lines. Do not combine values for different entities. Do not include any other text.\n\n{user_message}\n\n{param_name} list:"

        # Use more tokens for complex types
        if param_name in ["content", "code"]:
            n_predict = 220
        elif is_complex:
            n_predict = 250  # Enough for JSON but not too much rambling
        else:
            n_predict = 50  # Short for simple values (names, ages, enum values)

        # The current language grammars can be too permissive/noisy for long code outputs.
        # For code/content, prefer unconstrained generation with strict prompting.
        use_grammar = bool(param_grammar)
        if param_name in ["content", "code"] and dependency and dependency.is_grammar and dependency.source_name.startswith("<language:"):
            use_grammar = False

        if use_grammar:
            logger.info(f"Using grammar constraint for parameter {param_name} ({len(param_grammar)} bytes)")
            value = await self._complete(prompt, grammar=param_grammar, n_predict=n_predict)
        else:
            logger.info(f"No grammar constraint for parameter {param_name}, using unconstrained")
            # Use appropriate generation based on complexity
            value = await self._complete(prompt, n_predict=n_predict, stop=["\n\nUser:", "\n\nAssistant:"])

        # Clean up the value
        value = value.strip().strip('"')
        # Remove markdown code fences
        if value.startswith('```'):
            lines = value.split('\n')
            # Remove first line (```json or ```) and last line if it's closing fence
            if len(lines) > 1:
                lines = lines[1:]  # Skip first line
                if lines and lines[-1].strip().startswith('```'):
                    lines = lines[:-1]  # Skip last line if it's closing fence
                # For complex types and code, keep all lines; for simple, take first
                if is_complex or param_name in ["content", "code"]:
                    value = '\n'.join(lines).strip()
                else:
                    value = lines[0].strip() if lines else ''
            else:
                value = value.replace('```', '').strip()
        else:
            # For simple parameters (not content/code and not complex)
            # If on tool call N and model generated multiple lines, take line N
            if param_name not in ["content", "code"] and not is_complex:
                lines = [l.strip() for l in value.split('\n') if l.strip()]
                if lines:
                    # Use tool_call_count to select which line (0-indexed)
                    line_index = min(tool_call_count, len(lines) - 1)
                    value = lines[line_index]
                else:
                    value = value.strip()
        
        # Aggressive cleanup of chatty prefixes
        for prefix in ["Final Answer:", "The answer is:", "value:", "extracted:", f"{param_name}:"]:
            if value.lower().startswith(prefix.lower()):
                value = value[len(prefix):].strip()
        
        # Cleanup leading/trailing punctuation/quotes again
        value = value.strip().strip('"\'`.:')

        if param_name in ["content", "code"]:
            value = self._normalize_language_output("python", value)

        if dependency and dependency.is_grammar and dependency.source_name.startswith("<language:"):
            language = dependency.source_name[len("<language:"):-1]
            value = self._normalize_language_output(language, value)

        logger.info(f"> Parameter {param_name} = {value[:100]}..." if len(value) > 100 else f"> Parameter {param_name} = {value}")

        logger.debug(f"Final cleaned value: {repr(value[:200])}")

        # Convert type based on parameter annotation
        tool = registry.get_tool(tool_name)
        if tool and param_name in tool.parameters:
            param = tool.parameters[param_name]
            param_type = param.annotation if hasattr(param, 'annotation') else str
            type_name = str(param_type)

            try:
                if 'int' in type_name.lower():
                    # Try direct conversion first
                    try:
                        return int(value)
                    except ValueError:
                        # Try to convert written numbers to integers
                        number_words = {
                            'zero': 0, 'one': 1, 'two': 2, 'three': 3, 'four': 4, 'five': 5,
                            'six': 6, 'seven': 7, 'eight': 8, 'nine': 9, 'ten': 10,
                            'eleven': 11, 'twelve': 12, 'thirteen': 13, 'fourteen': 14, 'fifteen': 15,
                            'sixteen': 16, 'seventeen': 17, 'eighteen': 18, 'nineteen': 19, 'twenty': 20,
                            'twenty-one': 21, 'twenty-two': 22, 'twenty-three': 23, 'twenty-four': 24,
                            'twenty-five': 25, 'twenty-six': 26, 'twenty-seven': 27, 'twenty-eight': 28,
                            'twenty-nine': 29, 'thirty': 30, 'thirty-one': 31, 'thirty-two': 32,
                            'forty': 40, 'forty-five': 45, 'fifty': 50, 'fifty-seven': 57, 'sixty': 60, 'sixty-two': 62,
                            'seventy': 70, 'eighty': 80, 'ninety': 90, 'hundred': 100
                        }
                        value_lower = value.lower().strip()
                        if value_lower in number_words:
                            return number_words[value_lower]
                        # Try to find digits in the string
                        import re
                        match = re.search(r'\d+', value)
                        if match:
                            return int(match.group())
                        raise
                elif 'float' in type_name.lower():
                    return float(value)
                elif 'bool' in type_name.lower():
                    return value.lower() in ['true', '1', 'yes']
                elif 'list' in type_name.lower():
                    # Try to parse as JSON array
                    import json
                    from typing import get_args
                    try:
                        # Find start of JSON array
                        start_idx = value.find('[')
                        if start_idx != -1:
                            value = value[start_idx:]
                        
                        # Extract just the JSON part if there's extra content
                        # For arrays, find the matching closing bracket
                        if value.strip().startswith('['):
                            bracket_count = 0
                            json_end = 0
                            for i, char in enumerate(value):
                                if char == '[':
                                    bracket_count += 1
                                elif char == ']':
                                    bracket_count -= 1
                                    if bracket_count == 0:
                                        json_end = i + 1
                                        break
                            if json_end > 0:
                                value = value[:json_end]

                        parsed_list = json.loads(value)
                        logger.debug(f"Parsed list: {parsed_list}, type: {type(parsed_list)}")

                        # Check if this is a List of Pydantic models
                        # param_type is something like List[Medication]
                        logger.debug(f"param_type: {param_type}, has __args__: {hasattr(param_type, '__args__')}")
                        if hasattr(param_type, '__args__'):
                            # Get the inner type (e.g., Medication from List[Medication])
                            inner_type = get_args(param_type)[0] if get_args(param_type) else None
                            logger.debug(f"inner_type: {inner_type}, has __mro__: {hasattr(inner_type, '__mro__') if inner_type else False}")

                            # Check if it's a Pydantic BaseModel
                            if inner_type and hasattr(inner_type, '__mro__'):
                                try:
                                    from pydantic import BaseModel
                                    is_pydantic = BaseModel in inner_type.__mro__
                                    logger.debug(f"Is Pydantic: {is_pydantic}")
                                    if is_pydantic:
                                        # Convert each dict to the Pydantic model
                                        result = []
                                        for i, item in enumerate(parsed_list):
                                            if isinstance(item, dict):
                                                try:
                                                    # Coerce values to match Pydantic model types
                                                    coerced_item = {}
                                                    for key, value in item.items():
                                                        if key in inner_type.__annotations__:
                                                            field_type = inner_type.__annotations__[key]
                                                            field_type_str = str(field_type)

                                                            # Coerce integers
                                                            if 'int' in field_type_str.lower() and isinstance(value, str):
                                                                # Extract first number from string like "10 milligrams"
                                                                import re
                                                                match = re.search(r'\d+', value)
                                                                coerced_item[key] = int(match.group()) if match else value
                                                            else:
                                                                coerced_item[key] = value
                                                        else:
                                                            coerced_item[key] = value

                                                    obj = inner_type(**coerced_item)
                                                    result.append(obj)
                                                except Exception as e:
                                                    logger.error(f"Failed to convert item {i} to {inner_type.__name__}: {e}, item: {item}")
                                                    # Instead of raising, try to continue with the original item
                                                    result.append(item)
                                            else:
                                                result.append(item)
                                        logger.info(f"Converted {len(result)} items to {inner_type.__name__} objects")
                                        return result
                                except ImportError:
                                    logger.warning("Pydantic not available")
                                    pass

                        # Otherwise just return the parsed list
                        logger.debug(f"Returning parsed list as-is")
                        return parsed_list
                    except Exception as e:
                        logger.warning(f"Failed to parse list as JSON: {e}")
                        # Fallback: split by comma
                        return [v.strip() for v in value.split(',') if v.strip()]
                elif 'dict' in type_name.lower():
                    import json
                    return json.loads(value)
            except Exception as e:
                logger.warning(f"Failed to convert {param_name} to {param_type}: {e}, returning as string")
                return value

        return value

    def _normalize_language_output(self, language: str, value: str) -> str:
        normalized = value.strip()

        if "```" in normalized:
            import re

            def score_block(block: str) -> int:
                text = block.strip()
                score = 0
                if not text:
                    return -100
                if "RESULT" in text:
                    score += 10
                if "=" in text:
                    score += 4
                if "print(" in text:
                    score += 2
                if "def run_python" in text:
                    score -= 8
                if "{" in text and "}" in text:
                    score += 1
                return score

            lang = re.escape(language)
            blocks = re.findall(rf"```\s*{lang}\s*\n(.*?)```", normalized, re.DOTALL | re.IGNORECASE)
            if not blocks:
                blocks = re.findall(r"```\s*\w*\s*\n(.*?)```", normalized, re.DOTALL)

            if blocks:
                normalized = max(blocks, key=score_block).strip()

        lines = normalized.splitlines()
        if lines and lines[0].strip().lower() == language.lower() and len(lines) > 1:
            normalized = "\n".join(lines[1:]).strip()

        return normalized

    async def _execute_tool(self, tool_name: str, user_message: str, reasoning: str = "") -> str:
        """
        Execute a tool by getting parameter values and calling it.

        Args:
            tool_name: Name of the tool to execute
            user_message: The original user message for parameter extraction
            reasoning: The reasoning from the agent (provides context for parameter extraction)

        Returns:
            Tool result
        """
        tool = registry.get_tool(tool_name)
        if not tool:
            return f"Error: Tool {tool_name} not found"

        logger.info(f"Executing tool: {tool_name}")

        # Gather parameters
        kwargs = {}
        extracted_params = {}
        
        for param_name, param in tool.parameters.items():
            value = await self._get_parameter_value(tool_name, param_name, user_message, reasoning, extracted_params=extracted_params)
            kwargs[param_name] = value
            extracted_params[param_name] = value

        # Execute the tool
        try:
            result = tool.func(**kwargs)
            logger.info(f"Tool result: {result}")
            return str(result)
        except Exception as e:
            error_msg = f"Error executing tool: {e}"
            logger.error(error_msg)
            return error_msg

    async def run(self, user_message: str) -> str:
        """
        Run the agent on a user message.

        Args:
            user_message: The user's message/request

        Returns:
            Final response from the agent
        """
        logger.info(f"\n{'='*60}")
        logger.info(f"User: {user_message}")
        logger.info(f"{'='*60}\n")

        # Add user message to history
        self.conversation_history.append({"role": "User", "content": user_message})

        # Reasoning step
        reasoning = await self._reason(user_message)
        if reasoning:
            self.conversation_history.append({"role": "Reasoning", "content": reasoning})

        # Determine if we should use a tool
        tools = registry.get_all_tools()
        if not tools:
            logger.warning("No tools available, returning reasoning")
            return reasoning

        # Try to execute a tool
        for iteration in range(self.max_iterations):
            logger.info(f"\n--- Iteration {iteration + 1} ---")

            # Re-reason on each iteration to check if we should continue
            if iteration > 0:
                # After first iteration, reason about what to do next
                tool_results = [h.get("content", "") for h in self.conversation_history if h.get("role") == "ToolResult"]
                tool_counts = len(tool_results)
                
                # Extract processed names
                processed_names = []
                for res in tool_results:
                    import re
                    match = re.search(r"Recorded (.+)", res)
                    if match:
                        processed_names.append(match.group(1).strip())
                
                processed_str = ", ".join(processed_names) if processed_names else "None"
                
                reasoning_prompt = self._build_prompt("", include_history=True)
                reasoning_prompt += f"\n\nCompleted actions: {tool_counts} tool calls.\nProcessed Patients: {processed_str}.\nBased on the above history, what should I do next? Have you processed ALL patients mentioned in the text? If yes, output 'PROCESS_COMPLETE'. If no, what is the next step? Thinking:"
                reasoning = await self._complete(reasoning_prompt, n_predict=self.reasoning_tokens, stop=["Action:", "User:"])
                logger.info(f"< Re-reasoning: {reasoning.strip()}")
                self.conversation_history.append({"role": "Reasoning", "content": reasoning.strip()})
                
                # Check for STOP condition in reasoning
                reasoning_lower = reasoning.strip().lower()
                if "process_complete" in reasoning_lower:
                    logger.info("Agent decided to STOP based on reasoning (PROCESS_COMPLETE).")
                    break

            # Select a tool
            tool_name = await self._select_tool()
            if not tool_name:
                logger.info("Agent selected NONE, stopping")
                break

            # Execute the tool
            result = await self._execute_tool(tool_name, user_message, reasoning)

            # Add result to history
            self.conversation_history.append({
                "role": "ToolResult",
                "content": f"{tool_name}: {result}"
            })

            # Continue looping to allow multiple tool calls

        # After all iterations, return a summary
        tool_call_count = len([h for h in self.conversation_history if h.get('role') == 'ToolResult'])
        return f"Completed {tool_call_count} tool calls"


def setup_logging(level: int = logging.INFO) -> None:
    """
    Setup logging configuration.

    Args:
        level: Logging level
    """
    logging.basicConfig(
        level=level,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        datefmt='%H:%M:%S'
    )
