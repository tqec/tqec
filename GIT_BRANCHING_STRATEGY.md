# TQEC Git Branching Strategy & Contribution Best Practices

**Author**: Sean Collins  
**Date**: October 10, 2025  
**Purpose**: Learn from mistakes and document proper contribution workflow

---

## What Went Wrong: The PR #725 Mistake

### The Problem
I opened **PR #725** trying to merge my fix directly to `main`, but:
- PR #720 is still open (merging `framework_integration` → `main`)
- My fix was built ON TOP of `framework_integration` branch
- PR #725 tried to merge: `framework_integration` + all its changes + my fix → `main`
- This created a massive merge with 24 commits from PR #720 that I didn't write
- **Result**: Cluttered, confusing PR that was correctly closed

### What I Should Have Done
1. ✅ Branch from `framework_integration` (I did this correctly)
2. ✅ Make my fix (I did this correctly)
3. ✅ Comment on PR #720 offering the fix (I did this correctly)
4. ❌ **DO NOT** open a separate PR to `main`

### The Correct Approach
When fixing something in an **open PR that hasn't merged yet**:
- Comment on that PR with your commit
- Offer to let them cherry-pick it
- Let THEM decide how to integrate it
- **Do NOT** open your own PR

---

## TQEC Repository Structure

### Main Branches

```
main (protected)
├── Development happens in feature branches
└── PRs merge here after review

feature branches (e.g., framework_integration, feat/blocks, fix/detector_coordinates)
├── Long-lived branches for major features
├── Multiple contributors may work on same feature branch
└── Eventually merge to main via PR
```

### Current Active Branches (as of Oct 2025)

```bash
$ git branch -r | grep origin

origin/main                           # Protected, stable
origin/framework_integration          # PR #720 (jbolns)
origin/feat/blocks                    # Block system refactoring
origin/feat/change-plaquette-invariant
origin/feat/fixed-bulk-logical-hadamard
origin/feat/greedy_bfs_block_synthesis
origin/feat/lassynth
origin/feat/rpng_template_everywhere
origin/feat/spatial_junctions
origin/feat/spatial_junctions_and_hadamard
origin/feat/y-basis-block
origin/feat/y-basis-init-meas
origin/fix/detector_coordinates
origin/steane-code-demo
# ... and more
```

**Key Insight**: Many feature branches exist simultaneously. Contributors work on different features in parallel.

---

## Contribution Scenarios & Correct Strategies

### Scenario 1: Fixing a Bug in Main

**Goal**: Fix a bug in the current stable `main` branch

**Strategy**:
```bash
# 1. Fetch latest main
git fetch origin main
git checkout -b fix/my-bugfix origin/main

# 2. Make your fix
# ... edit files ...
git add .
git commit -m "Fix: description of bug fix"

# 3. Push to your fork
git push -u myfork fix/my-bugfix

# 4. Open PR: your-fork:fix/my-bugfix → tqec:main
gh pr create --base main --head SMC17:fix/my-bugfix
```

**✅ Correct because**: You're fixing something in `main`, so you branch from `main` and PR back to `main`.

---

### Scenario 2: Contributing to an Open PR

