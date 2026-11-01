#!/usr/bin/env bash
# Prepare a NEW lab machine for lab NN by running every earlier lab for you.
#
#   sudo apt-get update && sudo apt-get install -y git
#   git clone https://github.com/nicklotz/containerization-fundamentals.git ~/containerization-fundamentals
#   ~/containerization-fundamentals/scripts/catch-up.sh 05      # ready to start Lab 05
#
# The script runs each earlier lab's commands in order, does its UI steps through
# the tools' APIs, and checks the results. Use it on a machine where you have not
# started the labs. It cannot repair a lab that stopped halfway.
set -euo pipefail
target=$((10#${1:?usage: catch-up.sh NN   (the lab you want to start, for example 05)}))
repo="$(cd "$(dirname "$0")/.." && pwd)"
labs=()
for f in "$repo"/labs/[0-9][0-9]-*.md; do
  n=$((10#$(basename "$f" | cut -c1-2)))
  if [ "$n" -lt "$target" ]; then labs+=("$f"); fi
done
if [ ${#labs[@]} -eq 0 ]; then echo "Lab $1 is the first lab. There is nothing to run."; exit 0; fi
echo "Running ${#labs[@]} earlier lab(s): ${labs[*]##*/}"
echo "Each lab takes a few minutes. The log is in ~/lab-runs/."
exec python3 "$repo/tests/run-lab.py" --catchup "${labs[@]}"
