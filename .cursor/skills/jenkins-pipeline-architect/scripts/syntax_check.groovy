import org.codehaus.groovy.control.CompilerConfiguration
import org.codehaus.groovy.control.CompilationUnit
import org.codehaus.groovy.control.Phases

def files = []

if (args.length > 0) {
    args.each { arg ->
        def f = new File(arg)
        if (f.exists()) {
            files.add(f)
        } else {
            println "${arg}: FILE NOT FOUND"
        }
    }
} else {
    def dir = new File('.')
    dir.eachFileMatch(~/Jenkinsfile.*\.groovy/) { f ->
        files.add(f)
    }
    if (files.isEmpty()) {
        println "No Jenkinsfile*.groovy files found in ${dir.absolutePath}"
        System.exit(0)
    }
    files.sort { it.name }
}

def allPassed = true

files.each { f ->
    try {
        def config = new CompilerConfiguration()
        def cu = new CompilationUnit(config)
        cu.addSource(f)
        cu.compile(Phases.CONVERSION)
        println "${f.name}: SYNTAX OK"
    } catch (Exception e) {
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
