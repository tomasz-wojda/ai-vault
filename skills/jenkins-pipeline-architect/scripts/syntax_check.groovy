import org.codehaus.groovy.control.CompilerConfiguration
import org.codehaus.groovy.control.CompilationUnit
import org.codehaus.groovy.control.Phases

// syntax_check.sh passes its MAX_JDK through AI_VAULT_MAX_JDK and is authoritative.
// The literal below is the fallback for direct invocation, which is how Windows runs
// this script; keep the two in step.
def FALLBACK_MAX_SUPPORTED_JDK = 26
def ceilingFromWrapper = System.getenv('AI_VAULT_MAX_JDK')
def MAX_SUPPORTED_JDK = (ceilingFromWrapper ==~ /\d+/)
    ? ceilingFromWrapper.toInteger()
    : FALLBACK_MAX_SUPPORTED_JDK

// "1.8" means Java 8; anything else leads with its major version.
def jdkVersion = System.getProperty('java.specification.version')
def jdkMajor = jdkVersion.startsWith('1.')
    ? jdkVersion.split('\\.')[1].toInteger()
    : jdkVersion.split('\\.')[0].toInteger()

if (jdkMajor > MAX_SUPPORTED_JDK) {
    println "UNSUPPORTED JDK: running on JDK ${jdkVersion}, requires JDK ${MAX_SUPPORTED_JDK} or lower. Set JAVA_HOME to a supported JDK installation and re-run."
    System.exit(1)
}

def files = []
def argsSupplied = args.length > 0
def allPassed = true

if (argsSupplied) {
    args.each { arg ->
        def f = new File(arg)
        if (f.exists()) {
            files.add(f)
        } else {
            println "${arg}: FILE NOT FOUND"
            allPassed = false
        }
    }
    if (files.isEmpty()) {
        println "\nNo specified files could be read."
        System.exit(1)
    }
} else {
    def dir = new File('.')
    dir.eachFileMatch(~/(Jenkinsfile.*\.groovy|Jenkinsfile)/) { f ->
        files.add(f)
    }
    if (files.isEmpty()) {
        println "No Jenkinsfile or Jenkinsfile*.groovy files found in ${dir.absolutePath}"
        System.exit(0)
    }
    files.sort { it.name }
}

files.each { f ->
    try {
        def config = new CompilerConfiguration()
        def cu = new CompilationUnit(config)
        cu.addSource(f)
        cu.compile(Phases.CONVERSION)
        println "${f.name}: SYNTAX OK"
    } catch (Throwable e) {
        println "${f.name}: ERROR - ${e.message}"
        allPassed = false
    }
}

if (allPassed) {
    println "\nAll files passed syntax check."
} else {
    println "\nSome files have syntax errors."
    System.exit(1)
}
