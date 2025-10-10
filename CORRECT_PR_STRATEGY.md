# The CORRECT Strategy: Opening PRs to Feature Branches

**Date**: October 10, 2025  
**Realization**: Cherry-picking is passive. Opening PRs is professional.

---

## What We Realized

### Cherry-Pick Approach (What I Initially Suggested)
```
You: "Here's my fix, cherry-pick it if you want"
Them: *manually integrates*
Result: No review, no CI, no discussion
```

**Problem**: This puts the burden on THEM and bypasses proper review.

### PR to Feature Branch Approach (BETTER)
```
You: Opens PR to their feature branch
Them: Reviews like any other PR
CI: Runs tests automatically
Result: Proper review, discussion, and integration
```

**Why Better**:
- ✅ Gets proper code review
- ✅ CI/CD runs automatically
- ✅ Discussion happens in PR
- ✅ You respond to feedback
- ✅ More professional and collaborative

---

## The Correct Workflow

### Step 1: Verify You Have Something Worth Contributing

**Before doing anything, ask yourself**:
- Is this ACTUALLY a bug or improvement?
- Does it significantly help their PR?
- Is it well-tested and documented?
- Am I ready to defend this change?

**Only proceed if the answer to all is YES.**

### Step 2: Check if Feature Branch Accepts PRs

```bash
# Check if branch is protected
gh api repos/tqec/tqec/branches/framework_integration --jq '.protected'

# If false: You can open PR
# If true: Comment with cherry-pick instructions instead
```

For `framework_integration`: **false** ✅ (You can open PR!)

### Step 3: Create Properly Named Branch

```bash
# From your current pr-720 branch, create a better-named one
git checkout pr-720
git checkout -b fix/topologiq-coords-for-pr720

# Or create fresh from framework_integration
git fetch origin framework_integration
git checkout -b fix/topologiq-coords-for-pr720 origin/framework_integration

# Cherry-pick your commit from pr-720
git cherry-pick 8e80eb67

# Push to your fork
git push -u myfork fix/topologiq-coords-for-pr720
```

### Step 4: Open PR to Feature Branch

```bash
# Open PR: your-fork:fix/... → tqec:framework_integration
gh pr create \
  --repo tqec/tqec \
  --base framework_integration \
  --head SMC17:fix/topologiq-coords-for-pr720 \
  --title "Fix topologiq coordinate transformation bug" \
  --body "$(cat <<'EOF'
## Summary
Fixes coordinate transformation bug in `topologiq.py` that was causing incorrect pipe positioning.

## Changes
- Replace midpoint calculation with direct endpoint transformation
- Add 17 comprehensive tests covering all scenarios
- Update docstrings and comments

## Context
This fix is intended for PR #720 (framework integration). Found this issue while testing the integration notebooks.

## Testing
- All 17 new tests pass
- All 893 existing tests pass
- No regressions

## For Review
@jbolns - This fixes the coordinate bug I mentioned. Happy to make any changes you'd like before merging into your PR.

Closes #723
EOF
)"
```

### Step 5: Comment on Original PR

After opening your PR, comment on PR #720:

```markdown
@jbolns - I've opened PR #XXX to fix the coordinate transformation bug in `topologiq.py`.

Instead of having you cherry-pick, I figured a proper PR would allow for:
- Code review
- CI testing  
- Discussion if needed

Feel free to review and merge when ready, or let me know if you'd prefer a different approach.
```

---

## Why This is Better

### For You
- ✅ Your fix gets reviewed (catch any issues)
- ✅ CI runs (verify tests work in their environment)
- ✅ You can respond to feedback
- ✅ Shows you're professional and collaborative
- ✅ GitHub properly tracks your contribution

### For Them (jbolns)
- ✅ Don't have to manually integrate
- ✅ Can review like any PR
- ✅ Can request changes
- ✅ CI validates automatically
- ✅ Just click "Merge" when satisfied

### For the Project
- ✅ Proper review process
- ✅ Discussion is documented
- ✅ Tests verified by CI
- ✅ Clear audit trail
- ✅ Best practices followed

---

## When to Use Each Approach

### Open PR to Feature Branch (PREFERRED)
**When:**
- Branch is not protected
- You have substantial changes
- Changes need review
- You want CI to validate
- You're willing to iterate

**Example**: Your topologiq fix (2 files, 17 tests, significant change)

