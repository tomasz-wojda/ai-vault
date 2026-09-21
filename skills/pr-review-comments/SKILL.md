---
name: pr-review-comments
version: "1.4.0"
description: >-
  Author concise, evidence-backed GitHub PR review comments and prepare
  validated local fixes in the corresponding repos clone. Use when the user
  asks to comment on a PR, post a finding, create a suggested change, or fix a
  proven review finding locally without committing or pushing.
---

# PR Review Comments

Covers **authoring and posting** review comments on a GitHub pull request and,
when explicitly requested, preparing a validated fix in the corresponding
workspace clone.

For comparing a PR diff against a worklog plan and updating checklist markers,
see [jira-worklog-processor](../jira-worklog-processor/SKILL.md) § "PR Review
Workflow". That skill decides *what* to review; this one decides *how the
comment reads and where it lands*.

## Core principle: evidence over inference

Never report a defect from reading code alone. Prove it by running something
read-only against the real system. Include only the smallest output excerpt
needed to make that proof reproducible.

Every finding must clear three bars before it is posted:

| Bar | Question | If unmet |
|-----|----------|----------|
| Proven | Did a command demonstrate the behaviour? | Say "I don't know", do not post |
| Bounded | What can this defect **not** affect? | Keep digging until the limit is known |
| Measured | How often will it actually fire? | Do not assign severity yet |

A finding that fails the Proven bar is a suspicion. Report suspicions in chat,
not on the PR.

## Workflow

```
- [ ] 1. Load prior context from PR.log
- [ ] 2. Pin the head SHA
- [ ] 3. Establish the mechanism from the source
- [ ] 4. Prove it with a read-only execution
- [ ] 5. Bound the blast radius
- [ ] 6. Measure the probability
- [ ] 7. Verify exact line numbers and whitespace
- [ ] 8. Check for an existing comment on the same defect
- [ ] 9. Write the body to a file
- [ ] 10. Post anchored to the line(s)
- [ ] 11. Re-read and verify the posted comment
- [ ] 12. Record what was posted in PR.log
- [ ] 13. Report the permalink and fix status
```

## Workspace artifact storage

Keep every PR-review working artifact under:

`<workspace>/tmp/PR-reviews/<ticket-or-topic>/`

Never use the system `/tmp` directory. Resolve `<ticket-or-topic>` in this
order:

1. The uppercase ticket key when the PR resolves to a ticket
2. A topic-folder name explicitly supplied by the user
3. `<owner>-<repository>-pr-<number>` when neither is available

Restrict generated folder names to letters, numbers, dots, underscores, and
hyphens. Replace every other character run with `-`, then remove leading or
trailing hyphens. Create the directory once and reuse it throughout the review:

```bash
REVIEW_TOPIC="$(printf '%s' "$REVIEW_TOPIC" | LC_ALL=C tr -cs 'A-Za-z0-9._-' '-' | sed 's/^-//;s/-$//')"
REVIEW_DIR="tmp/PR-reviews/${REVIEW_TOPIC}"
mkdir -p -- "$REVIEW_DIR"
SOURCE_FILE="${REVIEW_DIR}/pr-${PR_NUMBER}-finding-${FINDING_NUMBER}-source.txt"
COMMENT_FILE="${REVIEW_DIR}/pr-${PR_NUMBER}-finding-${FINDING_NUMBER}-comment.md"
VERIFY_FILE="${REVIEW_DIR}/pr-${PR_NUMBER}-finding-${FINDING_NUMBER}-verification.json"
```

Run the block from the current ai-worklog workspace root and set `REVIEW_TOPIC`
from the resolution order first. Do not guess or hardcode an absolute workspace
path. Keep source snapshots, comment Markdown, fenced `suggestion` content, and
verification output after posting so the review remains reproducible within
the same workspace.

### 1. Load prior context from PR.log

Read before reviewing. `PR.log` at the workspace root is the local record of
every previous review, and a PR is often revisited after the author pushes.
Reviewing without it means re-deriving findings that were already settled.

The file is gitignored and local-only. If it does not exist, skip this step.

Entries begin with a `--- YYYY-MM-DDTHH:MM ---` header followed by
`PR #<N> | <org>/<repo>`. Split on the timestamp header, not on the `====`
rule — the rule is not present between every entry.

```bash
rg -n "^PR #<N> \| <org>/<repo>$" PR.log
```

```bash
python3 - PR.log "PR #<N> | <org>/<repo>" <<'PY'
import re, sys
text = open(sys.argv[1], encoding='utf-8').read()
for entry in re.split(r'(?m)^(?=--- 20\d\d-)', text):
    if sys.argv[2] in entry:
        print(entry.rstrip())
PY
```

