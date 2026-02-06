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

## Console Output
- Build multi-line output as a single string, print with one println call
- Never use multiple println/echo calls for multi-line reports (adds [Pipeline] echo noise per line)
- Remove progress echo statements unless specifically needed for debugging
- Use String.format() for column alignment (sprintf is not whitelisted in sandbox)

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
