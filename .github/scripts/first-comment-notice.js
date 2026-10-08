// Replies to a non-maintainer's first comment on an issue. The reply asks the commenter to read the contributing
// guide and answer two questions, and reports how many of the anti-slop account checks their account fails. A
// commenter with no merged pull request in the repository who already claims other open issues is also asked to
// claim one issue at a time.
//
// The account checks mirror src/checks/user-checks.ts and src/checks/merge-checks.ts of peakoss/anti-slop at
// ANTI_SLOP_VERSION, with the thresholds read from the anti-slop workflow so that they never drift from what pull
// requests face. The test file fails when the workflow uses another anti-slop version, so a version bump must also
// update these checks.
// The text of the reply is the template .github/first-comment-notice.md. Run by
// .github/workflows/first-comment-notice.yml through actions/github-script.

const fs = require("fs");
const path = require("path");

const ANTI_SLOP_URL = "https://github.com/peakoss/anti-slop";
const ANTI_SLOP_VERSION = "v0.3.0";
// Where the anti-slop configuration lives. A repository without its own copy uses tqec's.
const ANTI_SLOP_WORKFLOW = ".github/workflows/pr-quality.yml";
const FALLBACK_CONFIG_REPO = { owner: "tqec", repo: "tqec" };
const TEMPLATE_PATH = path.join(__dirname, "..", "first-comment-notice.md");
// GitHub roles at or above this one are maintainers: tqec's CONTRIBUTING.md calls contributors with write access
// maintainers.
const MAINTAINER_ROLES = ["write", "maintain", "admin"];

// anti-slop@v0.3.0 defaults, used for any input the workflow does not set.
const DEFAULTS = {
  "max-failures": "4",
  "detect-spam-usernames": "true",
  "min-account-age": "30",
  "max-daily-forks": "6",
  "require-public-profile": "true",
  "min-profile-completeness": "4",
  "min-repo-merged-prs": "0",
  "min-repo-merge-ratio": "0",
  "min-global-merge-ratio": "30",
  "global-merge-ratio-exclude-own": "false",
};

const SPAM_USERNAME_PATTERNS = [
  { pattern: /^\d+$/, reason: "username is all digits" },
  { pattern: /\d{2,}/, reason: "username contains 2 or more consecutive digits" },
  { pattern: /(?:^|-)ai(?:-|$)/i, reason: "username contains an 'ai' segment" },
];

const DAY_MS = 24 * 60 * 60 * 1000;

function marker(login) {
  return `<!-- first-comment-notice:${login.toLowerCase()} -->`;
}

// Reads the `with:` inputs of the anti-slop step. The workflow is flat `key: value` YAML, so a line match is enough.
// A value may be bare, single-quoted or double-quoted.
function parseSettings(yaml) {
  const settings = {};
  for (const key of Object.keys(DEFAULTS)) {
    const value = `(?:"([^"\\n]*)"|'([^'\\n]*)'|([^"'#\\n]*?))`;
    const match = yaml.match(new RegExp(`^\\s*${key}:\\s*${value}\\s*(?:#.*)?$`, "m"));
    settings[key] = match ? (match[1] ?? match[2] ?? match[3]).trim() : DEFAULTS[key];
  }
  const int = (key) => parseInt(settings[key], 10);
  const bool = (key) => settings[key].toLowerCase() === "true";
  return {
    maxFailures: int("max-failures"),
    detectSpamUsernames: bool("detect-spam-usernames"),
    minAccountAge: int("min-account-age"),
    maxDailyForks: int("max-daily-forks"),
    requirePublicProfile: bool("require-public-profile"),
    minProfileCompleteness: int("min-profile-completeness"),
    minRepoMergedPrs: int("min-repo-merged-prs"),
    minRepoMergeRatio: int("min-repo-merge-ratio"),
    minGlobalMergeRatio: int("min-global-merge-ratio"),
    globalMergeRatioExcludeOwn: bool("global-merge-ratio-exclude-own"),
  };
}

