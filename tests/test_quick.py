"""Run the recipe quick of the base with real just, uv, git, ruff, ty and pytest."""

from test_steps import CODE, MODULE, TOOLS, ProjectCase, needs

# A module with no tool: the base only.
BASE = "set positional-arguments\nset working-directory := '../..'\nimport? 'python/base.just'\n"
# A test that fails.
FAILING = "from m import add\n\n\ndef test_add():\n    assert add(1, 2) == 4\n"


@needs(TOOLS, "needs just, uv and git")
class QuickTests(ProjectCase):
    def setUp(self) -> None:
        super().setUp()
        self.write("ruff.toml", 'extend-exclude = [".agents"]\n')

    def test_quick_runs_the_unit_tests_with_no_coverage_and_writes_no_report(self) -> None:
        code, out = self.just("python::quick")
        self.assertEqual(code, 0, out)
        self.assertIn("1 passed", out)
        self.assertNotIn("coverage:", out)
        self.assertFalse((self.root / ".jnprofile-python/coverage.xml").exists())
        self.assertFalse((self.root / ".coverage").exists())

    def test_a_coverage_gate_of_the_project_does_not_fail_quick(self) -> None:
        self.write("pyproject.toml", self.read("pyproject.toml")
                   + 'addopts = "--cov=. --cov-fail-under=100"\n')
        self.write("m.py", CODE + '\n\ndef sub(a, b):\n    """Subtract B from A."""\n    return a - b\n')
        code, out = self.just("python::quick")
        self.assertEqual(code, 0, out)
        code, out = self.just("python::test")
        self.assertNotEqual(code, 0, out)

    def test_a_failing_test_fails_quick(self) -> None:
        self.write("tests/test_m.py", FAILING)
        code, out = self.just("python::quick")
        self.assertNotEqual(code, 0, out)
        self.assertIn("1 failed", out)

    def test_extra_arguments_go_to_pytest(self) -> None:
        self.write("tests/test_other.py", FAILING.replace("test_add", "test_other"))
        code, out = self.just("python::quick", "tests/test_m.py")
        self.assertEqual(code, 0, out)
        self.assertIn("1 passed", out)
        code, out = self.just("python::quick", "-k", "nothing_has_this_name")
        self.assertEqual(code, 5, out)
        self.assertIn("deselected", out)

    def test_a_format_problem_fails_quick_and_stops_the_tests(self) -> None:
        self.write("m.py", CODE.replace("a + b", "a+b"))
        code, out = self.just("python::quick")
        self.assertEqual(code, 1, out)
        self.assertIn("1 file would be reformatted", out)
        self.assertNotIn("passed", out)

    def test_a_lint_problem_fails_quick(self) -> None:
        self.write("m.py", CODE.replace('"""Math."""\n', '"""Math."""\n\nimport os\n'))
        code, out = self.just("python::quick")
        self.assertNotEqual(code, 0, out)
        self.assertIn("F401", out)

    def test_with_no_tool_quick_runs_nothing_and_passes(self) -> None:
        self.write(".agents/just/python.just", BASE)
        self.write("m.py", "import os\n" + CODE.replace("a + b", "a+b"))
        self.write("tests/test_m.py", FAILING)
        code, out = self.just("python::quick")
        self.assertEqual(code, 0, out)
        self.assertNotIn("ruff", out)
        self.assertNotIn("pytest", out)

    def test_quick_runs_typecheck_when_the_tool_is_installed(self) -> None:
        self.write("pyproject.toml", self.read("pyproject.toml").replace('"ruff"]', '"ruff", "ty"]'))
        self.write(".agents/just/python.just", MODULE + "import? 'python/typecheck.just'\n")
        self.write("ty.toml", '[src]\nexclude = [".agents"]\n')
        self.write("m.py", CODE + '\n\ndef bad() -> int:\n    """Bad."""\n    return "x"\n')
        code, out = self.just("python::quick")
        self.assertNotEqual(code, 0, out)
        self.assertIn("Return type does not match", out)
        self.write("m.py", CODE)
        code, out = self.just("python::quick")
        self.assertEqual(code, 0, out)

    def test_quick_is_not_a_step_and_leaves_coverage_check_to_run_the_tests(self) -> None:
        self.commit()
        code, out = self.just("python::quick")
        self.assertEqual(code, 0, out)
        code, out = self.just("python::coverage-check")
        self.assertEqual(code, 0, out)
        self.assertIn("1 passed", out)
        self.assertTrue((self.root / ".jnprofile-python/coverage.xml").exists())

    def test_with_the_integration_tool_quick_leaves_out_tests_integration(self) -> None:
        self.write("tests/integration/test_flow.py", FAILING.replace("test_add", "test_flow"))
        code, out = self.just("python::quick")
        self.assertNotEqual(code, 0, out)
        self.write(".agents/just/python.just", MODULE + "import? 'python/integration.just'\n")
        code, out = self.just("python::quick")
        self.assertEqual(code, 0, out)
        self.assertIn("1 passed", out)

    def read(self, name: str) -> str:
        return (self.root / name).read_text()

