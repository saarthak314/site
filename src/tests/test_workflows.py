import re
import unittest
from pathlib import Path

import yaml

PROJECT_ROOT = Path(__file__).resolve().parents[2]
WORKFLOW_DIR = PROJECT_ROOT / ".github" / "workflows"
FULL_SHA = re.compile(r"^[0-9a-f]{40}$")


def read_repository_file(relative_path: str) -> str:
  return PROJECT_ROOT.joinpath(relative_path).read_text(encoding="utf-8")


def load_yaml(relative_path: str):
  return yaml.load(read_repository_file(relative_path), Loader=yaml.BaseLoader)


def action_references(workflow_text: str) -> list[tuple[str, str]]:
  references = []
  for line in workflow_text.splitlines():
    stripped = line.strip()
    if not stripped.startswith("uses:"):
      continue
    reference = stripped.removeprefix("uses:").strip().split()[0]
    action, revision = reference.rsplit("@", 1)
    references.append((action, revision))
  return references


class TestWorkflowConfiguration(unittest.TestCase):
  def assert_actions_are_pinned(self, workflow_text: str) -> None:
    references = action_references(workflow_text)
    self.assertTrue(references)
    for action, revision in references:
      self.assertRegex(revision, FULL_SHA, action)

  def test_ci_workflow_checks_supported_python_versions(self) -> None:
    workflow_text = read_repository_file(".github/workflows/ci.yml")
    workflow = load_yaml(".github/workflows/ci.yml")

    self.assertIn("pull_request", workflow["on"])
    self.assertIn("push", workflow["on"])
    self.assertEqual(
      workflow["jobs"]["verify"]["strategy"]["matrix"]["python-version"],
      ["3.11", "3.13"],
    )
    self.assertEqual(list(workflow["jobs"]), ["verify"])
    self.assertIn("astral-sh/setup-uv", workflow_text)
    self.assertIn("uv sync --frozen --dev", workflow_text)
    self.assertIn("./scripts/verify.sh", workflow_text)
    self.assertIn("contents: read", workflow_text)
    branch_concurrency = "$" + "{{ github.workflow }}-" + "$" + "{{ github.ref }}"
    self.assertEqual(workflow["concurrency"]["group"], branch_concurrency)
    self.assert_actions_are_pinned(workflow_text)

  def test_deployment_workflow_uses_pages_artifacts_and_smoke_tests(self) -> None:
    workflow_text = read_repository_file(".github/workflows/deploy.yml")
    workflow = load_yaml(".github/workflows/deploy.yml")

    self.assertEqual(workflow["on"]["push"]["branches"], ["main"])
    self.assertIn("workflow_dispatch", workflow["on"])
    self.assertNotIn("pull_request", workflow["on"])
    self.assertIn("contents: read", workflow_text)
    self.assertIn("pages: write", workflow_text)
    self.assertIn("id-token: write", workflow_text)
    self.assertIn("environment:\n      name: github-pages", workflow_text)
    self.assertIn("actions/configure-pages", workflow_text)
    self.assertIn("actions/upload-pages-artifact", workflow_text)
    self.assertIn("actions/deploy-pages", workflow_text)
    self.assertIn("astral-sh/setup-uv", workflow_text)
    self.assertIn("uv sync --frozen --dev", workflow_text)
    self.assertIn("./scripts/verify.sh", workflow_text)
    self.assertIn("path: docs", workflow_text)
    self.assertIn("cancel-in-progress: false", workflow_text)
    self.assertIn("uv run python -m sitegen.smoke", workflow_text)
    self.assertIn('--base-url "https://sarrthak.com"', workflow_text)
    self.assertNotIn("curl --fail", workflow_text)
    self.assert_actions_are_pinned(workflow_text)

  def test_scheduled_link_check_builds_and_checks_external_links(self) -> None:
    workflow_text = read_repository_file(".github/workflows/links.yml")
    workflow = load_yaml(".github/workflows/links.yml")

    self.assertIn("schedule", workflow["on"])
    self.assertIn("workflow_dispatch", workflow["on"])
    self.assertIn("astral-sh/setup-uv", workflow_text)
    self.assertIn("uv sync --frozen", workflow_text)
    self.assertIn("sitegen build --no-incremental", workflow_text)
    self.assertIn("lycheeverse/lychee-action", workflow_text)
    self.assertIn("docs/**/*.html", workflow_text)
    self.assert_actions_are_pinned(workflow_text)

  def test_shared_verification_script_covers_style_tests_and_build(self) -> None:
    script = read_repository_file("scripts/verify.sh")

    self.assertIn("uv run ruff check .", script)
    self.assertIn("uv run ruff format --check .", script)
    self.assertIn("uv run python -m unittest discover -s src -p 'test*.py'", script)
    self.assertIn("uv run python -m compileall -q src", script)
    self.assertIn("uv run sitegen build --no-incremental", script)
    self.assertIn("uv run sitegen check", script)
    self.assertIn("git diff --check", script)

  def test_dependabot_updates_python_and_actions_dependencies(self) -> None:
    configuration = load_yaml(".github/dependabot.yml")
    ecosystems = {update["package-ecosystem"] for update in configuration["updates"]}

    self.assertEqual(ecosystems, {"pip", "github-actions"})
    for update in configuration["updates"]:
      self.assertEqual(update["schedule"]["interval"], "weekly")
      self.assertEqual(update["open-pull-requests-limit"], "5")

  def test_readme_documents_uv_scaffolding_and_asset_optimization(self) -> None:
    readme = read_repository_file("README.md")

    self.assertIn("uv sync --dev", readme)
    self.assertIn("uv run sitegen dev --open", readme)
    self.assertIn("uv run sitegen new", readme)
    self.assertIn("uv run python scripts/optimize_images.py", readme)

  def test_generated_site_is_ignored_but_custom_domain_is_source_controlled(
    self,
  ) -> None:
    ignored = read_repository_file(".gitignore").splitlines()

    self.assertIn("docs/", ignored)
    self.assertIn(".venv/", ignored)
    self.assertTrue(PROJECT_ROOT.joinpath("static/CNAME").is_file())
    self.assertTrue(PROJECT_ROOT.joinpath("uv.lock").is_file())


if __name__ == "__main__":
  unittest.main()
