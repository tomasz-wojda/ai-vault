---
name: pr-review-comments
version: "1.2.0"
description: >-
  Author and post evidence-backed GitHub PR review comments. Proves each defect
  by executing read-only checks against the live system, quantifies severity
  with measured data, bounds the blast radius, and anchors inline comments to
  exact lines with one-click suggestion blocks. Use when the user asks to
  comment on a PR, leave a review comment, flag or raise a finding on a pull
  request, post findings to GitHub, or says "comment finding N in <PR URL>".
---

# PR Review Comments

Covers **authoring and posting** review comments on a GitHub pull request.

For comparing a PR diff against a worklog plan and updating checklist markers,
see [jira-worklog-processor](../jira-worklog-processor/SKILL.md) § "PR Review
Workflow". That skill decides *what* to review; this one decides *how the
comment reads and where it lands*.

## Core principle: evidence over inference

Never report a defect from reading code alone. Prove it by running something
read-only against the real system and paste the output into the comment. A
reviewer can dismiss "this looks wrong". They cannot dismiss a transcript.

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
- [ ] 11. Record what was posted in PR.log
- [ ] 12. Report the permalink back to the user
```

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
gh api "repos/<org>/<repo>/contents/<path>?ref=<sha>" --jq '.content' | base64 -d > /tmp/f
python3 -c "
lines=open('/tmp/f').read().split('\n')
for i in range(88,92): print(i+1,'|',repr(lines[i]))
"
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
  -F body=@/tmp/comment.md \
  -f commit_id=<sha> \
  -f path='<path>' \
  -F line=91 \
  -f side=RIGHT \
  --jq '{html_url, path, line}'
```

Multi-line range, when one defect spans several lines:

```bash
gh api "repos/<org>/<repo>/pulls/<N>/comments" -X POST \
  -F body=@/tmp/comment.md \
  -f commit_id=<sha> \
  -f path='<path>' \
  -F start_line=41 -F line=52 \
  -f start_side=RIGHT -f side=RIGHT
```

`-F` for integers, `-f` for strings. Getting this backwards yields a 422.

### 11. Record what was posted in PR.log

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

### 12. Report back

Give the user the `html_url` permalink and one sentence on what the comment
argues. When several comments were posted, say which is substantive and which
is cosmetic.

## Comment structure

```markdown
**<Severity label> — <one-sentence verdict>.**

### Where it comes from

<Causal chain. Name the two things that disagree and the lines they live on.>

### <Evidence heading>

<Command output or transcript proving it. Real numbers.>

### How serious — <level>

<What it cannot affect, and why. Then the measured probability.>

### Proposed fix

<Suggestion block, plus a note on why adjacent lines need no change.>

<Optional closing note, explicitly marked "no action implied".>
```

Open with the verdict. The author reads the first line and decides whether to
keep reading; never make them reach paragraph three to learn whether this
blocks the merge.

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

## Suggestion blocks

Use a `suggestion` fence whenever the fix is a line replacement, so the author
can apply it in one click. Requirements:

- Reproduce the original indentation exactly
- The block replaces the anchored line(s) in full
- Check whether adjacent lines also need changing, and say so explicitly when
  they do not, or the fix reads as incomplete

Omit the suggestion when the fix spans multiple non-contiguous regions, or when
the user asked only for an explanation.

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

## Constraints

- Posting a comment is the only write to the PR. Never commit, never push.
- Never mutate the target system to produce evidence.
- Append the exchange to `prompt.log` with a timestamp after posting, including
  the comment id and permalink.
- The `PR.log` append is a Write Gate operation owned by `devops-daily-protocol`.
  `prompt.log` and `PR.log` are both append-only; never rewrite an entry.
