#!/usr/bin/env python3
"""Run the guarded controller with the selected local daemon's credentials.

The external planner must be installed in the invoking Python environment.
Credentials stay in process memory; this launcher never starts or retries input.
"""
import argparse
import os
from pathlib import Path
import plistlib
import re
import sys
from urllib.parse import urlsplit


def local_environment(env, home):
    result = dict(env)
    instance = result.get("IPHONE_USE_INSTANCE", "default")
    if not re.fullmatch(r"[a-z][a-z0-9-]{0,31}", instance):
        raise ValueError("invalid local daemon instance")
    label = "com.leeguoo.iphone-use" + ("." + instance if instance != "default" else "")
    path = Path(home) / "Library/LaunchAgents" / (label + ".plist")
    if path.is_symlink():
        raise ValueError("local daemon configuration must not be a symlink")
    values = {}
    if path.is_file():
        with path.open("rb") as stream:
            values = plistlib.load(stream).get("EnvironmentVariables", {})
    port = str(values.get("IPHONE_USE_PORT", "44321"))
    if not port.isdecimal() or not 1 <= int(port) <= 65535:
        raise ValueError("invalid configured daemon port")
    url = result.get("IPHONE_USE_URL") or "http://127.0.0.1:" + port
    result["IPHONE_USE_URL"] = url
    token = result.get("IPHONE_USE_AGENT_TOKEN") or result.get("IPHONE_USE_TOKEN")
    if not token:
        parsed = urlsplit(url)
        same_local_daemon = (parsed.scheme == "http" and parsed.hostname in
            ("127.0.0.1", "localhost", "::1") and parsed.port == int(port)
            and not parsed.username and not parsed.password
            and parsed.path in ("", "/") and not parsed.query and not parsed.fragment)
        if not same_local_daemon:
            raise ValueError("explicit credential required for a different daemon origin")
        token = values.get("IPHONE_USE_AGENT_TOKEN") or values.get("IPHONE_USE_PASSWORD")
    if not isinstance(token, str) or not token:
        raise ValueError("no configured daemon credential; complete local setup first")
    result["IPHONE_USE_AGENT_TOKEN"] = token
    return result


def main():
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument("--owner", required=True)
    args, remaining = parser.parse_known_args()
    if not args.owner.strip() or len(args.owner) > 200 or any(ord(c) < 32 for c in args.owner):
        raise ValueError("bounded task owner required")
    os.environ.update(local_environment(os.environ, Path.home()))
    os.environ["IPHONE_USE_OWNER"] = args.owner
    sys.argv = ["guarded_phone.py", *remaining]
    import guarded_phone
    return guarded_phone.main()


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (ValueError, OSError, plistlib.InvalidFileException):
        # Never include configuration values or exception text in host logs.
        print("Guarded launcher could not resolve its local daemon configuration.", file=sys.stderr)
        raise SystemExit(2)