// Returns the anti-slop version the workflow uses, for example "v0.3.0", or null if there is none.
function parseVersion(yaml) {
  return yaml.match(/uses:\s*peakoss\/anti-slop@(\S+)/)?.[1] ?? null;
}

// Reads a list input, written either as a `|` block with one entry per line or as one comma-separated string.
function parseList(yaml, key) {
  const lines = yaml.split("\n");
  const start = lines.findIndex((line) => new RegExp(`^\\s*${key}:`).test(line));
  if (start === -1) return [];
  const inline = lines[start].replace(/^[^:]*:\s*/, "").replace(/\s+#.*$/, "").replace(/^(["'])(.*)\1$/, "$2").trim();
  if (inline !== "|") return inline.split(",").map((v) => v.trim()).filter(Boolean);
  const indent = lines[start].search(/\S/);
  const entries = [];
  for (const line of lines.slice(start + 1)) {
    if (line.trim() && line.search(/\S/) <= indent) break;
    if (line.trim()) entries.push(line.trim());
  }
  return entries;
}

async function readAntiSlopConfig(github, owner, repo) {
  for (const source of [{ owner, repo }, FALLBACK_CONFIG_REPO]) {
    try {
      const { data } = await github.rest.repos.getContent({ ...source, path: ANTI_SLOP_WORKFLOW });
      const yaml = Buffer.from(data.content, "base64").toString("utf8");
      if (yaml.includes("peakoss/anti-slop")) {
        const exempt = [...parseList(yaml, "exempt-bots"), ...parseList(yaml, "exempt-users")];
        return {
          source,
          version: parseVersion(yaml),
          settings: parseSettings(yaml),
          exempt: exempt.map((u) => u.toLowerCase()),
        };
      }
    } catch (error) {
      if (error.status !== 404) throw error;
    }
  }
  throw new Error(`no ${ANTI_SLOP_WORKFLOW} using peakoss/anti-slop was found`);
}

async function isMaintainer(github, owner, repo, username) {
  try {
    const { data } = await github.rest.repos.getCollaboratorPermissionLevel({ owner, repo, username });
    return MAINTAINER_ROLES.includes(data.role_name) || MAINTAINER_ROLES.includes(data.permission);
  } catch (error) {
    // A user who is not a collaborator can get a 404 instead of the "read" role.
    if (error.status === 404) return false;
    throw error;
  }
}

async function countDailyForks(github, username) {
  const repos = await github.paginate(github.rest.repos.listForUser, {
    username,
    type: "owner",
    sort: "created",
    direction: "desc",
    per_page: 100,
  });
  const times = repos
    .filter((r) => r.fork)
    .map((r) => new Date(r.created_at ?? "").getTime())
    .sort((a, b) => a - b);
  let max = 0;
  let left = 0;
  for (let right = 0; right < times.length; right++) {
    while (times[right] - times[left] > DAY_MS) left++;
    max = Math.max(max, right - left + 1);
  }
  return max;
}

async function searchPrCount(github, q) {
  const { data } = await github.rest.search.issuesAndPullRequests({ q, per_page: 1 });
  return data.total_count;
}

// A comment that asks to be assigned, or says the commenter will work on the issue. Whole words only, so that
// "assignment" or "claimed" do not count.
const CLAIM_PATTERN =
  /\b(?:assign|claim)\b|\bassigned to me\b|\bwork(?:ing)? on (?:this|it|the issue)\b|\b(?:take|pick) (?:this|it)(?: issue)? (?:on|up)\b/i;
// How many of the commenter's other open issues are read, to bound the API calls.
const MAX_ISSUES_SCANNED = 20;

async function searchIssueNumbers(github, q) {
  const { data } = await github.rest.search.issuesAndPullRequests({ q, sort: "updated", per_page: MAX_ISSUES_SCANNED });
  return data.items.map((i) => i.number);
}

// Returns the other open issues of this repository that a commenter without a merged pull request here is assigned
// to or has asked to be assigned to, sorted by number. Returns an empty list for anyone with a merged pull request.
async function findOtherClaims(github, { owner, repo, username, issueNumber }) {
  const repoFull = `${owner}/${repo}`;
  if ((await searchPrCount(github, `is:pr is:merged author:${username} repo:${repoFull}`)) > 0) return [];

  const assigned = await searchIssueNumbers(github, `is:issue is:open assignee:${username} repo:${repoFull}`);
  const claims = new Set(assigned.filter((n) => n !== issueNumber));
  const commented = await searchIssueNumbers(github, `is:issue is:open commenter:${username} repo:${repoFull}`);
  for (const number of commented) {
    if (number === issueNumber || claims.has(number)) continue;
    const comments = await github.paginate(github.rest.issues.listComments, {
      owner,
      repo,
      issue_number: number,
      per_page: 100,
    });
    if (comments.some((c) => c.user?.login === username && CLAIM_PATTERN.test(c.body ?? ""))) claims.add(number);
  }
  return [...claims].sort((a, b) => a - b);
}

// Returns the checks anti-slop would record for this account. Checks that anti-slop skips are left out.
async function runAccountChecks(github, { owner, repo, username, authorAssociation, settings: s }) {
  const checks = [];
  const add = (name, passed, detail) => checks.push({ name, passed, detail });

  const { data: profile } = await github.rest.users.getByUsername({ username });
  const isPublic = (profile.user_view_type ?? "private") === "public";

  if (s.detectSpamUsernames) {
    const matched = SPAM_USERNAME_PATTERNS.filter((p) => p.pattern.test(username)).map((p) => p.reason);
    add("detect-spam-usernames", matched.length === 0, matched.length ? matched.join(", ") : "no spam pattern");
  }
  if (s.minAccountAge > 0) {
    const days = Math.floor((Date.now() - new Date(profile.created_at).getTime()) / DAY_MS);
    add("min-account-age", days >= s.minAccountAge, `${days} days old, minimum ${s.minAccountAge}`);
  }
  if (s.maxDailyForks > 0) {
    const forks = await countDailyForks(github, username);
    add("max-daily-forks", forks <= s.maxDailyForks, `${forks} forks in one day, maximum ${s.maxDailyForks}`);
  }
  if (s.requirePublicProfile) {
    add("require-public-profile", isPublic, isPublic ? "profile is public" : "profile is private");
  }
  if (s.minProfileCompleteness > 0) {
    const fields = {
      name: !!profile.name,
      company: !!profile.company,
      blog: !!profile.blog,
      location: !!profile.location,
      email: !!profile.email,
      hireable: profile.hireable !== null,
      bio: !!profile.bio,
      twitter: !!profile.twitter_username,
      followers: profile.followers > 0,
      following: profile.following > 0,
    };
    const filled = Object.values(fields).filter(Boolean).length;
    const missing = Object.keys(fields).filter((k) => !fields[k]);
    add(
      "min-profile-completeness",
      filled >= s.minProfileCompleteness,
      `${filled}/10 profile fields, minimum ${s.minProfileCompleteness}` +
        (missing.length ? ` (missing: ${missing.join(", ")})` : ""),
    );
  }

  // anti-slop cannot compute merge ratios for a private profile and skips these checks.
  if (!isPublic) return checks;

  const repoFull = `${owner}/${repo}`;
  const scope = s.globalMergeRatioExcludeOwn ? ` -user:${username}` : "";
  if (s.minRepoMergedPrs === 1) {
    // As in anti-slop, the CONTRIBUTOR association means at least one merged PR in this repository.
    add("min-repo-merged-prs", authorAssociation === "CONTRIBUTOR", `association ${authorAssociation}, minimum 1 merged PR`);
  } else if (s.minRepoMergedPrs > 1 || s.minRepoMergeRatio > 0) {
    const merged = await searchPrCount(github, `is:pr is:merged author:${username} repo:${repoFull}`);
    if (s.minRepoMergedPrs > 1) {
      add("min-repo-merged-prs", merged >= s.minRepoMergedPrs, `${merged} merged PRs here, minimum ${s.minRepoMergedPrs}`);
    }
    if (s.minRepoMergeRatio > 0) {
      const closed = await searchPrCount(github, `is:pr is:unmerged is:closed author:${username} repo:${repoFull}`);
      const total = merged + closed;
      if (total > 0) {
        const pct = Math.round((100 * merged) / total);
        add("min-repo-merge-ratio", merged / total >= s.minRepoMergeRatio / 100,
          `${pct}% of closed PRs here merged (${merged}/${total}), minimum ${s.minRepoMergeRatio}%`);
      }
    }
  }
  if (s.minGlobalMergeRatio > 0) {
    const merged = await searchPrCount(github, `is:pr is:merged author:${username}${scope}`);
    const closed = await searchPrCount(github, `is:pr is:unmerged is:closed author:${username}${scope}`);
    const total = merged + closed;
    if (total > 0) {
      const pct = Math.round((100 * merged) / total);
      add("min-global-merge-ratio", merged / total >= s.minGlobalMergeRatio / 100,
        `${pct}% of closed PRs on GitHub merged (${merged}/${total}), minimum ${s.minGlobalMergeRatio}%`);
    }
  }
  return checks;
}

// Describes the account checks, or says that they could not be run when `checks` is null.
function accountSection({ checks, maxFailures, configRepo }) {
  if (!checks) {
    return [
      `The [anti-slop](${ANTI_SLOP_URL}) account checks could not be run for your account at this time. They run ` +
        "again on any pull request you open.",
    ];
  }
  const failed = checks.filter((c) => !c.passed).length;
  const remaining = maxFailures - failed;
  const configUrl = `https://github.com/${configRepo.owner}/${configRepo.repo}/blob/main/${ANTI_SLOP_WORKFLOW}`;
  const rows = checks.map(
    (c) => `| [\`${c.name}\`](${ANTI_SLOP_URL}#${c.name}) | ${c.passed ? "passed" : "**failed**"} | ${c.detail} |`,
  );
  const distance =
    remaining > 0
      ? `If you open a pull request to ${configRepo.owner}/${configRepo.repo}, you are ${remaining} failing ` +
        `check${remaining === 1 ? "" : "s"} away from it being closed immediately: a pull request that fails ` +
        `${maxFailures} or more checks, counting these and the checks on the pull request itself, is closed ` +
        "automatically. If that happens, your account will be blocked and reported."
      : `A pull request you open to ${configRepo.owner}/${configRepo.repo} would be closed immediately, because ` +
        `these checks alone reach the limit of ${maxFailures} failures. If that happens, your account will be blocked and reported.`;
  return [
    `Your account currently fails **${failed}/${checks.length}** of the account checks that ` +
      `[anti-slop](${ANTI_SLOP_URL}) runs on pull requests ([configuration](${configUrl})).`,
    "",
    "| Check | Result | Detail |",
    "|---|---|---|",
    ...rows,
    "",
    distance,
  ];
}

// Fills the {{placeholders}} of the template. An unknown placeholder is an error, so that a typo in the template is
// not posted.
function fillTemplate(template, values) {
  const text = template.replace(/^\s*<!--[\s\S]*?-->\s*/, "");
  return text
    .replace(/\{\{\s*(\w+)\s*\}\}/g, (_, name) => {
      if (!(name in values)) throw new Error(`unknown placeholder {{${name}}} in ${TEMPLATE_PATH}`);
      return values[name];
    })
    .replace(/\n{3,}/g, "\n\n")
    .trimEnd();
}

function buildMessage({ owner, repo, username, checks, maxFailures, configRepo, otherClaims, template }) {
  const otherClaimsText = otherClaims.length
    ? `You have no merged pull request in ${owner}/${repo} yet, and you are assigned to or have asked to work on ` +
      `${otherClaims.map((n) => `#${n}`).join(", ")}. Until your first pull request here is merged, please ask ` +
      "to be assigned to one issue at a time, so that maintainers are not overwhelmed. Build your credibility " +
      "by taking one issue through the pull request process first."
    : "";
  const body = fillTemplate(template ?? fs.readFileSync(TEMPLATE_PATH, "utf8"), {
    username,
    contributing_url: `https://github.com/${owner}/${repo}/blob/main/CONTRIBUTING.md`,
    account_checks: accountSection({ checks, maxFailures, configRepo }).join("\n"),
    other_claims: otherClaimsText,
  });
  return `${marker(username)}\n${body}`;
}

module.exports = async ({ github, context, core, dryRun = false }) => {
  const { owner, repo } = context.repo;
  const { issue, comment } = context.payload;
  const username = comment.user?.login;

  if (!username) return core.info("Comment has no author (deleted account); skipping.");
  if (issue.pull_request) return core.info("Comment is on a pull request; skipping.");
  if (comment.user.type === "Bot") return core.info(`${username} is a bot; skipping.`);
  if (await isMaintainer(github, owner, repo, username)) {
    return core.info(`${username} has write access or higher; skipping.`);
  }

  const { source: configRepo, version, settings, exempt } = await readAntiSlopConfig(github, owner, repo);
  if (version !== ANTI_SLOP_VERSION) {
    core.warning(`${ANTI_SLOP_WORKFLOW} uses anti-slop ${version}, but these checks mirror ${ANTI_SLOP_VERSION}.`);
  }
  if (exempt.includes(username.toLowerCase())) {
    return core.info(`${username} is exempt from anti-slop; skipping.`);
  }

  const comments = await github.paginate(github.rest.issues.listComments, {
    owner,
    repo,
    issue_number: issue.number,
    per_page: 100,
  });
  // Compare ids rather than counting comments, so two quick comments do not both look like repeats.
  if (comments.some((c) => c.user?.login === username && c.id < comment.id)) {
    return core.info(`${username} has commented on #${issue.number} before; skipping.`);
  }
  // Only a bot's comment counts, so a commenter cannot suppress the notice by pasting the marker.
  if (comments.some((c) => c.user?.type === "Bot" && c.body?.includes(marker(username)))) {
    return core.info(`${username} was already sent the notice on #${issue.number}; skipping.`);
  }

  // A later comment by the same user is skipped as a repeat, so a failed lookup (for example a rate limit) must
  // not stop the notice: it posts the questions without the account results.
  let checks = null;
  try {
    checks = await runAccountChecks(github, {
      owner,
      repo,
      username,
      authorAssociation: comment.author_association,
      settings,
    });
  } catch (error) {
    core.warning(`could not run the account checks for ${username}: ${error.message}`);
  }
  // The reminder is optional, so a failed search (for example a rate limit) still lets the notice post.
  let otherClaims = [];
  try {
    otherClaims = await findOtherClaims(github, { owner, repo, username, issueNumber: issue.number });
  } catch (error) {
    core.warning(`could not scan ${username}'s other issues: ${error.message}`);
  }
  const body = buildMessage({ owner, repo, username, checks, maxFailures: settings.maxFailures, configRepo, otherClaims });

  if (dryRun) {
    core.info(body);
    return body;
  }
  await github.rest.issues.createComment({ owner, repo, issue_number: issue.number, body });
  return body;
};

// For first-comment-notice.test.js.
module.exports._internal = {
  ANTI_SLOP_VERSION,
  parseSettings,
  parseList,
  parseVersion,
  fillTemplate,
  findOtherClaims,
};
