# Contribution Validation & Self-Review
**Date**: October 10, 2025  
**Purpose**: Ensure all contributions meet TQEC standards and actually solve problems

---

## Philosophy

**We don't just write code - we solve problems correctly.**

Before submitting ANY PR, we must prove:
1. ✅ The problem exists and is worth solving
2. ✅ Our solution is correct and complete
3. ✅ We follow project conventions
4. ✅ We don't duplicate or conflict with existing work
5. ✅ Tests prove correctness
6. ✅ Documentation explains the solution

---

## Branch 1: feature/docs-contributing-guide

### Problem Statement (Issue #718)

**Requested by**: @purva-thakre  
**Issue**: Contributors don't know how to add documentation  

**Specific Requirements from Issue:**
- [ ] How to add a page in the user guide?
- [ ] How to add an example to the docs gallery?
- [ ] Must be added to `docs/contributor_guide.rst`
- [ ] Explain `.rst` format
- [ ] Explain `jupyter-sphinx` for executable code
- [ ] Explain `sphinxcontrib-bibtex` for references
- [ ] Note: Gallery notebooks must have outputs cleared

### Our Solution Analysis

**What we added:**
1. ✅ Section: "Contributing to Documentation"
2. ✅ Subsection: "How to add a page to the user guide"
3. ✅ Subsection: "How to add an example to the docs gallery"
4. ✅ Explains RST format with examples
5. ✅ Explains jupyter-sphinx usage
6. ✅ Explains sphinxcontrib-bibtex with examples
7. ✅ Emphasizes clearing notebook outputs
8. ✅ Includes best practices and common pitfalls

**Location**: Added to `docs/contributor_guide.rst` line 161-396 (237 new lines)

### Validation Checklist

#### 1. Does it solve the stated problem?
- [ ] Addresses "How to add a page in the user guide?"
- [ ] Addresses "How to add an example to the docs gallery?"
- [ ] Covers all points mentioned in issue description
- [ ] **Action**: Re-read issue #718 and map each requirement to our content

#### 2. Does it follow project conventions?
- [ ] Check existing RST structure in `docs/contributor_guide.rst`
- [ ] Match heading hierarchy (= for main, - for sub, ~ for subsub)
- [ ] Use same code-block style as existing docs
- [ ] Follow link format used elsewhere
- [ ] **Action**: Compare our style to lines 1-160 of contributor_guide.rst

#### 3. Does it duplicate existing content?
- [ ] Check if docs/README has similar content
- [ ] Check if any user guide pages explain this
- [ ] Search for "jupyter-sphinx" mentions elsewhere
- [ ] Search for "gallery" mentions in docs
- [ ] **Action**: `grep -r "jupyter-sphinx\|gallery\|footcite" docs/`

#### 4. Is it technically accurate?
- [ ] Test: Create a dummy user guide page following our instructions
- [ ] Test: Create a dummy gallery notebook following our instructions
- [ ] Verify: All paths mentioned are correct (`docs/user_guide/`, `docs/gallery/`)
- [ ] Verify: All commands work (`make html`, `jupyter nbconvert`)
- [ ] **Action**: Actually execute the workflow we documented

#### 5. Does it integrate well?
- [ ] Placement in file makes sense (after "Merge the PR" section)
- [ ] References to other sections are valid
- [ ] Links to external docs are current
- [ ] **Action**: Build docs and verify our section renders correctly

---

## Branch 2: feature/improve-error-messages

### Problem Analysis

**Related to**: Issue #262 (Exception refactoring)  
**Status**: @purva-thakre is working on exception TYPES  
**Our angle**: Improve error message CONTENT (complementary, not conflicting)

**Files Modified:**
1. `src/tqec/interop/pyzx/positioned.py` (6 error messages)
2. `src/tqec/interop/collada/read_write.py` (10 error messages)
3. `src/tqec/interop/pyzx/positioned_test.py` (5 test assertions)

### Validation Checklist

#### 1. Are we stepping on toes?
- [ ] Confirm @purva-thakre is working on exception TYPES, not messages
- [ ] Check if anyone else has opened error message PRs
- [ ] Verify our changes don't conflict with #262
- [ ] **Action**: Read all comments on #262 to ensure no overlap

#### 2. Do our improvements actually help?
- [ ] Each new message includes specific values
- [ ] Each new message suggests a fix
- [ ] Technical terms are explained
- [ ] File paths are included where relevant
- [ ] **Action**: Trigger each error intentionally and verify message quality

