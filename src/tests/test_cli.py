import importlib
import io
import sys
import tempfile
import types
import unittest
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from types import SimpleNamespace


@dataclass(frozen=True)
class FakeBuildOptions:
  include_drafts: bool = False
  incremental: bool = True


class PlaceholderBuilder:
  def __init__(self, project_root: Path) -> None:
    self.project_root = project_root


class PlaceholderValidator:
  pass


@contextmanager
def import_sitegen_module(module_name: str) -> Iterator[types.ModuleType]:
  injected = {
    "sitegen.build": types.ModuleType("sitegen.build"),
    "sitegen.validate": types.ModuleType("sitegen.validate"),
  }
  injected["sitegen.build"].BuildOptions = FakeBuildOptions
  injected["sitegen.build"].SiteBuilder = PlaceholderBuilder
  injected["sitegen.validate"].SiteValidator = PlaceholderValidator
  managed_names = (*injected, "sitegen.cli", "sitegen.server")
  saved_modules = {name: sys.modules.get(name) for name in managed_names}

  for name in ("sitegen.cli", "sitegen.server"):
    sys.modules.pop(name, None)
  sys.modules.update(injected)

  try:
    yield importlib.import_module(module_name)
  finally:
    for name in managed_names:
      sys.modules.pop(name, None)
      if saved_modules[name] is not None:
        sys.modules[name] = saved_modules[name]


class RecordingBuilder:
  instances: list["RecordingBuilder"] = []
  error: Exception | None = None

  def __init__(self, project_root: Path) -> None:
    self.project_root = project_root
    self.options: list[FakeBuildOptions] = []
    self.output_dir = project_root / "docs"
    self.__class__.instances.append(self)

  def build(self, options: FakeBuildOptions) -> SimpleNamespace:
    self.options.append(options)
    if self.__class__.error is not None:
      raise self.__class__.error
    return SimpleNamespace(rendered=3, reused=2, output_dir=self.output_dir)


class FormattedIssue:
  def __init__(self, message: str) -> None:
    self.message = message

  def format(self) -> str:
    return self.message


class RecordingValidator:
  instances: list["RecordingValidator"] = []
  issues: list[FormattedIssue] = []

  def __init__(self) -> None:
    self.roots: list[Path] = []
    self.__class__.instances.append(self)

  def validate(self, root: Path) -> list[FormattedIssue]:
    self.roots.append(root)
    return list(self.__class__.issues)


class CliTestCase(unittest.TestCase):
  def setUp(self) -> None:
    RecordingBuilder.instances = []
    RecordingBuilder.error = None
    RecordingValidator.instances = []
    RecordingValidator.issues = []

  def run_cli(
    self,
    cli: types.ModuleType,
    arguments: list[str],
    project_root: Path,
    **overrides: object,
  ) -> tuple[int, str, str]:
    stdout = io.StringIO()
    stderr = io.StringIO()
    exit_code = cli.main(
      arguments,
      project_root=project_root,
      builder_factory=RecordingBuilder,
      validator_factory=RecordingValidator,
      stdout=stdout,
      stderr=stderr,
      **overrides,
    )
    return exit_code, stdout.getvalue(), stderr.getvalue()


class TestBuildCommand(CliTestCase):
  def test_build_defaults_to_incremental_with_drafts(self) -> None:
    with tempfile.TemporaryDirectory() as temp_dir:
      project_root = Path(temp_dir)
      with import_sitegen_module("sitegen.cli") as cli:
        exit_code, stdout, _ = self.run_cli(cli, ["build"], project_root)

    self.assertEqual(exit_code, 0)
    self.assertEqual(RecordingBuilder.instances[0].project_root, project_root)
    self.assertEqual(
      RecordingBuilder.instances[0].options,
      [FakeBuildOptions(include_drafts=True, incremental=True)],
    )
    self.assertIn("built 3 page(s), reused 2", stdout)
    self.assertIn(str(project_root / "docs"), stdout)

  def test_build_flags_exclude_drafts_and_disable_incremental(self) -> None:
    with tempfile.TemporaryDirectory() as temp_dir:
      project_root = Path(temp_dir)
      with import_sitegen_module("sitegen.cli") as cli:
        exit_code, _, _ = self.run_cli(
          cli,
          ["build", "--no-drafts", "--no-incremental"],
          project_root,
        )

    self.assertEqual(exit_code, 0)
    self.assertEqual(
      RecordingBuilder.instances[0].options,
      [FakeBuildOptions(include_drafts=False, incremental=False)],
    )

  def test_build_error_returns_nonzero_and_reports_the_failure(self) -> None:
    RecordingBuilder.error = RuntimeError("render exploded")

    with tempfile.TemporaryDirectory() as temp_dir:
      with import_sitegen_module("sitegen.cli") as cli:
        exit_code, stdout, stderr = self.run_cli(
          cli,
          ["build"],
          Path(temp_dir),
        )

    self.assertNotEqual(exit_code, 0)
    self.assertIn("render exploded", stdout + stderr)


