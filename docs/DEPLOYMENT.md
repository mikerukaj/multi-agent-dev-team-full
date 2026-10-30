# Deployment

Running the team in containers: the application image and the Docker Compose file that runs it with a Chroma server.

## Docker Compose

The image (`Dockerfile`) is pinned by digest, runs as a non-root user, contains no
secrets and has Chroma's embedding model baked in. `docker-compose.yml` runs two
services: **`chroma`** (the Coder's long-term memory, with a health check) and the
one-shot **`agent`**, which starts only once Chroma is healthy.

**Prerequisites:** Docker Engine 24+ with Compose v2. Copy `.env.example` to `.env` and
fill in `ANTHROPIC_API_KEY`, `HOST_UID=$(id -u)`, `HOST_GID=$(id -g)` and
`DOCKER_GID=$(stat -c %g /var/run/docker.sock)` (on macOS, `stat -f %g`).

```bash
docker compose up --build --abort-on-container-exit --exit-code-from agent   # one run of TEAM_REQUIREMENT
docker compose run --rm agent "Write a word-count CLI for a text file"         # another requirement
docker compose run --rm agent --resume <run_id>                                # resume a run
docker compose run --rm --entrypoint python agent -m orchestration.health      # check prerequisites
```

Workspaces, run records, cost reports, benchmark results and the response cache are bind
mounts, so they stay on the host; the memory is the `chroma-data` volume. The workspace
is mounted at the same absolute path inside the container, so the sandbox's bind mounts
resolve on the host.

**Trust exception.** The `agent` container gets the host's Docker socket so it
can start sandbox containers through the host engine. **Access to that socket is
equivalent to root on the host.** Only the agent gets it, never Chroma and never a
sandbox, and generated code still sees only its own run's workspace. To limit the
exposure, run the deployment on a dedicated host or VM, use rootless Docker, or put a
socket proxy in front that allows only container create, start, wait, kill and delete,
images and build.

**Upgrade:** `git pull && docker compose build --pull`, then run as above; the Chroma
volume persists (bump the `chromadb` package and the server image together).
**Removal:** `docker compose down -v` and
`docker image rm multi-agent-lab:local multi-agent-sandbox:py3.12-pytest9.1.1`; the
workspaces and reports on the host are yours to delete.

**Embedded or server Chroma.** Outside Compose, memory is an embedded store in
`CODER_CHROMA_PATH`, which supports **one run at a time**. For concurrent runs, use the
Compose Chroma service or a Chroma server (`CHROMA_HOST`, `CHROMA_PORT`).

`python -m orchestration.health [--json]` checks credentials, Docker, the sandbox image,
a writable workspace and cost-report folder, Chroma and the price table without a model
call; every team run does the same before it starts.

## Running the test suite in the image

The image's `test` stage adds the development tools. Build it and run the suite inside
it, with the same Docker access the agent has (set `HOST_UID`, `HOST_GID` and
`DOCKER_GID` as above):

```bash
docker build --target test -t multi-agent-lab:test .
docker run --rm --user "$HOST_UID:$HOST_GID" --group-add "$DOCKER_GID" \
  -v /var/run/docker.sock:/var/run/docker.sock \
  -v "$PWD/workspace:$PWD/workspace" -e CODER_WORKSPACE="$PWD/workspace" \
  -e QA_OUTPUT_ROOT="$PWD/workspace/.qa-out" \
  --entrypoint scripts/test.sh multi-agent-lab:test
```

## What the deployment guarantees

`tests/integration/test_compose_config.py` checks the definition on every run of the
suite: every pulled image is pinned by digest, the image runs as a non-root user and
holds no secrets, only the agent gets the Docker socket, no ports are published, the
workspace path is the same inside and out, and the agent builds the `runtime` stage.
