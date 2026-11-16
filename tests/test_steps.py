"""Run the steps fmt-check, coverage-check and docstring-check with real just, uv, git and pytest."""

import functools
import importlib.util
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest
import unittest.mock

REPO = Path(__file__).resolve().parents[1]
FOLDER = REPO / ".agents/just/python"
PYPROJECT = """[project]
name = "app"
version = "0"
requires-python = ">=3.9"
dependencies = ["pytest", "pytest-cov", "ruff"]

[tool.pytest.ini_options]
pythonpath = ["."]
"""
# The module file as just install writes it, without the shell of jlog.
MODULE = """set positional-arguments
set working-directory := '../..'
import? 'python/base.just'
import? 'python/lint.just'
import? 'python/test.just'
import? 'python/docstring.just'
"""
CODE = '"""Math."""\n\n\ndef add(a, b):\n    """Add A and B."""\n    return a + b\n'
TEST = "from m import add\n\n\ndef test_add():\n    assert add(1, 2) == 3\n"
UNTESTED = '\n\ndef sub(a, b):\n    """Subtract B from A."""\n    return a - b\n'
IGNORE = ".venv/\n__pycache__/\n.coverage\n.pytest_cache/\n.ruff_cache/\n.jnprofile-python/\n"


def load_steps():
    """The module steps.py of the profile."""
    spec = importlib.util.spec_from_file_location("steps", FOLDER / "steps.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def load_lint():
    """The module scripts/lint_recipes.py of this repository."""
    spec = importlib.util.spec_from_file_location("lint_recipes", REPO / "scripts/lint_recipes.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


# The variables of CI that the steps read.
CI_VARIABLES = ("CI", "GITHUB_BASE_REF", "GITHUB_REF", "GITHUB_EVENT_NAME", "GITHUB_EVENT_PATH")


def in_ci() -> bool:
    """True in CI: the variable CI is set to a value other than empty, false and 0."""
    return os.environ.get("CI", "").lower() not in ("", "false", "0")


def needs(condition, reason: str):
    """unittest.skipUnless, except in CI. There a test or a class whose program or clone is missing fails, so a
    missing program cannot pass the run."""
    if condition:
        return lambda item: item
    if not in_ci():
        return unittest.skip(reason)
    message = f"CI must have it: {reason}"

    def mark(item):
        if isinstance(item, type):
            def setUpClass(cls) -> None:
                raise AssertionError(message)
            item.setUpClass = classmethod(setUpClass)
            return item

        @functools.wraps(item)
        def failing(self, *args, **kwargs) -> None:
            self.fail(message)
        return failing
    return mark


TOOLS = shutil.which("just") and shutil.which("uv") and shutil.which("git")


class ProjectCase(unittest.TestCase):
    """A Python project in a temporary folder, with the recipe files of the profile and a git repository."""

    def setUp(self) -> None:
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)
        shutil.copytree(FOLDER, self.root / ".agents/just/python")
        (self.root / ".agents/just/python.just").write_text(MODULE)
        (self.root / "Justfile").write_text('export JLOG_RUN := env("JLOG_RUN", uuid())\n'
                                            'mod python ".agents/just/python.just"\n')
        self.write("pyproject.toml", PYPROJECT)
        self.write(".gitignore", IGNORE)
        self.write("m.py", CODE)
        self.write("tests/test_m.py", TEST)
        # The variables of CI go too, so that the steps run as on a machine also in CI. A test of CI sets them.
        self.env = {k: v for k, v in os.environ.items()
                    if not k.startswith("GIT_") and k != "JLOG_RUN" and k not in CI_VARIABLES}
        self.env.update(GIT_AUTHOR_NAME="t", GIT_AUTHOR_EMAIL="t@example.com", GIT_COMMITTER_NAME="t",
                        GIT_COMMITTER_EMAIL="t@example.com")
        self.git("init", "-q")
        subprocess.run(["uv", "lock", "--quiet"], cwd=self.root, check=True, env=self.env)

    def write(self, name: str, text: str) -> None:
        path = self.root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text)

    def git(self, *args: str) -> None:
        subprocess.run(["git", "-c", "commit.gpgsign=false", *args], cwd=self.root, check=True, env=self.env,
                       capture_output=True)

    def commit(self) -> None:
        self.git("add", "-A")
        self.git("commit", "-q", "--no-verify", "-m", "c")

    def just(self, *args: str, env: dict = None) -> tuple:
        run = subprocess.run(["just", *args], cwd=self.root, capture_output=True, text=True, env=env or self.env)
        return run.returncode, run.stdout + run.stderr


