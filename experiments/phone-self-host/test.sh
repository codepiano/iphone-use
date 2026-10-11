#!/bin/sh
set -eu
cd "$(dirname "$0")"
TEST_DIR=$(mktemp -d)
trap 'rm -rf "$TEST_DIR"' EXIT
xcrun swiftc Sources/RemotePairingHandshake.swift Tests/main.swift -o "$TEST_DIR/protocol-test"
"$TEST_DIR/protocol-test"
