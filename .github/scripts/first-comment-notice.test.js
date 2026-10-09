// Tests for first-comment-notice.js with a mocked GitHub API. They need Node 18 or later and no packages:
//   node --test .github/scripts/first-comment-notice.test.js

const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const { test } = require("node:test");

const notice = require("./first-comment-notice.js");
const { ANTI_SLOP_VERSION, parseSettings, parseList, parseVersion, fillTemplate, findOtherClaims } = notice._internal;

const PR_QUALITY = fs.readFileSync(path.join(__dirname, "..", "workflows", "pr-quality.yml"), "utf8");
const DAY_MS = 24 * 60 * 60 * 1000;
const OLD = new Date(Date.now() - 1000 * DAY_MS).toISOString();

// A GitHub API mock. `options` overrides the data each endpoint returns; an endpoint given an Error throws it.
function mockGithub(options = {}) {
  const o = {
    role: "read",
    workflow: PR_QUALITY,
    profile: {
      created_at: OLD,
      user_view_type: "public",
      name: "Ada",
      bio: "physicist",
      followers: 1,
      following: 1,
      hireable: null,
    },
    repos: [],
    comments: { 1: [] },
    search: () => ({ total_count: 0, items: [] }),
    ...options,
  };
  const posted = [];
  const call = (value, params) => {
    const result = typeof value === "function" ? value(params) : value;
    if (result instanceof Error) return Promise.reject(result);
    return Promise.resolve({ data: result });
  };
  const github = {
    posted,
    paginate: async (fn, params) => (await fn(params)).data,
    rest: {
      repos: {
        getCollaboratorPermissionLevel: (p) => call({ role_name: o.role, permission: o.role }, p),
        getContent: (p) => call({ content: Buffer.from(o.workflow).toString("base64") }, p),
        listForUser: (p) => call(o.repos, p),
      },
      users: { getByUsername: (p) => call(o.profile, p) },
      search: { issuesAndPullRequests: (p) => call(o.search, p) },
      issues: {
        listComments: (p) => call(o.comments[p.issue_number] ?? [], p),
        createComment: async (p) => posted.push(p),
      },
    },
  };
  return github;
}

function mockCore() {
  const log = { info: [], warning: [] };
  return { log, info: (m) => log.info.push(m), warning: (m) => log.warning.push(m) };
}

function context({ login = "ada", type = "User", id = 100, association = "NONE", pullRequest = false } = {}) {
  return {
    repo: { owner: "tqec", repo: "tqec" },
    payload: {
      issue: { number: 1, ...(pullRequest ? { pull_request: {} } : {}) },
      comment: { id, user: login ? { login, type } : null, author_association: association },
    },
  };
}

async function run(github, ctx = context()) {
  const core = mockCore();
  const body = await notice({ github, context: ctx, core });
  return { body, core };
}

test("pr-quality.yml uses the anti-slop version that the script mirrors", () => {
  assert.equal(parseVersion(PR_QUALITY), ANTI_SLOP_VERSION);
});

test("settings are read bare, single-quoted and double-quoted, with defaults for missing keys", () => {
  const s = parseSettings(
    "  min-account-age: '45'\n  require-public-profile: \"false\"\n  max-failures: 3 # note\n" +
      "  detect-spam-usernames: false\n",
  );
  assert.equal(s.minAccountAge, 45);
  assert.equal(s.requirePublicProfile, false);
  assert.equal(s.maxFailures, 3);
  assert.equal(s.detectSpamUsernames, false);
  assert.equal(s.minGlobalMergeRatio, 30);
});

test("lists are read as blocks and as comma-separated strings", () => {
  const yaml = "  exempt-bots: |\n    a[bot]\n    b\n  exempt-users: 'x, y'\n  other: 1\n";
  assert.deepEqual(parseList(yaml, "exempt-bots"), ["a[bot]", "b"]);
  assert.deepEqual(parseList(yaml, "exempt-users"), ["x", "y"]);
  assert.deepEqual(parseList(PR_QUALITY, "exempt-users"), []);
});

