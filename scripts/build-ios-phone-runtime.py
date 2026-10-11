#!/usr/bin/env python3
"""Build the native app with its on-phone runtime; keep signing logs private."""
from pathlib import Path
import hashlib, os, plistlib, subprocess, sys
root = Path(__file__).resolve().parents[1]
experiment = root / 'experiments/phone-self-host'
lib = experiment / 'launcher/target/aarch64-apple-ios/release/libipu_phone_host.a'
digest = hashlib.sha256()
for rel in ['src/lib.rs', 'src/main.rs', 'src/image.rs', 'Cargo.toml', 'Cargo.lock', '../patches/idevice-rsd-xctest.patch', '../.deps/idevice/idevice/src/services/dvt/xctest/mod.rs']:
    digest.update((experiment / 'launcher' / rel).read_bytes())
if not lib.exists() or digest.hexdigest().encode() not in lib.read_bytes():
    raise SystemExit('Rebuild experiments/phone-self-host/launcher first: native archive is missing or stale')
app_root = root / 'apps/ios'
subprocess.run(['xcodegen', 'generate'], cwd=app_root, check=True)
abi = ['ipu_host_start', 'ipu_host_stop', 'ipu_host_status', 'ipu_host_string_free', 'ipu_host_copy_pair_record']
flags = '-force_load "' + str(lib) + '" -framework Security ' + ' '.join('-u _' + name for name in abi)
args = ['xcodebuild', '-project', 'IPhoneUseRemote.xcodeproj', '-scheme', 'IPhoneUseRemote', '-configuration', 'Debug', '-jobs', '2', '-destination', 'generic/platform=iOS', '-derivedDataPath', 'build-phone-runtime', '-allowProvisioningUpdates', 'CURRENT_PROJECT_VERSION=18', 'IPU_HOST_LDFLAGS=' + flags, 'build']
profile = Path.home() / 'Library/LaunchAgents/com.leeguoo.iphone-use.wda.plist'
env = plistlib.loads(profile.read_bytes()).get('EnvironmentVariables', {}) if profile.exists() else {}
for name, flag in [('WDA_ASC_KEY_PATH', '-authenticationKeyPath'), ('WDA_ASC_KEY_ID', '-authenticationKeyID'), ('WDA_ASC_ISSUER_ID', '-authenticationKeyIssuerID')]:
    value = os.environ.get(name) or env.get(name)
    if value: args.extend([flag, value])
log_dir = app_root / 'build-phone-runtime/logs'
log_dir.mkdir(parents=True, exist_ok=True)
fd = os.open(log_dir / 'xcodebuild.log', os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
with os.fdopen(fd, 'w') as log:
    result = subprocess.run(args, cwd=app_root, stdout=log, stderr=subprocess.STDOUT)
if result.returncode:
    for line in (log_dir / 'xcodebuild.log').read_text(errors='replace').splitlines():
        if 'error:' in line: print(line)
    raise SystemExit(result.returncode)
app = app_root / 'build-phone-runtime/Build/Products/Debug-iphoneos/Phone Use Remote.app'
subprocess.run(['codesign', '--verify', '--deep', '--strict', str(app)], check=True)

provider = app / 'PlugIns/PhoneLocalNetwork.appex/PhoneLocalNetwork'
symbols = subprocess.check_output(['nm', '-gU', str(provider)], text=True)
if not all('_' + name in symbols for name in abi):
    raise SystemExit('Native launcher ABI missing from embedded provider')

print('Signed app and on-phone extension built: ' + str(app))
