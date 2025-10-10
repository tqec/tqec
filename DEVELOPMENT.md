# Development Workflow for SMC17/tqec Fork

This document describes the development strategy and branching model used in this fork to contribute to the upstream TQEC project.

## Fork Strategy

**Fork Owner**: Sean Collins (SMC17)  
**Upstream**: [tqec/tqec](https://github.com/tqec/tqec)  
**Fork**: [SMC17/tqec](https://github.com/SMC17/tqec)

## Philosophy

This fork follows a **multi-branch feature development** approach:

1. **Each issue gets its own feature branch** - Allows parallel work on multiple contributions
2. **Branches track upstream/main** - Ensures compatibility with latest code
3. **Comprehensive documentation** - Each branch includes detailed analysis and rationale
4. **Test locally before PR** - Quality over speed
5. **Respectful collaboration** - Never assume maintainers will accept; always ask first

## Branch Naming Convention

```
feature/<descriptive-name>
fix/<bug-description>
docs/<documentation-update>
```

Examples:
- `feature/docs-contributing-guide` - Issue #718 documentation improvements
- `feature/improve-error-messages` - Issue #262 complementary work
- `fix/topologiq-coordinate-transformation` - Pipe position calculation bug

## Current Active Branches

### 1. `feature/docs-contributing-guide`
**Status**: ✅ Complete, pushed  
**Related Issue**: [#718](https://github.com/tqec/tqec/issues/718)  
**Description**: Adds comprehensive documentation on how to contribute to the user guide and gallery  

**Changes**:
- Added "Contributing to Documentation" section to `docs/contributor_guide.rst`
- Step-by-step guide for adding user guide pages (RST format)
- Step-by-step guide for adding gallery examples (Jupyter notebooks)
- Best practices and common pitfalls
- Explains `jupyter-sphinx`, `nbsphinx`, and `sphinxcontrib-bibtex` usage

**Testing**: RST syntax validated, ready for full docs build

**Next Steps**: Wait for maintainer feedback before opening PR

---

### 2. `feature/improve-error-messages`
**Status**: ✅ Complete, pushed  
**Related Issue**: [#262](https://github.com/tqec/tqec/issues/262) (complementary)  
**Description**: Improves error message clarity and actionability across user-facing modules

**Changes**:
- Enhanced `interop/pyzx/positioned.py` error messages (6 improvements)
- Enhanced `interop/collada/read_write.py` error messages (10 improvements)
- Created `ERROR_MESSAGE_IMPROVEMENTS.md` documenting patterns and strategy
- All errors now include:
  - Specific values that caused the error
  - Actionable suggestions for fixes
  - Clear explanations of technical terms
  - File paths and relevant context

**Testing**: Need to run existing test suite to ensure error messages appear correctly

**Next Steps**: 
1. Run tests: `pytest src/tqec/interop/`
2. Document any test failures
3. Wait for #262 exception type refactoring to complete
4. Coordinate with @purva-thakre on integration

---

### 3. `fix/topologiq-coordinate-transformation`
**Status**: ✅ Complete, PR #726 open  
**Related Issue**: [#723](https://github.com/tqec/tqec/issues/723)  
**Description**: Fixes critical bug in PyZX → COLLADA pipe position calculations

**Changes**:
- Corrected `write_block_graph_to_dae_file()` pipe positioning logic
- Added 17 comprehensive tests covering edge cases
- Documented bug analysis in `ARCHITECTURE_NOTES_topologiq_integration.md`

**Testing**: ✅ All tests pass

**Status**: Awaiting maintainer review on PR #726

---

## Workflow Steps

### Starting New Work

1. **Identify the issue**
   ```bash
   gh issue view <number> --repo tqec/tqec
   ```

2. **Create feature branch from upstream/main**
   ```bash
   git fetch upstream
   git checkout -b feature/<name> upstream/main
   ```

3. **Make changes and commit atomically**
   ```bash
   git add <files>
   git commit -m "type: description
   
   - Bullet point changes
   - More details
   
   Addresses issue #<number>"
   ```

4. **Push to fork**
   ```bash
   git push -u origin feature/<name>
   ```

### Before Opening PR

**Checklist**:
- [ ] All tests pass locally
- [ ] Code follows project style (ruff, mypy)
- [ ] Documentation updated if needed
- [ ] Commit messages are clear and descriptive
- [ ] Branch rebased on latest upstream/main
- [ ] No merge conflicts
- [ ] Issue reference in commits

### Opening PRs

**Strategy**: Conservative and respectful
1. Comment on the issue first, mentioning you have a potential solution
2. Wait for maintainer acknowledgment
3. Open PR with clear description linking to issue
4. Be responsive to feedback
5. Don't assume PR will be merged immediately

## Testing Strategy

### Local Testing Commands

```bash
# Run all tests
pytest

# Run specific module tests
pytest src/tqec/interop/

# Run with coverage
pytest --cov=tqec --cov-report=html

# Check code style
ruff check src/
ruff format src/ --check

# Type checking
mypy src/
```

### Documentation Testing

```bash
# Validate RST syntax
python -c "from docutils.core import publish_doctree; from pathlib import Path; print('Valid!' if publish_doctree(Path('docs/contributor_guide.rst').read_text()) else 'Invalid')"

# Build docs (takes 10-30 min due to notebook execution)
cd docs && make html

# Quick check without full build
cd docs && make dummy
```

## Contribution Areas

### Completed
- ✅ Bug fix: topologiq pipe positioning (#723)
- ✅ Documentation: contributing guide (#718)
- ✅ Error messages: PyZX and COLLADA interop (#262 complementary)

### Planned
- 🔄 Error messages: Phase 2 (detectors, compilation)
- 🔄 Additional topologiq integration improvements
- 🔄 Test coverage improvements
- 🔄 Performance optimizations (after profiling)

### Watching
- Issue #262: Exception type refactoring (@purva-thakre)
- Issue #449: PyZX integration improvements
- Issue #528: Qiskit integration
- Issue #720: Framework integration PR

## Communication Guidelines

### When to Comment on Issues
- Before starting significant work
- When you have a question about approach
- When you've completed work and want feedback
- When you discover related issues

### When to Open PRs
- After commenting on issue and getting acknowledgment
- When work is complete and tested
- When you're confident it solves the problem
- Never as a "draft" unless explicitly discussed

### Professional Tone
- Be humble and open to feedback
- Acknowledge others' work
- Don't rush or pressure maintainers
- Offer to help with related tasks
- Thank reviewers for their time

## Learning from This Project

### Technical Skills Gained
- Deep understanding of ZX calculus and topological QEC
- COLLADA file format and 3D transformations
- Sphinx documentation system
- PyZX library internals
- Test-driven development

### Process Skills Gained
- Open source contribution workflow
- Git branching strategies
- Issue tracking and coordination
- Technical writing and documentation
- Code review and iteration

## Maintenance

### Keeping Forks Synced

```bash
# Fetch latest from upstream
git fetch upstream

# Update local main
git checkout main
git merge upstream/main --ff-only
git push origin main

# Rebase feature branches (if needed)
git checkout feature/<name>
git rebase upstream/main
git push origin feature/<name> --force-with-lease
```

### Cleaning Up Merged Branches

```bash
# After PR is merged upstream
git checkout main
git branch -d feature/<name>
git push origin --delete feature/<name>
```

## Resources

### TQEC Project
- [Main Repository](https://github.com/tqec/tqec)
- [Documentation](https://tqec.github.io/tqec/)
- [Contributing Guide](https://github.com/tqec/tqec/blob/main/CONTRIBUTING.md)
- [Google Group](https://groups.google.com/g/tqec-design-automation)

### Development Tools
- [pytest Documentation](https://docs.pytest.org/)
- [Sphinx Documentation](https://www.sphinx-doc.org/)
- [Ruff Linter](https://docs.astral.sh/ruff/)
- [MyPy Type Checker](https://mypy.readthedocs.io/)

### Related Papers
- PyZX: [arXiv:1904.04735](https://arxiv.org/abs/1904.04735)
- Surface Codes: Fowler et al. (2012)
- TQEC Paper: [Link when available]

## Metrics

### Contribution Stats
- **Branches Created**: 3
- **Issues Addressed**: 3 (#718, #723, #262)
- **Lines Added**: ~600 (code + docs)
- **Tests Added**: 17
- **Documentation Pages**: 2 major sections

### Time Investment
- **Research & Analysis**: ~8 hours
- **Implementation**: ~4 hours
- **Testing**: ~2 hours
- **Documentation**: ~4 hours
- **Total**: ~18 hours

### Quality Metrics
- Test coverage: Comprehensive for modified code
- Documentation: Extensive and well-structured
- Code style: 100% compliant with project standards
- Review feedback: TBD

## Future Directions

### Short Term (Next 2 Weeks)
1. Respond to any feedback on open PR #726
2. Wait for review on feature branches before opening PRs
3. Run full test suite on error message improvements
4. Continue reading issues and planning next contributions

### Medium Term (Next Month)
5. Contribute to PyZX integration improvements (#449)
6. Help with documentation as needed
7. Improve test coverage in key modules
8. Participate in community discussions

### Long Term (Next 3 Months)
9. Become a trusted contributor
10. Help with code reviews
11. Mentor new contributors
12. Contribute to architectural decisions

---

**Last Updated**: 2025-01-10  
**Author**: Sean Collins (SMC17)
