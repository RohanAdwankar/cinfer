Python Sandbox Benchmark

This benchmark compares Cinfer's @depends_language against a minimal LangChain baseline
when all Python execution is forced into a locked-down Docker container.

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

- To allow only a single model URL from inside the sandbox, set:
  CINFER_SANDBOX_ALLOW_URL=http://127.0.0.1:8080
  This will block other URLs and rewrite 127.0.0.1 to host.docker.internal for the container.
