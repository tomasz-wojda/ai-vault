#!/usr/bin/env bash
set -u

MAX_JDK=17
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
GROOVY_SCRIPT="${SCRIPT_DIR}/syntax_check.groovy"
JVM_SEARCH_PATH="${JVM_SEARCH_PATH:-/usr/lib/jvm}"

java_major() {
    local home="$1"
    [ -x "${home}/bin/java" ] || return 1
    local raw
    raw="$("${home}/bin/java" -version 2>&1 | head -1 | sed -n 's/.*version "\([^"]*\)".*/\1/p')"
    [ -n "${raw}" ] || return 1
    case "${raw}" in
        1.*) printf '%s\n' "${raw}" | cut -d. -f2 ;;
        *)   printf '%s\n' "${raw}" | cut -d. -f1 ;;
    esac
}

resolve_jdk() {
    if [ -n "${JAVA_HOME_17:-}" ]; then
        local m
        m="$(java_major "${JAVA_HOME_17}")" && [ "${m}" -le "${MAX_JDK}" ] 2>/dev/null && {
            printf '%s\n' "${JAVA_HOME_17}"; return 0; }
    fi
    if [ -x /usr/libexec/java_home ]; then
        local mac
        mac="$(/usr/libexec/java_home -v "${MAX_JDK}" 2>/dev/null)" && [ -n "${mac}" ] && {
            printf '%s\n' "${mac}"; return 0; }
    fi
    local candidate
    for candidate in "${JVM_SEARCH_PATH}"/java-"${MAX_JDK}"-* "${JVM_SEARCH_PATH}"/jdk-"${MAX_JDK}"*; do
        [ -d "${candidate}" ] || continue
        local m
        m="$(java_major "${candidate}")" || continue
        [ "${m}" -le "${MAX_JDK}" ] 2>/dev/null && { printf '%s\n' "${candidate}"; return 0; }
    done
    return 1
}

if ! command -v groovy >/dev/null 2>&1; then
    echo "groovy not found on PATH. Install Groovy 3.x and re-run."
    exit 1
fi

if [ ! -f "${GROOVY_SCRIPT}" ]; then
    echo "syntax_check.groovy not found at ${GROOVY_SCRIPT}."
    exit 1
fi

SELECTED=""
if [ -n "${JAVA_HOME:-}" ]; then
    CURRENT_MAJOR="$(java_major "${JAVA_HOME}")" || CURRENT_MAJOR=""
    if [ -n "${CURRENT_MAJOR}" ] && [ "${CURRENT_MAJOR}" -le "${MAX_JDK}" ] 2>/dev/null; then
        SELECTED="${JAVA_HOME}"
    fi
fi

if [ -z "${SELECTED}" ]; then
    SELECTED="$(resolve_jdk)" || {
        echo "JDK ${MAX_JDK} or lower is required (Groovy 3.x cannot read newer class files). Install it and set JAVA_HOME, e.g. macOS: JAVA_HOME=\$(/usr/libexec/java_home -v ${MAX_JDK}); Linux: JAVA_HOME=${JVM_SEARCH_PATH}/java-${MAX_JDK}-openjdk; Windows: set JAVA_HOME to the JDK ${MAX_JDK} install path."
        exit 1
    }
fi

export JAVA_HOME="${SELECTED}"
exec groovy "${GROOVY_SCRIPT}" "$@"
