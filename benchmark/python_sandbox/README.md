Python Sandbox Benchmark

This benchmark compares Cinfer's @depends_language against a minimal LangChain baseline
when all Python execution is forced into a locked-down Docker container.

The benchmark is intentionally simple (4 short tasks) to show model reliability differences,
not complex reasoning limits:
- sales DataFrame shape
- first region name
- quantity sum
- East region id lookup

Setup
- Build the sandbox image:
  docker build -t cinfer-python-sandbox benchmark/python_sandbox/docker

- Run the benchmark:
  PYTHONPATH=. .venv/bin/python benchmark/python_sandbox/main.py

Sandbox notes
- The Python tool always executes inside Docker with:
  - read-only filesystem
  - all caps dropped
  - no-new-privileges
  - CPU/memory limits
  - network disabled by default

- To change network mode, set CINFER_SANDBOX_NETWORK (default: none).
  If you enable networking, access host services via host.docker.internal.

- Model endpoint is locked to `http://127.0.0.1:8080` in benchmark code.

- URL access from Python code run in the container is restricted to
  `http://127.0.0.1:8080` by default (override with `CINFER_SANDBOX_ALLOW_URL` only if needed).
  When networking is enabled, the sandbox rewrites `127.0.0.1` to `host.docker.internal`.
