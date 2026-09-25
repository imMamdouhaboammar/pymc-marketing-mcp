#!/usr/bin/env bash
# Kept for existing muscle memory; scripts/deploy_cloud_run.sh is the single deploy path.
#   ./scripts/fast_deploy.sh          -> API-key protected deploy
#   ./scripts/fast_deploy.sh beta     -> anonymous demo deploy
set -euo pipefail
exec "$(dirname "$0")/deploy_cloud_run.sh" "$@"
