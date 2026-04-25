#!/usr/bin/env bash

ACT_PATH="$(dirname "$0")/act/act"
WORKFLOW_DIR="$(dirname "$0")/../.."

"$ACT_PATH" -C "$WORKFLOW_DIR" workflow_dispatch --input dry_run=true
