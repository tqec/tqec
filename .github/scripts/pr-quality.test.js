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
// `pr` is the PR as pulls.get returns it now; by default it is the PR in the event payload.
function mockGithub(options = {}) {
  const o = { profile: { user_view_type: "public" }, events: [], update: {}, comment: {}, pr: null, ...options };
  const calls = [];
  const call = (name, value) => (params) => {
    calls.push({ name, params });
    if (value instanceof Error) return Promise.reject(value);
    return Promise.resolve({ data: value });
  };
  const github = {
    calls,
    called: (name) => calls.filter((c) => c.name === name),
    paginate: async (fn, params) => (await fn(params)).data,
    rest: {
      users: { getByUsername: call("getByUsername", o.profile) },
      issues: {
        listEvents: call("listEvents", o.events),
        createComment: call("createComment", o.comment),
        addLabels: call("addLabels", o.addLabels ?? {}),
      },
      pulls: {
        update: call("update", o.update),
        get: (params) => call("get", o.pr ?? github.payloadPr)(params),
      },
    },
  };
  return github;
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
  github.payloadPr = ctx.payload.pull_request;
  const run = new AsyncFunction("github", "context", "core", "process", stepScript(lines));
  await run(github, ctx, core, { env: stepEnv(lines) });
  return { outputs, log };
}

test("the private-profile step closes a PR from a private profile", async () => {
  const github = mockGithub({ profile: { user_view_type: "private" } });
  const { outputs } = await runStep("private-profile", github, context({}));
  assert.equal(outputs.skip, "true");
  const [comment] = github.called("createComment");
  assert.equal(comment.params.issue_number, 5);
  assert.match(comment.params.body, /^Thank you for the PR! .*profile is private.* a maintainer will take a look\.$/);
  assert.deepEqual(github.called("update")[0].params, { owner: "tqec", repo: "tqec", pull_number: 5, state: "closed" });
});

test("a failed close leaves the PR to anti-slop, and after a failed comment anti-slop is still skipped", async () => {
  const error = (message) => Object.assign(new Error(message), { status: 502 });
  const noClose = mockGithub({ profile: { user_view_type: "private" }, update: error("close failed") });
  const { outputs, log } = await runStep("private-profile", noClose, context({}));
  assert.equal(outputs.skip, undefined);
  assert.equal(noClose.called("createComment").length, 0);
  assert.match(log.warning.join("\n"), /close failed/);

  const noComment = mockGithub({ profile: { user_view_type: "private" }, comment: error("comment failed") });
  const { outputs: o, log: l } = await runStep("private-profile", noComment, context({}));
  assert.equal(o.skip, "true");
  assert.match(l.warning.join("\n"), /comment failed/);
});

test("the private-profile step runs after the override step and only without an override", () => {
  const ids = [...PR_QUALITY.matchAll(/^\s*id: (\S+)$/gm)].map((m) => m[1]);
  assert.deepEqual(ids, ["override", "private-profile"]);
  assert.ok(PR_QUALITY.indexOf("id: private-profile") < PR_QUALITY.indexOf("uses: peakoss/anti-slop@"));
  assert.ok(stepLines("private-profile").some((l) => l.trim() === "if: steps.override.outputs.skip != 'true'"));
  // The override step runs on every event, so a run for an earlier edit that runs after a reopen sees the reopen.
  assert.ok(!stepLines("override").some((l) => l.trim().startsWith("if:")));
});

test("runs for the same PR run one at a time", () => {
  const block = PR_QUALITY.slice(PR_QUALITY.indexOf("\nconcurrency:") + 1).split("\n").slice(0, 3);
  assert.deepEqual(block, [
    "concurrency:",
    "  group: pr-quality-${{ github.event.pull_request.number }}",
    "  cancel-in-progress: false",
  ]);
});

test("the private-profile step leaves public, unknown and unreadable profiles to anti-slop", async () => {
  for (const profile of [{ user_view_type: "public" }, {}, Object.assign(new Error("server error"), { status: 502 })]) {
    const github = mockGithub({ profile });
    const { outputs, log } = await runStep("private-profile", github, context({}));
    assert.equal(outputs.skip, undefined);
    assert.equal(github.called("createComment").length + github.called("update").length, 0);
    if (profile instanceof Error) assert.match(log.warning.join("\n"), /server error/);
  }
});

test("the private-profile step skips exempt authors, and skips anti-slop for exempt or closed PRs", async () => {
  for (const [ctx, skip] of [
    [context({ association: "COLLABORATOR" }), undefined],
    [context({ association: "OWNER" }), undefined],
    [context({ login: "Dependabot[bot]" }), undefined],
    [context({ labels: ["exempt"] }), "true"],
    [context({ action: "edited", state: "closed" }), "true"],
  ]) {
    const github = mockGithub({ profile: { user_view_type: "private" } });
    const { outputs } = await runStep("private-profile", github, ctx);
    assert.equal(outputs.skip, skip);
    assert.deepEqual(github.calls.map((c) => c.name), ["get"]);
  }
});

