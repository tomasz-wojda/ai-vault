---
name: jenkins-pipeline-architect
description: Use this when creating or editing Jenkinsfiles, defining CI/CD stages, or troubleshooting Groovy-based scripted pipelines.
---

# Jenkins Pipeline Architect
You are an expert in Jenkins Scripted Pipelines and DevSecOps.

## General Rules
- Use scripted pipeline syntax (not declarative)
- Do not add comments to code
- Optimize for build speed and resource management
- Ensure all credentials are handled securely

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

## Structured Logging

- Use structured format: `[LEVEL] message | key1=value1, key2=value2`
- Five levels: DEBUG, INFO, WARNING, ERROR, SUCCESS
- Persistent context via `setContext(Map)` / `addContext(Map)` — persists across calls
- Per-call context via method parameter — merged with persistent context at output time
- Temporary context scope via `withContext(Map, Closure)` — auto-restores after block
- Singleton logger per pipeline via binding variable

```groovy
private void log(String level, String message, Map additionalContext = [:]) {
    def allContext = [:]
    allContext.putAll(this.context)
    allContext.putAll(additionalContext)

    def output = "[${level}] ${message}"
    if (allContext) {
        def contextStr = allContext.collect { k, v -> "${k}=${v}" }.join(', ')
        output += " | ${contextStr}"
    }
    script.println output
}

def withContext(Map temporaryContext, Closure action) {
    def originalContext = new HashMap(this.context)
    try {
        addContext(temporaryContext)
        return action()
    } finally {
        this.context = originalContext
    }
}
```

## AWS SDK Integration
- Use @Grab for dependency management (requires sandbox disabled in job config)
- Use BasicAWSCredentials with AWSStaticCredentialsProvider (ProfileCredentialsProvider fails in containers)
- Always specify .withRegion() explicitly (auto-detection unavailable in containers)
- Wrap all AWS SDK calls in @NonCPS methods to avoid CPS serialization issues
- Shutdown AWS clients after use

## Jenkins Sandbox
- @Grab annotations are blocked in sandbox mode - disable sandbox for SDK pipelines
- Some Groovy methods are not whitelisted (e.g. sprintf) - use Java equivalents
- timestamps requires the timestamper plugin installed

## Performance
- Parse files once and cache results in memory (never re-parse per iteration)
- Keep data in memory as Groovy objects - avoid JSON serialization between stages
- Minimize stage count to reduce context-switch overhead
- AWS SDK outperforms AWS CLI after initial dependency download
- First @Grab run downloads JARs (~180s); subsequent runs use cache

