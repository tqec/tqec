# How to contribute to `tqec`

This file is the single source for the contribution process. It is shown by GitHub and is also included in the
[contributor guide](https://tqec.github.io/tqec/contributor_guide.html), which additionally explains the developer
installation and how to build the documentation.

<!-- sphinx-include-start -->

## Ways to contribute

- **Report a bug or request a feature:** [open an issue](https://github.com/tqec/tqec/issues/new/choose) with the
  matching template, and add the labels that fit.
- **Ask a question:** open an issue with the "Asking a question" template and give as much context as you can.
- **Contribute code or documentation:** follow the steps below.

## Contribution steps

### 1. Find an issue

Start with the [issues list](https://github.com/tqec/tqec/issues). Useful labels:

- [good first issue](https://github.com/tqec/tqec/issues?q=is%3Aissue+is%3Aopen+label%3A%22good+first+issue%22):
  judged easy to address without prior knowledge of the code base.
- [backend](https://github.com/tqec/tqec/issues?q=is%3Aissue+is%3Aopen+label%3Abackend): issues about the Python
  code.

Pick an issue you **want** to work on. This is an open source project: do not force yourself to work on something that
does not interest you.

If no issue describes the change you have in mind,
[create one](https://github.com/tqec/tqec/issues/new/choose) before writing any code.

### 2. Comment on the issue

Comment on the issue to:

1. make your interest public;
2. ask whether the issue is still up to date.

A maintainer will assign the issue to you if nobody else is working on it and it is still relevant. Wait for the
assignment before you start: it prevents two people from working on the same change without knowing about each other.

If you later find that you cannot finish, for whatever reason, say so in the issue so that a maintainer can un-assign
you and someone else can pick it up.

### 3. Create a branch

Contributors with write access to the tqec repository can
[create a branch](https://git-scm.com/book/en/v2/Git-Branching-Basic-Branching-and-Merging) directly in the tqec
repository. Everyone else can [fork the tqec repository](https://github.com/tqec/tqec/fork) and create a branch
there (see
[GitHub's guide to forks](https://docs.github.com/en/pull-requests/collaborating-with-pull-requests/working-with-forks/fork-a-repo)).
Give the branch a descriptive name and use one branch per issue.

### 4. Work in your branch

Implement your change in that branch only. To set up a development environment, follow the
[developer installation](https://tqec.github.io/tqec/contributor_guide.html#installation-procedure-for-developers).

Run the fast tests first:

```bash
uv run pytest
```

Run the slow (integration) tests with:

```bash
uv run pytest -m slow
```

Update existing tests if your change requires it, and add tests for every new class or function; see `tests/` for
examples. If you are new to the code base, `test_compile_memory` in `tests/compile/compile_test.py` is a good place to
see the compilation pipeline end to end. If you change the documentation, also read
[Contributing to documentation](https://tqec.github.io/tqec/contributor_guide.html#contributing-to-documentation).

### 5. Open a pull request

When your change is ready for review, or at least ready to be read by others,
[open a pull request (PR)](https://docs.github.com/en/pull-requests/collaborating-with-pull-requests/proposing-changes-to-your-work-with-pull-requests/creating-a-pull-request)
against the `main` branch of tqec. Fill in the pull request template: explain what the change does, which issue it
addresses and how you tested it. If the change is growing large, open a draft PR early so that others can look at it
before it is finished.

### 6. Review and merge

A PR is merged once at least one maintainer has reviewed and approved it. Iterate with the reviewers until then.

- **Contributors with write access** can merge the PR themselves with the "Merge" button.
- **External contributors** (no write access) cannot merge: add a comment such as "Ready to merge" on the PR, and a
  maintainer will merge it.

After the merge, delete your branch.

## Getting help

- Ask in the issue you are working on, or open an issue with the "Asking a question" template.
- Join the [weekly online meeting](https://meet.jit.si/TQEC-design-automation), every Wednesday at 8:30am Pacific
  time. It is used to discuss project progress and to give educational talks, and everyone is welcome.
