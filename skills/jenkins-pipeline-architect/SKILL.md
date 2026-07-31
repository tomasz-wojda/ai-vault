---
name: jenkins-pipeline-architect
version: "1.0.0"
description: Use this when creating or editing Jenkinsfiles, defining CI/CD stages, or troubleshooting Groovy-based scripted pipelines.
---

# Jenkins Pipeline Architect
You are an expert in Jenkins Scripted Pipelines and DevSecOps.

## General Rules
- Use scripted pipeline syntax (not declarative)
- Do not add comments to code
- Optimize for build speed and resource management
- Ensure all credentials are handled securely

## Integration with DevOps & JIRA Workflows

This skill serves as the **CI/CD Specialist (Layer 4)** in the `ai-vault` skill stack:

- **Handoff from `devops-daily-protocol`:**  
  When an investigation in `devops-daily-protocol` identifies a Jenkins build failure, this skill provides Groovy CPS diagnostic rules, log analysis guidelines, and syntax validation via `scripts/syntax_check.groovy`.

- **Integration with `jira-worklog-processor`:**  
  Scripted pipeline templates in this skill include automated notification steps (`postJiraComment`) that post CI status updates back to JIRA ticket keys managed by `jira-worklog-processor`.

- **Governance by `developer-protocol`:**  
  Any modification to Jenkinsfiles or shared library Groovy scripts (`vars/*.groovy`) must be planned in `PLAN` mode before code changes are executed in `EXECUTE` mode.

For full interaction details, see the master [Cross-Skill Integration Guide](../CROSS_SKILL_INTEGRATION.md).

## Pipeline Structure
- Always wrap pipeline body in: node { timestamps { stage('...') { } } }
- Prefer fewer stages - consolidate when stages don't provide meaningful separation
- Stage boundaries add overhead; avoid splitting logic across stages unnecessarily
- Use for loops in CPS context; use .each only inside @NonCPS methods
- Pass data between CPS and @NonCPS via serializable types only (String, Map, List, primitives)

## Groovy/CPS Pitfalls

### Underscore Variable Scoping

Error: `The current scope already contains a variable of the name _`

`_` is reserved in Jenkins pipeline scope (used by `@Library` import). Use descriptive names in closures.

Bad:
```groovy
buildResults.count { _, result -> result.result == 'SUCCESS' }
```

Good:
```groovy
buildResults.count { k, result -> result.result == 'SUCCESS' }
```

### Division Returns BigDecimal

Error: `No signature of method ... applicable for argument types: (BigDecimal)` when method expects `long`

Groovy `/` operator returns `BigDecimal` even when both operands are `long`. Use explicit cast.

Bad:
```groovy
def durationSeconds = (endTime.time - startTime.time) / 1000
```

Good:
```groovy
def durationSeconds = (long)((endTime.time - startTime.time) / 1000)
```

### NoSuchMethodError in vars/ Files

Error: `No such DSL method 'methodName' found among steps`

Typed optional parameters in `vars/` file methods break Jenkins method resolution. Remove type declarations and default values.

Bad:
```groovy
def completion(def jclient, String issueKey, Map results, long duration, Map summary = null)
```

Good:
```groovy
def completion(jclient, issueKey, results, duration, summary)
```

## Console Output
- Build multi-line output as a single string, print with one println call
- Never use multiple println/echo calls for multi-line reports (adds [Pipeline] echo noise per line)
- Remove progress echo statements unless specifically needed for debugging
- Use String.format() for column alignment (sprintf is not whitelisted in sandbox)

## Jenkins Sandbox
- @Grab annotations are blocked in sandbox mode - disable sandbox for SDK pipelines
- Some Groovy methods are not whitelisted (e.g. sprintf) - use Java equivalents
- timestamps requires the timestamper plugin installed

## Error Handling Patterns

- Wrap all pipeline stages in a global try-catch
- Always re-throw the exception in catch block: `throw e`
- Use nested try-catch inside catch blocks for critical cleanup (e.g., JIRA status update)
- Never filter exception types — handle all exceptions including `AbortException` (user cancellation)
- Use `validateAndFail` DSL: check condition → post error notification → throw error
- `withRetry` configurable parameters:
  - `maxAttempts` (default 3) — maximum retry attempts
  - `delaySeconds` (default 5) — delay between retries
  - `exponentialBackoff` (default false) — formula: `delay * 2^(attempt-1)`
  - `retryOn` (default `[Exception]`) — exception types to retry on
  - `onRetry` — optional callback receiving `(attempt, exception)`

```groovy
try {
    validateAndFail(jclient, issueKey, !issueData.version, "No version specified")

    stage('Deploy') {
        buildResults = triggerDeployments.sequential(targets, jenkinsInstance)
    }
} catch (Exception e) {
    if (issueKey && jclient) {
        try {
            withRetry(maxAttempts: 2, delaySeconds: 3) {
                jclient.setIssueStatus(issueKey, 'FAIL', null)
            }
        } catch (Exception statusError) {
            echo "Failed to update status: ${statusError.message}"
        }
        postJiraComment.error(jclient, issueKey, e.message, e)
    }
    throw e
}
```

## Extended Pattern Reference

For Active Choices parameters, script approval, properties blocks, environment and
service detection from job names, dynamic credential IDs, parameter validation,
Artifactory queries, JIRA notification steps, deployment execution, JSON config CRUD,
HTTP/curl API patterns, structured logging, AWS SDK usage, filesystem job deployment,
and shell-in-pipeline rules, read
[references/pipeline-patterns.md](references/pipeline-patterns.md).

## Syntax Validation

After every Jenkinsfile creation or edit, run the syntax check before proceeding.

macOS / Linux — use the wrapper, which resolves JDK 17 automatically:
```bash
<skill-dir>/scripts/syntax_check.sh [files...]
```

Windows — invoke the Groovy script directly with `JAVA_HOME` already pointing at JDK 17:
```
groovy <skill-dir>\scripts\syntax_check.groovy [files...]
```

Usage:
- No arguments: auto-discovers `Jenkinsfile` and `Jenkinsfile*.groovy` in the current directory
- With arguments: checks only the specified files; a path that does not resolve is a failure
- Exit code 0: all files pass. Exit code 1: syntax errors, unreadable paths, or an unusable JDK

JDK requirement: 17 or lower. Groovy 3.x cannot read class files from newer JDKs.
The wrapper resolves a JDK 17 in this order: `JAVA_HOME` if already 17 or lower,
then `JAVA_HOME_17`, then `/usr/libexec/java_home -v 17`, then `$JVM_SEARCH_PATH`
(default `/usr/lib/jvm`). If none is found it exits 1 with the required version named.

Failure signature `Unsupported class file major version <N>` means the JDK is too new
for the bundled Groovy. Use the wrapper, or set `JAVA_HOME` to a JDK 17 install.

What the check validates:
- Brace matching (`{` / `}`)
- String literals and GString interpolation
- Groovy grammar (closures, method calls, control flow)

What it cannot validate (requires a running Jenkins):
- Jenkins DSL methods (`node`, `stage`, `bat`, `timestamps`)
- Plugin class imports (`ScriptApproval`)
- Credential IDs, node labels, parameter names

If errors are found, fix them before proceeding. Do not skip this step.
