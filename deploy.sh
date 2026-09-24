#!/usr/bin/env bash

set -euo pipefail

if [[ $# -ne 1 ]]; then
    printf 'Usage: %s <remote-pedal-hostname>\n' "$0" >&2
    exit 1
fi

remote_host=$1
remote_target="patch@${remote_host}"
remote_dir="/home/patch/modep_ui"

printf 'Deploying to %s:%s\n' "$remote_target" "$remote_dir"

ssh "$remote_target" "mkdir -p '$remote_dir'"

rsync --archive --verbose --delete \
    --exclude='.git/' \
    --exclude='.github/' \
    --exclude='.pytest_cache/' \
    --exclude='.venv/' \
    --exclude='__pycache__/' \
    --exclude='*.pyc' \
    ./ "${remote_target}:${remote_dir}/"

ssh "$remote_target" "cd '$remote_dir' && sudo bash ./install_service.sh"

printf 'Deployment completed successfully.\n'
