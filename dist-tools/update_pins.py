#!/usr/bin/env python3
"""Check release metadata and refresh the pinned build image and apt snapshot.

1. Verifies pyproject.toml and debian/changelog declare the same version
   (and, with --tag, that the tag matches too). Aborts on mismatch.
2. Pulls the Debian image, then rewrites its digest in dist-tools/BUILD_IMAGE and
   .gitlab-ci.yml, and the matching snapshot.debian.org timestamp (taken from
   the image itself) in dist-tools/build-release.sh.

Requires Python 3.11+ and docker. Use --check-only to skip step 2.
"""
import argparse
import re
import subprocess
import sys
from pathlib import Path

import tomllib

ROOT = Path(__file__).resolve().parent.parent
IMAGE_TAG = "debian:trixie"
DIGEST_RE = re.compile(r"debian:trixie@sha256:[0-9a-f]{64}")
SNAPSHOT_RE = re.compile(r"^SNAPSHOT=\S+$", re.MULTILINE)


def run(*cmd: str) -> str:
    """run a command and return its stripped stdout"""
    return subprocess.run(cmd, check=True, capture_output=True, text=True).stdout.strip()


def check_versions(tag: str | None) -> str:
    """return the version if pyproject.toml, debian/changelog (and tag) agree"""
    with (ROOT / "pyproject.toml").open("rb") as file:
        py_version = tomllib.load(file)["project"]["version"]
    first_line = (ROOT / "debian/changelog").read_text(encoding="utf8").splitlines()[0]
    match = re.match(r"^\S+ \(([^)]+)\)", first_line)
    if not match:
        sys.exit(f"cannot parse debian/changelog first line: {first_line!r}")
    versions = {"pyproject.toml": py_version, "debian/changelog": match[1]}
    if tag:
        versions["tag"] = tag.removeprefix("v")
    if len(set(versions.values())) != 1:
        sys.exit(f"version mismatch: {versions}")
    print(f"version {py_version} OK")
    return py_version


def latest_pins() -> tuple[str, str]:
    """pull the image; return its pinned reference and snapshot timestamp"""
    run("docker", "pull", "-q", IMAGE_TAG)
    repo_digest = run("docker", "image", "inspect", "--format", "{{index .RepoDigests 0}}",
                      IMAGE_TAG)
    reference = f"{IMAGE_TAG}@{repo_digest.split('@')[1]}"
    sources = run("docker", "run", "--rm", reference, "cat",
                  "/etc/apt/sources.list.d/debian.sources")
    match = re.search(r"snapshot\.debian\.org/archive/debian/(\d{8}T\d{6}Z)", sources)
    if not match:
        sys.exit("image has no snapshot.debian.org timestamp in debian.sources")
    return reference, match[1]


def rewrite(path: str, pattern: re.Pattern[str], replacement: str) -> None:
    """substitute pattern in a file and report whether it changed"""
    file = ROOT / path
    old = file.read_text(encoding="utf8")
    new, count = pattern.subn(replacement, old)
    if not count:
        sys.exit(f"{path}: pattern {pattern.pattern!r} not found")
    file.write_text(new, encoding="utf8")
    print(f"{path}: {'updated' if new != old else 'unchanged'}")


def main() -> None:
    """entry point"""
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n", maxsplit=1)[0])
    parser.add_argument("--tag", help="also require this release tag (e.g. v1.1.0) to match")
    parser.add_argument("--check-only", action="store_true", help="only verify versions")
    args = parser.parse_args()

    check_versions(args.tag)
    if args.check_only:
        return
    reference, snapshot = latest_pins()
    (ROOT / "dist-tools/BUILD_IMAGE").write_text(reference + "\n", encoding="utf8")
    print(f"dist-tools/BUILD_IMAGE: {reference}")
    rewrite(".gitlab-ci.yml", DIGEST_RE, reference)
    rewrite("dist-tools/build-release.sh", SNAPSHOT_RE, f"SNAPSHOT={snapshot}")


if __name__ == "__main__":
    main()
