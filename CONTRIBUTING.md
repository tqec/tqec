# How to contribute to the `tqec` library

## Run tests

After downloading the code and setting up your development environment, try to run all the tests using `uv run pytest tests/`. If you're new to the codebase, try examining `compile_test.py::test_compile_memory` to understand the compilation pipeline that TQEC uses.

## Open issues

If you found a bug, an optimization, or would like a missing feature to be implemented, [create an issue](https://github.com/tqec/tqec/issues/new/choose). In order for your issue to be efficiently treated, please include the appropriate labels.

## Asking a question

If you only want to ask a question, go to the [issue panel](https://github.com/tqec/tqec/issues/new/choose) and click on the "Ask a question" template. Provide as much information as possible.

## Contributing code

Code contribution follow a rigid but standard process:

1. Check if there is an issue describing the problem you want to solve or the feature you want to implement in the [issues panel](https://github.com/tqec/tqec/issues).
2. If there is no issue, [create an issue](https://github.com/tqec/tqec/issues/new/choose) describing the change you'd like to see.
3. Ask for someone to assign yourself on the issue by commenting on the issue page.
4. If you haven't already, fork the repository into your GitHub account, and create a new branch (with a descriptive name).
5. Implement your code change in your branch. Update and create tests as needed. Be sure all tests pass.
7. Submit a pull request when you think you fixed the issue. If the changes start accumulating and the to-be-opened PR is large, open a draft PR to let other people look at your code, even if it still needs to be fully finished.
8. Wait for reviews and iterate with reviewers until the PR is satisfactory.
9. Merge the PR and delete the branch; well done!

Please do not forget to open an issue (and, if possible, assign yourself) **before** writing code, as this helps avoiding people working on the same feature/bug in parallel without knowing about each other.
