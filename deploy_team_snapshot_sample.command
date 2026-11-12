#!/bin/bash
# Deploy the sample Team Performance Snapshot, the restyled sample Leadership Insight Report, and the updated /samples page.
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"; cd "$SCRIPT_DIR"
rm -f .git/index.lock .git/HEAD.lock 2>/dev/null
git add api_server.py assets/team_snapshot_sample.html assets/lir_sample.html assets/sample_profiles.html deploy_team_snapshot_sample.command
git commit -m "Sample Team Performance Snapshot, restyled sample LIR, workshop archetype profiles back on /samples"
git push
echo "Done. Railway is rebuilding (about 3 to 5 minutes)."
