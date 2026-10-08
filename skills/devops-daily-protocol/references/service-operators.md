# Service Operators

Command reference for the `ai-worklog service` operators used by
[devops-daily-protocol](../SKILL.md). For the exact positionals, options, and
validation of any action, run `ai-worklog help --json service <name> <action>`.

## JIRA CLI
**Path**: `ai-worklog service jira`

| Mode | Command | Purpose |
|------|---------|---------|
| summary | `ai-worklog service jira summary` | Board overview: in-progress, blocked, to-do, recently completed |
| ticket | `ai-worklog service jira ticket <KEY>` | Full ticket detail: fields, description, comments, links, worklogs, assignment |
| rejected | `ai-worklog service jira rejected` | List rejected (Odrzucone) tickets |
| reporter | `ai-worklog service jira reporter <DISPLAY-NAME>` | Tickets created by one reporter |
| tempo | `ai-worklog service jira tempo [YYYY-MM-DD]` | Daily Tempo timesheet entries (defaults to today) |
| verify | `ai-worklog service jira verify [YYYY-MM-DD]` | Compare local worklog/ files against Tempo entries |
| whoami | `ai-worklog service jira whoami` | Validate Jira identity and authentication |
| log-time | `ai-worklog service jira log-time <KEY> <DATE> <SECONDS> <COMMENT>` | Preview or apply a Tempo worklog |
| assets-schemas | `ai-worklog service jira assets-schemas` | Jira Assets (Insight) object schemas |
| assets-types | `ai-worklog service jira assets-types <SCHEMA_ID>` | Object types in one schema |
| assets-attributes | `ai-worklog service jira assets-attributes <TYPE_ID>` | Attribute definitions of one object type |
| assets-object | `ai-worklog service jira assets-object <OBJECT-KEY>` | One Assets object with all attribute values |
| assets-search | `ai-worklog service jira assets-search "<IQL>" [--limit N]` | Bounded IQL search over Assets objects |
| get-ci | `ai-worklog service jira get-ci <CI-KEY>` | One application CI (`A.A.<ENV>.<App>`) with Artifactory path, automation flag, pipeline URL, status |
| get-cis | `ai-worklog service jira get-cis [--env ENV] [--limit N]` | All application CIs: key, id, and name |

All Jira and Assets actions are read-only except `log-time`, which is dry-run
until Write Gate approval adds `--apply`. Assets reads are GET-only. `assets-object`
and `assets-search` return every attribute, including owner and user fields;
`get-ci` returns only the mapped CI fields.

## New Relic Operator
**Path**: `ai-worklog service newrelic`

**Credentials**: `integrations/newrelic/newrelic.properties` with profile-scoped
keys. Existing `PROFILE.newrelic.*`, canonical `PROFILE.api_key` /
`PROFILE.account_id`, and legacy unprefixed keys remain
compatible. Select a profile with `--profile` or `NEW_RELIC_PROFILE`.

| Action | Command | Purpose |
|------|---------|---------|
| profiles | `ai-worklog service newrelic profiles` | List configured profiles without exposing key values |
| auth-test | `ai-worklog service newrelic auth-test` | Validate API key and account |
| applications | `ai-worklog service newrelic applications [--query TEXT]` | APM application inventory |
| application | `ai-worklog service newrelic application <APP_ID>` | Single application detail |
| hosts | `ai-worklog service newrelic hosts <APP_ID>` | Hosts for an application |
| deployments | `ai-worklog service newrelic deployments <APP_ID>` | Deployment history for an application |
| violations | `ai-worklog service newrelic violations` | Legacy open alert violations |
| issues | `ai-worklog service newrelic issues [--state STATE]` | NerdGraph AI issues |
| alert-conditions | `ai-worklog service newrelic alert-conditions [--policy ID] [--query TEXT]` | Alert condition inventory |
| nrql | `ai-worklog service newrelic nrql "<QUERY>"` or `--file PATH` | Arbitrary NRQL through NerdGraph |
| entities | `ai-worklog service newrelic entities [--query TEXT] [--domain D] [--type T]` | Entity search with cursor pagination |
| dashboards | `ai-worklog service newrelic dashboards [--query TEXT] [--owner O]` | Dashboard inventory |
| dashboard | `ai-worklog service newrelic dashboard <DASHBOARD-GUID>` | Dashboard metadata, pages, widgets, configuration |
| alert-policies | `ai-worklog service newrelic alert-policies [--query TEXT]` | Alert policy inventory |
| alert-policy | `ai-worklog service newrelic alert-policy <POLICY_ID>` | One alert policy and its linked conditions |
| alert-condition | `ai-worklog service newrelic alert-condition <CONDITION_ID>` | One alert condition with signal, terms, metadata |
| alert-condition-create | `ai-worklog service newrelic alert-condition-create <POLICY_ID> <FILE> --confirm-policy ID` | Write Gate: create a static NRQL condition (`--apply`) |
| alert-condition-update | `ai-worklog service newrelic alert-condition-update <CONDITION_ID> <FILE> --confirm-name NAME` | Write Gate: update a static NRQL condition (`--apply`) |
| dashboard-create | `ai-worklog service newrelic dashboard-create <FILE> --confirm-account ID` | Write Gate: create a dashboard (`--apply`) |
| dashboard-page-create | `ai-worklog service newrelic dashboard-page-create <DASHBOARD-GUID> <FILE> --confirm-dashboard NAME` | Write Gate: add a dashboard page (`--apply`) |
| dashboard-page-update | `ai-worklog service newrelic dashboard-page-update <PAGE-GUID> <FILE> --confirm-name NAME` | Write Gate: update a dashboard page (`--apply`) |
| dashboard-widget-create | `ai-worklog service newrelic dashboard-widget-create <DASHBOARD-GUID> <PAGE-GUID> <FILE> --confirm-dashboard NAME` | Write Gate: add a widget (`--apply`) |
| dashboard-widget-update | `ai-worklog service newrelic dashboard-widget-update <WIDGET-GUID> <FILE> --confirm-name NAME` | Write Gate: update a widget (`--apply`) |