@needs(TOOLS, "needs just, uv and git")
class CiVariablesTests(ProjectCase):
    """The projects of the tests run as on a machine, also in CI, which sets CI=true."""

    def setUp(self) -> None:
        patch = unittest.mock.patch.dict(os.environ, {"CI": "true", "GITHUB_EVENT_NAME": "push",
                                                      "GITHUB_REF": "refs/heads/x"})
        patch.start()
        self.addCleanup(patch.stop)
        super().setUp()

    def test_the_env_of_a_project_has_no_variable_of_ci(self) -> None:
        self.assertFalse(set(CI_VARIABLES) & set(self.env))


@needs(TOOLS, "needs just, uv and git")
class StepTests(ProjectCase):
    def test_an_untested_changed_line_fails_and_a_pragma_makes_it_pass(self) -> None:
        self.commit()
        self.write("m.py", CODE + UNTESTED)
        code, out = self.just("python::coverage-check")
        self.assertEqual(code, 1, out)
        self.assertIn("m.py (50.0%): Missing lines 11", out)
        self.assertIn("write tests", out)
        self.write("m.py", CODE + UNTESTED.replace("def sub(a, b):", "def sub(a, b):  # pragma: no cover"))
        code, out = self.just("python::coverage-check")
        self.assertEqual(code, 0, out)

    def test_a_test_file_with_a_skipped_test_does_not_count(self) -> None:
        self.commit()
        self.write("m.py", CODE + '\n\ndef mul(a, b):\n    """Multiply A and B."""\n    return a * b\n')
        self.write("tests/test_m.py", TEST + "\n\ndef test_mul():\n    from m import mul\n    assert mul(2, 3) == 6\n"
                   "\n\nimport pytest\n\n\n@pytest.mark.skip(reason='later')\ndef test_later():\n    assert False\n")
        code, out = self.just("python::coverage-check")
        self.assertEqual(code, 0, out)

    def test_an_untracked_file_in_a_project_in_a_subfolder_needs_each_line_to_run(self) -> None:
        # The git repository is one folder up, so the project is a subfolder of it.
        sub = self.root / "app"
        sub.mkdir()
        for name in [p.name for p in self.root.iterdir() if p.name not in ("app", ".git")]:
            shutil.move(str(self.root / name), str(sub / name))
        self.root = sub
        self.commit()
        self.write("n.py", '"""N."""\n\n\ndef f():\n    """F."""\n    return 1\n\n\n'
                   'def g():\n    """G."""\n    return 2\n')
        self.write("tests/test_n.py", "from n import f\n\n\ndef test_f():\n    assert f() == 1\n")
        code, out = self.just("python::coverage-check")
        self.assertEqual(code, 1, out)
        self.assertIn("n.py:11: no test runs this line", out)

    def test_a_cov_append_of_the_project_adds_to_no_old_run(self) -> None:
        self.write("pyproject.toml",
                   PYPROJECT.replace('pythonpath = ["."]', 'pythonpath = ["."]\naddopts = "--cov-append"'))
        subprocess.run(["uv", "lock", "--quiet"], cwd=self.root, check=True, env=self.env)
        self.commit()
        self.write("m.py", CODE + UNTESTED)
        self.write("tests/test_m.py", TEST + "\n\ndef test_sub():\n    from m import sub\n    assert sub(3, 1) == 2\n")
        self.assertEqual(self.just("python::test")[0], 0)
        self.write("tests/test_m.py", TEST)
        code, out = self.just("python::coverage-check")
        self.assertEqual(code, 1, out)
        self.assertIn("Missing lines 11", out)

    def test_a_project_on_python_3_9_runs_diff_cover(self) -> None:
        self.write(".python-version", "3.9\n")
        subprocess.run(["uv", "lock", "--quiet"], cwd=self.root, check=True, env=self.env)
        self.commit()
        self.write("m.py", CODE + UNTESTED)
        code, out = self.just("python::coverage-check")
        self.assertEqual(code, 1, out)
        self.assertIn("m.py (50.0%): Missing lines 11", out)
        self.assertNotIn("unsatisfiable", out)

    def test_changed_code_with_no_test_fails_and_says_write_tests(self) -> None:
        # A project with no test: test passes, and pytest-cov writes no report.
        (self.root / "tests/test_m.py").unlink()
        self.commit()
        self.write("n.py", '"""N."""\n\n\ndef n():\n    """N."""\n    return 1\n')
        code, out = self.just("python::coverage-check")
        self.assertEqual(code, 1, out)
        self.assertIn("there is no coverage report .jnprofile-python/coverage.xml, so write tests", out)

    def test_a_generated_path_of_the_parent_is_exempt_and_a_commit_cannot_exempt_itself(self) -> None:
        self.commit()
        # The commit that adds gen.py also lists it: the list of the parent does not have it, so both steps fail.
        self.write(".agents/generated.txt", "# made by a tool\ngen.py\n")
        self.write("gen.py", "def made():\n    return 1\n")
        code, out = self.just("python::coverage-check")
        self.assertEqual(code, 1, out)
        self.assertIn("gen.py: a changed file that is not in the coverage report", out)
        code, out = self.just("python::docstring-check")
        self.assertEqual(code, 1, out)
        self.assertIn("gen.py:1: Module gen.py has no docstring", out)
        # Once the parent lists it, a change to gen.py fails neither step.
        self.commit()
        self.write("gen.py", "def made():\n    return 2\n")
        code, out = self.just("python::coverage-check")
        self.assertEqual(code, 0, out)
        code, out = self.just("python::docstring-check")
        self.assertEqual(code, 0, out)

    def test_the_first_commit_needs_every_line_of_code_to_run(self) -> None:
        self.write("m.py", CODE + UNTESTED)
        code, out = self.just("python::coverage-check")
        self.assertEqual(code, 1, out)
        self.assertIn("the first commit, so every line of code must run", out)
        self.assertIn("m.py:11: no test runs this line", out)
        self.write("m.py", CODE)
        code, out = self.just("python::coverage-check")
        self.assertEqual(code, 0, out)

    def test_coverage_check_reads_the_report_of_test_in_the_same_run(self) -> None:
        env = dict(self.env, JLOG_RUN="run-1")
        code, out = self.just("python::test", env=env)
        self.assertEqual(code, 0, out)
        code, out = self.just("python::coverage-check", env=env)
        self.assertEqual(code, 0, out)
        self.assertIn("the tests of this run, run-1, wrote the report, so they do not run again", out)
        # Another run, or a change to the tree, runs the tests again.
        code, out = self.just("python::coverage-check", env=dict(self.env, JLOG_RUN="run-2"))
        self.assertIn("no report of the tests of this run and this tree, so they run now", out)
        self.just("python::test", env=env)
        self.write("m.py", CODE + "\n")
        code, out = self.just("python::coverage-check", env=env)
        self.assertIn("no report of the tests of this run and this tree, so they run now", out)

    def test_docstring_check_names_a_private_function_with_no_docstring(self) -> None:
        self.write("m.py", CODE + "\n\ndef _helper():\n    return 0\n\n\nclass K:\n    def __repr__(self):\n"
                   "        return ''\n")
        self.write("o.py", '"""O."""\nfrom typing import overload\n\n\n@overload\ndef f(x: int) -> int: ...\n\n\n'
                   '@overload\ndef f(x: str) -> str: ...\n\n\ndef f(x):\n    """F."""\n    return x\n\n\nclass P:\n'
                   '    """P."""\n\n    @property\n    def v(self):\n        """V."""\n        return 1\n\n'
                   '    @v.setter\n    def v(self, value):\n        pass\n\n    @v.deleter\n    def v(self):\n'
                   '        pass\n')
        code, out = self.just("python::docstring-check")
        self.assertEqual(code, 1, out)
        self.assertIn("m.py:9: FunctionDef _helper has no docstring", out)
        self.assertIn("m.py:13: ClassDef K has no docstring", out)
        # A magic method, an overload stub, a property setter, a test file and the folder .agents do not count.
        self.assertNotIn("__repr__", out)
        self.assertNotIn("o.py", out)
        self.assertNotIn("test_m.py", out)
        self.assertNotIn("steps.py:", out)

    def test_fmt_check_fails_on_code_that_ruff_would_change_and_changes_no_file(self) -> None:
        self.write("ruff.toml", 'extend-exclude = [".agents"]\n')
        self.write("m.py", CODE.replace("a + b", "a+b"))
        code, out = self.just("python::fmt-check")
        self.assertEqual(code, 1, out)
        self.assertIn("1 file would be reformatted", out)
        self.assertIn("m.py:6", out)
        self.assertIn("a+b", (self.root / "m.py").read_text())
        self.write("m.py", CODE)
        code, out = self.just("python::fmt-check")
        self.assertEqual(code, 0, out)