### Comment with Cherry-Pick Instructions
**When:**
- Branch is protected (you can't PR to it)
- Change is trivial (typo, formatting)
- You're not sure if they want it
- Quick suggestion, not critical

**Example**: Fixing a typo in a comment

### Direct Commit to Their Branch (RARELY)
**When:**
- You have write access
- They explicitly asked you to commit directly
- Emergency fix needed
- You're a co-author on the PR

**Example**: Almost never for external contributors

---

## Your Current Situation

### What You've Already Done
1. ✅ Commented on PR #720 with commit hash
2. ✅ Offered cherry-pick instructions
3. ⏳ Waiting for response

### What You SHOULD Do Now

**Option A: Wait for Response (Conservative)**
- They see your comment
- They might cherry-pick it
- Or they might ask you to open a PR

**Option B: Open PR Now (Proactive - RECOMMENDED)**
- Don't wait for them to ask
- Open PR to `framework_integration`
- Comment on PR #720 linking to your PR
- Shows initiative and professionalism

**I recommend Option B** because:
1. Your fix is substantial (not trivial)
2. It needs proper review
3. You have 17 tests (CI should validate)
4. It's the professional approach
5. They can always close it if they don't want it

---

## Exact Commands to Run

### Create Proper Branch

```bash
# From your existing pr-720 branch
cd /Users/seancollins/tqec_project
git checkout pr-720

# Create better-named branch
git checkout -b fix/topologiq-coordinate-transformation

# Push to your fork
git push -u myfork fix/topologiq-coordinate-transformation
```

### Open PR

```bash
# Open PR to framework_integration
gh pr create \
  --repo tqec/tqec \
  --base framework_integration \
  --head SMC17:fix/topologiq-coordinate-transformation \
  --title "Fix topologiq coordinate transformation in read_from_lattice_dicts" \
  --body "## Summary

Fixes a coordinate transformation bug in \`topologiq.py\` where pipe positions were calculated using midpoints instead of direct endpoint transformation.

## Problem
The original implementation attempted to:
1. Calculate midpoints between source and target nodes
2. Apply directional multipliers
3. Shift from the midpoint

This approach was conceptually incorrect because pipes in TQEC don't have positions—they're logical connections between cubes.

## Solution
- Transform source and target positions independently using \`int_position_before_scale()\`
- Let BlockGraph handle the connection
- Matches the pattern used in \`collada/read_write.py\`

## Changes
- \`src/tqec/interop/pyzx/topologiq.py\`: Fixed coordinate transformation logic
- \`src/tqec/interop/pyzx/topologiq_test.py\`: Added 17 comprehensive tests

## Testing
- ✅ All 17 new tests pass
- ✅ All 893 existing TQEC tests pass
- ✅ Tests cover: simple lattices, ports, complex structures, all cube types, all pipe directions

## Context
Found this while testing the integration notebooks for PR #720. The bug caused incorrect pipe positioning for certain lattice configurations.

## Review Request
@jbolns - This fix is intended for your framework integration PR. I've opened it as a proper PR so you can review and tests can run in CI. Happy to make any changes you'd like!

Fixes #723"
```

### Update PR #720 Comment

Add this comment to PR #720:

```markdown
Update: I've opened PR #XXX with the fix as a proper PR rather than just offering a commit to cherry-pick.

This allows for:
- Proper code review
- CI validation
- Discussion if needed

Feel free to review and merge when ready. Happy to address any feedback!
```

---

## The Lesson

### Wrong Thinking
> "I'll just give them my commit and let them integrate it"

**Problem**: Puts burden on them, bypasses review

### Right Thinking  
> "I'll open a PR to their branch so they can properly review and integrate it"

**Better**: Professional, collaborative, follows best practices

---

## Summary

**What to do RIGHT NOW**:

1. Create properly named branch from your `pr-720`
2. Push to your fork
3. Open PR: `SMC17:fix/topologiq-coordinate-transformation` → `tqec:framework_integration`
4. Add comment to PR #720 linking to your new PR
5. Be ready to respond to review feedback

**This is the CORRECT professional approach** ✅

---

## Updated Checklist

Before contributing to an open PR:

- [ ] ✅ Is my fix substantial and well-tested?
- [ ] ✅ Is the feature branch protected? (framework_integration: NO)
- [ ] ✅ Have I created a descriptive branch name?
- [ ] ✅ Have I written a clear PR description?
- [ ] ✅ Have I linked to the original PR?
- [ ] ✅ Have I offered to respond to feedback?
- [ ] ✅ Am I ready to iterate if needed?

If all YES: **Open the PR!** 🚀
