# hypothesmith
Hypothesis strategies for generating Python programs, something like CSmith.

This is definitely pre-alpha, but if you want to play with it feel free!
You can even keep the shiny pieces when - not if - it breaks.

Get it today with [`pip install hypothesmith`](https://pypi.org/project/hypothesmith/),
or by cloning [the GitHub repo](https://github.com/Zac-HD/hypothesmith).

You can run the tests, such as they are, with `tox` on Python 3.6 or later.
Use `tox -va` to see what environments are available.

## Changelog

### 0.0.3 - 2019-08-08
Checks validity at statement level, which makes filtering much more efficient.
Improved testing, input validation, and code comments.

### 0.0.2 - 2019-08-07
Improved filtering and fixing of source code generated from the grammar.
This version found a novel bug: `"pass #\\r#\\n"` is accepted by the
built-in `compile()` and `exec()` functions, but not by `black` or `lib2to3`.

### 0.0.1 - 2019-08-06
Initial release.  This is a minimal proof of concept, generating from the
grammar and rejecting it if we get errors from `black` or `tokenize`.
Cool, but while promising not very useful at this stage.
