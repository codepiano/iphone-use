#!/bin/sh
set -eu
SELF_ROOT=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
cd "$SELF_ROOT"
[ -d vendor/idevice ] || sh ./prepare.sh
rustup target add aarch64-apple-ios
if [ -x "$HOME/.local/bin/heavy-cargo" ]; then
    IPHONEOS_DEPLOYMENT_TARGET=17.4 "$HOME/.local/bin/heavy-cargo" build --locked --release --target aarch64-apple-ios
else
    IPHONEOS_DEPLOYMENT_TARGET=17.4 cargo build --locked --release --target aarch64-apple-ios
fi
xcodegen generate --spec project.yml
if [ "${1:-unsigned}" = signed ]; then
    xcodebuild -project PhoneSelfLaunch.xcodeproj -scheme PhoneSelfLaunch \
        -destination 'generic/platform=iOS' -derivedDataPath build/app -allowProvisioningUpdates build
else
    xcodebuild -project PhoneSelfLaunch.xcodeproj -scheme PhoneSelfLaunch \
        -destination 'generic/platform=iOS' -derivedDataPath build/app CODE_SIGNING_ALLOWED=NO build
fi
