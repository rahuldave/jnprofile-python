"""Run the recipe python::version with real just and uv, and check its output and exit code in each case. The live
case installs the profile with the installer of jnterfaces, as the live lab of api_rule.py does."""

from pathlib import Path
import os
import shutil
import subprocess
import tempfile
import unittest

from test_live_api_rule import AGENT, INSTALLER
from test_steps import needs

REPO = Path(__file__).resolve().parents[1]
FOLDER = REPO / ".agents/just/python"
# The module file as just install writes it, without the shell of jlog. version needs only base.just.
MODULE = """set positional-arguments
set working-directory := '../..'
import 'python/base.just'
"""
STATIC = '[project]\nname = "app"\nversion = "1.2.3"\n'
# Each case: the text of pyproject.toml, or None for no file, then the output and the exit code.
CASES = {
    "a static version": (STATIC, "1.2.3\n", 0),
    "a version of PEP 440 with a tag": ('[project]\nname = "app"\nversion = "2.0.0rc1"\n', "2.0.0rc1\n", 0),
    "no pyproject.toml": (None, "", 0),
    "no version": ('[project]\nname = "app"\n', "", 0),
    "no table project": ('[tool.ruff]\nline-length = 120\n', "", 0),
    "an empty file": ("", "", 0),
    "a dynamic version": ('[project]\nname = "app"\ndynamic = ["version"]\n', "", 0),
    "a byte order mark": ("﻿" + STATIC, "1.2.3\n", 0),
    "a version and a dynamic version": ('[project]\nname = "app"\nversion = "1"\ndynamic = ["version"]\n', "", 2),
    "a file that is not TOML": ('[project\nname = "app"\n', "", 2),
    "a version that is not a string": ('[project]\nname = "app"\nversion = 1\n', "", 2),
    "a version that is not of PEP 440": ('[project]\nname = "app"\nversion = "one"\n', "", 2),
    # The review: a build gives 1.2.3 for v1.2.3 and 1.0.0rc1 for 1.0.0-RC1, so a tag of the spelling would not match.
    "a version with a v": ('[project]\nname = "app"\nversion = "v1.2.3"\n', "", 2),
    "a version that is not in normal form": ('[project]\nname = "app"\nversion = "1.0.0-RC1"\n', "", 2),
    "a version with a leading zero": ('[project]\nname = "app"\nversion = "01.0"\n', "", 2),
    "a local version that is not ASCII": ('[project]\nname = "app"\nversion = "1.0+\u017f"\n', "", 2),
    "a version in normal form with each part": ('[project]\nname = "app"\nversion = "1!2.0rc1.post2.dev3+ab.7"\n',
                                                "1!2.0rc1.post2.dev3+ab.7\n", 0),
    # The review: uv stops on its own settings, such as required-version, unless the recipe runs it with --no-config.
    "a required version of uv that no uv has": (STATIC + '\n[tool.uv]\nrequired-version = ">=99"\n', "1.2.3\n", 0),
    "a version over two lines": ('[project]\nname = "app"\nversion = "1.0\\n2.0"\n', "", 2),
    "a project that is not a table": ('project = "app"\n', "", 2),
    "a dynamic that is not a list": ('[project]\nname = "app"\nversion = "1"\ndynamic = "version"\n', "", 2),
}


def listing(root: Path) -> list:
    """Each path under ROOT with its time of change, to see that a run writes nothing."""
    return sorted((str(p.relative_to(root)), p.lstat().st_mtime_ns) for p in root.rglob("*"))


