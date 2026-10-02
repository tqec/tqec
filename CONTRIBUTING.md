# How to contribute to `tqec`

This file is the single source for the contribution process. It is shown by GitHub and is also included in the
[contributor guide](https://tqec.github.io/tqec/contributor_guide.html), which additionally explains the developer
installation and how to build the documentation.

<!-- sphinx-include-start -->

## Ways to contribute

- **Report a bug or request a feature** — [open an issue](https://github.com/tqec/tqec/issues/new/choose) with the
  matching template, and add the [labels](#issue-labels) that fit.
- **Ask a question** — open an issue with the "Asking a question" template and give as much context as you can.
- **Contribute code or documentation** — follow the [contribution steps](#contribution-steps) below.

## Issue labels

Labels sort issues and pull requests by kind, topic and priority. The full list, with descriptions, is on the
[labels page](https://github.com/tqec/tqec/labels). The ones most useful for finding work are:

- [good first issue](https://github.com/tqec/tqec/labels/good%20first%20issue) — good for newcomers;
- [non-quantum](https://github.com/tqec/tqec/labels/non-quantum) — requires no knowledge of quantum science and
  technology;
- [help wanted](https://github.com/tqec/tqec/labels/help%20wanted) — more developers would accelerate progress;
- [priority: high](https://github.com/tqec/tqec/labels/priority%3A%20high) — along the critical path towards a
  milestone.

Other labels give the kind of change (`bug`, `enhancement`, `fix`, `refactor`, `performance`, `documentation`,
`ci/cd`) or the part of the project it touches (`circuit-generation`, `block graph`, `hci`, `ux`). Issues labelled
`on hold` or `future` are blocked and are not ready to be picked up.

## AI use

You may use AI tools, such as large language models (LLMs), to help you contribute. You are responsible for
everything you submit. Maintainers review contributions with these expectations:

- **Be concise.** Keep issues, comments and PR descriptions short and specific. Long AI-generated text that repeats
  what is already known, or does not answer the discussion, takes reviewers' time. It may be closed or marked as
  off-topic without further review.
- **Submit only code that can be verified.** Maintainers merge code only when they can check that it is correct, through
  readable changes, tests and a clear explanation. A feature or bug fix that reviewers cannot test will not be merged.
  In general, the more clearly verifiable evidence you present, the faster your PR will be merged.
- **Understand your contribution.** Be ready to explain your changes and to answer reviewers' questions in your own
  words. A PR whose author cannot answer questions about it may be closed.

Repeatedly ignoring these expectations may lead to being blocked from the repository.

### Saying how you used AI

Please say at the start whether a text you post on GitHub was written with AI help. The pull request and issue templates
have an "AI use" section for this, with four options: no AI tool, AI-assisted, mostly or entirely AI-written, and
AI-translated. GitHub cannot add such a section to comments and reviews. If a comment was mostly written or translated
by an AI tool, say so in its first line. Saying that you used AI is welcome and is never a reason to reject a
contribution; it helps reviewers decide how to read it.

## Contribution steps

### 1. Find an issue

Start with the [issues list](https://github.com/tqec/tqec/issues), and filter it by the [labels](#issue-labels) above.

Pick an issue you **want** to work on. This is an open source project — do not force yourself to work on something
that does not interest you.

#### Writing an issue

If no issue describes the change you have in mind, [create one](https://github.com/tqec/tqec/issues/new/choose) before
writing any code. Use the matching template and keep the issue short enough for a maintainer with limited time to read:

- one problem or feature per issue;
- a title that says what is wrong or what is wanted;
- for a bug — what happened, what you expected, and the smallest code example that reproduces it;
- for a feature — the motivation, and the alternatives you considered.

A bug report must include code that reproduces the bug, so that a maintainer can run it and see the problem.

### 2. Comment on the issue

Comment on the issue to:

1. make your interest public;
2. ask whether the issue is still up to date.

A maintainer will assign the issue to you if nobody else is working on it and it is still relevant. Wait for the
assignment before you start — this prevents two people from working on the same change without knowing about each
other.

You claim an issue by commenting on it, and it is yours once a maintainer assigns it to you. The "Assignees" field
of the issue shows who is working on it.

#### Working on an assigned issue

Post short progress updates in the issue, especially when you are stuck or progress slows down. A draft pull request is
a good way to show progress.

For some important, potentially advanced features, describe the advantages of your approach in the issue or PR.

If you find that you cannot finish, for whatever reason, say so in the issue so that a maintainer can remove your
assignment and someone else can pick it up.

#### If someone else is assigned

If an issue interests you but the person assigned to it seems inactive, comment on the issue or contact them to ask
about progress, and offer to help or to take over. If nobody answers, ask a maintainer in the issue to reassign it.

### 3. Create a branch

Contributors with write access (maintainers) can
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
see the compilation pipeline end to end.

If you change the documentation, `make fasthtml` (run in `docs/`) builds it quickly. It does not execute notebook cells,
and it skips the gallery notebooks and the user guide pages that execute code or run long simulations (`quick_start`,
`detailed_plots`, `collada_interop`, `build_computation` and `bgraph`). Your PR is checked with the full build
(`make html`), which runs all of them, and with a link check (`make linkcheck`). See
[Building documentation locally](https://tqec.github.io/tqec/contributor_guide.html#building-documentation-locally)
for both builds, and
[Contributing to documentation](https://tqec.github.io/tqec/contributor_guide.html#contributing-to-documentation) for
the rules specific to documentation changes.

### 5. Open a pull request

When your change is ready for review, or at least ready to be read by others,
[open a pull request (PR)](https://docs.github.com/en/pull-requests/collaborating-with-pull-requests/proposing-changes-to-your-work-with-pull-requests/creating-a-pull-request)
against the `main` branch of tqec. Fill in the pull request template. Explain what the change does, which issue it
addresses and how you tested it, and complete the "AI use" section. A maintainer may close a PR whose description is
empty, is missing the template's sections, or still contains the template's placeholder text. If the change is growing
large, open a draft PR early so that others can look at it before it is finished.

### 6. Review and merge

A PR is merged once at least one maintainer has reviewed and approved it. Iterate with the reviewers until then.

- **Contributors with write access (maintainers)** can merge the PR themselves with the "Merge" button.
- **External contributors** (no write access) cannot merge. Instead, add a comment such as "Ready to merge" on the PR,
  and a maintainer will merge it.

After the merge, delete your branch.

#### Inactive pull requests

A scheduled job runs daily and manages inactive pull requests. A PR with no activity for 30 days is labelled stale
with a comment. If there is still no activity 7 days after being marked stale, the PR is closed. PRs with an open
review request carry the `needs-review` label and are never marked stale; the label is added and removed
automatically. Issues are never marked stale or closed by this job.

To keep a PR open, push a commit, comment, or request a review. If your PR was closed this way, you can ask a
maintainer to reopen it.

## Getting help

- Ask in the issue you are working on, or open an issue with the "Asking a question" template.
- Join the [weekly online meeting](https://meet.jit.si/TQEC-design-automation), every Wednesday at 8:30am Pacific
  time. It is used to discuss project progress and to give educational talks, and everyone is welcome.
