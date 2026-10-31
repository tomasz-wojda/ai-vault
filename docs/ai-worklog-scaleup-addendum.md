# ai-worklog-scaleup Governance Addendum

Status: proposed. It is not in force until the owner references it from `.rules` (see "Put it in force").

Origin: `repos/ai-worklog-scaleup`, specification `docs/specs/001-ticket-scaleup/` (FR-002, FR-003, FR-004, FR-008, FR-014, FR-022) and decision D-17 in `docs/research/decision-log.md`. D-17 chose an addendum over a rewrite of `.rules`.

---

## 1. Scope

- The addendum applies only to work that starts from the ai-worklog-scaleup dashboard or its orchestrator, and to sessions that hold a ticket lock.
- Every other session follows `.rules` and R-01 to R-29 in `skills/CROSS_SKILL_INTEGRATION.md` without change.
- Where this addendum and a rule differ for a scoped session, this addendum wins for the points in section 7 only.

## 2. A1: Mode per ticket

Changes: R-01, R-02, R-04, R-06, R-07.

1. Each ticket has its own mode. It is the `governance_mode` field of the ticket state file `.ai-worklog/state/<KEY>.json`. It is the only mode source for that ticket.
2. A session that holds the lock of a ticket uses that ticket's mode. It declares the mode at the start of every response, as R-01 requires.
3. A background session starts in the stored mode of its ticket. It never changes the mode itself.
4. The mode changes only when the owner types the exact phrase `MODE: <name>` in the session of that ticket. The session then writes the new value to `governance_mode`.
5. R-02 applies to one ticket: a deviation from an approved plan reverts that ticket to PLAN. Other tickets keep their modes.
6. R-07 applies to one ticket: each ticket has at most one open gate. A mode change in one ticket cancels only its own gate.
7. R-04 is unchanged. A ticket in EXECUTE without a plan must state that no plan exists before it acts.

## 3. A2: Intake without the Write Gate

Changes: R-05, R-06, R-09. Reads stay free under R-03.

1. "Pick up" reads the ticket and its context from external systems. These calls are read-only.
2. After the reads, it creates two local files for a ticket that has none: the worklog with its structural sections (R-09) and the ticket state file.
3. This creation needs no Write Gate and no mode change, in the same way as ticket sync under R-29.
4. The new ticket starts in RESEARCH.
5. Intake never overwrites an existing worklog or state file, and it never writes to Jira or any other external system.

## 4. A3: Approval inbox

Changes: R-05, R-06.

1. Every write to an external system that starts from the dashboard is queued as an inbox item. Examples: a Jira transition or comment, a Jenkins build, a git push, a Tempo entry, an archive action.
2. An inbox item holds the target, the exact write and a preview. Showing the preview is the ANNOUNCE and PREVIEW step of the Write Gate.
3. The owner approves a selection of items in one action. That approval is the WAIT step. Only approved items run. An item that nobody approves never runs.
4. The result of each item goes to the ACTION LOG of its ticket.
5. Approval of an inbox item does not replace `MODE: EXECUTE` for file edits made in a session. It covers the external write of that item only.

## 5. A4: Ticket lock

New rule.

1. A ticket has at most one holder at a time. The holder takes the lock before it works on the ticket and releases it when it stops.
2. The dashboard takes the lock for "Continue" and "Start next". A manual Claude or Cursor session that works on a ticket takes the lock with `bin/ticket-lock acquire <KEY> --holder <name> --watch-pid <pid>` and releases it with `bin/ticket-lock release <KEY>`.
3. A held ticket is not started a second time. The second process stops and reports the holder, the process number and the start time.
4. If the holder process stops, the lock is released by the operating system. A lease file that stays behind is overwritten by the next holder.
5. Claude hooks are not used for locks. Organization policy blocks them, and `.rules` §1 forbids them for capture. The lock is a command that the session runs, as the rules already do for the journal writer.

## 6. A5: Memory for parallel sessions

Changes: `skills/CROSS_SKILL_INTEGRATION.md` §5.4 (already updated) and `skills/worklog-chat-memory/SKILL.md` 1.4.0.

1. A session that works on one ticket reads `worklog-chat/ticket-resume/<KEY>.md` at start. It reads `RESUME.md` only as an index.
2. `record_turn.py` and the sweep take the memory lock, so parallel sessions do not lose or mix journal and `prompt.log` writes.
3. A busy memory lock ends the record step with exit code 75. Nothing is recorded, and the payload stays for a retry.

## 7. Rules that change

| Rule | Effect for a scoped session |
|---|---|
| R-01 | The mode is the mode of the ticket that the session holds |
| R-02 | A deviation reverts that ticket to PLAN only |
| R-04 | Unchanged; stated again for each ticket |
| R-05 | Intake files need no gate (A2); dashboard writes use the inbox (A3) |
| R-06 | Inbox approval covers ANNOUNCE, PREVIEW and WAIT for external writes |
| R-07 | One open gate per ticket |
| R-09 | Pick up creates the structural sections in RESEARCH without a gate |
| §5.4 | Parallel sessions are supported with the memory lock |

## 8. What does not change

- R-03 (reads), R-08 (credential files are never read for values) and the credential rules.
- The commit handoff rule: agents never run `git add`, `git commit` or `git push`.
- The rule that no document is created without a request.
- The STE100 summary standard with the "Remaining 20%" line.
- The exact-phrase rule for every mode change.

## 9. Put it in force

The owner adds this line to `.rules` §3, after the mode protocol, and to the matching Cursor rule:

`For sessions that start from the ai-worklog-scaleup dashboard or hold a ticket lock, docs/ai-worklog-scaleup-addendum.md applies.`

Until then the addendum is a proposal, and the dashboard works under the existing rules.

## Summary (STE)

This addendum lets many tickets run at the same time under clear rules. Each ticket has its own mode. Pick up can create the local files without a gate. Every external write waits in an inbox until the owner approves it. One process holds a ticket at a time. The memory files are safe for parallel sessions. All other rules stay as they are.

**Remaining 20% (not STE100):** rule numbers, file and command names; the words "lease", "inbox", "gate", "hook" and "handoff"; the table; some sentences over 20 words.

---

Created using Anthropic Claude. Internal only until a person has reviewed and verified it.