@needs(shutil.which("just") and shutil.which("uv"), "needs just and uv")
class VersionTests(unittest.TestCase):
    def project(self, text) -> Path:
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        root = Path(temp.name)
        (root / ".agents/just/python").mkdir(parents=True)
        for name in ("base.just", "steps.py"):
            shutil.copy(FOLDER / name, root / ".agents/just/python" / name)
        (root / ".agents/just/python.just").write_text(MODULE)
        (root / "Justfile").write_text('mod python ".agents/just/python.just"\n')
        if text is not None:
            (root / "pyproject.toml").write_text(text, encoding="utf-8")
        return root

    def version(self, root: Path, cwd: Path = None) -> subprocess.CompletedProcess:
        return subprocess.run(["just", "python::version"], cwd=cwd or root, capture_output=True, text=True)

    def test_each_case_gives_its_output_and_code(self) -> None:
        for case, (text, out, code) in CASES.items():
            with self.subTest(case=case):
                root = self.project(text)
                before = listing(root)
                run = self.version(root)
                self.assertEqual((run.stdout, run.returncode), (out, code), run.stderr)
                if code == 2:
                    self.assertIn("version: ", run.stderr)
                else:
                    self.assertEqual(run.stderr, "")
                self.assertEqual(listing(root), before, "the recipe wrote a file")

    def test_a_file_that_cannot_be_read_exits_2_with_a_message(self) -> None:
        root = self.project(STATIC)
        (root / "pyproject.toml").chmod(0)
        self.addCleanup((root / "pyproject.toml").chmod, 0o644)
        if os.access(root / "pyproject.toml", os.R_OK):
            self.skipTest("this user reads a file with no permission, as root does")
        run = self.version(root)
        self.assertEqual((run.stdout, run.returncode), ("", 2))
        self.assertIn("version: cannot read pyproject.toml", run.stderr)

    def test_a_folder_or_a_broken_link_exits_2(self) -> None:
        for kind in ("folder", "link"):
            with self.subTest(kind=kind):
                root = self.project(None)
                if kind == "folder":
                    (root / "pyproject.toml").mkdir()
                else:
                    (root / "pyproject.toml").symlink_to(root / "missing.toml")
                run = self.version(root)
                self.assertEqual((run.stdout, run.returncode), ("", 2), run.stderr)
                self.assertIn("version: cannot read pyproject.toml", run.stderr)

    def test_it_reads_the_top_of_the_project_from_a_subfolder(self) -> None:
        root = self.project(STATIC)
        (root / "sub").mkdir()
        (root / "sub/pyproject.toml").write_text('[project]\nname = "sub"\nversion = "9.9.9"\n')
        run = self.version(root, root / "sub")
        self.assertEqual((run.stdout, run.returncode), ("1.2.3\n", 0), run.stderr)

    def test_the_variables_of_python_do_not_change_it(self) -> None:
        # python -I leaves out PYTHONPATH, so a tomllib.py there cannot take the place of the standard library.
        root = self.project(STATIC)
        fake = root / "fake"
        fake.mkdir()
        (fake / "tomllib.py").write_text("raise SystemExit('the fake tomllib ran')\n")
        env = dict(os.environ, PYTHONPATH=str(fake))
        run = subprocess.run(["just", "python::version"], cwd=root, capture_output=True, text=True, env=env)
        self.assertEqual((run.stdout, run.returncode), ("1.2.3\n", 0), run.stderr)

    def test_a_uv_toml_of_a_parent_folder_does_not_stop_it(self) -> None:
        root = self.project(STATIC)
        (root / "sub").mkdir()
        for name in os.listdir(root):
            if name != "sub":
                shutil.move(str(root / name), str(root / "sub" / name))
        (root / "uv.toml").write_text('required-version = ">=99"\n')
        run = self.version(root / "sub")
        self.assertEqual((run.stdout, run.returncode), ("1.2.3\n", 0), run.stderr)

    def test_the_recipe_asks_uv_for_a_floor_of_python_3_11(self) -> None:
        dump = subprocess.run(["just", "--justfile", str(FOLDER / "base.just"), "--show", "version"],
                              capture_output=True, text=True)
        self.assertEqual(dump.returncode, 0, dump.stderr)
        self.assertIn("uv run --no-project --no-config --quiet --python '>=3.11' python -I -B", dump.stdout)

@needs(all(shutil.which(tool) for tool in ("uv", "git", "just", "jlog")) and INSTALLER.is_file(),
       f"the live lab needs uv, git, just, jlog and the installer of jnterfaces at {INSTALLER}")
class LiveVersionTests(unittest.TestCase):
    def run_in(self, root: Path, *command: str) -> subprocess.CompletedProcess:
        env = {k: v for k, v in os.environ.items() if k not in AGENT and not k.startswith("GIT_")}
        return subprocess.run(command, cwd=root, capture_output=True, text=True, env=env)

    def test_an_installed_profile_prints_the_version(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            self.run_in(root, "git", "init", "-q", "-b", "main")
            made = self.run_in(root, "uv", "init", "-q", "--lib", "--name", "m", "--python", "3.12", ".")
            self.assertEqual(made.returncode, 0, made.stderr)
            installed = self.run_in(root, "uv", "run", "--script", str(INSTALLER), "--target", ".", "--defaults",
                                    "--profile", "python", "--clone", f"jnprofile-python={REPO}",
                                    "--without", "tasker")
            self.assertEqual(installed.returncode, 0, installed.stdout + installed.stderr)
            pyproject = root / "pyproject.toml"
            text = pyproject.read_text()
            self.assertIn('version = "0.1.0"', text)
            pyproject.write_text(text.replace('version = "0.1.0"', 'version = "3.4.5"'))
            # jlog, the shell of the installed Justfile, writes its log of each run into .agents/log. The recipe
            # writes nothing else.
            status = ("git", "status", "--porcelain", "--ignored", "--", ".", ":!.agents/log")
            before = self.run_in(root, *status).stdout
            run = self.run_in(root, "just", "python::version")
            self.assertEqual((run.stdout, run.returncode), ("3.4.5\n", 0), run.stderr)
            self.assertEqual(self.run_in(root, *status).stdout, before)
            pyproject.write_text(text.replace('version = "0.1.0"', 'dynamic = ["version"]'))
            run = self.run_in(root, "just", "python::version")
            self.assertEqual((run.stdout, run.returncode), ("", 0), run.stderr)


if __name__ == "__main__":
    unittest.main()
