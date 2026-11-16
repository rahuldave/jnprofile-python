# Python rules for the prose

These rules add to the base task for the prose of the Python docs of the change.

- **Docstrings are prose.** Apply the guide to the text of each changed docstring, as to a page. Keep the code
  examples, the doctest lines that start with `>>>` and the names of the parameters as they are.
- **The first line.** The first line of a docstring is one sentence that ends with a period. `help()` and the
  lists of items show it alone, so it makes sense without the rest of the docstring.
- **Names in code.** Write the name of a module, a class, a function or a parameter in backticks, as in
  `parse()`, so that the check of the guide and the reader see it as code.
