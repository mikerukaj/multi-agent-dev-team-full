# Security

The agents write and run code, and they hold an API key. This is how each risk is contained: generated code runs only in a locked-down sandbox, file access goes through a server that enforces its own rules, and secrets are scrubbed from everything the team writes.

## The sandbox: where generated code runs

The agents run code they wrote themselves, and that code is untrusted. **It never runs on
your machine directly.** Every Coder `exec_python` call and every QA test run starts a
fresh, throwaway Docker container that:

- has **no network** (`--network none`), so nothing can be downloaded or sent out;
- has **no secrets**: the only environment variables are three harmless Python settings,
  and the agent's own process (which holds your API key) is not visible inside it;
- sees **only that run's workspace** (`workspace/<run_id>/`, mounted at `/work`), with
  `tests/` read-only; the rest of the filesystem is the read-only sandbox image;
- runs as your user ID, never root, with all Linux capabilities dropped and
  `no-new-privileges`;
- is limited to 512 MB of memory, 1 CPU, and 128 processes, and is killed at the time
  limit (30 s for Coder runs, 60 s for a QA test run by default);
- uses the project's sandbox image: the `python:3.12-slim` base pinned by digest plus
  pytest 9.1.1, built locally from `sandbox/Dockerfile`.

If Docker is not available, the agents refuse to start rather than run code unsandboxed.
No sandbox container is given the Docker socket; the application container is, as a
documented trust exception (see [DEPLOYMENT.md](DEPLOYMENT.md)). The PM
Agent runs no code. Every sandbox container is labelled with its run ID, so a stopped
run's containers are killed, and those left by runs that died are removed at the next
start-up.

## File access through MCP

Both agents read and write files only through the MCP file-tool server
(`tools/mcp_server.py`), started for one workspace per session. It refuses any path that
leaves the workspace (absolute paths, `..`, or links pointing out). The Coder's sessions
run with `tests/` and `.qa/` protected, so the Coder can't change QA's tests: a write
there is refused with `Path is protected: … (only the QA Agent may change tests)`. The
server gets an environment with only `PATH` and `PYTHONIOENCODING`, never reads `.env`,
and if it can't start, the session fails rather than falling back to direct file access.
See [ARCHITECTURE.md](ARCHITECTURE.md#messaging-and-tools).

## Secrets

The API key is read from the environment (or `.env`, which is git-ignored and never
copied into an image) at run time. The value of every environment variable whose name
contains `KEY`, `TOKEN`, `SECRET`, `PASSWORD` or `CREDENTIAL` (8 or more characters), and
any text shaped like an Anthropic key, is replaced by `[REDACTED]` in events, error
messages, run records, checkpoints, QA reports, cost reports and everything sent to
LangSmith. `tests/test_secret_sweep.py` plants secrets in a full run and checks that none
reaches any output, and `tests/test_docs.py` scans every published file.

## The Docker-socket trust exception

Under Docker Compose, the `agent` container gets the host's Docker socket so it can start
sandbox containers. **Access to that socket is equivalent to root on the host.** Only the
agent gets it, never Chroma and never a sandbox. See [DEPLOYMENT.md](DEPLOYMENT.md) for
the ways to limit that exposure.
