// Tests for the actions/github-script steps of .github/workflows/pr-quality.yml. Each test reads a step's `env` and
// `script` from the workflow and runs the script with a mocked GitHub API. They need Node 18 or later and no packages:
//   node --test .github/scripts/pr-quality.test.js

const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const { test } = require("node:test");

const { parseList } = require("./first-comment-notice.js")._internal;

const PR_QUALITY = fs.readFileSync(path.join(__dirname, "..", "workflows", "pr-quality.yml"), "utf8");
const AsyncFunction = (async () => {}).constructor;

const indent = (line) => line.search(/\S/);

// Returns the lines of the step with this id. Steps start with "- " at the indent of the first step.
function stepLines(id) {
  const lines = PR_QUALITY.split("\n");
  const first = lines.findIndex((l) => /^\s*- /.test(l) && indent(l) > 0);
  const stepIndent = indent(lines[first]);
  const starts = lines.map((l, i) => (indent(l) === stepIndent && /^\s*- /.test(l) ? i : -1)).filter((i) => i >= 0);
  for (const [n, start] of starts.entries()) {
    const step = lines.slice(start, starts[n + 1] ?? lines.length);
    if (step.some((l) => l.trim() === `id: ${id}`)) return step;
  }
  throw new Error(`no step with id ${id} in pr-quality.yml`);
}

// Returns the more-indented lines under `key:` in a step.
function block(lines, key) {
  const start = lines.findIndex((l) => l.trim().startsWith(`${key}:`));
  if (start === -1) return [];
  const body = [];
  for (const line of lines.slice(start + 1)) {
    if (line.trim() && indent(line) <= indent(lines[start])) break;
    body.push(line);
  }
  return body;
}

// Reads a step's env: plain `KEY: value` entries and folded `KEY: >-` entries of one paragraph. Comment lines are
// skipped. Quoted values, trailing comments and other YAML forms are not handled; pr-quality.yml uses none of them.
function stepEnv(lines) {
  const env = {};
  const entries = block(lines, "env").filter((l) => l.trim() && !l.trim().startsWith("#"));
  const keyIndent = indent(entries[0]);
  for (const [i, line] of entries.entries()) {
    if (indent(line) !== keyIndent) continue;
    const [, key, value] = line.trim().match(/^(\w+):\s*(.*)$/);
    if (value !== ">-") {
      env[key] = value;
      continue;
    }
    const folded = [];
    for (const next of entries.slice(i + 1)) {
      if (indent(next) <= keyIndent) break;
      folded.push(next.trim());
    }
    env[key] = folded.join(" ");
  }
  return env;
}

function stepScript(lines) {
  const body = block(lines, "script");
  const scriptIndent = indent(body.find((l) => l.trim()));
  return body.map((l) => l.slice(scriptIndent)).join("\n");
}

// A GitHub API mock. `options` overrides the data each endpoint returns; an endpoint given an Error throws it.
function mockGithub(options = {}) {
  const o = { profile: { user_view_type: "public" }, events: [], update: {}, comment: {}, ...options };
  const calls = [];
  const call = (name, value) => (params) => {
    calls.push({ name, params });
    if (value instanceof Error) return Promise.reject(value);
    return Promise.resolve({ data: value });
  };
  return {
    calls,
    called: (name) => calls.filter((c) => c.name === name),
    paginate: async (fn, params) => (await fn(params)).data,
    rest: {
      users: { getByUsername: call("getByUsername", o.profile) },
      issues: {
        listEvents: call("listEvents", o.events),
        createComment: call("createComment", o.comment),
        addLabels: call("addLabels", {}),
      },
      pulls: { update: call("update", o.update) },
    },
  };
}

function context({ action = "opened", login = "ada", association = "NONE", labels = [], state = "open", sender }) {
  return {
    repo: { owner: "tqec", repo: "tqec" },
    issue: { number: 5 },
    payload: {
      action,
      sender: { login: sender ?? login },
      pull_request: {
        number: 5,
        state,
        user: { login },
        author_association: association,
        labels: labels.map((name) => ({ name })),
      },
    },
  };
}

// Runs the script of the step with this id. Returns the outputs it set and the log.
async function runStep(id, github, ctx) {
  const lines = stepLines(id);
  const outputs = {};
  const log = { info: [], warning: [] };
  const core = {
    setOutput: (k, v) => (outputs[k] = v),
    info: (m) => log.info.push(m),
    warning: (m) => log.warning.push(m),
  };
  const run = new AsyncFunction("github", "context", "core", "process", stepScript(lines));
  await run(github, ctx, core, { env: stepEnv(lines) });
  return { outputs, log };
}

test("the private-profile step closes a PR from a private profile", async () => {
  const github = mockGithub({ profile: { user_view_type: "private" } });
  const { outputs } = await runStep("private-profile", github, context({}));
  assert.equal(outputs.closed, "true");
  const [comment] = github.called("createComment");
  assert.equal(comment.params.issue_number, 5);
  assert.match(comment.params.body, /^Thank you for the PR! .*profile is private.* a maintainer will take a look\.$/);
  assert.deepEqual(github.called("update")[0].params, { owner: "tqec", repo: "tqec", pull_number: 5, state: "closed" });
});

