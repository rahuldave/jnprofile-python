"""Tests of api_rule.py: is_api(path), which tells the commit gate whether a file feeds the API pages."""
import ast
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

from test_steps import load_steps

RULE = Path(__file__).resolve().parent.parent / ".agents/just/python/api_rule.py"
# A Python 3.9 on this machine, to run the rule as the gate may run it.
PYTHON39 = shutil.which("python3.9")
ON = {"tools": ["python:lint", "python:api"], "choices": {"docs": True, "prose": True}}


class ApiRuleTests(unittest.TestCase):
    def setUp(self) -> None:
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)
        self.write(".agents/stack.json", json.dumps(ON))
        self.write("pyproject.toml", '[project]\nname = "my-app"\nversion = "0"\n')

    def write(self, name: str, text: str = "") -> None:
        path = self.root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text)

    def is_api(self, *paths: str, python: str = "python3") -> list:
        """is_api of each of PATHS, run as the gate runs it: python -I -B, in the top of the repository."""
        code = ("import importlib.util, json, sys\n"
                "spec = importlib.util.spec_from_file_location('api_rule', sys.argv[1])\n"
                "rule = importlib.util.module_from_spec(spec)\nspec.loader.exec_module(rule)\n"
                "print(json.dumps([rule.is_api(p) for p in sys.argv[2:]]))\n")
        run = subprocess.run([python, "-I", "-B", "-c", code, str(RULE), *paths], cwd=self.root,
                             capture_output=True, text=True)
        self.assertEqual(run.returncode, 0, run.stderr)
        return json.loads(run.stdout)

    def test_without_the_key_api_the_found_packages_count(self) -> None:
        self.write("pkg/__init__.py")
        self.write("src/lib/__init__.py")
        self.write("my_app.py")
        self.write("noxfile.py")
        self.write("loose/x.py")
        self.write("_private/__init__.py")
        self.write("tests/__init__.py")
        # smalldocs documents each module of a package, a test module in it too.
        accepted = ["pkg/__init__.py", "pkg/core.py", "pkg/sub/deep.py", "src/lib/x.py", "./pkg/core.py", "my_app.py",
                    "pkg/test_core.py", "pkg/conftest.py"]
        rejected = ["noxfile.py", "loose/x.py", "_private/__init__.py", "tests/test_m.py", "tests/__init__.py",
                    "pkg/README.md", ".agents/just/python/steps.py", "../pkg/core.py",
                    "/pkg/core.py", "docs/index.md", "setup.py"]
        self.assertEqual(self.is_api(*accepted), [True] * len(accepted))
        self.assertEqual(self.is_api(*rejected), [False] * len(rejected))

    def test_a_package_or_module_of_generated_txt_does_not_count(self) -> None:
        self.write("pkg/__init__.py")
        self.write("made/__init__.py")
        self.write("my_app.py")
        self.write(".agents/generated.txt", "# made by a tool\nmade/\nmy_app.py\npkg/gen.py\n")
        # A generated module in a package that counts still has an API page.
        self.assertEqual(self.is_api("made/x.py", "my_app.py", "pkg/gen.py", "pkg/core.py"),
                         [False, False, True, True])

    def test_a_list_of_sections_with_its_dashes_at_the_column_of_the_key(self) -> None:
        self.write("pkg/__init__.py")
        self.write("other/__init__.py")
        self.write("docs/_smalldocs.yml", "api:\n- packages: [pkg]\n  out: api\n- packages:\n  - other\nproject:\n"
                                          "  type: website\n")
        self.assertEqual(self.is_api("pkg/a.py", "other/a.py", "x/a.py"), [True, True, False])

    def test_a_package_is_found_as_python_imports_it(self) -> None:
        # src/ holds only a folder with no __init__.py, so the package at the top wins.
        (self.root / "src/pkgq/__pycache__").mkdir(parents=True)
        self.write("pkgq/__init__.py")
        # A module beats a folder of data with the same name.
        self.write("modq.py")
        (self.root / "modq/templates").mkdir(parents=True)
        # With no package and no module, the folders are a namespace package.
        self.write("src/space/a.py")
        self.write("space/b.py")
        self.write("docs/_smalldocs.yml", "api:\n  packages: [pkgq, modq, space]\n")
        self.assertEqual(self.is_api("pkgq/a.py", "src/pkgq/a.py", "modq.py", "modq/templates/t.py", "src/space/a.py",
                                     "space/b.py"), [True, False, True, False, True, True])

    def test_the_name_of_the_project_as_toml_reads_it(self) -> None:
        self.write("my_app.py")
        for text in ('[project] # the metadata\nname = "my-app"\n', 'project.name = "my-app"\n',
                     '[tool.poetry]\nname = "My.App"\n'):
            self.write("pyproject.toml", text)
            self.assertEqual(self.is_api("my_app.py"), [True], text)
            # Python 3.10 or older has no tomllib. Its regular expression does not read a dotted key.
            if PYTHON39 and not text.startswith("project.name"):
                self.assertEqual(self.is_api("my_app.py", python=PYTHON39), [True], text)

    def test_the_packages_and_the_check_globs_of_the_key_api(self) -> None:
        self.write("src/pkg/sub/__init__.py")
        self.write("one.py")
        self.write("docs/_smalldocs.yml", "project:\n  type: website\napi:\n  packages: [pkg.sub, one]  # the packages\n"
                                          "  root: ..\n  check:\n    - 'scripts/*.py'\n    - \"**/tool_*.py\"\n")
        accepted = ["src/pkg/sub/x.py", "src/pkg/sub/deep/y.py", "one.py", "scripts/run.py", "a/b/tool_x.py",
                    "tool_y.py"]
        rejected = ["pkg/__init__.py", "src/pkg/other.py", "scripts/deep/run.py", "src/pkg/sub/data.json",
                    ".hidden/tool_x.py"]
        self.assertEqual(self.is_api(*accepted), [True] * len(accepted))
        self.assertEqual(self.is_api(*rejected), [False] * len(rejected))

    def test_a_package_folder_at_the_top_when_src_has_none(self) -> None:
        self.write("pkg/sub/__init__.py")
        self.write("docs/_smalldocs.yml", "api:\n  packages:\n    - pkg.sub\n")
        self.assertEqual(self.is_api("pkg/sub/x.py", "src/pkg/sub/x.py"), [True, False])

    def test_a_list_of_sections_and_another_language(self) -> None:
        self.write("pkg/__init__.py")
        self.write("web/__init__.py")
        self.write("docs/_smalldocs.yml", "api:\n  - packages: pkg\n    out: api\n"
                                          "  - language: typescript\n    packages: [web]\n    entry: [web]\n")
        self.assertEqual(self.is_api("pkg/x.py", "web/x.py"), [True, False])

    def test_a_root_out_of_the_repository_or_another_folder(self) -> None:
        self.write("code/pkg/__init__.py")
        self.write("docs/_smalldocs.yml", "api:\n  packages: [pkg]\n  root: ../code\n")
        self.assertEqual(self.is_api("code/pkg/x.py", "pkg/x.py"), [True, False])
        self.write("docs/_smalldocs.yml", "api:\n  packages: [pkg]\n  root: ../../away\n")
        self.assertEqual(self.is_api("code/pkg/x.py"), [False])

    def test_without_the_api_tool_or_the_docs_role_no_path_counts(self) -> None:
        self.write("pkg/__init__.py")
        for record in ({"tools": ["python:lint"], "choices": {"docs": True}},
                       {"tools": ["python:api"], "choices": {"docs": False}}, {}):
            self.write(".agents/stack.json", json.dumps(record))
            self.assertEqual(self.is_api("pkg/x.py"), [False], record)
        (self.root / ".agents/stack.json").unlink()
        self.assertEqual(self.is_api("pkg/x.py"), [False])

    def test_no_config_and_no_package_gives_false(self) -> None:
        self.assertEqual(self.is_api("x.py", "pkg/x.py"), [False, False])

    def test_a_broken_config_gives_false_and_no_crash(self) -> None:
        self.write("pkg/__init__.py")
        for text in ("api: {packages: [pkg]}\n", "api:\n  packages: [pkg\n", "api:\n  packages: 'pkg\n",
                     "api:\n  - packages: [pkg]\n   oops\n", "api:\n  just text\n"):
            self.write("docs/_smalldocs.yml", text)
            self.assertEqual(self.is_api("pkg/x.py"), [False], text)
        # A config that is not UTF-8 has no key api that api-check reads, so the found packages count, as there.
        (self.root / "docs/_smalldocs.yml").write_bytes(b"api:\n  packages: [other]\n\xff")
        self.assertEqual(self.is_api("pkg/x.py"), [True])
        self.write(".agents/stack.json", "{not json")
        self.assertEqual(self.is_api("pkg/x.py"), [False])
        (self.root / ".agents/stack.json").write_bytes(b"\xff\xfe")
        self.assertEqual(self.is_api("pkg/x.py"), [False])

    def test_an_empty_key_api_gives_false(self) -> None:
        self.write("pkg/__init__.py")
        self.write("docs/_smalldocs.yml", "api:\nproject:\n  type: website\n")
        self.assertEqual(self.is_api("pkg/x.py"), [False])

    def test_it_writes_nothing(self) -> None:
        self.write("pkg/__init__.py")
        self.write("docs/_smalldocs.yml", "api:\n  packages: [pkg]\n")
        before = sorted(str(p) for p in self.root.rglob("*"))
        self.is_api("pkg/x.py")
        self.assertEqual(sorted(str(p) for p in self.root.rglob("*")), before)

    def test_the_rule_has_python_3_9_syntax_and_only_the_standard_library(self) -> None:
        tree = ast.parse(RULE.read_text(), feature_version=(3, 9))
        names = {alias.name.split(".")[0] for node in ast.walk(tree) if isinstance(node, ast.Import)
                 for alias in node.names}
        names |= {node.module.split(".")[0] for node in ast.walk(tree) if isinstance(node, ast.ImportFrom)}
        self.assertEqual(names, {"json", "os", "re", "tomllib"})

    @unittest.skipUnless(PYTHON39, "needs python3.9")
    def test_it_runs_on_python_3_9(self) -> None:
        self.write("pkg/__init__.py")
        self.write("docs/_smalldocs.yml", "api:\n  packages: [pkg]\n")
        self.assertEqual(self.is_api("pkg/x.py", "x.py", python=PYTHON39), [True, False])

    @unittest.skipUnless(shutil.which("git"), "needs git")
    def test_without_the_key_api_it_finds_the_packages_that_api_check_finds(self) -> None:
        files = ["pkg/__init__.py", "pkg/core.py", "src/lib/__init__.py", "src/lib/x.py", "my_app.py", "src/my_app.py",
                 "noxfile.py", "loose/x.py", "_private/__init__.py", "pkg/test_core.py", "tests/test_m.py",
                 "setup.py", "pkg/gen.py"]
        for name in files:
            self.write(name)
        self.write(".agents/generated.txt", "pkg/gen.py\n")
        subprocess.run(["git", "init", "-q"], cwd=self.root, check=True)
        steps = load_steps()
        here = os.getcwd()
        os.chdir(self.root)
        try:
            names = set(steps.top_names(set()))
        finally:
            os.chdir(here)
        found = [name for name, yes in zip(files, self.is_api(*files)) if yes]
        tops = {Path(name).parts[1] if name.startswith("src/") else Path(name).parts[0] for name in found}
        self.assertEqual({top.removesuffix(".py") for top in tops}, names)

    def test_the_profile_installs_it_and_generated_txt_does_not_name_it(self) -> None:
        package = json.loads((RULE.parents[3] / "skill-package.json").read_text())
        self.assertIn(".agents/just/python", package["install_extras"]["files"])
        self.assertNotIn("api_rule", (RULE.parents[3] / "profile.json").read_text())


if __name__ == "__main__":
    unittest.main()
