"""The deployment definition keeps its invariants (contracts/deployment.md, FR-227-FR-233).

The Dockerfile checks need no Docker. The Compose checks read
``docker compose config --format json`` and skip, with a reason, without Docker Compose.
The Compose file is resolved in a temporary folder with a ``.env`` made from
``.env.example``, so the developer's own ``.env`` (which holds real secrets) never changes
the result or reaches the output (FR-013).
"""

import json
import os
import re
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
SECRET_NAME = re.compile("KEY|TOKEN|SECRET|PASSWORD|CREDENTIAL", re.IGNORECASE)
SOCKET = "/var/run/docker.sock"


def compose_available() -> bool:
    if shutil.which("docker") is None:
        return False
    probe = subprocess.run(["docker", "compose", "version"], capture_output=True, check=False)
    return probe.returncode == 0


def isolated_env_file(overrides: dict[str, str]) -> str:
    """``.env.example`` with ``overrides`` applied: the run-time file Compose reads."""
    lines = []
    for line in (REPO_ROOT / ".env.example").read_text(encoding="utf-8").splitlines():
        key = line.split("=", 1)[0]
        lines.append(f"{key}={overrides[key]}" if key in overrides else line)
    return "\n".join(lines) + "\n"


def resolve_compose(env_text: str) -> dict:
    """The resolved Compose services, read in a temporary folder holding ``env_text``."""
    env = {**os.environ, "PWD": str(REPO_ROOT)}
    with tempfile.TemporaryDirectory() as folder:
        shutil.copy(REPO_ROOT / "docker-compose.yml", folder)
        (Path(folder) / ".env").write_text(env_text, encoding="utf-8")
        result = subprocess.run(
            ["docker", "compose", "config", "--format", "json"], cwd=folder, env=env,
            capture_output=True, text=True, check=True,
        )
    return json.loads(result.stdout)["services"]


def secret_settings(services: dict) -> list[str]:
    """``<service> sets <KEY>`` for every non-empty secret-named setting; never the value."""
    return [f"{name} sets {key}" for name, service in services.items()
            for key, value in (service.get("environment") or {}).items()
            if SECRET_NAME.search(key) and value]


class DockerfileTests(unittest.TestCase):
    def setUp(self) -> None:
        self.text = (REPO_ROOT / "Dockerfile").read_text(encoding="utf-8")
        self.stages = re.findall(r"^FROM\s+(\S+)(?:\s+AS\s+(\S+))?", self.text, re.M)

    def test_external_images_are_pinned_by_digest(self) -> None:
        stage_names = {name for _, name in self.stages if name}
        external = [image for image, _ in self.stages if image not in stage_names]
        external += re.findall(r"COPY\s+--from=(\S+)", self.text)
        self.assertTrue(external)
        for image in external:
            self.assertIn("@sha256:", image, image)

    def test_the_last_stage_is_runtime_and_a_test_stage_exists(self) -> None:
        names = [name for _, name in self.stages]
        self.assertIn("test", names)
        self.assertEqual(names[-1], "runtime")

    def test_the_image_runs_as_a_non_root_user(self) -> None:
        users = re.findall(r"^USER\s+(\S+)", self.text, re.M)
        self.assertTrue(users)
        app_stage = self.text.split("FROM app AS test")[0]
        self.assertNotIn(re.findall(r"^USER\s+(\S+)", app_stage, re.M)[-1], ("root", "0"))

    def test_secrets_are_never_copied_in(self) -> None:
        ignored = (REPO_ROOT / ".dockerignore").read_text(encoding="utf-8").split()
        self.assertIn(".env*", ignored)
        self.assertNotRegex(self.text, r"(?i)ANTHROPIC_API_KEY\s*=")


@unittest.skipUnless(compose_available(), "Docker Compose is not available")
class ComposeConfigTests(unittest.TestCase):
    IDS = {"HOST_UID": "1000", "HOST_GID": "1000", "DOCKER_GID": "999"}

    @classmethod
    def setUpClass(cls) -> None:
        cls.services = resolve_compose(isolated_env_file(cls.IDS))

    def test_the_agent_waits_for_a_healthy_chroma(self) -> None:
        self.assertEqual(self.services["agent"]["depends_on"]["chroma"]["condition"],
                         "service_healthy")
        self.assertIn("healthcheck", self.services["chroma"])

    def test_only_the_agent_gets_the_docker_socket(self) -> None:
        for name, service in self.services.items():
            sources = [volume.get("source") for volume in service.get("volumes", [])]
            self.assertEqual(SOCKET in sources, name == "agent", name)

    def test_no_secret_is_set_in_any_environment(self) -> None:
        self.assertEqual(secret_settings(self.services), [])

    def test_a_planted_secret_is_reported_by_name_never_by_value(self) -> None:
        planted = "sk-ant-test-PLANTED0000"
        services = resolve_compose(isolated_env_file({**self.IDS, "ANTHROPIC_API_KEY": planted}))
        messages = secret_settings(services)
        self.assertIn("agent sets ANTHROPIC_API_KEY", messages)
        self.assertNotIn(planted, "\n".join(messages))

    def test_pulled_images_are_pinned_and_nothing_is_published(self) -> None:
        self.assertIn("@sha256:", self.services["chroma"]["image"])
        for name, service in self.services.items():
            self.assertNotIn("ports", service, name)

    def test_the_workspace_path_is_the_same_inside_and_out(self) -> None:
        workspace = [volume for volume in self.services["agent"]["volumes"]
                     if str(volume.get("source", "")).endswith("/workspace")]
        self.assertEqual(len(workspace), 1)
        self.assertEqual(workspace[0]["source"], workspace[0]["target"])

    def test_the_agent_builds_the_runtime_stage(self) -> None:
        self.assertEqual(self.services["agent"]["build"]["target"], "runtime")


if __name__ == "__main__":
    unittest.main()
