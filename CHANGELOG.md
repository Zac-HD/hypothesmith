# Changelog

### 0.1.5 - 2020-10-12
- Emit additional debug info when Python fails to compile a string

### 0.1.4 - 2020-08-16
- Improve handling of identifiers
- Fix internal error in `from_grammar("single_input")`

### 0.1.3 - 2020-07-30
- Update to latest versions of LibCST and Hypothesis, for Python 3.9 support

### 0.1.2 - 2020-05-17
- Emit *more* debug info to diagnose a `compile()` issue in CPython nightly

### 0.1.1 - 2020-05-17
- Emit some debug info to help diagnose a possible upstream bug in CPython nightly

### 0.1.0 - 2020-04-24
- Added `auto_target=True` argument to the `from_node()` strategy.
- Improved `from_node()` generation of comments and trailing whitespace.

### 0.0.8 - 2020-04-23
- Added a `from_node()` strategy which uses [`LibCST`](https://pypi.org/project/libcst/)
  to generate source code.  This is a proof-of-concept rather than a robust tool,
  but IMO it's a pretty cool concept.

### 0.0.7 - 2020-04-19
- The `from_grammar()` strategy now takes an `auto_target=True` argument, to
drive generated examples towards (relatively) larger and more complex programs.

### 0.0.6 - 2020-04-08
- support for non-ASCII identifiers

### 0.0.5 - 2019-11-27
- Updated project metadata and started testing on Python 3.8

### 0.0.4 - 2019-09-10
- Depends on more recent Hypothesis version, with upstreamed grammar generation.
- Improved filtering rejects fewer valid examples, finding another bug in Black.

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
