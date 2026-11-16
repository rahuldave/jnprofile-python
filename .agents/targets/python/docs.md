# Python rules for the docs

These rules add to the base task for the docs of the Python code of the change.

- **A docstring for each item.** Write a docstring for each module, class, function and method, public or
  private. `docstring-check` fails on an item without one. A magic method, such as `__repr__`, `__init__`, an `@overload` stub, a
  property setter and a property deleter
  need none, because the protocol and the docstring of the class say what they do.
- **The first line.** The first line of a docstring is one sentence that says what the item is for, beyond what
  its name says.
- **The parts.** Say what each parameter is for when its name does not, what the function returns, and which
  error it raises, and on which input. Give an example for a public function whose use is not plain from its
  signature.
- **Type hints.** Give the types in the signature, not in the docstring, so that `typecheck` checks them.
