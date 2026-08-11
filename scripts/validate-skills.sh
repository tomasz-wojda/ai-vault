#!/usr/bin/env bash
set -u

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "${REPO_ROOT}" || exit 1

MAX_DESCRIPTION=1024
MAX_SKILL_LINES=500
PATH_ALLOWLIST="skills/jenkins-pipeline-architect/scripts/syntax_check.sh"
SELF_PATH="scripts/validate-skills.sh"
LABEL_WIDTH=17
CHECK_COUNT=7

FAILURES=0
USE_COLOR=0
if [ -t 1 ] && [ -z "${NO_COLOR:-}" ] && [ "${TERM:-}" != "dumb" ]; then
    USE_COLOR=1
fi

if [ "${USE_COLOR}" -eq 1 ]; then
    C_GREEN=$'\033[32m'
    C_RED=$'\033[31m'
    C_DIM=$'\033[2m'
    C_RESET=$'\033[0m'
else
    C_GREEN=''
    C_RED=''
    C_DIM=''
    C_RESET=''
fi

REPORT_DIR="$(mktemp -d "${TMPDIR:-/tmp}/validate-skills.XXXXXX")"
trap 'rm -rf "${REPORT_DIR}"' EXIT

for section in metadata links fences leakage paths sizes manifest; do
    : > "${REPORT_DIR}/${section}"
done

add_finding() {
    printf '%s\n' "$2" >> "${REPORT_DIR}/$1"
    FAILURES=$((FAILURES + 1))
}

section_count() {
    wc -l < "${REPORT_DIR}/$1" | tr -d ' '
}

tracked_md() {
    git ls-files --cached --others --exclude-standard '*.md' 2>/dev/null \
        || find . -name '*.md' -not -path './.git/*'
}

repo_grep() {
    git grep --untracked -nE "$1" -- . 2>/dev/null
}

frontmatter() {
    awk 'NR==1 && $0=="---" { inside=1; next } inside && $0=="---" { exit } inside { print }' "$1"
}

yaml_parser() {
    if python3 -c 'import yaml' >/dev/null 2>&1; then
        echo python
    elif command -v ruby >/dev/null 2>&1; then
        echo ruby
    else
        echo none
    fi
}

yaml_valid() {
    case "$(yaml_parser)" in
        python) frontmatter "$1" | python3 -c 'import sys,yaml; yaml.safe_load(sys.stdin.read())' 2>&1 ;;
        ruby)   frontmatter "$1" | ruby -ryaml -e 'YAML.safe_load(STDIN.read)' 2>&1 ;;
        none)   return 0 ;;
    esac
}

fm_value() {
    frontmatter "$1" | awk -v key="$2" '
        $0 ~ "^"key":" {
            sub("^"key":[ ]*", "")
            gsub(/^"|"$/, "")
            print
            exit
        }'
}

