"""The live lab of api_rule.py: install the profile into a new project, commit, change only a docstring, and ask
is_api of the parent commit about the file, as the commit gate does.

It runs the installer of jnterfaces, in just test and alone in just live-api-rule. JNTERFACES_INSTALLER names the
installer, by default ~/Projects/jnterfaces/scripts/install_stack.py. The installer takes the other packages from the
folder SKILL_PACKAGES_DIR, else from the folder of its clone of jnterfaces. Without the installer, the lab fails, so
just test never passes without it.
"""
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

REPO = Path(__file__).resolve().parent.parent
INSTALLER = Path(os.environ.get("JNTERFACES_INSTALLER", Path.home() / "Projects/jnterfaces/scripts/install_stack.py"))
# The variables of a session of an agent, which the installer reads, and which a lab leaves out.
AGENT = ("CLAUDECODE", "CLAUDE_CODE_SESSION_ID", "CODEX_THREAD_ID")
CODE = ('"""The package m."""\n\n\ndef add(\n    a: int,  # The first number\n) -> int:  # A\n'
        '    """Give A back."""\n    return a\n')
# The gate loads the rule from the parent commit and runs it with python -I -B, in the top of the repository.
ASK = ("import importlib.util, json, subprocess, sys, tempfile, os\n"
       "text = subprocess.run(['git', 'show', 'HEAD:.agents/just/python/api_rule.py'], capture_output=True,\n"
       "                      text=True, check=True).stdout\n"
       "folder = tempfile.mkdtemp()\npath = os.path.join(folder, 'api_rule.py')\nopen(path, 'w').write(text)\n"
       "spec = importlib.util.spec_from_file_location('api_rule', path)\n"
       "rule = importlib.util.module_from_spec(spec)\nspec.loader.exec_module(rule)\n"
       "print(json.dumps({name: rule.is_api(name) for name in sys.argv[1:]}))\n")


class LiveApiRuleTests(unittest.TestCase):
    def setUp(self) -> None:
        for tool in ("uv", "git", "just", "jlog"):
            self.assertTrue(shutil.which(tool), f"the live lab needs {tool}")
        self.assertTrue(INSTALLER.is_file(), f"the live lab needs the installer of jnterfaces at {INSTALLER}. Set "
                                             f"JNTERFACES_INSTALLER")

    def run_in(self, root: Path, *command: str) -> subprocess.CompletedProcess:
        env = {k: v for k, v in os.environ.items() if k not in AGENT and not k.startswith("GIT_")}
        env.update(GIT_AUTHOR_NAME="t", GIT_AUTHOR_EMAIL="t@example.com", GIT_COMMITTER_NAME="t",
                   GIT_COMMITTER_EMAIL="t@example.com")
        return subprocess.run(command, cwd=root, capture_output=True, text=True, env=env)

    def test_a_change_of_only_a_docstring_is_a_change_of_the_api(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            self.run_in(root, "git", "init", "-q", "-b", "main")
            self.run_in(root, "uv", "init", "-q", "--lib", "--name", "m", "--python", "3.12", ".")
            (root / "src/m/__init__.py").write_text(CODE)
            installed = self.run_in(root, "uv", "run", "--script", str(INSTALLER), "--target", ".", "--defaults",
                                    "--profile", "python", "--clone", f"jnprofile-python={REPO}", "docs",
                                    "--without", "tasker")
            self.assertEqual(installed.returncode, 0, installed.stdout + installed.stderr)
            record = json.loads((root / ".agents/stack.json").read_text())
            self.assertIn("python:api", record["tools"])
            self.assertTrue(record["choices"]["docs"])
            # The tasker needs the program gest, which CI does not have, so the lab installs none.
            self.assertFalse(record["choices"]["tasker"])
            self.assertTrue((root / ".agents/just/python/api_rule.py").is_file())
            generated = root / ".agents/generated.txt"
            self.assertNotIn("api_rule", generated.read_text() if generated.is_file() else "")
            self.run_in(root, "git", "add", "-A")
            committed = self.run_in(root, "git", "-c", "commit.gpgsign=false", "commit", "-q", "--no-verify", "-m", "m")
            self.assertEqual(committed.returncode, 0, committed.stderr)
            (root / "src/m/__init__.py").write_text(CODE.replace("Give A back.", "Return A as it is."))
            changed = self.run_in(root, "git", "diff", "--name-only").stdout.split()
            self.assertEqual(changed, ["src/m/__init__.py"])
            asked = self.run_in(root, "python3", "-I", "-B", "-c", ASK, "src/m/__init__.py", "README.md",
                                "tests/test_m.py")
            self.assertEqual(asked.returncode, 0, asked.stderr)
            self.assertEqual(json.loads(asked.stdout),
                             {"src/m/__init__.py": True, "README.md": False, "tests/test_m.py": False})


if __name__ == "__main__":
    unittest.main()
