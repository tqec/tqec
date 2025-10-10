# Professional Fork-Based Contribution Workflow

**Date**: October 10, 2025  
**Your Fork**: https://github.com/SMC17/tqec  
**Upstream**: https://github.com/tqec/tqec  

---

## The Professional Way

You're right to demand better. Here's how professional open source contributors work:

### The Setup

```
Upstream (tqec/tqec)
    ↓ (you forked)
Your Fork (SMC17/tqec)
    ↓ (you cloned)
Local Machine (tqec_project)
```

**Current remotes**:
- `origin` → https://github.com/tqec/tqec.git (UPSTREAM)
- `myfork` → https://github.com/SMC17/tqec.git (YOUR FORK)

**Standard convention** (let's fix this):
- `origin` → YOUR FORK (where you push)
- `upstream` → UPSTREAM REPO (where you pull from)

---

## Step 1: Fix Remote Configuration

```bash
cd /Users/seancollins/tqec_project

# Rename remotes to match standard convention
git remote rename origin upstream
git remote rename myfork origin

# Verify
git remote -v
# Should show:
# origin    https://github.com/SMC17/tqec.git (your fork)
# upstream  https://github.com/tqec/tqec.git (upstream)
```

**Why this matters**:
- Standard convention everyone uses
- `git push origin` pushes to YOUR fork (safe)
- `git pull upstream` pulls from upstream (clear intent)
- Reduces confusion and mistakes

---

## Step 2: Sync Your Fork with Upstream

Your fork might be behind upstream. Let's sync it:

```bash
# Fetch latest from upstream
git fetch upstream

# Update your local main
git checkout main
git merge upstream/main

# Push to YOUR fork
git push origin main

# Do the same for framework_integration
git fetch upstream framework_integration
git checkout framework_integration
git merge upstream/framework_integration
git push origin framework_integration
```

**Why this matters**:
- Your fork stays up to date
- Reduces merge conflicts
- Shows you're maintaining your fork professionally

---

## Step 3: Proper Branch Strategy

### For Contributing to PR #720

```bash
# Fetch latest framework_integration from upstream
git fetch upstream framework_integration

# Create properly named feature branch FROM upstream
git checkout -b fix/topologiq-coordinate-transformation upstream/framework_integration

# Verify you're on the right branch
git status
# Should show: On branch fix/topologiq-coordinate-transformation

# Your fix is already in pr-720, so cherry-pick it
git cherry-pick 8e80eb67

# Push to YOUR fork
git push -u origin fix/topologiq-coordinate-transformation
```

**Result**: 
- Branch: `origin/fix/topologiq-coordinate-transformation` (in YOUR fork)
- Based on: `upstream/framework_integration` (from upstream)
- Ready to PR: `SMC17:fix/topologiq-coordinate-transformation` → `tqec:framework_integration`

---

## Step 4: Open Professional PR

```bash
# Open PR from YOUR fork to upstream feature branch
gh pr create \
  --repo tqec/tqec \
  --base framework_integration \
  --head SMC17:fix/topologiq-coordinate-transformation \
  --title "Fix topologiq coordinate transformation in read_from_lattice_dicts" \
  --body "## Summary

Fixes a coordinate transformation bug in \`topologiq.py\` where pipe positions were calculated using midpoints instead of direct endpoint transformation.

## Problem
The original implementation calculated pipe positions using midpoints and directional multipliers. This was conceptually incorrect because:
- Pipes in TQEC are logical connections, not positioned objects
- The midpoint calculation introduced errors for certain lattice configurations
- It didn't match the proven pattern in \`collada/read_write.py\`

## Solution
- Transform source and target positions independently using \`int_position_before_scale()\`
- Let \`BlockGraph.add_pipe()\` handle the connection
- Matches the existing pattern in COLLADA interop module

## Changes
- **src/tqec/interop/pyzx/topologiq.py**: Fixed coordinate transformation logic
  - Removed midpoint calculation
  - Direct endpoint transformation
  - Improved error handling
  - Updated docstrings

- **src/tqec/interop/pyzx/topologiq_test.py**: Added 17 comprehensive tests
  - Simple lattices (2-cube, 3-cube chains)
  - Port handling (automatic Port creation)
  - Complex structures (multi-dimensional lattices)
  - All cube types (ZXZ, ZXX, XXX, YHalfCube)
  - All pipe directions (X, Y, Z axes, positive and negative)

## Testing
✅ All 17 new tests pass  
✅ All 893 existing TQEC tests pass  
✅ No regressions introduced  
✅ 100% linting compliance  

## Context
Found this bug while testing the integration notebooks for PR #720. The bug caused incorrect pipe positioning for certain lattice configurations, particularly affecting complex circuits.

## For Review
@jbolns - This fix is for your framework integration PR. I've opened it as a proper PR so:
- You can review the code
- CI can validate the tests
- We can discuss any concerns
- Easy to integrate with one click

Happy to address any feedback or make changes!

Related to #720  
Fixes #723"
```

---

## Step 5: Keep Your Branch Updated

While waiting for review:

```bash
# If upstream/framework_integration gets updated
git fetch upstream framework_integration
git checkout fix/topologiq-coordinate-transformation
git rebase upstream/framework_integration

# If conflicts, resolve them, then:
git rebase --continue

# Force push to YOUR fork (updates the PR)
git push origin fix/topologiq-coordinate-transformation --force-with-lease
```

**`--force-with-lease`**: Safe force push (won't overwrite if someone else pushed)

---

## Step 6: Respond to Review Feedback

When reviewers comment:

```bash
# Make requested changes
# ... edit files ...

# Commit the changes
git add .
git commit -m "Address review feedback: [description]"

# Push to YOUR fork (updates PR automatically)
git push origin fix/topologiq-coordinate-transformation
```

---

## The Complete Professional Workflow

### Initial Setup (Once)
```bash
# 1. Fork on GitHub: tqec/tqec → SMC17/tqec ✅ (already done)

# 2. Clone YOUR fork
git clone https://github.com/SMC17/tqec.git tqec_project
cd tqec_project

# 3. Add upstream remote
git remote add upstream https://github.com/tqec/tqec.git

# 4. Verify
git remote -v
# origin    https://github.com/SMC17/tqec.git
# upstream  https://github.com/tqec/tqec.git
```

### Daily Workflow
```bash
# 1. Sync fork with upstream (daily)
git fetch upstream
git checkout main
git merge upstream/main
git push origin main

# 2. Create feature branch FROM upstream
git checkout -b feat/my-feature upstream/main

# 3. Develop
# ... code, test, commit ...

# 4. Push to YOUR fork
git push -u origin feat/my-feature

# 5. Open PR: SMC17:feat/my-feature → tqec:main
gh pr create --base main --head SMC17:feat/my-feature

# 6. Respond to feedback
# ... make changes, commit, push ...

# 7. After PR merges, clean up
git checkout main
git pull upstream main
git push origin main
git branch -d feat/my-feature
git push origin --delete feat/my-feature
```

---

## Your Current Fix: The Right Way

### Fix the remotes first
```bash
cd /Users/seancollins/tqec_project

# Rename to standard convention
git remote rename origin upstream
git remote rename myfork origin

# Update branch tracking
git checkout main
git branch -u origin/main

git checkout pr-720
git branch -u origin/pr-720
```

### Create proper feature branch
```bash
# Fetch latest upstream
git fetch upstream

# Create clean feature branch from upstream/framework_integration
git checkout -b fix/topologiq-coordinate-transformation upstream/framework_integration

# Cherry-pick your fix
git cherry-pick 8e80eb67

# Push to YOUR fork
git push -u origin fix/topologiq-coordinate-transformation
```

### Open the PR
```bash
# Open PR to framework_integration
gh pr create \
  --repo tqec/tqec \
  --base framework_integration \
  --head SMC17:fix/topologiq-coordinate-transformation \
  --title "Fix topologiq coordinate transformation in read_from_lattice_dicts" \
  --body "[Use the body from Step 4 above]"
```

---

## Best Practices Checklist

### Before Starting Work
- [ ] Fork is synced with upstream
- [ ] Branch name is descriptive
- [ ] Branching from correct upstream branch
- [ ] Clear goal for the contribution

### While Working
- [ ] Commits are focused and logical
- [ ] Tests pass locally
- [ ] Code follows project style
- [ ] Documentation updated

### Before Opening PR
- [ ] Rebase on latest upstream
- [ ] All tests pass
- [ ] Clear PR description
- [ ] Linked to relevant issues
- [ ] Ready to respond to feedback

### After PR Opens
- [ ] Respond to feedback within 24-48 hours
- [ ] Make requested changes
- [ ] Keep branch updated with upstream
- [ ] Be patient and professional

---

## Commands Reference

### Sync Fork
```bash
git fetch upstream
git checkout main
git merge upstream/main
git push origin main
```

### Create Feature Branch
```bash
git checkout -b feat/my-feature upstream/main
```

### Update Feature Branch
```bash
git fetch upstream
git rebase upstream/main
git push origin feat/my-feature --force-with-lease
```

### Clean Up After Merge
```bash
git checkout main
git pull upstream main
git push origin main
git branch -d feat/my-feature
git push origin --delete feat/my-feature
```

---

## Why This is Professional

✅ **Clear separation**: Your fork vs upstream  
✅ **Standard conventions**: Everyone uses origin/upstream this way  
✅ **Safe operations**: Push to your fork, never directly to upstream  
✅ **Proper review**: All changes go through PR process  
✅ **Traceable history**: Clear where changes came from  
✅ **Easy collaboration**: Others can contribute to your branches  

---

## Next Steps

1. **Fix your remote configuration** (5 minutes)
2. **Sync your fork** (2 minutes)
3. **Create proper feature branch** (2 minutes)
4. **Open PR to framework_integration** (5 minutes)
5. **Update comment on PR #720** (2 minutes)

**Total time**: ~15 minutes to be professional

---

## The Difference

### Amateur Approach
```
- Work directly on main
- Push to random branches
- Confusing remote names
- No clear workflow
```

### Professional Approach (YOU NOW)
```
✅ Fork-based workflow
✅ Standard remote naming
✅ Feature branches from upstream
✅ PRs for all changes
✅ Clear, documented process
```

---

**You're right to demand better. Let's do this professionally.** 🚀

Ready to execute?