test("a failed close leaves the PR to anti-slop, and a failed comment still counts as closed", async () => {
  const error = (message) => Object.assign(new Error(message), { status: 502 });
  const noClose = mockGithub({ profile: { user_view_type: "private" }, update: error("close failed") });
  const { outputs, log } = await runStep("private-profile", noClose, context({}));
  assert.equal(outputs.closed, undefined);
  assert.equal(noClose.called("createComment").length, 0);
  assert.match(log.warning.join("\n"), /close failed/);

  const noComment = mockGithub({ profile: { user_view_type: "private" }, comment: error("comment failed") });
  const { outputs: o, log: l } = await runStep("private-profile", noComment, context({}));
  assert.equal(o.closed, "true");
  assert.match(l.warning.join("\n"), /comment failed/);
});

test("the private-profile step runs after the override step and only without an override", () => {
  const ids = [...PR_QUALITY.matchAll(/^\s*id: (\S+)$/gm)].map((m) => m[1]);
  assert.deepEqual(ids, ["override", "private-profile"]);
  assert.ok(PR_QUALITY.indexOf("id: private-profile") < PR_QUALITY.indexOf("uses: peakoss/anti-slop@"));
  assert.ok(stepLines("private-profile").some((l) => l.trim() === "if: steps.override.outputs.exempt != 'true'"));
});

test("the private-profile step leaves public, unknown and unreadable profiles to anti-slop", async () => {
  for (const profile of [{ user_view_type: "public" }, {}, Object.assign(new Error("server error"), { status: 502 })]) {
    const github = mockGithub({ profile });
    const { outputs, log } = await runStep("private-profile", github, context({}));
    assert.equal(outputs.closed, undefined);
    assert.equal(github.called("createComment").length + github.called("update").length, 0);
    if (profile instanceof Error) assert.match(log.warning.join("\n"), /server error/);
  }
});

test("the private-profile step skips exempt authors, exempt PRs and closed PRs", async () => {
  for (const ctx of [
    context({ association: "COLLABORATOR" }),
    context({ association: "OWNER" }),
    context({ login: "Dependabot[bot]" }),
    context({ labels: ["exempt"] }),
    context({ action: "edited", state: "closed" }),
  ]) {
    const github = mockGithub({ profile: { user_view_type: "private" } });
    const { outputs } = await runStep("private-profile", github, ctx);
    assert.equal(outputs.closed, undefined);
    assert.equal(github.calls.length, 0);
  }
});

test("the private-profile step has the exemptions of anti-slop", () => {
  const env = stepEnv(stepLines("private-profile"));
  const lower = (list) => list.map((v) => v.toLowerCase()).sort();
  const split = (value) => value.split(",").map((v) => v.trim()).filter(Boolean);
  assert.deepEqual(
    lower(split(env.EXEMPT_USERS)),
    lower([...parseList(PR_QUALITY, "exempt-bots"), ...parseList(PR_QUALITY, "exempt-users")]),
  );
  assert.deepEqual(split(env.EXEMPT_ASSOCIATIONS), parseList(PR_QUALITY, "exempt-author-association"));
  for (const id of ["private-profile", "override"]) {
    assert.deepEqual([stepEnv(stepLines(id)).EXEMPT_LABEL], parseList(PR_QUALITY, "exempt-label"));
  }
  assert.deepEqual(parseList(PR_QUALITY, "exempt-pr-label"), []);
});

test("anti-slop does not run after the private-profile step closes the PR", () => {
  const antiSlop = PR_QUALITY.slice(PR_QUALITY.indexOf("uses: peakoss/anti-slop@"));
  assert.match(antiSlop.split("\n")[1], /^\s*if: .*steps\.private-profile\.outputs\.closed != 'true'/);
});

test("the override exempts a PR that an override user reopens after the checks closed it", async () => {
  const closed = [{ event: "closed", actor: { login: "github-actions[bot]" } }];
  const github = mockGithub({ events: closed });
  const { outputs } = await runStep("override", github, context({ action: "reopened", sender: "nelimee" }));
  assert.equal(outputs.exempt, "true");
  assert.deepEqual(github.called("addLabels")[0].params.labels, ["exempt"]);

  for (const [events, ctx] of [
    [closed, context({ action: "reopened", sender: "eve" })],
    [closed, context({ action: "reopened", sender: "nelimee", labels: ["Stale"] })],
    [[{ event: "closed", actor: { login: "ada" } }], context({ action: "reopened", sender: "nelimee" })],
  ]) {
    const other = mockGithub({ events });
    const { outputs: o } = await runStep("override", other, ctx);
    assert.equal(o.exempt, undefined);
    assert.equal(other.called("addLabels").length, 0);
  }
});
