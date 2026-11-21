#!/usr/bin/env python3
"""Restore and patch /Applications/Gemini.app from the pristine 1.147.5.1526 backup.

Usage:
  python3 restore_gemini.py             restore original binary, apply all 7 patches, re-sign
  python3 restore_gemini.py --check     verify the installed app has all patches and a valid signature
  python3 restore_gemini.py --dry-run   validate the backup and print the patch plan only
"""
import argparse
import hashlib
import shutil
import subprocess
import sys
from pathlib import Path

KIT = Path(__file__).resolve().parent
APP = Path("/Applications/Gemini.app")
APP_BIN = APP / "Contents/MacOS/Gemini"
ORIG_BIN = KIT / "original-backup/Gemini"
ENTITLEMENTS = KIT / "scripts/gemini_entitlements.plist"

ORIG_SHA256 = "1015c0c3c063f982f8ec5b178b20605dc0c58d5ccab9b730a30748f6fc39ec05"

# (name, offset, pristine bytes, patched bytes)
PATCHES = [
    ("P1  deadlock fix (SpellCheckerWarmUpTask)", 0x034F68E0,
     "08b406d0", "07000014"),
    ("P2  CALayerFlippedContentsWorkaround off", 0x034CEBF4,
     "fd7bbfa9", "c0035fd6"),
    ("P3a toolbar font scale clamp", 0x0568B88C,
     "e8e702b2a89999f288fee7f20101679e", "01106e1e0020611e20cc601ec0035fd6"),
    ("P3b toolbar icon button scale clamp", 0x0568B8A8,
     "e8e702b2a89999f288fee7f20101679e", "01106e1e1f2003d51f2003d51f2003d5"),
    ("P3c toolbar pill height 36pt", 0x0568B8C8,
     "e8e702b2a89999f288fee7f2", "4808e8d20001679ec0035fd6"),
    ("P3d toolbar top padding 6pt", 0x0568B900,
     "e8e702b2a89999f2", "0010631ec0035fd6"),
    ("P4  account-switch deadlock (Clearcut defaults write)", 0x027B652C,
     "1a73eb94", "18000014"),
]


def sha256(path):
    with open(path, "rb") as f:
        return hashlib.file_digest(f, "sha256").hexdigest()


def read_at(path, offset, length):
    with open(path, "rb") as f:
        f.seek(offset)
        return f.read(length)


def app_running():
    return subprocess.run(["pgrep", "-x", "Gemini"], capture_output=True).returncode == 0


def verify_backup():
    if not ORIG_BIN.is_file():
        sys.exit(f"missing backup binary: {ORIG_BIN}")
    digest = sha256(ORIG_BIN)
    if digest != ORIG_SHA256:
        sys.exit(f"backup binary hash mismatch: {digest}")
    for name, off, pristine, _ in PATCHES:
        actual = read_at(ORIG_BIN, off, len(pristine) // 2).hex()
        if actual != pristine:
            sys.exit(f"backup not pristine for {name} at {hex(off)}: {actual}")
    print(f"backup OK  sha256={digest}")


def check_patched(path):
    ok = True
    for name, off, _, patched in PATCHES:
        actual = read_at(path, off, len(patched) // 2).hex()
        if actual == patched:
            print(f"OK    {name} @ {hex(off)}")
        else:
            print(f"MISS  {name} @ {hex(off)}: {actual}")
            ok = False
    return ok


def apply_patches(path):
    for name, off, pristine, _ in PATCHES:
        actual = read_at(path, off, len(pristine) // 2).hex()
        if actual != pristine:
            sys.exit(f"refusing to patch {name} at {hex(off)}: found {actual}")
    with open(path, "r+b") as f:
        for name, off, _, patched in PATCHES:
            f.seek(off)
            f.write(bytes.fromhex(patched))
            print(f"patched {name} @ {hex(off)} -> {patched}")


def resign():
    cmd = [
        "codesign", "--force", "--sign", "-",
        "-i", "com.google.GeminiMacOS",
        "--entitlements", str(ENTITLEMENTS),
        str(APP),
    ]
    subprocess.run(cmd, check=True)
    subprocess.run(["codesign", "--verify", "--verbose=2", str(APP)], check=True)


def main():
    parser = argparse.ArgumentParser(description="Gemini.app 1.147.5.1526 repair kit")
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--check", action="store_true", help="verify installed app")
    group.add_argument("--dry-run", action="store_true", help="validate backup, patch nothing")
    args = parser.parse_args()

    if args.check:
        if not APP_BIN.is_file():
            sys.exit(f"missing app binary: {APP_BIN}")
        print(f"checking {APP_BIN}")
        patched = check_patched(APP_BIN)
        result = subprocess.run(["codesign", "--verify", "--verbose=2", str(APP)],
                                capture_output=True, text=True)
        print("signature OK" if result.returncode == 0 else "signature INVALID:\n" + result.stderr.strip())
        sys.exit(0 if patched and result.returncode == 0 else 1)

    verify_backup()
    if args.dry_run:
        print(f"ready: would restore {ORIG_BIN} -> {APP_BIN}, apply {len(PATCHES)} patches, re-sign")
        sys.exit(0)

    if app_running():
        sys.exit("Gemini is running; quit it first")
    if not APP_BIN.parent.is_dir():
        sys.exit(f"not found: {APP}")

    shutil.copy2(ORIG_BIN, APP_BIN)
    APP_BIN.chmod(0o755)
    print(f"restored {APP_BIN}")
    apply_patches(APP_BIN)
    resign()
    if not check_patched(APP_BIN):
        sys.exit("post-sign verification failed")
    print("done: launch with `open /Applications/Gemini.app`")


if __name__ == "__main__":
    main()