test("the template fills every placeholder and rejects unknown ones", () => {
  const template = fs.readFileSync(path.join(__dirname, "..", "first-comment-notice.md"), "utf8");
  const body = fillTemplate(template, {
    username: "ada",
    contributing_url: "C",
    account_checks: "CHECKS",
    other_claims: "",
  });
  assert.doesNotMatch(body, /\{\{|<!--/);
  assert.match(body, /^@ada /);
  assert.match(body, /CHECKS$/);
  assert.throws(() => fillTemplate("{{nope}}", {}), /unknown placeholder/);
});

test("skips deleted accounts, pull requests, bots, maintainers and exempt users", async () => {
  for (const [github, ctx] of [
    [mockGithub(), context({ login: null })],
    [mockGithub(), context({ pullRequest: true })],
    [mockGithub(), context({ type: "Bot" })],
    [mockGithub({ role: "write" }), context()],
    [mockGithub({ role: "admin" }), context()],
    [mockGithub(), context({ login: "renovate[bot]" })],
  ]) {
    await run(github, ctx);
    assert.equal(github.posted.length, 0);
  }
});

test("skips a repeat comment and a commenter who already got the notice", async () => {
  const repeat = mockGithub({ comments: { 1: [{ id: 50, user: { login: "ada", type: "User" } }] } });
  await run(repeat);
  assert.equal(repeat.posted.length, 0);

  const notified = mockGithub({
    comments: { 1: [{ id: 150, user: { type: "Bot" }, body: "<!-- first-comment-notice:ada -->" }] },
  });
  await run(notified);
  assert.equal(notified.posted.length, 0);
});

test("a marker pasted by a person does not suppress the notice", async () => {
  const github = mockGithub({
    comments: {
      1: [{ id: 150, user: { login: "eve", type: "User" }, body: "<!-- first-comment-notice:ada -->" }],
    },
  });
  await run(github);
  assert.equal(github.posted.length, 1);
});

test("posts the questions and the account checks", async () => {
  const github = mockGithub({
    profile: { created_at: new Date().toISOString(), user_view_type: "public", hireable: null },
  });
  const { body } = await run(github);
  assert.equal(github.posted.length, 1);
  assert.equal(github.posted[0].body, body);
  assert.match(body, /^<!-- first-comment-notice:ada -->\n@ada \*\*IMPORTANT:\*\*/);
  assert.match(body, /Are you a human being\?/);
  assert.match(body, /\| \[`min-account-age`\].* \| \*\*failed\*\* \| 0 days old, minimum 30 \|/);
  assert.match(body, /\| \[`min-profile-completeness`\].* \| \*\*failed\*\* \| 0\/10 profile fields, minimum 2/);
  assert.doesNotMatch(body, /detect-spam-usernames/);
  assert.doesNotMatch(body, /no merged pull request/);
});

test("a failed account lookup still posts the questions", async () => {
  const github = mockGithub({ profile: Object.assign(new Error("rate limited"), { status: 403 }) });
  const { body, core } = await run(github);
  assert.equal(github.posted.length, 1);
  assert.match(body, /could not be run for your account/);
  assert.doesNotMatch(body, /\| Check \|/);
  assert.match(core.log.warning.join("\n"), /rate limited/);
});

test("lists other claimed issues for a commenter with no merged pull request", async () => {
  const github = mockGithub({
    search: ({ q }) => {
      if (q.includes("is:merged")) return { total_count: 0, items: [] };
      if (q.includes("assignee:")) return { total_count: 1, items: [{ number: 7 }] };
      if (q.includes("commenter:")) return { total_count: 2, items: [{ number: 1 }, { number: 3 }] };
      return { total_count: 0, items: [] };
    },
    comments: { 1: [], 3: [{ user: { login: "ada" }, body: "Can I work on this?" }] },
  });
  const claims = await findOtherClaims(github, { owner: "tqec", repo: "tqec", username: "ada", issueNumber: 1 });
  assert.deepEqual(claims, [3, 7]);
  const { body } = await run(github);
  assert.match(body, /asked to work on #3, #7\. Until your first pull request/);
});

test("lists no claims for a commenter with a merged pull request", async () => {
  const github = mockGithub({ search: () => ({ total_count: 1, items: [{ number: 7 }] }) });
  const claims = await findOtherClaims(github, { owner: "tqec", repo: "tqec", username: "ada", issueNumber: 1 });
  assert.deepEqual(claims, []);
});