class TestCheckCommand(CliTestCase):
  def test_check_build_error_returns_nonzero_without_validation(self) -> None:
    RecordingBuilder.error = RuntimeError("content invalid")

    with tempfile.TemporaryDirectory() as temp_dir:
      with import_sitegen_module("sitegen.cli") as cli:
        exit_code, stdout, stderr = self.run_cli(
          cli,
          ["check"],
          Path(temp_dir),
        )

    self.assertNotEqual(exit_code, 0)
    self.assertIn("content invalid", stdout + stderr)
    self.assertEqual(RecordingValidator.instances, [])

  def test_check_uses_the_builders_validation_once(self) -> None:
    with tempfile.TemporaryDirectory() as temp_dir:
      project_root = Path(temp_dir)
      with import_sitegen_module("sitegen.cli") as cli:
        exit_code, stdout, stderr = self.run_cli(
          cli,
          ["check", "--no-drafts"],
          project_root,
        )

    self.assertEqual(exit_code, 0, stdout + stderr)
    self.assertEqual(
      RecordingBuilder.instances[0].options,
      [FakeBuildOptions(include_drafts=False, incremental=True)],
    )
    self.assertEqual(RecordingValidator.instances, [])

  def test_check_returns_zero_when_the_generated_site_is_valid(self) -> None:
    with tempfile.TemporaryDirectory() as temp_dir:
      with import_sitegen_module("sitegen.cli") as cli:
        exit_code, _, _ = self.run_cli(cli, ["check"], Path(temp_dir))

    self.assertEqual(exit_code, 0)


class TestNewCommand(CliTestCase):
  def test_new_scaffolds_a_draft_post(self) -> None:
    with tempfile.TemporaryDirectory() as temp_dir:
      project_root = Path(temp_dir)
      with import_sitegen_module("sitegen.cli") as cli:
        exit_code, stdout, stderr = self.run_cli(
          cli,
          ["new", "better-builds", "--title", "better builds"],
          project_root,
        )

      post = project_root / "content/blogs/better-builds/index.md"
      content = post.read_text()

    self.assertEqual(exit_code, 0, stdout + stderr)
    self.assertIn("title: better builds", content)
    self.assertIn(f"date: {date.today().isoformat()}", content)
    self.assertIn("draft: true", content)
    self.assertIn("created", stdout)

  def test_new_rejects_existing_or_invalid_slugs(self) -> None:
    with tempfile.TemporaryDirectory() as temp_dir:
      project_root = Path(temp_dir)
      existing = project_root / "content/blogs/existing"
      existing.mkdir(parents=True)
      existing.joinpath("index.md").write_text("existing")
      with import_sitegen_module("sitegen.cli") as cli:
        existing_result = self.run_cli(cli, ["new", "existing"], project_root)
        invalid_result = self.run_cli(cli, ["new", "Bad Slug"], project_root)

    self.assertNotEqual(existing_result[0], 0)
    self.assertIn("already exists", existing_result[1] + existing_result[2])
    self.assertNotEqual(invalid_result[0], 0)
    self.assertIn("invalid slug", invalid_result[1] + invalid_result[2])


