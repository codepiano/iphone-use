#!/bin/sh
set -eu
SELF_ROOT=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
REV=41c388baef0dd55c0ce4924789abbfde889d9b87
if [ -d "$SELF_ROOT/vendor" ]; then
  echo 'vendor already exists; remove it explicitly to regenerate' >&2
  exit 1
fi
mkdir -p "$SELF_ROOT/build"
SELF_SOURCE=${IPU_IDEVICE_SOURCE:-$SELF_ROOT/build/idevice-source}
if [ ! -d "$SELF_SOURCE" ]; then
  git clone https://github.com/leeguooooo/idevice.git "$SELF_SOURCE" >&2
  git -C "$SELF_SOURCE" checkout --detach "$REV" >&2
fi
[ "$(git -C "$SELF_SOURCE" rev-parse HEAD)" = "$REV" ] || { echo 'unexpected idevice revision' >&2; exit 1; }
[ -z "$(git -C "$SELF_SOURCE" status --porcelain --untracked-files=no)" ] || { echo 'idevice source has edits' >&2; exit 1; }
SELF_STAGE=$(mktemp -d "$SELF_ROOT/build/vendor-prepare.XXXXXX")
trap 'rm -rf "$SELF_STAGE"' EXIT HUP INT TERM
cp -R "$SELF_SOURCE/idevice" "$SELF_STAGE/idevice"
cp "$SELF_SOURCE/LICENSE.txt" "$SELF_STAGE/LICENSE"
git -C "$SELF_STAGE" apply --check "$SELF_ROOT/idevice-rsd-launch.patch"
git -C "$SELF_STAGE" apply "$SELF_ROOT/idevice-rsd-launch.patch"
printf '%s\n' "$REV" > "$SELF_STAGE/.prepared"
mv "$SELF_STAGE" "$SELF_ROOT/vendor"