Widen the search when the same PR has no entry:

| Looking for | Command |
|-------------|---------|
| Other PRs in the same repo | `rg -n "^PR #[0-9]+ \| <org>/<repo>$" PR.log` |
| Prior findings on the same file | `rg -n -B2 "<path>" PR.log` |
| Defects that shipped unfixed | `rg -n -A3 "still open at merge" PR.log` |

What each part of a prior entry changes about this review:

| Section found | Effect |
|---------------|--------|
| `POSTED COMMENTS` | Already raised. Do not post again; check whether the author responded |
| `NOT POSTED` | Already weighed and withheld. Do not re-litigate without new evidence |
| `OBSERVATIONS` | Analysis already done. Re-verify against the new head SHA rather than redoing it |
| `FOLLOW-UP … still open at merge` | A known defect shipped. Likely still present, and precedent for how it was handled |
| Entries for other PRs, same repo | Recurring patterns and risks the team has already accepted |

State what was carried over in the review output, so the user can tell a fresh
finding from a repeated one.

### 2. Pin the head SHA

Every inline comment must be anchored to a commit. Re-fetch it each time; the
author may have pushed since the review started.

```bash
gh pr view <N> --repo <org>/<repo> --json headRefOid,changedFiles,files,state
```

### 3. Establish the mechanism

Read the source at that SHA, not at `develop` or `master`.

```bash
gh api "repos/<org>/<repo>/contents/<path>?ref=<sha>" --jq '.content' | base64 -d
```

State the defect as a causal chain, not an adjective. "Line 91 derives the
overflow from the capped array while line 98 renders the header from the
uncapped total" beats "the count is wrong".

### 4. Prove it

Replay the exact call or command shape the code uses, read-only. Prefer:

- Re-issuing the same API request the code issues, against live data
- Running the script's error paths and recording exit codes and output
- Isolating a language primitive when the claim rests on it
  (`bash -c 'set -e; set -- one; shift 2; echo NOT REACHED'`)
- Querying the live target system for a referenced identifier, e.g.
  `ai-worklog service jenkins credentials <controller>` to confirm a
  `credentialsId` actually exists

Never mutate anything to prove a point. If the proof requires a write, say so
and stop.

### 5. Bound the blast radius

Explicitly state what the defect cannot reach. This is what lets the author
triage in seconds. Typical bounds:

- Display-only, because the decision path reads a different variable
- Latent, not live, because the job pins a different branch
- Unreachable from CI, because the pipeline never passes that flag

### 6. Measure the probability

Use real data from the target system to say how often the defect fires. A
measured rarity is what converts "bug" into "nit", and it is the difference
between a comment that blocks a merge and one that does not.

### 7. Verify exact lines

Diff line numbers must match the file at the head SHA, and a suggestion block
must reproduce the original indentation byte for byte.

```bash
gh api "repos/<org>/<repo>/contents/<path>?ref=<sha>" \
  --jq '.content' | base64 -d > "$SOURCE_FILE"
python3 - "$SOURCE_FILE" <<'PY'
import sys
lines = open(sys.argv[1], encoding="utf-8").read().split("\n")
for i in range(88, 92):
    print(i + 1, "|", repr(lines[i]))
PY
```

`repr()` rather than `cat`, so tabs and trailing spaces are visible.

### 8. Check for duplicates

```bash
gh api repos/<org>/<repo>/pulls/<N>/comments --jq '.[] | {id, path, line, user: .user.login}'
```

This and step 1 catch different things. GitHub shows what is on the PR now,
including comments from other reviewers; `PR.log` additionally shows what was
considered and deliberately withheld. Run both.

### 9-10. Write to a file, then post

Write the body to a file and pass it with `-F body=@<file>`. Never inline a
multi-paragraph body in the shell; backticks, `${}` and quotes will be mangled.

Single line:

```bash
gh api "repos/<org>/<repo>/pulls/<N>/comments" -X POST \
  -F "body=@${COMMENT_FILE}" \
  -f commit_id=<sha> \
  -f path='<path>' \
  -F line=91 \
  -f side=RIGHT \
  --jq '{html_url, path, line}'
```

Multi-line range, when one defect spans several lines:

```bash
gh api "repos/<org>/<repo>/pulls/<N>/comments" -X POST \
  -F "body=@${COMMENT_FILE}" \
  -f commit_id=<sha> \
  -f path='<path>' \
  -F start_line=41 -F line=52 \
  -f start_side=RIGHT -f side=RIGHT
```

