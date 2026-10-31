# The documentation site, from docs/, with smalldocs.
smalldocs := "uvx --quiet smalldocs@0.5.4"

docs-check:
  {{smalldocs}} check docs

docs:
  {{smalldocs}} preview docs

docs-build:
  {{smalldocs}} render docs --strict

# Build the site in strict mode, then push it to the branch gh-pages
docs-publish: docs-build
  {{smalldocs}} publish gh-pages docs --no-render