test("the private-profile step reads the PR as it is now, not the event's copy", async () => {
  // The event saw an open PR without the exempt label; since then it was closed, or reopened with the label.
  const queued = context({ action: "edited" });
  for (const pr of [
    { ...queued.payload.pull_request, state: "closed" },
    { ...queued.payload.pull_request, labels: [{ name: "exempt" }] },
  ]) {
    const github = mockGithub({ profile: { user_view_type: "private" }, pr });
    const { outputs } = await runStep("private-profile", github, queued);
    assert.equal(outputs.skip, "true");
    assert.equal(github.called("update").length + github.called("createComment").length, 0);
    assert.equal(github.called("get")[0].params.pull_number, 5);
  }
  // The event saw a closed or exempt PR; since then it was reopened, or the label was removed.
  const stale = [context({ action: "edited", state: "closed" }), context({ action: "edited", labels: ["exempt"] })];
  for (const ctx of stale) {
    const pr = { ...ctx.payload.pull_request, state: "open", labels: [] };
    const github = mockGithub({ profile: { user_view_type: "private" }, pr });
    const { outputs } = await runStep("private-profile", github, ctx);
    assert.equal(outputs.skip, "true");
    assert.equal(github.called("update").length, 1);
  }
  // A failed read fails the step, so anti-slop does not run on the event's copy either.
  const unread = mockGithub({ profile: { user_view_type: "private" }, pr: new Error("not found") });
  await assert.rejects(runStep("private-profile", unread, queued), /not found/);
  assert.equal(unread.called("update").length, 0);
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

test("anti-slop does not run when the private-profile step says to skip it", () => {
  const antiSlop = PR_QUALITY.slice(PR_QUALITY.indexOf("uses: peakoss/anti-slop@"));
  assert.match(antiSlop.split("\n")[1], /^\s*if: steps\.override\..*steps\.private-profile\.outputs\.skip != 'true'/);
});

const by = (event, login, label) => ({ event, actor: { login }, ...(label ? { label: { name: label } } : {}) });
const BOT = "github-actions[bot]";

test("the override exempts a PR that an override user reopens after the checks closed it", async () => {
  const reopen = [by("closed", BOT), by("reopened", "nelimee")];
  // The reopen run, and a run for an earlier edit that runs after the reopen.
  for (const ctx of [context({ action: "reopened", sender: "nelimee" }), context({ action: "edited" })]) {
    const github = mockGithub({ events: reopen });
    const { outputs } = await runStep("override", github, ctx);
    assert.equal(outputs.skip, "true");
    assert.deepEqual(github.called("addLabels")[0].params.labels, ["exempt"]);
    assert.equal(github.called("listEvents")[0].params.issue_number, 5);
  }
  // A later run finds the label that the reopen run added and does not add it again.
  const labelled = mockGithub({ events: [...reopen, by("labeled", BOT, "exempt")] });
  assert.equal((await runStep("override", labelled, context({ action: "edited" }))).outputs.skip, "true");
  assert.equal(labelled.called("addLabels").length, 0);
  for (const events of [
    // A stale label removed before the close does not make it a stale closure.
    [by("labeled", BOT, "Stale"), by("unlabeled", "ada", "Stale"), ...reopen],
    // An exempt label removed before the close does not turn this override off.
    [by("labeled", "nelimee", "exempt"), by("unlabeled", "nelimee", "exempt"), ...reopen],
    // Override users are matched without case.
    [by("closed", BOT), by("reopened", "KabirDubey")],
  ]) {
    const github = mockGithub({ events });
    assert.equal((await runStep("override", github, context({}))).outputs.skip, "true");
    assert.equal(github.called("addLabels").length, 1);
  }
  // The reopen run trusts its own event when the events do not list the reopen yet.
  const lagging = mockGithub({ events: [by("closed", BOT)] });
  const { outputs: o } = await runStep("override", lagging, context({ action: "reopened", sender: "nelimee" }));
  assert.equal(o.skip, "true");
  // A failed label still skips this run; the next run reads the reopen again.
  const noLabel = mockGithub({ events: reopen, addLabels: new Error("label failed") });
  const { outputs, log } = await runStep("override", noLabel, context({}));
  assert.equal(outputs.skip, "true");
  assert.match(log.warning.join("\n"), /label failed/);
});

test("the override does not exempt other closures, reopens or a removed label", async () => {
  for (const [events, ctx] of [
    [[], context({})],
    [[by("closed", BOT)], context({ action: "reopened", sender: "eve" })],
    [[by("closed", BOT), by("reopened", "eve")], context({})],
    [[by("closed", "ada"), by("reopened", "nelimee")], context({})],
    [[by("labeled", BOT, "Stale"), by("closed", BOT), by("reopened", "nelimee")], context({})],
    [[by("labeled", BOT, "Stale"), by("closed", BOT), by("unlabeled", "nelimee", "Stale"), by("reopened", "nelimee")],
      context({})],
    [[by("closed", BOT), by("reopened", "nelimee"), by("labeled", BOT, "exempt"), by("unlabeled", "nelimee", "exempt")],
      context({})],
  ]) {
    const github = mockGithub({ events });
    const { outputs } = await runStep("override", github, ctx);
    assert.equal(outputs.skip, undefined);
    assert.equal(github.called("addLabels").length, 0);
  }
  const unread = mockGithub({ events: new Error("events failed") });
  await assert.rejects(runStep("override", unread, context({})), /events failed/);
});

test("the override skips both checks while the PR is closed, so a reopen during the run is not undone", async () => {
  for (const [events, ctx] of [
    [[by("closed", BOT)], context({ action: "edited", sender: "nelimee" })],
    [[by("closed", BOT), by("reopened", "nelimee"), by("closed", BOT)], context({ action: "edited" })],
  ]) {
    const github = mockGithub({ events });
    const { outputs } = await runStep("override", github, ctx);
    assert.equal(outputs.skip, "true");
    assert.equal(github.called("addLabels").length, 0);
  }
});