`-F` for integers, `-f` for strings. Getting this backwards yields a 422.

### 11. Verify the posted comment

Re-read the comment from GitHub and verify its permalink, pinned commit, path,
line or range, body, and `suggestion` fence before reporting success:

```bash
gh api repos/<org>/<repo>/pulls/comments/<comment-id> \
  --jq '{html_url, commit_id, path, start_line, line, body}' \
  | tee "$VERIFY_FILE"
```

Do not call a comment a one-click suggestion unless the returned body contains
a valid `suggestion` fence on an addressable diff line or contiguous range.

### 12. Record what was posted in PR.log

`PR.log` is owned by [jira-worklog-processor](../jira-worklog-processor/SKILL.md)
§ "PR.log Entry Format", and appends route through the Write Gate Protocol in
[devops-daily-protocol](../devops-daily-protocol/SKILL.md). This skill does not
redefine the entry — it contributes one block to it.

Add a `POSTED COMMENTS` block after `OBSERVATIONS`, because `OBSERVATIONS` is
the analysis and this is the subset that was raised publicly:

```
POSTED COMMENTS:
  1. <severity> — <one-line verdict>
     <path>:<line or start-end>
     https://github.com/<org>/<repo>/pull/<N>#discussion_r<id>
     Suggestion: yes|no   From: OBSERVATION <n>
  2. ...

NOT POSTED (kept in chat):
  - <finding> — <which of the three bars it failed>
```

The `NOT POSTED` list is the point of the block. The three-bar rule means some
findings never reach the PR, and a review record that only shows what was said
publicly loses the reasoning about what was deliberately withheld. Omit the
list only when every finding was posted.

Cross-reference in both directions: each posted comment names the
`OBSERVATION` it came from, and an observation that produced no comment is
accounted for in `NOT POSTED`.

### Follow-up on merge

When the merge follow-up runs, append outcomes under the original entry rather
than editing the `POSTED COMMENTS` lines:

```
POSTED COMMENTS FOLLOW-UP (YYYY-MM-DDTHH:MM):
  1. r<id> — suggestion applied in <sha>
  2. r<id> — resolved without change, author response: <summary>
  3. r<id> — still open at merge
```

`still open at merge` is worth recording explicitly. A defect that was raised,
not addressed, and merged anyway is the single most useful thing to find in
this log six months later.

### 13. Report back

Give the user the `html_url` permalink, one sentence on the finding, the merge
recommendation, whether the comment has an applicable one-click suggestion,
whether a validated local fix was prepared, and the workspace artifact
directory and comment-file path.

## Production-ready comment contract

```markdown
**<Severity> — <merge impact>: <one-sentence defect>.**

<One compact paragraph covering the causal mechanism, minimal proof, affected
scope, and any boundary or measured frequency that changes triage.>

<One actionable correction, preferably an applicable suggested change.>
```

Keep prose at or below 150 words, excluding suggestion blocks and minimal
evidence output. Open with severity and merge impact. Use precise production
behaviour and measured facts; remove conversational filler, repetition,
speculation, transcript dumps, excessive headings, and unrelated optional
notes.

## Severity calibration

| Label | Meaning | Evidence required |
|-------|---------|-------------------|
| Blocker | Fails on first run | Proof the failure occurs, e.g. the referenced identifier does not exist |
| Regression | Working behaviour is broken by this change | The full downstream chain, plus whether it is live or latent |
| Minor | Wrong, but bounded and rare | The bound plus a measured frequency |
| Nit | Correct outcome, poor ergonomics | Enough to show it is not a correctness issue |

Say "non-blocking" in the headline when it is. Reviewers over-weight anything
that looks like a defect report; stating the opposite is a courtesy that gets
the real blockers acted on.

## Suggested changes and one-click suggestions

A **suggested change** is a review comment containing a fenced block tagged
`suggestion`. GitHub renders an eligible block as a diff with a **Commit
suggestion** button; this is an **applicable one-click suggestion**. Multiple
valid suggestions can be batched through **Commit suggestions** in the Files
changed view unless they are unavailable, outdated, or conflicting.

Prefer an applicable one-click suggestion for every concise, contiguous
replacement that can be anchored to the current diff. Before posting:

- Confirm the line or contiguous range is addressable in the diff hunk,
  including an eligible context line
- Pin the current head SHA and reproduce indentation exactly
- Replace the complete anchored range; one line may be replaced by several
- Include adjacent required edits when they form one contiguous replacement
- Keep one defect in one comment and one contiguous suggested change

