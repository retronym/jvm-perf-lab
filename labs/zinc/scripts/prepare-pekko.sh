#!/usr/bin/env bash
# The pristine Pekko 1.7.1 checkout the benchmark copies per fork: labs/zinc/out/pekko, or $PEKKO_CHECKOUT.
set -euo pipefail
here=$(cd "$(dirname "$0")/.." && pwd)
dest=${PEKKO_CHECKOUT:-$here/out/pekko}
[ -d "$dest/.git" ] || git clone --depth 1 --branch v1.7.1 https://github.com/apache/pekko.git "$dest"
git -C "$dest" describe --tags
