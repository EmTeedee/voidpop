# Voidpop

Voidpop is a dummy POP3 server. It accepts any username/password and always
reports that there are no messages.

## Usage

    voidpop [--port PORT] [--verbose] [--version]

The port defaults to 110 and can also be set with `VOIDPOP_PORT`. The Debian
package installs a systemd unit and an init script; configure it in
`/etc/default/voidpop`.

## Development

    pip install -e '.[dev]'
    ruff check . && pylint voidpop.py && pytest

## Releasing

1. Bump `version` in `pyproject.toml` and add a new entry on top of
   `debian/changelog` (`dch -v X.Y.Z`); both must match the tag.
2. Commit, then `git tag vX.Y.Z && git push --tags`.

The tag triggers GitHub Actions (`.github/workflows/release.yml`) and the GitLab
pipeline (`.gitlab-ci.yml`). Both run `dist-tools/build-release.sh` in a clean
pinned Debian container (`dist-tools/BUILD_IMAGE`, by digest, with apt packages from a fixed snapshot.debian.org timestamp) and publish the sdist, wheel, `.deb` and `SHA256SUMS`
as release assets. Builds are reproducible: timestamps come from the
`debian/changelog` date (`SOURCE_DATE_EPOCH`), and only git-tracked files are
built. To reproduce locally:

    docker run --rm -v "$PWD:/src" -w /src "$(cat dist-tools/BUILD_IMAGE)" dist-tools/build-release.sh

### Refreshing pins

`dist-tools/update_pins.py` verifies that `pyproject.toml` and `debian/changelog`
agree, then pulls `debian:trixie` and updates the image digest
(`dist-tools/BUILD_IMAGE`, `.gitlab-ci.yml`) and the apt snapshot timestamp
(`dist-tools/build-release.sh`). Use `--check-only` to only verify versions.
Renovate (`renovate.json`) keeps the GitHub Actions SHAs, Python dependencies and
the image digest (`.gitlab-ci.yml`, `dist-tools/BUILD_IMAGE`) current. It cannot
derive the matching apt snapshot timestamp, so after merging an image-digest
update, run `dist-tools/update_pins.py` and commit the `SNAPSHOT=` change.
