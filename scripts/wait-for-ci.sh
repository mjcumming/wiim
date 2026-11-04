#!/usr/bin/env bash
# Reuse a successful PR run for the same tree, or wait for main-branch CI.
set -euo pipefail

main_ci() {
    gh run list --repo "$GITHUB_REPOSITORY" --workflow tests.yaml \
        --branch main --event push --commit "$GITHUB_SHA" --limit 1 \
        --json status,conclusion \
        --jq '.[0] | [.status, (.conclusion // "")] | @tsv' 2>/dev/null
}

result=$(main_ci) || result=""
case "$result" in
    $'completed\tsuccess') echo "CI passed for $GITHUB_SHA"; exit 0 ;;
    $'completed\t'*) echo "::error::CI did not pass for $GITHUB_SHA: $result"; exit 1 ;;
esac

if bash "$(dirname "$0")/has-tested-pr-tree.sh" tests.yaml default; then
    exit 0
fi

echo "No matching successful PR CI; waiting for main-branch CI"
attempts=${CI_WAIT_ATTEMPTS:-90}
interval=${CI_WAIT_INTERVAL:-10}

for ((attempt = 1; attempt <= attempts; attempt++)); do
    if ! result=$(main_ci); then
        result=""
    fi
    case "$result" in
        $'completed\tsuccess')
            echo "CI passed for $GITHUB_SHA"
            exit 0
            ;;
        $'completed\t'*)
            echo "::error::CI did not pass for $GITHUB_SHA: $result"
            exit 1
            ;;
    esac
    echo "Waiting for main-branch CI for $GITHUB_SHA ($attempt/$attempts)"
    if ((attempt < attempts)); then
        sleep "$interval"
    fi
done

echo "::error::Timed out waiting for main-branch CI for $GITHUB_SHA"
exit 1
