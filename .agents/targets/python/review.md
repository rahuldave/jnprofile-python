# Python rules for the review

These rules add to the review lenses for the Python code of the change.

- **Errors.** Check each new `except`. A bare `except:` or an `except Exception:` that drops the error is a finding,
  unless it logs the error or raises it again. `raise ... from err` keeps the cause.
- **Mutable defaults.** A default value of a parameter that is a list, a dict or a set is shared between calls.
  Use `None`, and make the value in the function.
- **Paths and processes.** Build paths with `pathlib`, not with `+`. A `subprocess` call takes a list of
  arguments, not a string with `shell=True`, unless the shell is the point and the input is not from a user.
- **Public names.** A new name without a leading `_` is part of the API of the module. Check that it must be
  public.
- **The docs lens.** A docstring says what the item is for, beyond what its name says. A stub, for example
  `"""Returns the result."""`, is a finding.
- **Lint and type pragmas.** Each new `# noqa`, `# type: ignore` or `# ty: ignore` names its rule and a reason.
