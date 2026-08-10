#!/usr/bin/env bash
set -u

SERVICES="jira newrelic aws eks jenkins github argocd artifactory ssh snow datadog"
MARKER=".managed-by-ai-vault"

usage() {
    cat <<'EOF'
Usage: setup-workspace-interface.sh <workspace> [--dry-run|--link|--move|--revert]

  --dry-run   (default) print every action, change nothing
  --link      create worklog/interface/<svc> as symlinks to the existing ../../<svc>
  --move      relocate <svc> into worklog/interface/<svc>, leaving a root symlink back
  --revert    undo whichever mode was applied

Only service directories this script created a link or marker for are touched.
Existing targets are never overwritten. Credential file contents are never read.
EOF
}

WORKSPACE="${1:-}"
MODE="${2:---dry-run}"

case "${WORKSPACE}" in
    ''|-h|--help) usage; exit 1 ;;
esac

if [ ! -d "${WORKSPACE}" ]; then
    echo "workspace not found: ${WORKSPACE}"
    exit 1
fi

WORKSPACE="$(cd "${WORKSPACE}" && pwd)"
IFACE="${WORKSPACE}/worklog/interface"

case "${MODE}" in
    --dry-run|--link|--move|--revert) ;;
    *) echo "unknown mode: ${MODE}"; usage; exit 1 ;;
esac

echo "DEPRECATED: use 'ai-worklog workspace init ${WORKSPACE}' for new workspaces." >&2

DRY=0
[ "${MODE}" = "--dry-run" ] && DRY=1

act() {
    if [ "${DRY}" -eq 1 ]; then
        echo "  would: $*"
    else
        echo "  run:   $*"
        "$@" || { echo "  FAILED: $*"; exit 1; }
    fi
}

echo "workspace: ${WORKSPACE}"
echo "mode:      ${MODE}"
echo

if [ "${MODE}" = "--revert" ]; then
    if [ ! -d "${IFACE}" ]; then
        echo "nothing to revert: ${IFACE} does not exist"
        exit 0
    fi
    for svc in ${SERVICES}; do
        entry="${IFACE}/${svc}"
        [ -e "${entry}" ] || [ -L "${entry}" ] || continue
        if [ -L "${entry}" ]; then
            echo "${svc}: linked -> removing link"
            act rm "${entry}"
        elif [ -f "${entry}/${MARKER}" ]; then
            echo "${svc}: moved -> restoring to workspace root"
            [ -L "${WORKSPACE}/${svc}" ] && act rm "${WORKSPACE}/${svc}"
            act rm "${entry}/${MARKER}"
            act mv "${entry}" "${WORKSPACE}/${svc}"
        else
            echo "${svc}: not managed by this script, leaving alone"
        fi
    done
    if [ "${DRY}" -eq 0 ] && [ -d "${IFACE}" ]; then
        rmdir "${IFACE}" 2>/dev/null && echo "removed empty ${IFACE}"
    fi
    echo
    echo "revert complete"
    exit 0
fi

[ -d "${IFACE}" ] || act mkdir -p "${IFACE}"

LINKED=0
MOVED=0
SKIPPED=0

for svc in ${SERVICES}; do
    src="${WORKSPACE}/${svc}"
    dst="${IFACE}/${svc}"

    if [ ! -d "${src}" ] && [ ! -L "${src}" ]; then
        echo "${svc}: absent at workspace root, skipping"
        SKIPPED=$((SKIPPED + 1))
        continue
    fi

    if [ -e "${dst}" ] || [ -L "${dst}" ]; then
        echo "${svc}: ${dst} already exists, refusing to overwrite"
        SKIPPED=$((SKIPPED + 1))
        continue
    fi

    if [ -L "${src}" ]; then
        echo "${svc}: root entry is already a symlink, skipping"
        SKIPPED=$((SKIPPED + 1))
        continue
    fi

    case "${MODE}" in
        --link|--dry-run)
            echo "${svc}: link"
            act ln -s "../../${svc}" "${dst}"
            LINKED=$((LINKED + 1))
            ;;
        --move)
            echo "${svc}: move + back-link"
            act mv "${src}" "${dst}"
            act ln -s "worklog/interface/${svc}" "${src}"
            if [ "${DRY}" -eq 0 ]; then
                : > "${dst}/${MARKER}"
            fi
            MOVED=$((MOVED + 1))
            ;;
    esac
done

echo
echo "linked=${LINKED} moved=${MOVED} skipped=${SKIPPED}"
if [ "${DRY}" -eq 1 ]; then
    echo "dry run only, nothing changed. re-run with --link or --move."
fi
