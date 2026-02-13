#!/usr/bin/env python3
"""
Validate Python files against a GBNF grammar using an external validator.

Default flow:
- Find a validator binary on PATH (llama-gbnf-validator, gbnf-validator, test-gbnf-validator).
- Validate all .py files under a base directory (skipping common build/cache dirs).
- Report approval percentage.
"""

from __future__ import annotations

import argparse
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
from typing import Iterable, List, Optional, Tuple

DEFAULT_VALIDATORS = [
    "llama-gbnf-validator",
    "gbnf-validator",
    "test-gbnf-validator",
]

SKIP_DIR_NAMES = {
    ".git",
    ".venv",
    "venv",
    "__pycache__",
    "node_modules",
    "dist",
    "build",
    "old",
    "cinfer.egg-info",
    "llama.cpp",
}


def find_validator(explicit: Optional[str]) -> Optional[str]:
    if explicit:
        return explicit
    for name in DEFAULT_VALIDATORS:
        path = shutil.which(name)
        if path:
            return path
    return None


def read_help_text(binary: str) -> str:
    try:
        result = subprocess.run(
            [binary, "--help"],
            check=False,
            capture_output=True,
            text=True,
        )
        return (result.stdout or "") + (result.stderr or "")
    except Exception:
        return ""


def pick_flag(help_text: str, candidates: Iterable[str]) -> Optional[str]:
    for flag in candidates:
        if flag in help_text:
            return flag
    return None


def build_validator_command(
    binary: str,
    grammar_path: Path,
    root_rule: str,
    input_path: Path,
) -> List[str]:
    help_text = read_help_text(binary)

    if "<grammar_filename>" in help_text and "<input_filename>" in help_text:
        return [binary, str(grammar_path), str(input_path)]

    grammar_flag = (
        pick_flag(help_text, ["--grammar", "--grammar-file", "-g"]) or "-g"
    )
    root_flag = pick_flag(help_text, ["--root", "-r"])
    file_flag = pick_flag(help_text, ["--file", "-f", "--input", "-i"])

    cmd = [binary, grammar_flag, str(grammar_path)]
    if root_flag:
        cmd += [root_flag, root_rule]
    if file_flag:
        cmd += [file_flag, str(input_path)]
    else:
        cmd += [str(input_path)]
    return cmd


def iter_python_files(base: Path) -> Iterable[Path]:
    for path in base.rglob("*.py"):
        if any(part in SKIP_DIR_NAMES for part in path.parts):
            continue
        yield path


def validate_file(binary: str, grammar_path: Path, root_rule: str, file_path: Path) -> Tuple[bool, str]:
    cmd = build_validator_command(binary, grammar_path, root_rule, file_path)
    result = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace")
    ok = result.returncode == 0
    output = (result.stdout or "") + (result.stderr or "")
    return ok, output.strip()


def extract_refs(rhs: str) -> List[str]:
    refs: List[str] = []
    buf: List[str] = []
    in_quote = False
    in_class = False

    def flush() -> None:
        if buf:
            token = "".join(buf)
            if token and token[0].islower():
                refs.append(token)
            buf.clear()

    i = 0
    while i < len(rhs):
        c = rhs[i]
        if in_quote:
            if c == "\\":
                i += 2
                continue
            if c == '"':
                in_quote = False
            i += 1
            continue
        if in_class:
            if c == "\\":
                i += 2
                continue
            if c == "]":
                in_class = False
            i += 1
            continue
        if c == '"':
            flush()
            in_quote = True
            i += 1
            continue
        if c == "[":
            flush()
            in_class = True
            i += 1
            continue
        if c.isalnum() or c == "-":
            buf.append(c)
        else:
            flush()
        i += 1
    flush()
    return refs


