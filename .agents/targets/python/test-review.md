# Python rules for the test review

These rules add to the base task for the Python tests of the change.

- **Where the tests are.** A test file is in `tests/`, or its name is `test_*.py` or `*_test.py`. `conftest.py`
  holds the fixtures. `test-parent` copies only these files into the parent commit, so a new test of new code
  fails there.
- **Each test checks a result.** A test uses `assert` on a value, or `pytest.raises` with `match=` on the text of
  the error. A test that only calls the code and checks nothing is a finding.
- **The pragma.** `# pragma: no cover` leaves a line, or a block that starts on that line, out of
  `coverage-check`. Each new pragma needs a reason in a comment, for example
  `# pragma: no cover - only runs on Windows`. A pragma on logic that a test can reach is a finding.
- **The lists.** A change to a file that the parent commit lists in `.agents/generated.txt` or
  `.agents/coverage-exclude.txt` passes `coverage-check` without a test. Each new entry needs a reason in a comment
  line above it. Judge each such change, and report new logic in it that a test can reach.
- **The coverage config.** The settings of coverage.py in `[tool.coverage.*]` of `pyproject.toml`, in
  `.coveragerc`, in `setup.cfg` or in `tox.ini` come from the commit itself, not from its parent. A new
  `exclude_lines`, `exclude_also`, `omit` or `partial_branches` can hide new code from `coverage-check`. Each change
  to that config is a finding, unless it has a reason and hides no logic that a test can reach.
- **Skips and xfail.** A new `pytest.mark.skip`, `skipif` or `xfail` names its reason with `reason=`. A test that
  is skipped on every machine of the project proves nothing.
- **Mocks.** A mock stands in for a slow or outside service, not for the code under test. A test whose mocks
  give back the answer that it checks is a finding.