SKILL_COUNT=0
for skill in skills/*/SKILL.md; do
    [ -f "${skill}" ] || continue
    SKILL_COUNT=$((SKILL_COUNT + 1))

    dir="$(basename "$(dirname "${skill}")")"

    if [ "$(head -1 "${skill}")" != "---" ] || ! frontmatter "${skill}" | grep -q .; then
        add_finding metadata "${skill}:1 missing YAML frontmatter"
        continue
    fi

    yaml_err="$(yaml_valid "${skill}")"
    if [ -n "${yaml_err}" ]; then
        add_finding metadata "${skill}:1 frontmatter is not valid YAML: $(printf '%s' "${yaml_err}" | tr '\n' ' ' | cut -c1-140)"
        continue
    fi

    name="$(fm_value "${skill}" name)"
    if [ "${name}" != "${dir}" ]; then
        add_finding metadata "${skill}:2 frontmatter name '${name}' does not match directory '${dir}'"
    fi

    desc="$(frontmatter "${skill}" | awk '/^description:/{f=1} f && !/^(name|version):/{print}' | tr '\n' ' ')"
    desc_len=${#desc}
    if [ "${desc_len}" -eq 0 ]; then
        add_finding metadata "${skill}:2 frontmatter description missing"
    elif [ "${desc_len}" -gt "${MAX_DESCRIPTION}" ]; then
        add_finding metadata "${skill}:2 description is ${desc_len} chars, limit ${MAX_DESCRIPTION}"
    fi

    version="$(fm_value "${skill}" version)"
    if ! printf '%s' "${version}" | grep -Eq '^[0-9]+\.[0-9]+\.[0-9]+$'; then
        add_finding metadata "${skill}:2 frontmatter version '${version}' is not MAJOR.MINOR.PATCH"
    fi
done

while IFS= read -r file; do
    [ -f "${file}" ] || continue
    dir="$(dirname "${file}")"
    grep -noE '\]\([^)]+\)' "${file}" | while IFS=: read -r lno link; do
        target="${link#](}"
        target="${target%)}"
        target="${target%%#*}"
        case "${target}" in
            http*|mailto:*|'') continue ;;
        esac
        if [ ! -e "${dir}/${target}" ]; then
            printf '%s\n' "${file}:${lno} broken link -> ${target}"
        fi
    done
done < <(tracked_md) > "${REPORT_DIR}/links.tmp" 2>/dev/null
if [ -s "${REPORT_DIR}/links.tmp" ]; then
    cat "${REPORT_DIR}/links.tmp" >> "${REPORT_DIR}/links"
    LINK_FAILS="$(wc -l < "${REPORT_DIR}/links.tmp" | tr -d ' ')"
    FAILURES=$((FAILURES + LINK_FAILS))
fi
rm -f "${REPORT_DIR}/links.tmp"

while IFS= read -r file; do
    [ -f "${file}" ] || continue
    count="$(grep -c '^```' "${file}")"
    if [ $((count % 2)) -ne 0 ]; then
        add_finding fences "${file} has ${count} code fences (odd; a block is unterminated)"
    fi
done < <(tracked_md)

LEAK_HITS="$(repo_grep '<tool_call>|<function=|<parameter=' | grep -v "^${SELF_PATH}:" || true)"
if [ -n "${LEAK_HITS}" ]; then
    printf '%s\n' "${LEAK_HITS}" >> "${REPORT_DIR}/leakage"
    FAILURES=$((FAILURES + $(printf '%s\n' "${LEAK_HITS}" | wc -l | tr -d ' ')))
fi

PATH_HITS="$(repo_grep '/Users/|file:///|~/\.(cursor|agent)/skills/.|/opt/homebrew/' | grep -v -e "^${PATH_ALLOWLIST}:" -e "^${SELF_PATH}:" || true)"
if [ -n "${PATH_HITS}" ]; then
    printf '%s\n' "${PATH_HITS}" >> "${REPORT_DIR}/paths"
    FAILURES=$((FAILURES + $(printf '%s\n' "${PATH_HITS}" | wc -l | tr -d ' ')))
fi

for skill in skills/*/SKILL.md; do
    [ -f "${skill}" ] || continue
    n="$(wc -l < "${skill}" | tr -d ' ')"
    if [ "${n}" -gt "${MAX_SKILL_LINES}" ]; then
        add_finding sizes "${skill} is ${n} lines, limit ${MAX_SKILL_LINES}"
    fi
done

MANIFEST="skills/manifest.json"
MANIFEST_SKILL_COUNT=0
MANIFEST_IDE_COUNT=0

if [ ! -f "${MANIFEST}" ]; then
    add_finding manifest "${MANIFEST} missing"
else
    manifest_counts="$(python3 <<'PY' 2>/dev/null
import json

try:
    with open("skills/manifest.json", encoding="utf-8") as handle:
        data = json.load(handle)
except Exception:
    print("0 0")
    raise SystemExit

skills = data.get("skills")
if not isinstance(skills, list):
    print("0 0")
else:
    ides = set()
    for skill in skills:
        if isinstance(skill, dict):
            for ide in skill.get("ides") or []:
                if isinstance(ide, str):
                    ides.add(ide)
    print(f"{len(skills)} {len(ides)}")
PY
)"
    read -r MANIFEST_SKILL_COUNT MANIFEST_IDE_COUNT <<< "${manifest_counts}"

    manifest_err="$(python3 <<'PY' 2>&1
import glob
import json
import os
import sys

manifest_path = "skills/manifest.json"
valid_ides = {"cursor", "claude", "antigravity"}
errors = []

try:
    with open(manifest_path, encoding="utf-8") as handle:
        data = json.load(handle)
except json.JSONDecodeError as exc:
    errors.append(f"{manifest_path}: invalid JSON: {exc}")
    for err in errors:
        print(err)
    sys.exit(0)

if data.get("version") != 1:
    errors.append(
        f"{manifest_path}: version must be 1, got {data.get('version')!r}"
    )

skills = data.get("skills")
if not isinstance(skills, list):
    errors.append(f"{manifest_path}: skills must be an array")
    skills = []

names = set()
dirs = set()
declared_dirs = set()

