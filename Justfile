# The documentation site, from docs/, with smalldocs.
smalldocs := "uvx --quiet smalldocs@0.5.12"

docs-check:
  {{smalldocs}} check docs

docs:
  {{smalldocs}} preview docs

docs-build:
  {{smalldocs}} render docs --strict

# Build the site in strict mode, then push it to the branch gh-pages
docs-publish: docs-build
  {{smalldocs}} publish gh-pages docs --no-render

# Run the tests of the recipes of the profile, with real just, uv and pytest
test:
  python3 -m unittest discover -s tests -q

# The live lab of api_rule.py: install the profile into a new project with the installer of jnterfaces
live-api-rule:
  JNPROFILE_LIVE=1 python3 -m unittest discover -s tests -p 'test_live_*.py' -v