When required lines are outside the diff hunk, GitHub cannot apply them as a
one-click suggestion. Post a concise plain fenced replacement and state why the
one-click action is unavailable. Also omit a suggestion when the correction
spans non-contiguous regions or the user requested explanation only.

Never claim `Suggestion: yes` until the posted comment has been re-read and its
valid `suggestion` fence and addressable anchor verified.

Keep the fenced `suggestion` in the finding-specific `COMMENT_FILE`; do not
create or post it from an arbitrary temporary file.

## Anti-patterns

**Posting a suspicion.** If a read-only proof was not run, it goes in chat.

**Severity by adjective.** "Serious" and "critical" mean nothing without a
measured frequency and a stated bound.

**Top-level comment dumps.** A general PR comment listing five findings is
unactionable. One inline comment per defect, anchored to its line.

**Repeating one defect across several lines.** When a single defect appears in
three parallel case arms, use one multi-line comment over the whole range.

**Trusting memory about what was posted.** When asked what a comment said,
re-read it:

```bash
gh api repos/<org>/<repo>/pulls/comments/<comment-id> --jq '.body'
```

**Claiming an unverified consequence.** If the downstream effect depends on
which branch a job tracks, check the branch before describing the impact.

**Reviewing without loading `PR.log`.** On a revisited PR this re-derives
settled findings and risks re-posting a comment, or re-raising something that
was already weighed and withheld.

**Calling plain code a suggestion.** A replacement outside the diff hunk is
useful guidance, but it is not an applicable one-click suggestion.

## Worked example

Defect: a Slack message under-reports an overflow count.

- **Mechanism** — `maxResults=200` in the shell script caps the issues array,
  while the count comes from the uncapped `total`. The Jenkinsfile renders the
  header from the total and the overflow from the array length.
- **Proof** — replayed the same search against live Jira: `total: 7277`,
  issues returned `200`. The message would read "7277 issues" above a line
  implying 200.
- **Bound** — display only. The rotation decision reads the uncapped total in
  both the shell comparison and the JSON flag, so no release can rotate early
  or late because of it.
- **Measurement** — grouped all 1560 issues carrying a fix version: 141
  versions, median 5, max 463, and the only one above 200 cannot match the
  pattern the job selects on.
- **Verdict** — minor, non-blocking, worth fixing while the file is open.
- **Fix** — one-line suggestion swapping the array length for the total, plus a
  note that the adjacent condition is already equivalent and needs no change.

## Local remediation in the corresponding repo

Review and comment requests are read-only. Prepare a local fix only when the
user explicitly requests one and the session reaches `MODE: EXECUTE` through
the developer protocol.

Resolve the clone deterministically:

1. Read `<owner>/<repository>` from the PR metadata.
2. Resolve `<workspace>/repos/<owner>-<repository>`, preserving GitHub casing.
3. Normalize and verify a configured GitHub remote matches the PR repository.
4. Stop if the clone is absent or mismatched. Do not clone or select another
   repository without an explicit request.

Prepare the fix:

1. Re-fetch and pin the current PR head SHA.
2. Inspect the local status and current branch before mutation. Stop on
   unrelated changes rather than overwriting or mixing them.
3. Create `fix/<ticket>-<finding-slug>`, or
   `fix/pr-<number>-<finding-slug>` when no ticket exists, from the pinned head.
4. Apply only the proven finding's correction.
5. Run the focused reproduction and relevant repository validation.
6. Verify the final diff contains no unrelated changes.
7. Stage only the intended files. Never commit or push.
8. Report the clone path, branch, changed files, validation results, remaining
   risk, semantic commit title, and one-paragraph commit description.

## Constraints

- Posting a comment is the only remote write to the PR.
- Local remediation follows the mode and Write Gate protocols. Never commit or
  push.
- Store PR-review artifacts only under
  `<workspace>/tmp/PR-reviews/<ticket-or-topic>/`; never use system `/tmp`.
- Never mutate the target system to produce evidence.
- After posting, record the exchange through
  [worklog-chat-memory](../worklog-chat-memory/SKILL.md) § "Record turn events".
  Write `journal.db` synchronously first with exact user text, exact final
  assistant response, PR URL/ticket keys in `tickets` when known, and comment
  id and permalink in `raw_payload` or the assistant text. Only after success
  append the shadow audit entry to `prompt.log` with a timestamp, comment id,
  and permalink.
- The `PR.log` append is a Write Gate operation owned by `devops-daily-protocol`.
  `prompt.log` and `PR.log` are both append-only; never rewrite an entry. If
  `record-event` fails, leave the failure visible and do not append
  `prompt.log`.
