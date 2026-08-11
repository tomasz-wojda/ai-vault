#!/usr/bin/env bash
set -u

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "${REPO_ROOT}" || exit 1

MAX_DESCRIPTION=1024
MAX_SKILL_LINES=500
PATH_ALLOWLIST="skills/jenkins-pipeline-architect/scripts/syntax_check.sh"
SELF_PATH="scripts/validate-skills.sh"

FAILURES=0

fail() {
    printf '%s\n' "FAIL  $1"
    FAILURES=$((FAILURES + 1))
}

pass() {
    printf '%s\n' "ok    $1"
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

echo "== 1-4: SKILL.md frontmatter =="
for skill in skills/*/SKILL.md; do
    [ -f "${skill}" ] || continue
    dir="$(basename "$(dirname "${skill}")")"

    if [ "$(head -1 "${skill}")" != "---" ] || ! frontmatter "${skill}" | grep -q .; then
        fail "${skill}:1 missing YAML frontmatter"
        continue
    fi

    yaml_err="$(yaml_valid "${skill}")"
    if [ -n "${yaml_err}" ]; then
        fail "${skill}:1 frontmatter is not valid YAML: $(printf '%s' "${yaml_err}" | tr '\n' ' ' | cut -c1-140)"
        continue
    fi

    name="$(fm_value "${skill}" name)"
    if [ "${name}" != "${dir}" ]; then
        fail "${skill}:2 frontmatter name '${name}' does not match directory '${dir}'"
    fi

    desc="$(frontmatter "${skill}" | awk '/^description:/{f=1} f && !/^(name|version):/{print}' | tr '\n' ' ')"
    desc_len=${#desc}
    if [ "${desc_len}" -eq 0 ]; then
        fail "${skill}:2 frontmatter description missing"
    elif [ "${desc_len}" -gt "${MAX_DESCRIPTION}" ]; then
        fail "${skill}:2 description is ${desc_len} chars, limit ${MAX_DESCRIPTION}"
    fi

    version="$(fm_value "${skill}" version)"
    if ! printf '%s' "${version}" | grep -Eq '^[0-9]+\.[0-9]+\.[0-9]+$'; then
        fail "${skill}:2 frontmatter version '${version}' is not MAJOR.MINOR.PATCH"
    fi
done
[ "${FAILURES}" -eq 0 ] && pass "frontmatter"

echo "== 5: relative link targets resolve =="
LINK_FAILS=0
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
            printf '%s\n' "FAIL  ${file}:${lno} broken link -> ${target}"
        fi
    done
done < <(tracked_md) > /tmp/.vs_links.$$ 2>/dev/null
if [ -s /tmp/.vs_links.$$ ]; then
    cat /tmp/.vs_links.$$
    LINK_FAILS="$(wc -l < /tmp/.vs_links.$$ | tr -d ' ')"
    FAILURES=$((FAILURES + LINK_FAILS))
else
    pass "links"
fi
rm -f /tmp/.vs_links.$$

echo "== 6: code fence balance =="
FENCE_OK=1
while IFS= read -r file; do
    [ -f "${file}" ] || continue
    count="$(grep -c '^```' "${file}")"
    if [ $((count % 2)) -ne 0 ]; then
        fail "${file} has ${count} code fences (odd; a block is unterminated)"
        FENCE_OK=0
    fi
done < <(tracked_md)
[ "${FENCE_OK}" -eq 1 ] && pass "fences"

echo "== 7: no leaked tool-call syntax =="
LEAK_HITS="$(repo_grep '<tool_call>|<function=|<parameter=' | grep -v "^${SELF_PATH}:" || true)"
if [ -n "${LEAK_HITS}" ]; then
    printf '%s\n' "${LEAK_HITS}" | while IFS= read -r hit; do printf '%s\n' "FAIL  ${hit}"; done
    FAILURES=$((FAILURES + $(printf '%s\n' "${LEAK_HITS}" | wc -l | tr -d ' ')))
else
    pass "no tool-call leakage"
fi

echo "== 8: no machine-specific paths =="
PATH_HITS="$(repo_grep '/Users/|file:///|~/\.(cursor|agent)/skills/.|/opt/homebrew/' | grep -v -e "^${PATH_ALLOWLIST}:" -e "^${SELF_PATH}:" || true)"
if [ -n "${PATH_HITS}" ]; then
    printf '%s\n' "${PATH_HITS}" | while IFS= read -r hit; do printf '%s\n' "FAIL  ${hit}"; done
    FAILURES=$((FAILURES + $(printf '%s\n' "${PATH_HITS}" | wc -l | tr -d ' ')))
else
    pass "no machine-specific paths"
fi

echo "== 9: SKILL.md size =="
SIZE_OK=1
for skill in skills/*/SKILL.md; do
    [ -f "${skill}" ] || continue
    n="$(wc -l < "${skill}" | tr -d ' ')"
    if [ "${n}" -gt "${MAX_SKILL_LINES}" ]; then
        fail "${skill} is ${n} lines, limit ${MAX_SKILL_LINES}"
        SIZE_OK=0
    fi
done
[ "${SIZE_OK}" -eq 1 ] && pass "skill size"

echo "== 10: skills manifest =="
MANIFEST="skills/manifest.json"
MANIFEST_OK=1

if [ ! -f "${MANIFEST}" ]; then
    fail "${MANIFEST} missing"
    MANIFEST_OK=0
else
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
            [ -n "${line}" ] && fail "${line}"
        done <<EOF
${manifest_err}
EOF
        MANIFEST_OK=0
    fi
fi
[ "${MANIFEST_OK}" -eq 1 ] && pass "manifest"

echo
if [ "${FAILURES}" -eq 0 ]; then
    echo "validate-skills: PASS"
    exit 0
fi
echo "validate-skills: ${FAILURES} finding(s)"
exit 1