## Job Deployment via Filesystem
- Create job directory under jenkins_home/jobs/<name>/
- Create config.xml with flow-definition plugin type
- XML-escape all Groovy code in config.xml (& < > " ')
- Use jenkins-cli.jar with reload-configuration after filesystem changes
- CSRF crumb is required for HTTP API - prefer jenkins-cli for automation

## Shell in Pipelines
- Process substitution (< <(...)) requires explicit #!/bin/bash shebang
- Jenkins sh step defaults to /bin/sh which lacks bash features
- XML regex escaping: use [[] instead of \[, [[:space:]] instead of \s
- Use set +e for commands that may fail without aborting the pipeline
- Capture shell output with returnStdout: true

## Dynamic Parameters with Active Choices

### DRY_RUN Configuration Reload
When using dynamic parameters (Active Choices, CascadeChoice), add DRY_RUN mode for configuration reload:

```groovy
properties([
    parameters([
        [$class: 'ChoiceParameter',
            choiceType: 'PT_SINGLE_SELECT',
            name: 'ARTIFACT_VERSION',
            script: [
                $class: 'GroovyScript',
                fallbackScript: [...],
                script: [...]
            ]
        ],
        booleanParam(
            name: 'DRY_RUN',
            defaultValue: false,
            description: 'Reloads job\'s configuration from repository. No deployment.'
        )
    ])
])

if (params.DRY_RUN) {
    println """\
    
        DRY_RUN MODE: Configuration Reload Only.
        Job configuration has been reloaded from SCM.
        Parameter definitions are now updated.
        No deployment actions were performed.
        """.stripIndent()
    currentBuild.description = "DRY_RUN: Config reloaded"
    currentBuild.result = 'SUCCESS'
    return
}

node('label') {
}
```

Why this matters:
- Active Choices parameters execute GroovyScript at job configuration time
- Changes to parameter scripts in Jenkinsfile require configuration reload
- DRY_RUN runs before node allocation (no resource consumption)
- User workflow: commit changes → check DRY_RUN → build → refresh page → parameters updated

## Automatic Script Approval

When using Active Choices with GroovyScript, auto-approve pending scripts to prevent manual approval bottleneck:

```groovy
import org.jenkinsci.plugins.scriptsecurity.scripts.ScriptApproval

try {
    def approval = ScriptApproval.get()
    def pendingScripts = approval.getPendingScripts()
    if (pendingScripts.size() > 0) {
        echo "Approving ${pendingScripts.size()} pending script(s)..."
        pendingScripts.each { 
            approval.approveScript(it.hash)
        }
        echo "Script approval completed successfully"
    } else {
        echo "No pending scripts to approve"
    }
} catch (Exception e) {
    echo "Script approval failed: ${e.message}"
}
```

Requirements:
- Import at top of Jenkinsfile
- Execute before DRY_RUN check
- Wrap in try-catch to prevent pipeline failure if approval fails
- Required Jenkins permission: Overall/Administer or Script Security/Approve

## Active Choices Parameter Implementation

### ChoiceParameter (Standalone)
For independent dynamic parameters:

```groovy
[$class: 'ChoiceParameter',
    choiceType: 'PT_SINGLE_SELECT',
    description: 'Select artifact version from Artifactory',
    filterLength: 1,
    filterable: true,
    name: 'ARTIFACT_VERSION',
    script: [
        $class: 'GroovyScript',
        fallbackScript: [
            classpath: [],
            sandbox: true,
            script: 'return ["Not selected", "ERROR: Failed to fetch versions"]'
        ],
        script: [
            classpath: [],
            sandbox: true,
            script: '''
                import groovy.json.JsonSlurper
                
                try {
                    def artifactoryBaseUrl = "https://artifacts.example.com/artifactory"
                    def repoKey = "maven-repo"
                    def groupId = "com.example"
                    def artifactId = "my-artifact"
                    
                    def groupPath = groupId.replace('.', '/')
                    def folderUrl = "${artifactoryBaseUrl}/api/storage/${repoKey}/${groupPath}/${artifactId}"
                    
                    def connection = new URL(folderUrl).openConnection()
                    connection.setRequestProperty("Accept", "application/json")
                    
                    def responseCode = connection.getResponseCode()
                    if (responseCode != 200) {
                        return ["ERROR: HTTP ${responseCode}", "1.0.0"]
                    }
                    
                    def json = new JsonSlurper().parseText(connection.getInputStream().getText())
                    
                    def versions = json.children.findAll { 
                        it.folder == true 
                    }.collect { 
                        it.uri.replaceAll('/', '') 
                    }.findAll { 
                        it ==~ /\\d+\\.\\d+\\.\\d+.*/ 
                    }
                    
                    if (versions.isEmpty()) {
                        return ["Not selected", "No versions found", "1.0.0"]
                    }
                    
                    versions = versions.sort().reverse()
                    
                    return ['Not selected'] + versions
                    
                } catch (Exception e) {
                    return ["ERROR: ${e.message}", "1.0.0"]
                }
            '''
        ]
    ]
]
```

### CascadeChoiceParameter (Dependent on Another Parameter)
For parameters that depend on another parameter's value:

```groovy
choice(
    name: 'SERVICE_NAME',
    choices: ['Service1', 'Service2', 'Service3'],
    description: 'Select the service'
),
[$class: 'CascadeChoiceParameter',
    choiceType: 'PT_SINGLE_SELECT',
    description: 'Select artifact version from Artifactory',
    filterLength: 1,
    filterable: true,
    name: 'ARTIFACT_VERSION',
    referencedParameters: 'SERVICE_NAME',
    script: [
        $class: 'GroovyScript',
        fallbackScript: [
            classpath: [],
            sandbox: true,
            script: 'return ["Not selected", "ERROR: Failed to fetch versions"]'
        ],
        script: [
            classpath: [],
            sandbox: false,
            script: '''
                import groovy.json.JsonSlurper
                
                try {
                    def serviceName = null
                    try {
                        serviceName = SERVICE_NAME
                    } catch (Exception e) {
                        if (binding.hasVariable('SERVICE_NAME')) {
                            serviceName = binding.getVariable('SERVICE_NAME')
                        }
                    }
                    
                    if (serviceName == null || serviceName == '') {
                        return ["Not selected", "ERROR: Please select SERVICE_NAME first"]
                    }
                    
                    def serviceMap = [
                        'Service1': 'artifact1',
                        'Service2': 'artifact2',
                        'Service3': 'artifact3'
                    ]
                    
                    def artifactId = serviceMap[serviceName]
                    if (artifactId == null) {
                        return ["Not selected", "ERROR: Unknown service: ${serviceName}"]
                    }
                    
                } catch (Exception e) {
                    return ["Not selected", "ERROR: ${e.message}"]
                }
            '''
        ]
    ]
]
```

Key differences:
- CascadeChoiceParameter includes referencedParameters field
- Referenced parameter access requires try-catch with binding fallback
- Sandbox mode often needs to be false for parameter access
- Always validate referenced parameter is not null/empty before use

### DynamicReferenceParameter (HTML Output)

For parameters that render raw HTML/CSS/JavaScript in the Jenkins build form:

```groovy
[$class: 'org.biouno.unochoice.DynamicReferenceParameter',
    choiceType: 'ET_FORMATTED_HTML',
    name: 'DISPLAY_PANEL',
    description: 'Dynamic HTML Display',
    referencedParameters: 'CONFIG,APPLICATION,OPERATION',
    script: [
        $class: 'org.biouno.unochoice.model.GroovyScript',
        fallbackScript: [classpath: [], sandbox: false, script: 'return ""'],
        script: [
            classpath: [],
            sandbox: false,
            script: '''
                def config = CONFIG
                def operation = OPERATION
                if (!operation || operation != 'VIEW') { return "" }

                def html = "<div style='padding:10px;'>"
                html += "<input type='hidden' name='value' id='formData'/>"
                html += "</div>"
                return html
            '''
        ]
    ]
]
```

Key differences from ChoiceParameter/CascadeChoiceParameter:
- Class: `org.biouno.unochoice.DynamicReferenceParameter`
- `choiceType: 'ET_FORMATTED_HTML'` renders raw HTML (not a select dropdown)
- Hidden `<input name='value'>` passes data back to `params.DISPLAY_PANEL`
- Return empty string `""` when parameter should not render (conditional display)
- Can contain `<style>`, `<script>`, and full HTML markup

## JavaScript in Active Choice Parameters

- Use `createElement`/`appendChild` instead of `innerHTML` for dynamic DOM elements
- Use IIFE `(function(){...})();` for inline `onclick` handlers
- Use `&quot;` for double quotes inside onclick attribute strings
- Use `String.fromCharCode()` to encode complex selectors and avoid nested quote conflicts
- Use `window.functionName` to expose functions to global scope
- Assign handlers directly: `btn.onclick = function(){}` when using `createElement`
- Use `setInterval(window.collectFormData, 1000)` for continuous form data collection into hidden inputs
- Place `<script>` blocks after the HTML elements they reference
- Use `setTimeout(function(){...}, 100)` in `onchange` handlers to wait for DOM updates

IIFE onclick pattern:
```groovy
def removeCode = "(function(){var e=document.getElementById(&quot;item_${idx}&quot;);if(e)e.remove();})();"
html += "<button onclick='${removeCode}'>Remove</button>"
```

createElement pattern:
```groovy
html += "var btn=document.createElement(&quot;button&quot;);"
html += "btn.onclick=function(){d.remove();};"
html += "d.appendChild(btn);"
```

Data collection with setInterval:
```groovy
html += "window.collectFormData = function() {"
html += "  var data = {};"
html += "  document.getElementById('formData').value = JSON.stringify(data);"
html += "};"
html += "setInterval(window.collectFormData, 1000);"
```

## Environment Detection from Job Names

Extract environment and configuration from job name pattern:

```groovy
def determineEnvironment() {
    def jobName = env.JOB_NAME
    if (jobName.contains('-PROD-')) {
        return 'PROD'
    } else if (jobName.contains('-PREPROD-')) {
        return 'PREPROD'
    } else if (jobName.contains('-TEST-')) {
        return 'TEST'
    } else {
        return 'TEST'
    }
}

def ENVIRONMENT = determineEnvironment()
def NODE_LABEL = "DEPLOY-${ENVIRONMENT}"
```

Job naming convention: Project-Component-ENVIRONMENT-Action
- Example: BNG-Services-CRM2BNG-TEST-Deploy

### Dynamic Configuration Mapping

Use Map structures for service-to-configuration mapping:

```groovy
def mapServiceToArtifactId(serviceName) {
    def serviceMap = [
        'Service1': 'artifact-id-1',
        'Service2': 'artifact-id-2',
        'Service3': 'artifact-id-3'
    ]
    def artifactId = serviceMap[serviceName]
    if (!artifactId) {
        error("Unknown service name: ${serviceName}")
    }
    return artifactId
}

def mapServiceToConfig(serviceName, environment) {
    def configMap = [
        'TEST': [
            'Service1': 'config-test-1',
            'Service2': 'config-test-2'
        ],
        'PROD': [
            'Service1': 'config-prod-1',
            'Service2': 'config-prod-2'
        ]
    ]
    def config = configMap.get(environment)?.get(serviceName)
    if (!config) {
        error("Unknown service/environment combination: ${serviceName}/${environment}")
    }
    return config
}
```

Benefits:
- Single generic pipeline handles multiple services
- Centralized mapping maintenance
- Type-safe lookups with error handling

## Dynamic Credential ID Patterns

Build credential IDs based on environment:

```groovy
def ENVIRONMENT = determineEnvironment()

def DB_CREDS_ID = "APP-DB-${ENVIRONMENT}-DB-CREDS"
def API_KEY_ID = "APP-API-${ENVIRONMENT}-API-KEY"
def NET_USER_CREDS_ID = "APP-EXE-${ENVIRONMENT}-NET-USER-CREDS"

withCredentials([
    usernamePassword(credentialsId: DB_CREDS_ID, 
                     usernameVariable: 'DB_USER', 
                     passwordVariable: 'DB_PASS'),
    string(credentialsId: API_KEY_ID, variable: 'API_KEY')
]) {
}
```

Pattern: {APP}-{COMPONENT}-{ENVIRONMENT}-{TYPE}

Examples:
- BNG-DB-TEST-DB-CREDS
- BNG-EXE-PROD-NET-USER-CREDS
- BNG-API-PREPROD-API-KEY

Static credentials (all environments):
- JIRA-ARTIFACTORY_TOKEN (shared across all jobs)

## Multi-line Console Output Best Practices

Use println with triple-quoted strings instead of multiple echo calls:

Bad (adds [Pipeline] echo noise per line):
```groovy
echo "DRY_RUN MODE: Configuration Reload Only"
echo "Job configuration has been reloaded from SCM"
echo "Parameter definitions are now updated"
echo "No deployment actions were performed"
```

Good (single output block):
```groovy
println """\

    DRY_RUN MODE: Configuration Reload Only.
    Job configuration has been reloaded from SCM.
    Parameter definitions are now updated.
    No deployment actions were performed.
    """.stripIndent()
```

Benefits:
- Cleaner console output (no [Pipeline] echo markers)
- Better readability in Jenkins Blue Ocean
- Easier to format complex multi-line messages
- stripIndent() removes leading whitespace from indented strings

## Parameter Validation

Always validate user-selected parameters before pipeline execution:

```groovy
def ARTIFACT_VERSION = params.ARTIFACT_VERSION

if (ARTIFACT_VERSION == 'Not selected') {
    error("Pipeline aborted: No artifact version selected. Please select a version from the dropdown and try again.")
}

if (!ARTIFACT_VERSION || ARTIFACT_VERSION.trim() == '') {
    error("Pipeline aborted: ARTIFACT_VERSION parameter is required")
}
```

For Active Choices parameters:
- Always include "Not selected" as first option
- Fail fast if user didn't make selection
- Provide clear error message directing user to correct action

## Properties Block Pattern

Complete properties block structure for pipelines with dynamic parameters:

```groovy
import org.jenkinsci.plugins.scriptsecurity.scripts.ScriptApproval

properties([
    parameters([
        [$class: 'ChoiceParameter',
            choiceType: 'PT_SINGLE_SELECT',
            description: 'Select artifact version from Artifactory',
            filterLength: 1,
            filterable: true,
            name: 'ARTIFACT_VERSION',
            script: [
                $class: 'GroovyScript',
                fallbackScript: [...],
                script: [...]
            ]
        ],
        booleanParam(
            name: 'DRY_RUN',
            defaultValue: false,
            description: 'Reloads job\'s configuration from repository. No deployment.'
        )
    ])
])

def determineEnvironment() {
    def jobName = env.JOB_NAME
    if (jobName.contains('-PROD-')) {
        return 'PROD'
    } else if (jobName.contains('-PREPROD-')) {
        return 'PREPROD'
    } else if (jobName.contains('-TEST-')) {
        return 'TEST'
    } else {
        return 'TEST'
    }
}

def ENVIRONMENT = determineEnvironment()
def NODE_LABEL = "DEPLOY-${ENVIRONMENT}"

try {
    def approval = ScriptApproval.get()
    def pendingScripts = approval.getPendingScripts()
    if (pendingScripts.size() > 0) {
        echo "Approving ${pendingScripts.size()} pending script(s)..."
        pendingScripts.each { 
            approval.approveScript(it.hash)
        }
        echo "Script approval completed successfully"
    } else {
        echo "No pending scripts to approve"
    }
} catch (Exception e) {
    echo "Script approval failed: ${e.message}"
}

if (params.DRY_RUN) {
    println """\
    
        DRY_RUN MODE: Configuration Reload Only.
        Job configuration has been reloaded from SCM.
        Parameter definitions are now updated.
        No deployment actions were performed.
        """.stripIndent()
    currentBuild.description = "DRY_RUN: Config reloaded"
    currentBuild.result = 'SUCCESS'
    return
}

node(NODE_LABEL) {
    def ARTIFACT_VERSION = params.ARTIFACT_VERSION
    
    if (ARTIFACT_VERSION == 'Not selected') {
        error("Pipeline aborted: No artifact version selected. Please select a version from the dropdown and try again.")
    }
}
```

Execution order (critical):
1. Import statements
2. properties() block with parameters
3. Helper functions (determineEnvironment, etc.)
4. Global variable assignments (ENVIRONMENT, NODE_LABEL)
5. Script approval automation
6. DRY_RUN check (before node allocation)
7. node() block with pipeline stages

## Generic Pipeline Pattern

Pattern for single pipeline handling multiple services/configurations:

```groovy
def determineService() {
    def jobName = env.JOB_NAME
    def pattern = ~/Project-Component-(.+?)-(TEST|PREPROD|PROD)-Deploy/
    def matcher = jobName =~ pattern
    
    if (matcher.find()) {
        def serviceName = matcher.group(1)
        def validServices = ['Service1', 'Service2', 'Service3']
        
        if (validServices.contains(serviceName)) {
            return serviceName
        } else {
            error("Invalid service name extracted from job name: ${serviceName}")
        }
    } else {
        error("Unable to extract service name from job name: ${jobName}")
    }
}

def ENVIRONMENT = determineEnvironment()
def SERVICE_NAME = determineService()
def ARTIFACT_ID = mapServiceToArtifactId(SERVICE_NAME)
def CONFIG_VALUE = mapServiceToConfig(SERVICE_NAME, ENVIRONMENT)

node("DEPLOY-${ENVIRONMENT}") {
    echo "Deploying ${SERVICE_NAME} to ${ENVIRONMENT}"
    echo "Using artifact: ${ARTIFACT_ID}"
    echo "Configuration: ${CONFIG_VALUE}"
}
```

Benefits:
- Single Jenkinsfile for N services
- Job naming convention enforces structure
- Regex extraction with validation
- Fail fast on invalid job names

## Artifactory Integration

Pattern for querying Artifactory Storage API:

```groovy
script: '''
    import groovy.json.JsonSlurper
    
    try {
        def artifactoryBaseUrl = "https://artifacts.example.com/artifactory"
        def repoKey = "maven-repo"
        def groupId = "com.example"
        def artifactId = "my-artifact"
        
        def groupPath = groupId.replace('.', '/')
        def folderUrl = "${artifactoryBaseUrl}/api/storage/${repoKey}/${groupPath}/${artifactId}"
        
        def connection = new URL(folderUrl).openConnection()
        connection.setRequestProperty("Accept", "application/json")
        
        def responseCode = connection.getResponseCode()
        if (responseCode != 200) {
            return ["ERROR: HTTP ${responseCode}", "1.0.0"]
        }
        
        def json = new JsonSlurper().parseText(connection.getInputStream().getText())
        
        def versions = json.children.findAll { 
            it.folder == true 
        }.collect { 
            it.uri.replaceAll('/', '') 
        }.findAll { 
            it ==~ /\\d+\\.\\d+\\.\\d+.*/ 
        }
        
        if (versions.isEmpty()) {
            return ["Not selected", "No versions found", "1.0.0"]
        }
        
        versions = versions.sort().reverse()
        
        return ['Not selected'] + versions
        
    } catch (Exception e) {
        return ["ERROR: ${e.message}", "1.0.0"]
    }
'''
```

Key points:
- Use Artifactory Storage API (not Search API)
- URL pattern: /api/storage/{repo}/{groupPath}/{artifactId}
- Filter versions with regex: \\d+\\.\\d+\\.\\d+.* (matches 1.0.0, 1.0.0-SNAPSHOT, etc.)
- Sort reverse for latest-first display
- Always return array with "Not selected" as first element
- Comprehensive error handling with fallback values

Authentication (if required):
```groovy
connection.setRequestProperty("Authorization", "Bearer ${ARTIFACTORY_TOKEN}")
```

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

## JIRA Notification Patterns

- Four notification types: `start()`, `completion()`, `error()`, `artifact()`
- Post start notification before deployment trigger (shows intent, not result)
- Post completion notification with build results map and duration
- Post error notification in catch block — always post regardless of exception type
- Post artifact notification per-component after downloading build artifacts
- Wrap JIRA status updates in `withRetry` (API can be flaky)
- Set JIRA status to SUCCESS with resolution or FAIL without resolution

```groovy
postJiraComment.start(jclient, issueKey, application, deploymentTargets)

buildResults = application.sequential_deployment ?
    triggerDeployments.sequential(targets, jenkinsInstance) :
    triggerDeployments.parallel(targets, jenkinsInstance)

def failedBuilds = buildResults.findAll { k, result -> result.result != 'SUCCESS' }
def status = failedBuilds.isEmpty() ? 'SUCCESS' : 'FAIL'
def resolution = failedBuilds.isEmpty() ? 'Done' : null

withRetry(maxAttempts: 2, delaySeconds: 3) {
    jclient.setIssueStatus(issueKey, status, resolution)
}

postJiraComment.completion(jclient, issueKey, buildResults, endTime, durationSeconds, artifactSummaries)
```

## Deployment Execution

- Use `propagate: false` on triggered builds for independent failure handling
- Set `wait: true` to collect build results
- Always set timeout: `timeout: [time: 120, unit: 'MINUTES']`
- Choose sequential or parallel based on application config flag
- For artifact download: `curl -s -f -k -u` with `withCredentials`
- `-k` bypasses SSL certificate issues, `-u` provides Jenkins authentication
- URL pattern: `buildUrl + "artifact/" + artifactFilename`
- Return null on download failure (graceful degradation)

Build trigger:
```groovy
def result = build(
    job: jobName,
    parameters: buildParams,
    propagate: false,
    wait: true,
    timeout: [time: 120, unit: 'MINUTES']
)
```

Artifact download:
```groovy
def artifactUrl = "${buildUrl}artifact/${artifactFilename}"
withCredentials([usernamePassword(credentialsId: credId, usernameVariable: 'JENKINS_USER', passwordVariable: 'JENKINS_TOKEN')]) {
    content = sh(script: "curl -s -f -k -u \${JENKINS_USER}:\${JENKINS_TOKEN} '${artifactUrl}'", returnStdout: true).trim()
}
```

## JSON Configuration CRUD via Pipeline

- Use Active Choice parameters to load and display JSON configuration in build form
- Four operations: VIEW (read-only display), MODIFY (editable form), ADD (new entries), DELETE (removal)
- Parse JSON once in parameter script, pass as hidden input to pipeline
- For MODIFY: use `setInterval` to continuously collect form data into hidden input
- Save results with `writeFile` + `archiveArtifacts` (manual git commit step)
- Use `readJSON text:` to parse parameter values in pipeline stages
- Auto-increment IDs: `json.applications.collect { it.id }.max() + 1`
- Always validate operation parameter before processing

```groovy
def jsonText = params.CONFIG
def json = readJSON text: jsonText

if (operation == 'DELETE') {
    def appIndex = json.applications.findIndexOf { it.id == appId }
    json.applications.remove(appIndex)
}

def updatedJson = groovy.json.JsonOutput.prettyPrint(groovy.json.JsonOutput.toJson(json))
writeFile file: 'ApplicationMap_updated.json', text: updatedJson
archiveArtifacts artifacts: 'ApplicationMap_updated.json', fingerprint: true
```

## Boolean Parameter Filtering

- When all component parameters have `valuetype == 'boolean'`, check if any value is true
- Skip components where all boolean values are false (nothing to deploy)
- Use `return` to skip inside closures (not `continue`)
- Case-insensitive comparison: `value.toLowerCase() == 'true'`

```groovy
def allBoolean = parameterKeys.every { paramKey ->
    envConfig.parameters[paramKey].valuetype == 'boolean'
}

if (allBoolean) {
    def anyTrue = manifestValues.any { value ->
        value.toLowerCase() == 'true'
    }
    if (!anyTrue) {
        return
    }
}
```

## HTTP API Patterns

### Standardized Response Map

All API methods return a consistent response structure:

```groovy
[
    success: true,
    code: 200,
    data: responseData,
    message: "Request successful"
]
```

### curl-based API Calls

- Use curl with `-s` (silent), `-f` (fail on HTTP errors), `-k` (ignore SSL), `-w "\\n%{http_code}"` (append status code)
- Set `--connect-timeout 10` and `--max-time 30`
- Parse response: body on all lines except last, HTTP code on last line
- Switch on HTTP codes: 200/201/204 success, 401 auth failed, 403 forbidden, 404 not found, 5xx server error
- Bearer token: `-H "Authorization: Bearer ${token}"`

```groovy
def curlCmd = [
    "curl", "-s", "-w", "\\n%{http_code}",
    "-X", method,
    "-H", "Content-Type: application/json",
    "-H", "Authorization: Bearer ${token}",
    "--connect-timeout", "10",
    "--max-time", "30"
]
if (data) { curlCmd.addAll(["-d", JsonOutput.toJson(data)]) }
curlCmd.add(url)

def process = curlCmd.execute()
def output = process.text
def exitCode = process.waitFor()
```

### CLI/Process-based API Calls

- Use `['bash', '-c', cmd].execute()` for CLI tools (e.g., `gh api`)
- `consumeProcessOutput(stdout, stderr)` for non-blocking output capture
- `waitForOrKill(timeout)` kills process if it exceeds timeout
- Use `set -o pipefail` in shell scripts for pipeline error propagation
- Extract HTTP code from stderr, body from stdout
- Fallback HTTP code detection from error strings ("Not Found" → 404, "Unauthorized" → 401)
- All Process/IO methods must be `@NonCPS`

```groovy
def process = ['bash', '-c', cmd].execute()
def stdout = new StringBuilder()
def stderr = new StringBuilder()
process.consumeProcessOutput(stdout, stderr)

process.waitForOrKill(30000)
def exitCode = process.exitValue()
def httpCode = stderr.toString().trim().isNumber() ? stderr.toString().trim().toInteger() : 500
def isSuccess = (httpCode >= 200 && httpCode < 300)
```

### Async Polling with Timeout

- Use `while (System.currentTimeMillis() < timeoutTimestamp)` loop
- Track state changes with timestamps for observability
- Return 408 (Request Timeout) on timeout
- Sleep interval between polls
- Trigger-then-detect: snapshot existing IDs → trigger action → sleep → query → diff to find new entry

```groovy
def startTime = System.currentTimeMillis()
def timeoutMs = timeoutMinutes * 60 * 1000
def timeoutTimestamp = startTime + timeoutMs

while (System.currentTimeMillis() < timeoutTimestamp) {
    def result = checkStatus(resourceId)
    if (result.data.status == "completed") {
        def duration = (System.currentTimeMillis() - startTime) / 1000
        return _buildResponse(true, 200, result.data, "Completed in ${duration}s")
    }
    sleep(pollIntervalSeconds * 1000)
}

return _buildResponse(false, 408, null, "Timed out after ${timeoutMinutes} minutes")
```