def sanitize_cycles(grammar_text: str) -> Tuple[str, List[str]]:
    rules = {}
    order: List[str] = []
    for line in grammar_text.splitlines():
        if "::=" not in line:
            continue
        name, rhs = line.split("::=", 1)
        name = name.strip()
        if not name:
            continue
        rules[name] = rhs.strip()
        order.append(name)

    graph = {name: [r for r in extract_refs(rhs) if r in rules] for name, rhs in rules.items()}

    index = 0
    stack: List[str] = []
    on_stack = set()
    index_map = {}
    lowlink = {}
    cycles = set()

    def strongconnect(v: str) -> None:
        nonlocal index
        index_map[v] = index
        lowlink[v] = index
        index += 1
        stack.append(v)
        on_stack.add(v)

        for w in graph.get(v, []):
            if w not in index_map:
                strongconnect(w)
                lowlink[v] = min(lowlink[v], lowlink[w])
            elif w in on_stack:
                lowlink[v] = min(lowlink[v], index_map[w])

        if lowlink[v] == index_map[v]:
            scc = []
            while True:
                w = stack.pop()
                on_stack.remove(w)
                scc.append(w)
                if w == v:
                    break
            if len(scc) > 1:
                cycles.update(scc)
            elif len(scc) == 1:
                w = scc[0]
                if w in graph.get(w, []):
                    cycles.add(w)

    for node in rules:
        if node not in index_map:
            strongconnect(node)

    if not cycles:
        return grammar_text, []

    fallback = "fallback ::= tok-name | tok-number | tok-string"
    out_lines = []
    for line in grammar_text.splitlines():
        if "::=" in line:
            name, _rhs = line.split("::=", 1)
            name = name.strip()
            if name in cycles:
                out_lines.append(f"{name} ::= fallback")
                continue
        out_lines.append(line)

    if not any(l.strip().startswith("fallback ::=") for l in out_lines):
        out_lines.append(fallback)

    return "\n".join(out_lines) + "\n", sorted(cycles)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Validate Python files using a GBNF grammar.")
    parser.add_argument("--grammar", default="grammar/python_grammar/python.gbnf")
    parser.add_argument("--root", default="root")
    parser.add_argument("--base", default=".")
    parser.add_argument("--validator", default=None)
    parser.add_argument("--limit", type=int, default=0, help="Limit files checked (0 = no limit).")
    parser.add_argument("--no-sanitize-cycles", action="store_true", help="Disable cycle sanitization.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    grammar_path = Path(args.grammar).resolve()
    base_path = Path(args.base).resolve()

    if not grammar_path.exists():
        print(f"Grammar not found: {grammar_path}", file=sys.stderr)
        return 2

    validator = find_validator(args.validator)
    if not validator:
        print(
            "No GBNF validator found on PATH. Install/build one from llama.cpp or "
            "pass --validator /path/to/validator.",
            file=sys.stderr,
        )
        return 2

    files = list(iter_python_files(base_path))
    if args.limit > 0:
        files = files[: args.limit]

    if not files:
        print("No Python files found.")
        return 0

    grammar_text = grammar_path.read_text()
    cycle_rules: List[str] = []
    if not args.no_sanitize_cycles:
        grammar_text, cycle_rules = sanitize_cycles(grammar_text)
        if cycle_rules:
            print(f"Sanitized {len(cycle_rules)} cyclic rules for GBNF compatibility.")

    if cycle_rules:
        temp = tempfile.NamedTemporaryFile("w", delete=False)
        temp.write(grammar_text)
        temp.flush()
        grammar_for_validation = Path(temp.name)
    else:
        grammar_for_validation = grammar_path

    approved = 0
    total = len(files)
    failed_samples = []

    for path in files:
        ok, output = validate_file(validator, grammar_for_validation, args.root, path)
        if ok:
            approved += 1
        else:
            if len(failed_samples) < 5:
                failed_samples.append((path, output))

    percent = (approved / total) * 100.0
    print(f"Approved: {approved}/{total} ({percent:.2f}%)")
    if failed_samples:
        print("\nSample failures:")
        for path, output in failed_samples:
            print(f"- {path}")
            if output:
                first_line = output.splitlines()[0]
                print(f"  {first_line}")

    return 0 if approved == total else 1


if __name__ == "__main__":
    raise SystemExit(main())