#### 3. Are tests correct?
- [ ] All 6 positioned_test.py tests pass
- [ ] Test regex patterns match new messages
- [ ] Tests still validate the BEHAVIOR (not just the message)
- [ ] **Action**: Run pytest with verbose output

#### 4. Code quality?
- [ ] Line length < 100 characters (ruff requirement)
- [ ] No unnecessary computation (manhattan_distance calculation is minimal)
- [ ] Messages are clear and concise
- [ ] **Action**: Run full pre-commit on all modified files

#### 5. Backward compatibility?
- [ ] Exception types unchanged (still TQECError)
- [ ] Exceptions raised at same locations
- [ ] Only message content changed
- [ ] **Action**: Verify no API changes with git diff

---

## Advanced Testing Plan

### Phase 1: Local Validation (Mac)

**1. Documentation Branch Testing**
```bash
# Test 1: Build docs completely
cd docs && time make clean && time make html

# Test 2: Verify our section appears
grep -A 10 "Contributing to Documentation" _build/html/contributor_guide.html

# Test 3: Follow our own instructions
# - Create dummy page in docs/user_guide/test_contribution.rst
# - Create dummy notebook in docs/gallery/test_notebook.ipynb
# - Build docs again
# - Verify both appear correctly

# Test 4: Check for broken links
# (if linkcheck exists)
make linkcheck
```

**2. Error Messages Branch Testing**
```bash
# Test 1: Run specific test suites
pytest src/tqec/interop/pyzx/positioned_test.py -v
pytest src/tqec/interop/collada/ -v

# Test 2: Trigger errors manually and verify messages
python -c "
from tqec.interop.pyzx.positioned import PositionedZX
from pyzx.graph.graph_s import GraphS
g = GraphS()
g.add_vertex(0)
try:
    PositionedZX(g, {})
except Exception as e:
    print('Error message:', str(e))
    # Verify message has details about mismatch
"

# Test 3: Run full test suite
pytest src/tqec/interop/ -v --tb=short

# Test 4: Check test coverage
pytest src/tqec/interop/ --cov=src/tqec/interop --cov-report=term-missing
```

**3. Integration Testing**
```bash
# Test 1: Verify no regressions
pytest  # Full test suite

# Test 2: Check type hints
mypy src/tqec/interop/pyzx/positioned.py
mypy src/tqec/interop/collada/read_write.py

# Test 3: Performance check (ensure error messages don't slow down)
python -m timeit -s "from tqec.interop.pyzx.positioned import PositionedZX" "PositionedZX.__init__"
```

### Phase 2: Threadripper Deep Testing

**When transferred to Threadripper:**

**1. Comprehensive Test Suite**
```bash
# Run full test suite with all combinations
pytest -v --tb=long --durations=10

# Run with different Python versions (if available)
pytest  # Python 3.10
pytest  # Python 3.11
pytest  # Python 3.12
```

**2. Stress Testing**
```bash
# Test docs build under load
for i in {1..10}; do
  (cd docs && make html) &
done
wait

# Test error message generation under load
# Create script that triggers various errors repeatedly
python stress_test_errors.py
```

**3. Fuzzing / Edge Case Testing**
```bash
# Test with unusual inputs
# - Very large lattices
# - Malformed DAE files
# - Corrupt JSON files
# - Edge cases for coordinates
```

**4. Memory Profiling**
```bash
# Ensure error messages don't leak memory
python -m memory_profiler test_error_messages.py
```

---

## Project Alignment Checklist

### Understanding TQEC's Mission

**From architecture docs and code:**
- TQEC = Topological Quantum Error Correction design automation
- Goal: Make QEC circuit design accessible
- Focus: Surface codes, lattice surgery, ZX calculus
- Integration: PyZX, Qiskit, Qrisp, Stim

### Do our contributions align?

#### Docs Guide (Branch 1)
- ✅ Makes contributing easier = more community growth
- ✅ Helps integrate new frameworks (Qiskit, Qrisp examples)
- ✅ Lowers barrier to entry for contributors
- ✅ Aligns with democratization goal

#### Error Messages (Branch 2)
- ✅ Makes debugging PyZX integration easier
- ✅ Helps users understand COLLADA import issues
- ✅ Reduces maintainer support burden
- ✅ Makes topologiq integration more accessible

**Verdict**: Both contributions directly support TQEC's mission ✅

---

## Code Review Standards

### What TQEC Expects (based on merged PRs)

**From analyzing successful PRs:**
1. **Comprehensive tests** - Your PR #726 had 17 tests ✅
2. **Clear documentation** - PR descriptions are detailed ✅
3. **Pre-commit compliance** - All hooks must pass ✅
4. **No regressions** - Full test suite must pass ✅
5. **Type hints** - Use proper typing throughout ✅

