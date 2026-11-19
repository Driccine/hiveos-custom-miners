#!/usr/bin/env bash
set -euo pipefail

usage() {
    printf 'Usage: %s [aria|solo] [output-directory]\n' "${0##*/}"
}

case "${1:-aria}" in
    aria)
        base=https://dl.ariabrain.com/neb-dl
        archive=aria-energy-neb-3.2.0.tar.gz
        ;;
    solo)
        base=https://github.com/SilasEigen/neb/releases/download/v1.0.1
        archive=nebminer-1.0.1.tar.gz
        digest=a16fe04014d765ffd7684f27445f738cc8249f65553d10bf5a5f7fd97861e0f6
        ;;
    -h|--help) usage; exit 0 ;;
    *) usage >&2; exit 2 ;;
esac
if (( $# > 2 )); then
    usage >&2
    exit 2
fi

destination=${2:-.}
mkdir -p -- "$destination"
stage=$(mktemp -d "$destination/.neb-download.XXXXXXXX")
trap 'rm -rf -- "$stage"' EXIT

download() {
    curl --fail --silent --show-error --location --proto '=https' \
        --proto-redir '=https' --connect-timeout 15 --max-time 300 --retry 2 \
        --output "$stage/$1" "$base/$1"
}

if [[ -z ${digest:-} ]]; then
    checksums=aria-energy-neb-3.2.0-SHA256SUMS.txt
    download "$checksums"
    digest=$(awk -v archive="$archive" '
        NF == 2 && ($2 == archive || $2 == "*" archive) { print $1 }
    ' "$stage/$checksums")
fi
if [[ ! $digest =~ ^[[:xdigit:]]{64}$ ]]; then
    printf 'SHA-256 absent ou ambigu pour %s\n' "$archive" >&2
    exit 1
fi

download "$archive"
(
    cd -- "$stage"
    printf '%s  %s\n' "$digest" "$archive" | sha256sum --check --status
) || {
    printf 'SHA-256 incorrect pour %s\n' "$archive" >&2
    exit 1
}

mv -T -- "$stage/$archive" "$destination/$archive"
printf '%s\n' "$destination/$archive"
