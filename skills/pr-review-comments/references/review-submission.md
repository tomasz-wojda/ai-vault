# Review Submission

Procedure for steps 12–14 of [pr-review-comments](../SKILL.md): deriving the
GitHub review event from the most severe proven finding, gating it, and
submitting one verified `APPROVE` or `REQUEST_CHANGES` review per head SHA.

Run it after every intended inline comment has been posted and verified, or
directly after step 2 when the completed review produced no findings.

## Decision table

The event follows the most severe **unresolved** finding at the pinned head
SHA. Unresolved findings are this review's proven findings plus earlier
`POSTED COMMENTS` from `PR.log` that re-verification shows are still present
at the pinned SHA.

| Most severe unresolved finding | Event | Resulting state |
|--------------------------------|-------|-----------------|
| None | `APPROVE` | `APPROVED` |
| Nit | `APPROVE` | `APPROVED` |
| Minor | `APPROVE` | `APPROVED` |
| Mixed nit and minor | `APPROVE` | `APPROVED` |
| Regression | `REQUEST_CHANGES` | `CHANGES_REQUESTED` |
| Blocker | `REQUEST_CHANGES` | `CHANGES_REQUESTED` |

Suspicions that failed the Proven bar never enter the calculation. Never use
`COMMENT`; inline findings are already posted as standalone comments. Never
send an empty `event`; GitHub then creates an unsubmitted `PENDING` review.

## Withhold conditions

Submit nothing and record `WITHHELD` with the reason when any of these hold:

| Condition | Reason recorded |
|-----------|-----------------|
| A changed file was not reviewed, or a suspicion that could be a Blocker or Regression is still unproven | `incomplete review` |
| An earlier Blocker or Regression cannot be re-verified at the pinned SHA | `unknown prior finding` |
| The head SHA moved after the review was pinned | `stale head <new-sha>` |
| Any intended inline comment failed to post or verify | `comment failure` |
| `gh` authentication fails or the reviewer lacks review permission | `insufficient permission` |
| The authenticated reviewer authored the PR | `self-authored PR` |
| The user declines at the Write Gate | `declined at gate` |

Resolve the reviewer, author, base branch, and head in one read:

```bash
REVIEWER="$(gh api user --jq .login)"
gh pr view <N> --repo <org>/<repo> \
  --json author,baseRefName,headRefOid \
  --jq '{author: .author.login, base: .baseRefName, head: .headRefOid}'
```

## Review body contract

Write the body to `REVIEW_BODY_FILE`. Keep it at or below 60 words and do not
repeat inline findings; the inline comments carry the evidence.

```markdown
**Approve — <n> non-blocking finding(s) inline.** <One sentence on what was verified.>
```

```markdown
**Request changes — <n> blocking finding(s) inline.** <One sentence naming the blocker and the condition for re-review.>
```

Use `no findings` for `<n> ... inline` when the review produced none.

## Write Gate

The submission is a remote write and follows the Write Gate Protocol in
[devops-daily-protocol](../../devops-daily-protocol/SKILL.md). ANNOUNCE,
PREVIEW, and WAIT happen in PLAN; EXECUTE and VERIFY happen only in
`MODE: EXECUTE`. This gate is separate from the inline-comment gate.

Read the branch-protection effect when the token allows it:

```bash
gh api "repos/<org>/<repo>/branches/<base>/protection/required_pull_request_reviews" \
  --jq '{required_approving_review_count, require_code_owner_reviews, dismiss_stale_reviews}'
```

A 403 or 404 means the rules are not readable; state that instead of guessing.

PREVIEW:

```
REVIEW SUBMISSION
  Reviewer:  <login>
  PR:        <org>/<repo>#<N>
  Head SHA:  <sha>
  Event:     APPROVE | REQUEST_CHANGES
  Basis:     <most severe unresolved finding, or "no findings">
  Body:      <REVIEW_BODY_FILE>
  Effect:    <counts toward <k> required approvals | blocks merge until re-reviewed | protection not readable>
  Request:   POST repos/<org>/<repo>/pulls/<N>/reviews
```

## Pre-submit checks

Run immediately before the POST. Abort on a moved head:

```bash
CURRENT_SHA="$(gh pr view <N> --repo <org>/<repo> --json headRefOid --jq .headRefOid)"
[ "$CURRENT_SHA" = "<sha>" ] || { echo "stale head: $CURRENT_SHA"; exit 1; }
```

Skip the POST when the reviewer's latest review on the pinned SHA already has
the target state, and record `already <state>`. Reviews are returned in
chronological order, so the last printed line is the latest:

```bash
gh api "repos/<org>/<repo>/pulls/<N>/reviews" --paginate \
  --jq ".[] | select(.user.login == \"${REVIEWER}\" and .commit_id == \"<sha>\") | {id, state, html_url}"
```

## Submit

```bash
gh api "repos/<org>/<repo>/pulls/<N>/reviews" -X POST \
  -f commit_id=<sha> \
  -f event=APPROVE \
  -F "body=@${REVIEW_BODY_FILE}" \
  --jq '{id, state, html_url}'
```

Replace `APPROVE` with `REQUEST_CHANGES` when the decision table requires it.
Submit once; never loop or retry automatically.

## Verify

```bash
gh api "repos/<org>/<repo>/pulls/<N>/reviews/<review-id>" \
  --jq '{id, user: .user.login, state, commit_id, html_url, body}' \
  | tee "$REVIEW_VERIFY_FILE"
```

Success requires all of:

- `user` equals `REVIEWER`
- `commit_id` equals the pinned SHA
- `state` is `APPROVED` for `APPROVE` or `CHANGES_REQUESTED` for
  `REQUEST_CHANGES`
- `body` matches `REVIEW_BODY_FILE`

## Failure handling

| Failure | Action |
|---------|--------|
| 403 on POST | Record `WITHHELD — insufficient permission`; report the response |
| 422 on POST | Record `WITHHELD`; report the response; do not resubmit |
| Verification mismatch | Report the mismatch and the review permalink; do not submit a second review; re-run step 12 only after the user decides |
| Head moved between POST and verify | Report that the review is pinned to the older SHA; do not submit again without a new review |

The merge recommendation reported in chat must equal the verified state, or
name the `WITHHELD` reason.
