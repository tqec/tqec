<!--
The reply that .github/scripts/first-comment-notice.js posts to a non-maintainer's first comment on an issue.
Edit the text freely. This comment is removed before posting. The script fills in these placeholders:
  {{username}}          the commenter's login, without the @
  {{contributing_url}}  the CONTRIBUTING.md of the repository the workflow runs in
  {{account_checks}}    the table of anti-slop account checks, or a note that they could not be run
  {{other_claims}}      a paragraph that lists the other open issues the commenter claims, or nothing
-->
@{{username}} **IMPORTANT:** this is your first comment on this issue. Please closely read our [contributing guidelines]({{contributing_url}}), including the [AI use]({{contributing_url}}#ai-use) section.

You must answer all of these questions, otherwise you will be ignored or blocked and reported. Using AI tools is allowed; we only ask that you say so, and please provide a plan or spec with explicit file names and lines.

1. Are you a human being? Please state whether you are or are not.
2. How did you use AI tools such as large language models (LLMs) for your comment? Copy this checklist into your reply and tick every line that applies:
   ```
   - [ ] No AI tool was used.
   - [ ] AI-assisted: I did the research and wrote the comment, and used an AI tool for parts of it.
   - [ ] AI-generated: an AI tool did most of the research or wrote most of the comment. I have read all of it and can explain it.
   - [ ] Translated into English with an AI tool.
   ```

{{account_checks}}

{{other_claims}}
