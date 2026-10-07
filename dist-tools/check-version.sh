#!/bin/sh
# Verify that the release tag (argument, e.g. v1.1.0), pyproject.toml and
# debian/changelog all agree on the version.
set -eu
tag="${1:?usage: check-version.sh vX.Y.Z}"
want="${tag#v}"
py=$(sed -n 's/^version = "\(.*\)"/\1/p' pyproject.toml)
deb=$(sed -n '1s/^[^(]*(\([^)]*\)).*/\1/p' debian/changelog)
[ "$py" = "$want" ] || { echo "pyproject.toml version $py != tag $want" >&2; exit 1; }
[ "$deb" = "$want" ] || { echo "debian/changelog version $deb != tag $want" >&2; exit 1; }
echo "version $want OK"
