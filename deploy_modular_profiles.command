#!/bin/bash
# Deploy hosted modular profiles (/generate-modular) to Railway.
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"; cd "$SCRIPT_DIR"
echo "Deploying modular profiles..."
rm -f .git/index.lock .git/HEAD.lock 2>/dev/null
git add Dockerfile api_server.py modular_profile.py modular_route.py templates_modular/one_skill.html deploy_modular_profiles.command
echo "Staged:"; git status --short -- Dockerfile api_server.py modular_profile.py modular_route.py templates_modular
echo ""
git commit -m "Hosted modular one-skill profiles: POST /generate-modular (v2.9.0)"
echo ""; echo "Pushing to GitHub -> Railway..."; git push
echo ""; echo "Done. Railway is rebuilding (about 3 to 5 minutes)."
