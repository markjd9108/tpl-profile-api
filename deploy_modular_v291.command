#!/bin/bash
# Deploy modular profile update v2.9.1 (new design, emotional journey, text rules) to Railway.
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"; cd "$SCRIPT_DIR"
echo "Deploying modular profiles v2.9.1..."
rm -f .git/index.lock .git/HEAD.lock 2>/dev/null
git add Dockerfile api_server.py modular_profile.py modular_route.py profile_text_rules.py PROFILE_TEXT_RULES.md templates_modular/one_skill.html deploy_modular_v291.command
echo "Staged:"; git status --short -- Dockerfile api_server.py modular_profile.py modular_route.py profile_text_rules.py templates_modular
echo ""
git commit -m "Modular profiles v2.9.1: banded donut, working style in snapshot, What strong looks like, during and end feelings with roles, text rules check"
echo ""; echo "Pushing to GitHub -> Railway..."; git push
echo ""; echo "Done. Railway is rebuilding (about 3 to 5 minutes)."
