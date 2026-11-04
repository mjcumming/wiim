#!/usr/bin/env bash
# Accept a successful PR CI run only when it tested this release's exact tree.
set -euo pipefail

workflow=${1:?CI workflow file is required}
shift
repo=${GITHUB_REPOSITORY:?}
commit=${GITHUB_SHA:?}
[[ "$commit" =~ ^[0-9a-f]{40}$ ]] || exit 1

head=$(gh api "repos/$repo/commits/$commit/pulls" \
    --jq ".[] | select(.merged_at != null and .merge_commit_sha == \"$commit\" and .base.ref == \"main\") | .head.sha" \
    2>/dev/null) || exit 1
[[ "$head" =~ ^[0-9a-f]{40}$ ]] || exit 1

run_info=$(gh run list --repo "$repo" --workflow "$workflow" --event pull_request \
    --commit "$head" --limit 1 --json databaseId,attempt,status,conclusion \
    --jq '.[0] | select(.status == "completed" and .conclusion == "success") | [.databaseId, .attempt] | @tsv' \
    2>/dev/null) || exit 1
IFS=$'\t' read -r run attempt <<< "$run_info"
[[ "$run" =~ ^[0-9]+$ && "$attempt" =~ ^[0-9]+$ ]] || exit 1

dir=$(mktemp -d)
trap 'rm -rf "$dir"' EXIT
found=false
for version in "$@"; do
    if gh run download "$run" --repo "$repo" --name "ci-tested-tree-$version-$attempt" --dir "$dir" >/dev/null 2>&1; then
        found=true
        break
    fi
done
"$found" || exit 1
IFS= read -r tested_tree < "$dir/tested-tree" || exit 1
[[ "$tested_tree" =~ ^[0-9a-f]{40}$ ]] || exit 1
release_tree=$(git rev-parse "$commit^{tree}") || exit 1
[[ "$tested_tree" == "$release_tree" ]] || exit 1

echo "PR CI run $run passed for the release tree $release_tree"
