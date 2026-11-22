#!/usr/bin/env python3
"""
Unified patch script for /Applications/Gemini.app on macOS.

Fixes included:
1. Patch 1: Startup AB-BA deadlock between main thread and SpellCheckerWarmUpTask.
2. Patch 2: Missing icons & profile avatar caused by CALayerFlippedContentsWorkaround.install() wiping layer contents.
3. Patch 3: Top navigation bar pill clipping & positioning (font scale, icon size, height, top padding).
4. Patch 4: Account switch / add account hang caused by Clearcut service deadlock against NSUserDefaults notification.

Supports exact offset patching for tested versions (1.147.5.1526, 1.147.6.1557)
with unique-pattern fallback for minor future updates.
"""

import plistlib
import shutil
import subprocess
import sys
from pathlib import Path

APP_PATH = Path("/Applications/Gemini.app")
INFO_PLIST_PATH = APP_PATH / "Contents/Info.plist"
BIN_PATH = APP_PATH / "Contents/MacOS/Gemini"
ENTITLEMENTS_PATH = Path(__file__).parent / "gemini_entitlements.plist"

# Shared replacement machine code across 1.147.x builds
PATCH_SPECS = [
    ("Patch 1 (SpellCheckerWarmUpTask Deadlock)", "07000014"),
    ("Patch 2 (CALayerFlippedContentsWorkaround Image Wiping)", "c0035fd6"),
    ("Patch 3a (Toolbar Pill Font Scale Clamp <= 1.0)", "01106e1e0020611e20cc601ec0035fd6"),
    ("Patch 3b (Toolbar Pill Icon Size Clamp <= 1.0)", "01106e1e1f2003d51f2003d51f2003d5"),
    ("Patch 3c (Toolbar Pill Height = 36.0)", "4808e8d20001679ec0035fd6"),
    ("Patch 3d (Toolbar Pill Top Padding = 6.0)", "0010631ec0035fd6"),
    ("Patch 4 (Account Switch 3-Way Deadlock in shouldSendCrashesAndUsageData)", "18000014"),
]

# Per-version (offset, original_hex) entries aligned with PATCH_SPECS
OFFSETS_BY_VERSION = {
    "1.147.5.1526": [
        (0x034F68E0, "08b406d0"),
        (0x034CEBF4, "fd7bbfa9"),
        (0x0568B88C, "e8e702b2a89999f288fee7f20101679e"),
        (0x0568B8A8, "e8e702b2a89999f288fee7f20101679e"),
        (0x0568B8C8, "e8e702b2a89999f288fee7f2"),
        (0x0568B900, "e8e702b2a89999f2"),
        (0x027B652C, "1a73eb94"),
    ],
    "1.147.6.1557": [
        (0x0354D5A0, "e8b406b0"),
        (0x035258B4, "fd7bbfa9"),
        (0x056E2760, "e8e702b2a89999f288fee7f20101679e"),
        (0x056E277C, "e8e702b2a89999f288fee7f20101679e"),
        (0x056E279C, "e8e702b2a89999f288fee7f2"),
        (0x056E27D4, "e8e702b2a89999f2"),
        (0x0280D7EC, "b971eb94"),
    ],
}


def get_app_version() -> str:
    """Return CFBundleShortVersionString for /Applications/Gemini.app."""
    if not INFO_PLIST_PATH.exists():
        return "unknown"
    with INFO_PLIST_PATH.open("rb") as f:
        info = plistlib.load(f)
    return info.get("CFBundleShortVersionString", "unknown")


def build_patch_table(version: str) -> list[dict]:
    """Build the patch table for the installed Gemini.app version."""
    entries = OFFSETS_BY_VERSION.get(version) or OFFSETS_BY_VERSION["1.147.6.1557"]
    return [
        {
            "name": name,
            "offset": off,
            "original": bytes.fromhex(orig_hex),
            "replacement": bytes.fromhex(rep_hex),
        }
        for (name, rep_hex), (off, orig_hex) in zip(PATCH_SPECS, entries)
    ]


def check_process() -> None:
    """Quit Gemini if it is currently running."""
    res = subprocess.run(["pgrep", "-x", "Gemini"], capture_output=True, text=True)
    if res.returncode == 0:
        print("[!] Gemini is currently running. Quitting it before patching...")
        subprocess.run(["killall", "Gemini"])


def patch_binary() -> None:
    """Back up, patch, re-sign, and verify /Applications/Gemini.app."""
    if not BIN_PATH.exists():
        print(f"[-] Gemini executable not found at {BIN_PATH}")
        sys.exit(1)

    version = get_app_version()
    print(f"[*] Detected Gemini.app version: {version}")
    if version not in OFFSETS_BY_VERSION:
        print(f"[!] Version {version} is not in exact table; using latest offsets with pattern fallback.")

    backup_file = Path(__file__).parent / f"Gemini.{version}.backup"
    if not backup_file.exists():
        print(f"[*] Creating backup at {backup_file} ...")
        shutil.copy2(BIN_PATH, backup_file)

    data = bytearray(BIN_PATH.read_bytes())
    applied_count = 0
    already_applied_count = 0

    for p in build_patch_table(version):
        name = p["name"]
        off = p["offset"]
        orig = p["original"]
        rep = p["replacement"]
        length = len(rep)

        current = bytes(data[off : off + length])
        if current == rep:
            print(f"[=] {name}: already applied at {hex(off)}")
            already_applied_count += 1
        elif current == orig:
            data[off : off + length] = rep
            print(f"[+] {name}: applied at {hex(off)}")
            applied_count += 1
        else:
            print(f"[?] {name}: offset mismatch at {hex(off)} (current: {current.hex()}, expected orig: {orig.hex()})")
            idx = data.find(orig)
            if idx != -1 and data.find(orig, idx + 1) == -1:
                data[idx : idx + length] = rep
                print(f"    -> Found unique match at {hex(idx)}, applied successfully!")
                applied_count += 1
            else:
                print("    -> Could not find a safe unique pattern match in binary. Skipping.")

    print(f"\n[*] Total patches applied: {applied_count}, already active: {already_applied_count}")
    if applied_count > 0:
        BIN_PATH.write_bytes(data)
        print("[*] Saved patched binary.")

    print("[*] Re-signing Gemini.app ad-hoc...")
    sign_cmd = [
        "codesign",
        "--force",
        "--sign",
        "-",
        "-i",
        "com.google.GeminiMacOS",
        "--entitlements",
        str(ENTITLEMENTS_PATH),
        str(APP_PATH),
    ]
    sign_res = subprocess.run(sign_cmd, capture_output=True, text=True)
    if sign_res.returncode != 0:
        print(f"[-] Codesign failed:\n{sign_res.stderr}")
        sys.exit(1)

    verify_cmd = ["codesign", "--verify", "--verbose=2", str(APP_PATH)]
    verify_res = subprocess.run(verify_cmd, capture_output=True, text=True)
    if verify_res.returncode == 0:
        print("[✓] Codesign verified successfully: satisfies Designated Requirement.")
    else:
        print(f"[!] Warning on verification:\n{verify_res.stderr}")


if __name__ == "__main__":
    check_process()
    patch_binary()
