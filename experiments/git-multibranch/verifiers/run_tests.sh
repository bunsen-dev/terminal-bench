#!/bin/bash
set -euo pipefail

tmp_dir="$(mktemp -d)"
repo_dir="$tmp_dir/project-test"
trap 'rm -rf "$tmp_dir"' EXIT

export HOME="$tmp_dir/home"
mkdir -p "$HOME"

export GIT_SSH_COMMAND="sshpass -p password ssh -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null"

wait_for_content() {
    local url="$1"
    local expected="$2"
    local start_ns now_ns actual

    start_ns="$(date +%s%N)"
    while true; do
        actual="$(curl -sk --max-time 2 "$url" 2>/dev/null || true)"
        if [ "$actual" = "$expected" ]; then
            return 0
        fi

        now_ns="$(date +%s%N)"
        if [ $((now_ns - start_ns)) -gt 3000000000 ]; then
            echo "Timed out waiting for $url"
            echo "Expected: $expected"
            echo "Actual:   $actual"
            return 1
        fi
        sleep 0.2
    done
}

git clone git@localhost:/git/project "$repo_dir"
cd "$repo_dir"
git config user.email "verifier@example.com"
git config user.name "Verifier"

main_content="main-branch-$(date +%s%N)"
git checkout -B main
printf '%s' "$main_content" > index.html
git add index.html
git commit -m "main verifier commit"
git push -f -u origin main
wait_for_content "https://localhost:8443/index.html" "$main_content"

dev_content="dev-branch-$(date +%s%N)"
git checkout -B dev
printf '%s' "$dev_content" > index.html
git add index.html
git commit -m "dev verifier commit"
git push -f -u origin dev
wait_for_content "https://localhost:8443/dev/index.html" "$dev_content"

echo "TEST PASSED"
