---
name: pr-review-comments
version: "1.0.0"
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
- [ ] 1. Pin the head SHA
- [ ] 2. Establish the mechanism from the source
- [ ] 3. Prove it with a read-only execution
- [ ] 4. Bound the blast radius
- [ ] 5. Measure the probability
- [ ] 6. Verify exact line numbers and whitespace
- [ ] 7. Check for an existing comment on the same defect
- [ ] 8. Write the body to a file
- [ ] 9. Post anchored to the line(s)
- [ ] 10. Report the permalink back to the user
```

### 1. Pin the head SHA

Every inline comment must be anchored to a commit. Re-fetch it each time; the
author may have pushed since the review started.

```bash
gh pr view <N> --repo <org>/<repo> --json headRefOid,changedFiles,files,state
```

### 2. Establish the mechanism

Read the source at that SHA, not at `develop` or `master`.

```bash
gh api "repos/<org>/<repo>/contents/<path>?ref=<sha>" --jq '.content' | base64 -d
```

State the defect as a causal chain, not an adjective. "Line 91 derives the
overflow from the capped array while line 98 renders the header from the
uncapped total" beats "the count is wrong".

### 3. Prove it

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

### 4. Bound the blast radius

Explicitly state what the defect cannot reach. This is what lets the author
triage in seconds. Typical bounds:

- Display-only, because the decision path reads a different variable
- Latent, not live, because the job pins a different branch
- Unreachable from CI, because the pipeline never passes that flag

### 5. Measure the probability

Use real data from the target system to say how often the defect fires. A
measured rarity is what converts "bug" into "nit", and it is the difference
between a comment that blocks a merge and one that does not.

### 6. Verify exact lines

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

### 7. Check for duplicates

```bash
gh api repos/<org>/<repo>/pulls/<N>/comments --jq '.[] | {id, path, line, user: .user.login}'
```

### 8-9. Write to a file, then post

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

### 10. Report back

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

- Posting a comment is the only write. Never commit, never push.
- Never mutate the target system to produce evidence.
- Append the exchange to `prompt.log` with a timestamp after posting, including
  the comment id and permalink.