class ProfileTests(unittest.TestCase):
    def test_the_test_files_of_the_steps_are_those_of_the_profile(self) -> None:
        profile = json.loads((REPO / "profile.json").read_text())
        self.assertEqual(list(load_steps().TESTS), profile["tests"])

    def test_each_step_is_in_the_verify_of_its_tool(self) -> None:
        tools = json.loads((REPO / "profile.json").read_text())["tools"]
        self.assertEqual(tools["lint"]["verify"], ["fmt-check", "lint"])
        self.assertEqual(tools["test"]["verify"], ["test", "coverage-check"])
        self.assertEqual(tools["docstring"]["verify"], ["docstring-check"])
        self.assertEqual(tools["integration"]["verify"], ["integration"])
        self.assertEqual(tools["api"]["verify"], ["api-check"])
        for name in ("test", "integration", "api"):
            self.assertIn(".jnprofile-python/", tools[name]["lines"][".gitignore"])

    def test_the_api_tool_is_on_by_default_and_integration_is_not(self) -> None:
        profile = json.loads((REPO / "profile.json").read_text())
        self.assertIn("api", profile["default_tools"])
        self.assertNotIn("integration", profile["default_tools"])

    def test_the_profile_defines_no_step_of_a_role(self) -> None:
        # The installer stops when a role file and a profile define one step, so docs-check and prose-check stay with
        # the docs and prose roles.
        for path in FOLDER.glob("*.just"):
            names = {line.split(":")[0].split()[0] for line in path.read_text().splitlines()
                     if line and line[0].isalpha() and ":" in line and ":=" not in line}
            self.assertFalse(names & {"docs-check", "prose-check"}, path.name)

    def test_a_missing_program_skips_on_a_machine_and_fails_in_ci(self) -> None:
        def run(decorated) -> unittest.TestResult:
            result = unittest.TestResult()
            unittest.defaultTestLoader.loadTestsFromTestCase(decorated).run(result)
            return result

        def case():
            class Case(unittest.TestCase):
                def test_it(self) -> None:
                    pass
            return Case

        for value, skipped in (("", True), ("false", True), ("0", True), ("true", False), ("1", False)):
            with unittest.mock.patch.dict(os.environ, {"CI": value}):
                # needs on a class, and on a method.
                method = case()
                method.test_it = needs(False, "no tool")(method.test_it)
                for result in (run(needs(False, "no tool")(case())), run(method)):
                    self.assertEqual(len(result.skipped), 1 if skipped else 0, value)
                    self.assertEqual(len(result.failures) + len(result.errors), 0 if skipped else 1, value)
                    if not skipped:
                        self.assertIn("CI must have it: no tool", str(result.failures + result.errors))
                self.assertEqual(run(needs(True, "no tool")(case())).testsRun, 1)

    @needs(shutil.which("just"), "needs just")
    def test_the_lint_of_the_recipes_passes_and_finds_each_kind_of_bad_step(self) -> None:
        lint = load_lint()
        self.assertEqual(lint.main([]), 0)
        recipes, error = lint.dump(FOLDER)
        self.assertIsNone(error)
        self.assertTrue({"test", "coverage-check", "integration", "docstring-check", "api-check"} <= set(recipes))
        bad = {"test": "#!/usr/bin/env sh\n    echo t", "lint": "-echo l", "typecheck": "@-echo t"}
        with tempfile.TemporaryDirectory() as temp:
            folder = Path(temp) / "python"
            folder.mkdir()
            text = "".join(f"{name}:\n    {body}\n\n" for name, body in bad.items())
            text += "[no-cd]\ndiff-check:\n    echo d\n\n[script]\nfmt-check:\n    echo f\n\n"
            text += "[working-directory: 'x']\nintegration:\n    echo i\n\n"
            # A step that is an alias gets the lint of the recipe that it names.
            text += "_check:\n    -echo c\n\nalias docstring-check := _check\n"
            (folder / "bad.just").write_text(text)
            recipes, error = lint.dump(folder)
            self.assertIsNone(error)
            found = "\n".join(lint.findings(recipes))
            for expected in ("test: a step is a shebang recipe", "lint: a line starts with -",
                             "typecheck: a line starts with -", "diff-check: a step has the attribute [no-cd]",
                             "fmt-check: a step has the attribute [script]",
                             "integration: a step has the attribute [working-directory]",
                             "docstring-check: a line starts with -"):
                self.assertIn(expected, found)
            (folder / "two.just").write_text("lint:\n    echo again\n")
            self.assertEqual(lint.main([str(folder)]), 1)

    def test_the_messages_of_the_prose_run_name_api_prose_check(self) -> None:
        steps = load_steps()
        self.assertEqual(steps.recipe_of("prose"), "api-prose-check")
        self.assertEqual(steps.recipe_of("integration"), "integration")

    def test_the_tools_page_says_the_pythonpath_part_under_the_test_tool(self) -> None:
        section = None
        for line in (REPO / "docs/tools.md").read_text().splitlines():
            section = line[3:] if line.startswith("## ") else section
            if "pythonpath" in line:
                self.assertEqual(section, "test", line)

    def test_the_name_of_the_project_comes_from_pyproject(self) -> None:
        steps = load_steps()
        cases = {'[project]\nname = "My.App-x"\n': "my_app_x",
                 '[project]\n  name = "app"\n': "app",
                 '[project]\ndescription = """\n[not a table]\n"""\nname = "app"\n': "app",
                 '[tool.poetry]\nname = "poet"\n': "poet",
                 '[tool.ruff]\nline-length = 1\n': None,
                 'project = "x"\n': None,
                 '[tool]\npoetry = "x"\n': None}
        with tempfile.TemporaryDirectory() as temp:
            here = os.getcwd()
            os.chdir(temp)
            try:
                for text, want in cases.items():
                    Path("pyproject.toml").write_text(text)
                    self.assertEqual(steps.project_name(), want, text)
            finally:
                os.chdir(here)

    def test_the_union_of_two_reports_counts_a_line_that_one_report_runs(self) -> None:
        steps = load_steps()
        with tempfile.TemporaryDirectory() as temp:
            root = Path(os.path.realpath(temp))
            (root / "m.py").write_text("a = 1\nb = 2\nc = 3\n")
            for name, hits in (("one.xml", "110"), ("two.xml", "010")):
                lines = "".join(f'<line number="{i + 1}" hits="{h}"/>' for i, h in enumerate(hits))
                (root / name).write_text(f'<coverage><sources><source>{root}</source></sources><packages><package>'
                                         f'<classes><class filename="m.py"><lines>{lines}</lines></class></classes>'
                                         '</package></packages></coverage>')
            tree = steps.union([root / "one.xml", root / "two.xml"], root)
        hits = {int(line.get("number")): int(line.get("hits")) for line in tree.iter("line")}
        self.assertEqual(hits, {1: 1, 2: 1, 3: 0})
        self.assertEqual(steps.missed_lines(tree, root, {"m.py"}), ["m.py:3: no test runs this line"])


if __name__ == "__main__":
    unittest.main()