### Applying to Our Branches

**Branch 1 (Docs):**
- Tests: N/A (documentation)
- Documentation: Self-documenting (it IS documentation)
- Pre-commit: Must verify RST syntax
- Regressions: Docs must build successfully
- Type hints: N/A

**Branch 2 (Errors):**
- Tests: 6 existing tests updated ✅
- Documentation: ERROR_MESSAGE_IMPROVEMENTS.md created ✅
- Pre-commit: All hooks passing ✅
- Regressions: positioned_test.py passes ✅
- Type hints: Existing hints maintained ✅

---

## Defensive Arguments

### If Challenged: "Why should we merge this?"

**For Docs Guide (Branch 1):**

**Challenge**: "This is too basic / obvious"
**Response**: 
- Issue #718 was opened by a maintainer (@purva-thakre)
- It's labeled "good first issue" - meant to be accessible
- Current contributor_guide.rst has NO docs info
- Qiskit/Qrisp integration (PR #720) needs clear docs contribution path
- Evidence: We followed EXACT requirements from issue description

**Challenge**: "This might be outdated soon"
**Response**:
- Documented current toolchain (Sphinx, jupyter-sphinx, sphinxcontrib-bibtex)
- These are in pyproject.toml dependencies
- Included warnings about execution time
- Easy to update if tools change

**For Error Messages (Branch 2):**

**Challenge**: "This conflicts with exception refactoring #262"
**Response**:
- #262 is about exception TYPES (InvalidCodeException, FormatException, etc.)
- We improved message CONTENT, not structure
- Our changes are complementary - better messages help any exception type
- Created ERROR_MESSAGE_IMPROVEMENTS.md explaining strategy
- When #262 merges, our improved messages map cleanly to new types

**Challenge**: "Error messages make files longer"
**Response**:
- Improved messages reduce support burden
- Users debug themselves instead of opening issues
- Each message includes actionable fix suggestion
- Evidence: Your PR #726 merged with "outstanding" feedback - same style

**Challenge**: "Tests are too fragile (regex patterns)"
**Response**:
- Tests validate error CONDITIONS, not just messages
- Regex patterns are flexible (`.*` matches variations)
- Alternative would be no message validation at all
- Easy to update if messages change

---

## Final Checklist Before PR

**For EACH branch:**

- [ ] All tests pass locally
- [ ] All pre-commit hooks pass
- [ ] Documentation builds successfully (if applicable)
- [ ] No regressions in full test suite
- [ ] Changes align with stated issue requirements
- [ ] No conflicts with other active work
- [ ] Commit messages are clear
- [ ] Code follows project style
- [ ] Ready to defend every decision

**Additional:**
- [ ] Branch is rebased on upstream/main
- [ ] Git identity is correct (SMC17, Northwestern email)
- [ ] PR description is written (clear, detailed)
- [ ] Screenshots/examples ready (if applicable)

---

## Testing Commands Reference

```bash
# Switch branches
git checkout feature/docs-contributing-guide
git checkout feature/improve-error-messages

# Run tests
pytest src/tqec/interop/pyzx/positioned_test.py -v
pytest src/tqec/interop/collada/ -v
pytest  # Full suite

# Pre-commit
pre-commit run --all-files
pre-commit run --files src/tqec/interop/pyzx/positioned.py

# Docs
cd docs && make html
cd docs && make clean && make html

# Type checking
mypy src/tqec/interop/

# Coverage
pytest --cov=src/tqec/interop --cov-report=html

# Code style
ruff check src/
ruff format src/ --check
```

---

## Next Steps

### Before Threadripper Transfer

1. [ ] Complete all Phase 1 local testing
2. [ ] Document any issues found
3. [ ] Fix any issues found
4. [ ] Re-run all tests
5. [ ] Commit fixes with clear messages
6. [ ] Create comprehensive test script for Threadripper

### On Threadripper

1. [ ] Run Phase 2 comprehensive testing
2. [ ] Stress test with parallel execution
3. [ ] Profile memory and performance
4. [ ] Test edge cases exhaustively
5. [ ] Document all findings

### Before Opening PRs

1. [ ] Review all testing results
2. [ ] Ensure 100% confidence in changes
3. [ ] Write detailed PR descriptions
4. [ ] Prepare to defend every decision
5. [ ] Be ready for quick iteration on feedback

---

**Philosophy**: We don't submit PRs to "try things out". We submit PRs because we've proven they're correct.