Nineteen read actions are always allowed under RESEARCH. Eight actions accept
`--apply` and are dry-run without it — the seven create/update mutations plus
`dashboard-export`, which writes to the workspace — and each requires Write Gate
approval. Delete operations and host-side infra mutations are outside this
operator.

## Automox Operator
**Path**: `ai-worklog service automox`

**Credentials**: `integrations/automox/automox.properties` with profile-scoped
keys, alongside `token` and `server-id`. Select a profile with `--profile`.

| Action | Command | Purpose |
|------|---------|---------|
| profiles | `ai-worklog service automox profiles` | List configured profiles without exposing key values |
| auth-test | `ai-worklog service automox auth-test` | Validate the API token |
| orgs | `ai-worklog service automox orgs` | Accessible organizations |
| groups | `ai-worklog service automox groups [--query TEXT]` | Server group inventory |
| devices | `ai-worklog service automox devices [--group ID]` | Device inventory with group, name, connection filters |
| device | `ai-worklog service automox device <ID-or-HOSTNAME>` | Single device detail |
| device-packages | `ai-worklog service automox device-packages <ID>` | Packages on one device, filterable by state |
| activity | `ai-worklog service automox activity` | Events within a date range |
| patch-summary | `ai-worklog service automox patch-summary` | Patch activity summary for a date range |
| policies | `ai-worklog service automox policies [--query TEXT]` | Policy inventory |
| policy-stats | `ai-worklog service automox policy-stats` | Policy execution statistics |
| device-queue | `ai-worklog service automox device-queue <ID>` | Command queue for one device |

Fourteen read actions are always allowed under RESEARCH. Five actions accept
`--apply` and are dry-run without it — `policy-run`, `worklet-create`,
`policy-delete`, `device-move` and `policy-add-group` — and each requires Write
Gate approval. `policy-delete` additionally requires `--confirm-name` to match.

## Jenkins Operator
**Path**: `ai-worklog service jenkins`

**Credentials**: `integrations/jenkins/jenkins.properties` or `credentials`.
Controllers are named in configuration; `controllers` lists them without
exposing secrets.

| Group | Actions | Purpose |
|-------|---------|---------|
| Controller | `controllers`, `health`, `whoami`, `nodes`, `queue` | Controller inventory, operating mode, authenticated identity, executor and queue state |
| Jobs | `jobs`, `job`, `seed`, `views` | Job listing and filtering, one job's status and recent builds, seed-job result, views |
| Builds | `artifacts`, `download-artifact`, `job-export` | Artifacts of a selected build; download one by exact relative path; export a job's `config.xml` |
| Config | `plugins`, `credentials`, `credential-domains` | Installed plugins and required-plugin verification, credential metadata, credential domains |
| Validation | `syntax-check <files...>` | Validate scripted Jenkinsfiles |
| Script | `run-script` | Run Groovy in the Script Console from a file, stdin (`-`) or `--script` |

Fourteen read actions are always allowed under RESEARCH. `download-artifact`,
`job-export` and `run-script` are dry-run without `--apply` and need Write Gate
approval; `run-script` runs with full controller privileges, only where
`jenkins.properties` sets `<id>.run_scripts=true`. `credentials` and
`credential-domains` return metadata only — never secret values.

`syntax-check` is not a second implementation. The framework resolves and runs
this repo's own `skills/jenkins-pipeline-architect/scripts/syntax_check.sh`,
preferring a configured `syntax_check_script`, then `ai_vault_root`, then a
resolved vault root. It reports BLOCKED when that script cannot be found. Either
entry point therefore applies the same grammar check and the same `MAX_JDK`
ceiling; use whichever is at hand and satisfy R-16 once.
