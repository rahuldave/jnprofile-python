# The recipes of this repository, the same in each profile of jnterfaces: lint, test, prose-check, docs-check,
# release-check, release and check. CI runs just check, in .github/workflows/verify.yml.
smalldocs := "uvx --quiet smalldocs@0.5.12"
ruff := "uvx --quiet ruff@0.17.5"
# The checker of nossaifd. CI sets NOSSAIFD_CHECK to its clone of nossaifd.
nossaifd_check := env("NOSSAIFD_CHECK", home_directory() / "Projects/nossaifd/check.py")

# Every check of the repository, in this order
check: release-check lint test prose-check docs-check

# The release tags. scripts/release_tag.py is a copy of .agents/skills/gpa/scripts/release_tag.py of
# agent_gest_git_skills at the commit 26ef730. The job release of verify.yml runs just release on each push to main.
release_tag := "uv run --no-project --quiet --no-python-downloads --python '>=3.9' python scripts/release_tag.py"

# Tag HEAD with the next release vX.Y.Z by semver, push the tag and check it. Takes --dry-run first
[positional-arguments]
release *args:
  @{{release_tag}} "$@"

# Print the next tag, or fail on a git error. It needs no network and no remote
release-check:
  {{release_tag}} --check

# The lint of the Python scripts with ruff, and of the recipe files of the profile
lint:
  {{ruff}} check .
  python3 scripts/lint_recipes.py

# Run the tests of the recipes of the profile, with real just, uv, git and pytest. The live lab installs the profile
# with the installer of jnterfaces: JNTERFACES_INSTALLER, else ~/Projects/jnterfaces/scripts/install_stack.py
test:
  python3 -m unittest discover -s tests -q

# The live lab of api_rule.py alone
live-api-rule:
  python3 -m unittest discover -s tests -p 'test_live_*.py' -v

# The checker of nossaifd on each Markdown page of the repository. A hard note fails it
prose-check:
  git ls-files -z '*.md' | xargs -0 uv run --no-project --quiet python {{quote(nossaifd_check)}}

docs-check:
  {{smalldocs}} check docs

docs:
  {{smalldocs}} preview docs

docs-build:
  {{smalldocs}} render docs --strict

# Build the site in strict mode, then push it to the branch gh-pages
docs-publish: docs-build
  {{smalldocs}} publish gh-pages docs --no-render
