import os
import re
import shutil
import subprocess
import tempfile
from pathlib import Path

DEFAULT_IMAGE = "cinfer-python-sandbox"
DEFAULT_TIMEOUT = 15
DEFAULT_NETWORK = "none"


def wrap_benchmark_code(code: str) -> str:
    indented = "\n".join(f"    {line}" for line in code.strip().splitlines())
    return "\n".join(
        [
            "import contextlib",
            "import io",
            "import json",
            "import ast",
            "import pandas as pd",
            "",
            "def _patched_read_csv(path, *args, **kwargs):",
            "    if path in ('sales.csv', 'sales_data.csv'):",
            "        path = '/input/sales.csv'",
            "    elif path in ('regions.csv', 'regions_data.csv'):",
            "        path = '/input/regions.csv'",
            "    return _original_read_csv(path, *args, **kwargs)",
            "",
            "_original_read_csv = pd.read_csv",
            "pd.read_csv = _patched_read_csv",
            "",
            "sales_df = pd.read_csv('/input/sales.csv')",
            "regions_df = pd.read_csv('/input/regions.csv')",
            "",
            "_stdout = io.StringIO()",
            "with contextlib.redirect_stdout(_stdout):",
            indented if indented else "    pass",
            "",
            "def _cinfer_get_result():",
            "    if 'RESULT' in globals():",
            "        return RESULT",
            "    if 'solve' in globals():",
            "        return solve(sales_df, regions_df)",
            "    if 'run_python' in globals():",
            "        return run_python(sales_df, regions_df)",
            "    return None",
            "",
            "def _maybe_parse_json(text):",
            "    text = text.strip()",
            "    if not text:",
            "        return None",
            "    if text.startswith('ERROR') or 'Traceback' in text:",
            "        return text",
            "    start = text.find('{')",
            "    alt_start = text.find('[')",
            "    if start == -1 or (alt_start != -1 and alt_start < start):",
            "        start = alt_start",
            "    if start == -1:",
            "        start = 0",
            "    candidate = text[start:]",
            "    try:",
            "        return json.loads(candidate)",
            "    except Exception:",
            "        pass",
            "    try:",
            "        literal = ast.literal_eval(candidate)",
            "        if isinstance(literal, tuple):",
            "            return list(literal)",
            "        return literal",
            "    except Exception:",
            "        pass",
            "    try:",
            "        if '.' in text:",
            "            return float(text)",
            "        return int(text)",
            "    except Exception:",
            "        return text",
            "",
            "result = _cinfer_get_result()",
            "if result is None:",
            "    result = _maybe_parse_json(_stdout.getvalue())",
            "elif isinstance(result, str):",
            "    result = _maybe_parse_json(result)",
            "",
            "print(json.dumps(result))",
            "",
        ]
    )


def run_python_in_container(code: str, data_dir: Path, timeout: int = DEFAULT_TIMEOUT) -> str:
    if not shutil.which("docker"):
        raise RuntimeError("docker is required to run the sandbox")

    image = os.environ.get("CINFER_SANDBOX_IMAGE", DEFAULT_IMAGE)
    network = os.environ.get("CINFER_SANDBOX_NETWORK", DEFAULT_NETWORK)
    allow_url = os.environ.get("CINFER_SANDBOX_ALLOW_URL", "http://127.0.0.1:8080")

    if allow_url:
        url_pattern = re.compile(r"https?://[^\s'\"\\)]+")
        found = url_pattern.findall(code)
        for url in found:
            if not url.startswith(allow_url):
                return f"ERROR: disallowed url {url} (only {allow_url} is permitted)"

        if allow_url.startswith("http://127.0.0.1:8080"):
            code = code.replace("http://127.0.0.1:8080", "http://host.docker.internal:8080")

    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp_path = Path(tmp_dir)
        code_path = tmp_path / "code.py"
        code_path.write_text(code, encoding="utf-8")

        cmd = [
            "docker",
            "run",
            "--rm",
            "--network",
            network,
        ]

        if allow_url and network != "none":
            cmd += ["--add-host", "host.docker.internal:host-gateway"]

        cmd += [
            "--memory",
            "512m",
            "--pids-limit",
            "256",
            "--cpus",
            "1",
            "--read-only",
            "--cap-drop",
            "ALL",
            "--security-opt",
            "no-new-privileges",
            "-v",
            f"{data_dir}:/input:ro",
            "-v",
            f"{tmp_path}:/workspace:rw",
            image,
            "python",
            "/workspace/code.py",
        ]

        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=timeout,
                check=False,
            )
        except subprocess.TimeoutExpired as exc:
            return f"ERROR: timeout after {timeout}s"

        if result.returncode != 0:
            stderr = result.stderr.strip()
            stdout = result.stdout.strip()
            details = stderr or stdout or "unknown error"
            return f"ERROR: sandbox failed ({result.returncode}): {details}"

        return result.stdout
