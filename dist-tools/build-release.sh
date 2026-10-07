#!/bin/sh
# Build sdist, wheel and .deb reproducibly into ./dist.
# Run inside the container pinned by digest in dist-tools/BUILD_IMAGE, e.g.:
#   docker run --rm -v "$PWD:/src" -w /src "$(cat dist-tools/BUILD_IMAGE)" dist-tools/build-release.sh
# Packages come from a fixed snapshot.debian.org timestamp (bump deliberately).
set -eu

export DEBIAN_FRONTEND=noninteractive
SNAPSHOT=20261005T000000Z
cat > /etc/apt/sources.list.d/debian.sources <<EOF
Types: deb
URIs: http://snapshot.debian.org/archive/debian/$SNAPSHOT
Suites: trixie
Components: main
Signed-By: /usr/share/keyrings/debian-archive-keyring.pgp
EOF
echo 'Acquire::Check-Valid-Until "false";' > /etc/apt/apt.conf.d/99snapshot
apt-get update -qq
apt-get install -y -qq --no-install-recommends \
    build-essential debhelper dh-python dh-exec pybuild-plugin-pyproject \
    python3-all python3-build python3-setuptools python3-wheel python3-trio fakeroot git ca-certificates

# Timestamps derive from the last debian/changelog entry, so the same source
# always yields the same artifacts regardless of when/where it is built.
SOURCE_DATE_EPOCH=$(dpkg-parsechangelog -S Timestamp)
export SOURCE_DATE_EPOCH
export LC_ALL=C.UTF-8 TZ=UTC
umask 022

# dpkg-buildpackage writes the .deb next to the source dir, so nest it
root=$(mktemp -d)
trap 'rm -rf "$root"' EXIT
work="$root/voidpop"
mkdir "$work"
# build from a pristine copy of tracked files only
git config --global --add safe.directory "$PWD"
git ls-files -z | xargs -0 tar -cf - | tar -xf - -C "$work"

rm -rf dist
mkdir -p dist
(
    cd "$work"
    python3 -m build --no-isolation --sdist --wheel --outdir "$root/out"
    dpkg-buildpackage -us -uc -b
)

# setuptools stamps the sdist with the current time; repack it deterministically
sdist=$(ls "$root"/out/*.tar.gz)
mkdir "$root/sdist"
tar -xzf "$sdist" -C "$root/sdist"
chmod -R u=rwX,go=rX "$root/sdist"
(cd "$root/sdist" && tar --sort=name --format=gnu --mtime="@$SOURCE_DATE_EPOCH" \
    --owner=0 --group=0 --numeric-owner -cf - -- *) | gzip -nc9 > "$sdist"

mv "$root"/out/* "$root"/voidpop_*.deb dist/
(cd dist && sha256sum -- * > SHA256SUMS && cat SHA256SUMS)