class TestServeCommand(CliTestCase):
  def test_serve_uses_local_defaults(self) -> None:
    calls: list[tuple[str, int, bool]] = []

    def fake_serve(
      _project_root: Path,
      _options: FakeBuildOptions,
      *,
      host: str,
      port: int,
      watch: bool,
      **_: object,
    ) -> int:
      calls.append((host, port, watch))
      return 0

    with tempfile.TemporaryDirectory() as temp_dir:
      with import_sitegen_module("sitegen.cli") as cli:
        exit_code, _, _ = self.run_cli(
          cli,
          ["serve"],
          Path(temp_dir),
          serve_func=fake_serve,
        )

    self.assertEqual(exit_code, 0)
    self.assertEqual(calls, [("127.0.0.1", 8888, False)])

  def test_serve_passes_network_watch_and_draft_options(self) -> None:
    calls: list[tuple[Path, FakeBuildOptions, str, int, bool]] = []

    def fake_serve(
      project_root: Path,
      options: FakeBuildOptions,
      *,
      host: str,
      port: int,
      watch: bool,
      **_: object,
    ) -> int:
      calls.append((project_root, options, host, port, watch))
      return 0

    with tempfile.TemporaryDirectory() as temp_dir:
      project_root = Path(temp_dir)
      with import_sitegen_module("sitegen.cli") as cli:
        exit_code, _, _ = self.run_cli(
          cli,
          [
            "serve",
            "--no-drafts",
            "--watch",
            "--host",
            "0.0.0.0",
            "--port",
            "4321",
          ],
          project_root,
          serve_func=fake_serve,
        )

    self.assertEqual(exit_code, 0)
    self.assertEqual(
      calls,
      [
        (
          project_root,
          FakeBuildOptions(include_drafts=False, incremental=True),
          "0.0.0.0",
          4321,
          True,
        )
      ],
    )

  def test_serve_error_returns_nonzero_and_reports_the_failure(self) -> None:
    def broken_serve(*_: object, **__: object) -> int:
      raise RuntimeError("port unavailable")

    with tempfile.TemporaryDirectory() as temp_dir:
      with import_sitegen_module("sitegen.cli") as cli:
        exit_code, stdout, stderr = self.run_cli(
          cli,
          ["serve"],
          Path(temp_dir),
          serve_func=broken_serve,
        )

    self.assertNotEqual(exit_code, 0)
    self.assertIn("port unavailable", stdout + stderr)

  def test_dev_enables_drafts_watch_and_live_reload(self) -> None:
    calls: list[tuple[FakeBuildOptions, bool, bool, bool]] = []

    def fake_serve(
      _project_root: Path,
      options: FakeBuildOptions,
      *,
      watch: bool,
      live_reload: bool,
      open_browser: bool,
      **_: object,
    ) -> int:
      calls.append((options, watch, live_reload, open_browser))
      return 0

    with tempfile.TemporaryDirectory() as temp_dir:
      with import_sitegen_module("sitegen.cli") as cli:
        try:
          exit_code, _, _ = self.run_cli(
            cli,
            ["dev"],
            Path(temp_dir),
            serve_func=fake_serve,
          )
        except SystemExit as error:
          exit_code = int(error.code)

    self.assertEqual(exit_code, 0)
    self.assertEqual(
      calls,
      [(FakeBuildOptions(include_drafts=True, incremental=True), True, True, False)],
    )

  def test_dev_can_open_the_browser_and_exclude_drafts(self) -> None:
    calls: list[tuple[FakeBuildOptions, bool]] = []

    def fake_serve(
      _project_root: Path,
      options: FakeBuildOptions,
      *,
      open_browser: bool,
      **_: object,
    ) -> int:
      calls.append((options, open_browser))
      return 0

    with tempfile.TemporaryDirectory() as temp_dir:
      with import_sitegen_module("sitegen.cli") as cli:
        try:
          exit_code, _, _ = self.run_cli(
            cli,
            ["dev", "--open", "--no-drafts"],
            Path(temp_dir),
            serve_func=fake_serve,
          )
        except SystemExit as error:
          exit_code = int(error.code)

    self.assertEqual(exit_code, 0)
    self.assertEqual(
      calls,
      [(FakeBuildOptions(include_drafts=False, incremental=True), True)],
    )


if __name__ == "__main__":
  unittest.main()
