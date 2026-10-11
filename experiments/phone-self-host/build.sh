#!/bin/sh
set -eu
cd "$(dirname "$0")"
MODE="${1:-unsigned}"
case "$MODE" in
  unsigned) SIGNING="CODE_SIGNING_ALLOWED=NO" ;;
  signed) SIGNING="-allowProvisioningUpdates" ;;
  *) echo 'usage: build.sh [unsigned|signed]' >&2; exit 2 ;;
esac
xcodegen generate --spec project.yml
xcodebuild -project PhoneSelfHostProbe.xcodeproj -scheme PhoneSelfHostProbe \
    -configuration Debug -destination 'generic/platform=iOS' \
    -derivedDataPath build "$SIGNING" build
