import os
import re
import shutil
import subprocess
import tempfile
from pathlib import Path

DEFAULT_IMAGE = "cinfer-python-sandbox"
DEFAULT_TIMEOUT = 15
DEFAULT_NETWORK = "none"


def run_python_in_container(code: str, data_dir: Path, timeout: int = DEFAULT_TIMEOUT) -> str:
    if not shutil.which("docker"):
        raise RuntimeError("docker is required to run the sandbox")

    image = os.environ.get("CINFER_SANDBOX_IMAGE", DEFAULT_IMAGE)
    network = os.environ.get("CINFER_SANDBOX_NETWORK", DEFAULT_NETWORK)
    allow_url = os.environ.get("CINFER_SANDBOX_ALLOW_URL")

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
