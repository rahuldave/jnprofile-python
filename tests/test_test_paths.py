"""Run the recipe python::test-paths with real just, uv and pytest, and check the exit code of each case."""

from pathlib import Path
import os
import shutil
import subprocess
import tempfile
import unittest

from test_steps import needs

REPO = Path(__file__).resolve().parents[1]
FOLDER = REPO / ".agents/just/python"
# The module file as just install writes it, without the shell of jlog. test.just needs the variables of base.just.
MODULE = """set positional-arguments
set working-directory := '../..'
import 'python/base.just'
import 'python/test.just'
"""
PYPROJECT = """[project]
name = "app"
version = "0"
requires-python = ">=3.9"
dependencies = ["pytest"{extra}]

[tool.pytest.ini_options]
pythonpath = ["."]
"""
FILES = {
    "m.py": "def add(a, b):\n    return a + b\n",
    "tests/test_pass.py": "from m import add\n\ndef test_a():\n    assert add(1, 2) == 3\n",
    "tests/test_fail.py": "def test_f():\n    assert False\n",
    "tests/test_new.py": "from m import new\n\ndef test_n():\n    assert new()\n",
    "tests/test_skip.py": "import pytest\n\n@pytest.mark.skip\ndef test_s():\n    pass\n",
    "tests/test_mixed.py": "def test_a():\n    assert True\n\ndef test_f():\n    assert False\n",
    "tests/test_empty.py": "x = 1\n",
    "t2/conftest.py": "from m import new\n",
    "t2/test_x.py": "def test_x():\n    pass\n",
    "tests/test_xfail.py": "import pytest\n\n@pytest.mark.xfail\ndef test_x():\n    assert False\n",
    "tests/test_exit.py": "import os\n\ndef test_a():\n    pass\n\ndef test_b():\n    os._exit(0)\n",
    "-dash_test.py": "def test_d():\n    pass\n",
    "tests/test_exit1.py": "import os\n\ndef test_a():\n    os._exit(1)\n",
    "tests/test_exit5.py": "import os\n\ndef test_a():\n    os._exit(5)\n",
    "xml/__init__.py": "",
}


@needs(shutil.which("just") and shutil.which("uv"), "needs just and uv")
class TestPathsTests(unittest.TestCase):
    def project(self, extra: str = "") -> Path:
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        root = Path(temp.name)
        (root / ".agents/just/python").mkdir(parents=True)
        for name in ("base.just", "test.just", "steps.py"):
            shutil.copy(FOLDER / name, root / ".agents/just/python" / name)
        (root / ".agents/just/python.just").write_text(MODULE)
        (root / "Justfile").write_text('mod python ".agents/just/python.just"\n')
        (root / "pyproject.toml").write_text(PYPROJECT.format(extra=extra))
        for name, text in FILES.items():
            (root / name).parent.mkdir(parents=True, exist_ok=True)
            (root / name).write_text(text)
        return root

    def run_paths(self, root: Path, *files: str, env: dict = None) -> tuple:
        run = subprocess.run(["just", "python::test-paths", *files], cwd=root, capture_output=True, text=True,
                             env=env)
        return run.returncode, run.stdout + run.stderr

    def test_each_case_gives_its_code(self) -> None:
        root = self.project()
        cases = ((("tests/test_pass.py",), 0), (("tests/test_fail.py",), 1), (("tests/test_new.py",), 1),
                 (("tests/test_skip.py",), 5), (("tests/test_empty.py",), 5), ((), 5),
                 (("tests/test_mixed.py",), 1), (("t2/test_x.py",), 1), (("--nosuchoption",), 2),
                 (("tests/test_xfail.py",), 5), (("tests/test_exit.py",), 2), (("-dash_test.py",), 0),
                 (("tests/test_exit1.py",), 2), (("tests/test_exit5.py",), 2))
        for files, code in cases:
            with self.subTest(files=files):
                found, out = self.run_paths(root, *files)
                self.assertEqual(found, code, out)

    def test_a_file_that_starts_with_a_dash_runs_on_each_python(self) -> None:
        # pytest on Python 3.10 and 3.11 reads -dash_test.py as an option, also after --. uv gets each Python.
        root = self.project()
        for version in ("3.10", "3.11", "3.12"):
            with self.subTest(version=version):
                code, out = self.run_paths(root, "-dash_test.py", env=dict(os.environ, UV_PYTHON=version))
                self.assertEqual(code, 0, out)
                self.assertIn(f"Python {version}", out)
                self.assertIn("PASSED -dash_test.py::test_d", out)
        # An option that is not a file still goes to pytest, which stops on it.
        self.assertEqual(self.run_paths(root, "--nosuchoption", env=dict(os.environ, UV_PYTHON="3.11"))[0], 2)

    def test_a_file_that_cannot_be_collected_hides_no_other_test(self) -> None:
        code, out = self.run_paths(self.project(), "tests/test_new.py", "tests/test_pass.py")
        self.assertEqual(code, 1)
        self.assertIn("PASSED tests/test_pass.py::test_a", out)

    def test_each_test_has_its_line(self) -> None:
        code, out = self.run_paths(self.project(), "tests/test_mixed.py")
        self.assertEqual(code, 1)
        self.assertIn("PASSED tests/test_mixed.py::test_a", out)
        self.assertIn("FAILED tests/test_mixed.py::test_f", out)

    def test_a_plugin_that_changes_the_summary_does_not_change_the_count(self) -> None:
        # pytest-pretty prints its own summary in place of the lines of each test.
        root = self.project(extra=', "pytest-pretty"')
        self.assertEqual(self.run_paths(root, "tests/test_pass.py")[0], 0)
        self.assertEqual(self.run_paths(root, "tests/test_skip.py")[0], 5)

    def test_an_install_that_fails_is_a_failed_runner(self) -> None:
        code, out = self.run_paths(self.project(extra=', "nosuchpkg-zzzq-xx==9.9"'), "tests/test_pass.py")
        self.assertEqual(code, 2)
        self.assertIn("uv cannot make the environment", out)


if __name__ == "__main__":
    unittest.main()