**Goal**: Fix something in an open PR (like I did with PR #720)

**Strategy**:
```bash
# 1. Fetch the PR's branch
git fetch origin framework_integration
git checkout -b fix/topologiq-coords origin/framework_integration

# 2. Make your fix
# ... edit files ...
git add .
git commit -m "Fix topologiq coordinate transformation"

# 3. Push to your fork
git push -u myfork fix/topologiq-coords

# 4. Comment on the PR (don't open new PR!)
# Post comment with commit link and cherry-pick instructions
```

**Comment template**:
```markdown
@author - Found and fixed [issue] while testing.

Commit: https://github.com/YOUR_USERNAME/tqec/commit/COMMIT_HASH

To include in this PR:
git remote add your_username https://github.com/YOUR_USERNAME/tqec.git
git fetch your_username
git cherry-pick COMMIT_HASH

Or I can open a separate PR if you prefer.
```

**✅ Correct because**: 
- You're fixing something in THEIR branch
- Let them decide how to integrate
- Avoids duplicate PRs
- Keeps history clean

---

### Scenario 3: New Feature (Independent)

**Goal**: Add a completely new feature

**Strategy**:
```bash
# 1. Fetch latest main
git fetch origin main
git checkout -b feat/my-awesome-feature origin/main

# 2. Develop feature
# ... implement feature ...
git add .
git commit -m "feat: Add awesome new feature"

# 3. Push and open PR
git push -u myfork feat/my-awesome-feature
gh pr create --base main --head SMC17:feat/my-awesome-feature
```

**✅ Correct because**: Independent feature branches from `main` and PR back to `main`.

---

### Scenario 4: Building on an Unmerged Feature

**Goal**: Add something that DEPENDS on an open PR

**Strategy**:
```bash
# 1. Branch from the feature branch
git fetch origin feature-branch-name
git checkout -b feat/my-addition origin/feature-branch-name

# 2. Make your additions
# ... develop ...
git add .
git commit -m "feat: Add functionality on top of feature X"

# 3. Push to your fork
git push -u myfork feat/my-addition

# 4. Open PR: your-fork:feat/my-addition → tqec:feature-branch-name
# NOTE: Base is the feature branch, NOT main!
gh pr create --base feature-branch-name --head SMC17:feat/my-addition
```

**✅ Correct because**: Your work depends on unmerged code, so you branch from and PR to that feature branch.

**Important**: Once the feature branch merges to `main`, you may need to rebase your PR onto `main`.

---

## What I Did & What I Should Have Done

### What Actually Happened

```
origin/main
    ↓
origin/framework_integration (PR #720 - jbolns)
    ↓
myfork/pr-720 (my fix)
    ↓
❌ PR #725: myfork/pr-720 → origin/main
   (WRONG: Tried to merge framework_integration + my fix to main)
```

### What I Should Have Done

```
origin/main
    ↓
origin/framework_integration (PR #720 - jbolns)
    ↓
myfork/pr-720 (my fix)
    ↓
✅ Comment on PR #720: "Here's my fix, cherry-pick if you want"
✅ Let jbolns integrate it into PR #720
✅ PR #720 merges to main (with my fix included)
```

---

## Understanding Cherry-Pick

**What is cherry-pick?**
A way to apply a single commit from one branch to another without merging the entire branch.

**Example**:
```bash
# jbolns wants to include my fix in his PR #720 branch

# 1. He adds my fork as a remote
git remote add smc17 https://github.com/SMC17/tqec.git
git fetch smc17

# 2. He cherry-picks just my commit
git cherry-pick 8e80eb67

# 3. My fix is now in his branch
# 4. When PR #720 merges, my fix goes to main
```

**Why this is better than a separate PR**:
- Keeps history clean
- No duplicate code
- Credits both contributors
- Avoids merge conflicts

---

## TQEC's Current PR Workflow (Observed)

### Draft PRs
Many PRs start as drafts:
- `Draft` label indicates work in progress
- Allows early feedback
- Can be updated multiple times before final review
- Example: PR #720 is a draft

### Review Process
1. Author opens PR (often as draft)
2. Reviewers comment on specific lines
3. Author addresses feedback with new commits
4. Multiple review cycles common
5. Once approved, PR merges to `main`

### Multiple Reviewers
- PRs often have 3-5 reviewers
- Each with different expertise areas
- Consensus needed before merge

---

## Best Practices for TQEC Contributions

### 1. Always Branch from the Right Base

**Ask yourself**: "Where do I want my changes to ultimately go?"

- Fixing `main`? → Branch from `main`
- Fixing a feature branch? → Branch from that feature branch
- Building on unmerged work? → Branch from that work

### 2. Keep Commits Focused

**Good commit**:
```
Fix topologiq coordinate transformation

- Replace midpoint calculation with direct endpoint transformation
- Add 17 comprehensive tests
- Update docstrings

Fixes #723
```

**Bad commit**:
```
Fix stuff and add tests and update docs and also some formatting
```

### 3. One Logical Change Per PR

**Good PR**: "Fix topologiq coordinate bug"
- 1 file changed (topologiq.py)
- 1 file changed (topologiq_test.py)
- Clear scope

**Bad PR**: "Fix topologiq, update docs, refactor BlockGraph, add new feature"
- Too many unrelated changes
- Hard to review
- Increases merge conflict risk

### 4. Communicate Early

**Before** spending days on a feature:
- Comment on related issues
- Ask if approach makes sense
- Get buy-in from maintainers

**Example**:
> "I'm thinking of fixing [X] by doing [Y]. Does this approach make sense before I invest time in implementation?"

### 5. Respect Draft PRs

If a PR is marked "Draft":
- It's not ready for merge
- Author is still working on it
- You can comment on it
- **But**: Don't try to merge your own version of their work

### 6. Use Descriptive Branch Names

**Good**:
- `fix/topologiq-coordinate-transformation`
- `feat/add-logging-to-interop`
- `docs/improve-integration-guide`

**Bad**:
- `my-branch`
- `fix1`
- `pr-720` (confusing - is it FOR PR #720 or IS it PR #720?)

### 7. Keep Your Fork Synced

```bash
# Regularly update your fork's main
git fetch origin main
git checkout main
git merge origin/main
git push myfork main
```

---

## Checking PR Dependencies

**Before opening a PR, check**:

```bash
# What branch am I on?
git branch

# What commits am I bringing in?
git log origin/main..HEAD --oneline

# Does this show ONLY my commits?
# Or does it show dozens of commits from someone else's feature branch?
```

**If you see other people's commits**: You're branching from the wrong base!

---

## Fixing My Current Situation

### Current State
```bash
$ git branch -vv
  framework_integration        52427404 [origin/framework_integration]
  main                         064cd70f [origin/main]
  pr-720                       8e80eb67 [myfork/pr-720]
* pr-720-framework-integration 2069475e
```

### What to Do

1. **✅ pr-720 branch is correct**
   - Branched from `origin/framework_integration`
   - Has my fix
   - Pushed to `myfork/pr-720`
   - Used in comment on PR #720

2. **🗑️ pr-720-framework-integration is a duplicate**
   - Not needed
   - Can be deleted

3. **✅ PR #725 is closed**
   - Good, it was wrong
   - No cleanup needed

### Cleanup

```bash
# Delete the duplicate local branch
git checkout main
git branch -D pr-720-framework-integration

# Keep pr-720 for reference
# (It's the one jbolns might cherry-pick from)
```

---

## Going Forward: Contribution Checklist

Before opening a PR, ask:

- [ ] Does an open PR already exist for this area?
- [ ] If yes, should I contribute TO that PR instead of opening my own?
- [ ] Am I branching from the correct base?
- [ ] Does `git log origin/main..HEAD` show ONLY my commits?
- [ ] Is my PR focused on one logical change?
- [ ] Have I tested my changes?
- [ ] Have I updated documentation?
- [ ] Is my commit message clear and descriptive?

---

## Resources

### TQEC Contributing Guide
- Read: `CONTRIBUTING.md` in the repo (if it exists)
- Check: `docs/` for contribution guidelines
- Ask: In issues or discussions if unsure

### Git Resources
- [Git branching model](https://nvie.com/posts/a-successful-git-branching-model/)
- [GitHub flow](https://guides.github.com/introduction/flow/)
- [Conventional commits](https://www.conventionalcommits.org/)

---

## Summary

### ✅ What I Did Right
1. Branched from `framework_integration` (the PR branch)
2. Made a focused, tested fix
3. Commented on PR #720 with cherry-pick instructions
4. Closed PR #725 when I realized the mistake

### ❌ What I Did Wrong
1. Opened PR #725 trying to merge to `main`
2. Didn't check that PR #720 was still open
3. Created branch name `pr-720` (confusing)
4. Created duplicate branch `pr-720-framework-integration`

### 🎓 Lessons Learned
1. **Always check if there's an open PR** in the area you're working
2. **Branch from the right base** - where you want changes to go
3. **Comment on existing PRs** instead of opening duplicate PRs
4. **Cherry-pick is your friend** for contributing to open PRs
5. **Check `git log`** before opening PR to see what commits you're including

---

## Next Time

When I want to fix something in TQEC:

1. **Check existing PRs**: `gh pr list --search "topologiq"`
2. **If open PR exists**: Comment with fix, don't open new PR
3. **If no PR exists**: Branch from `main`, open PR to `main`
4. **Before pushing**: Check `git log origin/main..HEAD`
5. **Ask if unsure**: Better to ask than mess up the history

---

**Status**: Understood the mistake, documented the correct approach, ready to contribute properly going forward.