for index, skill in enumerate(skills):
    if not isinstance(skill, dict):
        errors.append(f"{manifest_path}: skills[{index}] must be an object")
        continue

    name = skill.get("name")
    dir_name = skill.get("dir")
    required = skill.get("required")
    ides = skill.get("ides")

    if not isinstance(name, str) or not name:
        errors.append(f"{manifest_path}: skills[{index}] missing or invalid name")
        continue
    if name in names:
        errors.append(f"{manifest_path}: duplicate skill name '{name}'")
    names.add(name)

    if not isinstance(dir_name, str) or not dir_name:
        errors.append(
            f"{manifest_path}: skills[{index}] ({name}) missing or invalid dir"
        )
        continue
    if dir_name in dirs:
        errors.append(f"{manifest_path}: duplicate skill dir '{dir_name}'")
    dirs.add(dir_name)
    declared_dirs.add(dir_name)

    if name != dir_name:
        errors.append(
            f"{manifest_path}: skills[{index}] name '{name}' does not match dir '{dir_name}'"
        )

    if not isinstance(required, bool):
        errors.append(
            f"{manifest_path}: skills[{index}] ({name}) required must be boolean"
        )

    if not isinstance(ides, list) or not ides:
        errors.append(
            f"{manifest_path}: skills[{index}] ({name}) ides must be a non-empty array"
        )
    else:
        seen_ides = set()
        for ide in ides:
            if not isinstance(ide, str) or ide not in valid_ides:
                errors.append(
                    f"{manifest_path}: skills[{index}] ({name}) invalid ide '{ide}'"
                )
            elif ide in seen_ides:
                errors.append(
                    f"{manifest_path}: skills[{index}] ({name}) duplicate ide '{ide}'"
                )
            seen_ides.add(ide)

    skill_md = os.path.join("skills", dir_name, "SKILL.md")
    if not os.path.isfile(skill_md):
        errors.append(
            f"{manifest_path}: declared dir '{dir_name}' missing {skill_md}"
        )

for skill_md in sorted(glob.glob("skills/*/SKILL.md")):
    dir_name = os.path.basename(os.path.dirname(skill_md))
    if dir_name not in declared_dirs:
        errors.append(
            f"{manifest_path}: undeclared skill directory '{dir_name}' ({skill_md})"
        )

for err in errors:
    print(err)
PY
)"
    if [ -n "${manifest_err}" ]; then
        while IFS= read -r line; do
            [ -n "${line}" ] && add_finding manifest "${line}"
        done <<EOF
${manifest_err}
EOF
    fi
fi

print_row() {
    local label="$1"
    local section="$2"
    local ok_detail="$3"
    local count
    count="$(section_count "${section}")"

    if [ "${count}" -eq 0 ]; then
        if [ -n "${ok_detail}" ]; then
            printf '  %s✓%s %-*s %s%s%s\n' \
                "${C_GREEN}" "${C_RESET}" "${LABEL_WIDTH}" "${label}" \
                "${C_DIM}" "${ok_detail}" "${C_RESET}"
        else
            printf '  %s✓%s %s\n' "${C_GREEN}" "${C_RESET}" "${label}"
        fi
        return
    fi

    if [ "${count}" -eq 1 ]; then
        ok_detail="${count} finding"
    else
        ok_detail="${count} findings"
    fi
    printf '  %s✗%s %-*s %s%s%s\n' \
        "${C_RED}" "${C_RESET}" "${LABEL_WIDTH}" "${label}" \
        "${C_DIM}" "${ok_detail}" "${C_RESET}"
    while IFS= read -r line; do
        [ -n "${line}" ] && printf '      %s\n' "${line}"
    done < "${REPORT_DIR}/${section}"
}

printf '%s\n\n' "AI Vault Validation"

print_row "Skill metadata" metadata "${SKILL_COUNT} skill$([ "${SKILL_COUNT}" -eq 1 ] && echo '' || echo s)"
print_row "Relative links" links ""
print_row "Code fences" fences ""
print_row "Tool-call leakage" leakage ""
print_row "Machine paths" paths ""
print_row "Skill sizes" sizes ""
if [ "$(section_count manifest)" -eq 0 ]; then
    manifest_detail="${MANIFEST_SKILL_COUNT} skill$([ "${MANIFEST_SKILL_COUNT}" -eq 1 ] && echo '' || echo s) · ${MANIFEST_IDE_COUNT} IDE$([ "${MANIFEST_IDE_COUNT}" -eq 1 ] && echo '' || echo s)"
else
    manifest_detail=""
fi
print_row "Skills manifest" manifest "${manifest_detail}"

printf '\n'
if [ "${FAILURES}" -eq 0 ]; then
    printf '%sPASS%s  %d checks · %d skill%s\n' \
        "${C_GREEN}" "${C_RESET}" "${CHECK_COUNT}" "${SKILL_COUNT}" \
        "$([ "${SKILL_COUNT}" -eq 1 ] && echo '' || echo s)"
    exit 0
fi
if [ "${FAILURES}" -eq 1 ]; then
    printf '%sFAIL%s  1 finding\n' "${C_RED}" "${C_RESET}"
else
    printf '%sFAIL%s  %d findings\n' "${C_RED}" "${C_RESET}" "${FAILURES}"
fi
exit 1
