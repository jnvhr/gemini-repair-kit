#!/usr/bin/env python3
"""
Unified patch script for /Applications/Gemini.app on macOS.

Fixes included:
1. Patch 1: Startup AB-BA deadlock between main thread and SpellCheckerWarmUpTask.
2. Patch 2: Missing icons & profile avatar caused by CALayerFlippedContentsWorkaround.install() wiping layer contents.
3. Patch 3: Top navigation bar pill clipping & positioning (font scale, icon size, height, top padding).
4. Patch 4: Account switch / add account hang caused by Clearcut service deadlock against NSUserDefaults notification.

Supports both direct byte offset patching (for identical version 1.147.5.1526)
and pattern-based / symbol-assisted search for minor future updates.
"""

import os
import shutil
import subprocess
import sys
from pathlib import Path

APP_PATH = Path("/Applications/Gemini.app")
BIN_PATH = APP_PATH / "Contents/MacOS/Gemini"
ENTITLEMENTS_PATH = Path(__file__).parent / "gemini_entitlements.plist"

PATCHES_EXACT = [
    {
        "name": "Patch 1 (SpellCheckerWarmUpTask Deadlock)",
        "offset": 0x034F68E0,
        "original": bytes.fromhex("08b406d0"),
        "replacement": bytes.fromhex("07000014"),  # b 0x1034f68fc
    },
    {
        "name": "Patch 2 (CALayerFlippedContentsWorkaround Image Wiping)",
        "offset": 0x034CEBF4,
        "original": bytes.fromhex("fd7bbfa9"),
        "replacement": bytes.fromhex("c0035fd6"),  # ret
    },
    {
        "name": "Patch 3a (Toolbar Pill Font Scale Clamp <= 1.0)",
        "offset": 0x0568B88C,
        "original": bytes.fromhex("e8e702b2a89999f288fee7f20101679e"),
        "replacement": bytes.fromhex("01106e1e0020611e20cc601ec0035fd6"),
    },
    {
        "name": "Patch 3b (Toolbar Pill Icon Size Clamp <= 1.0)",
        "offset": 0x0568B8A8,
        "original": bytes.fromhex("e8e702b2a89999f288fee7f20101679e"),
        "replacement": bytes.fromhex("01106e1e1f2003d51f2003d51f2003d5"),
    },
    {
        "name": "Patch 3c (Toolbar Pill Height = 36.0)",
        "offset": 0x0568B8C8,
        "original": bytes.fromhex("e8e702b2a89999f288fee7f2"),
        "replacement": bytes.fromhex("4808e8d20001679ec0035fd6"),
    },
    {
        "name": "Patch 3d (Toolbar Pill Top Padding = 6.0)",
        "offset": 0x0568B900,
        "original": bytes.fromhex("e8e702b2a89999f2"),
        "replacement": bytes.fromhex("0010631ec0035fd6"),
    },
    {
        "name": "Patch 4 (Account Switch 3-Way Deadlock in shouldSendCrashesAndUsageData)",
        "offset": 0x027B652C,
        "original": bytes.fromhex("1a73eb94"),
        "replacement": bytes.fromhex("18000014"),  # b 0x1027b658c
    },
]

def check_process():
    res = subprocess.run(["pgrep", "-x", "Gemini"], capture_output=True, text=True)
    if res.returncode == 0:
        print("[!] Gemini is currently running. Quitting it before patching...")
        subprocess.run(["killall", "Gemini"])

def patch_binary():
    if not BIN_PATH.exists():
        print(f"[-] Gemini executable not found at {BIN_PATH}")
        sys.exit(1)

    # Make a backup first outside the app bundle
    backup_file = Path(__file__).parent / "Gemini.backup"
    if not backup_file.exists():
        print(f"[*] Creating backup at {backup_file} ...")
        shutil.copy2(BIN_PATH, backup_file)

    data = bytearray(BIN_PATH.read_bytes())
    applied_count = 0
    already_applied_count = 0

    for p in PATCHES_EXACT:
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
            # Attempt pattern search
            idx = data.find(orig)
            if idx != -1 and data.find(orig, idx + 1) == -1:
                data[idx : idx + length] = rep
                print(f"    -> Found unique match at {hex(idx)}, applied successfully!")
                applied_count += 1
            else:
                print(f"    -> Could not find a safe unique pattern match in binary. Skipping.")

    print(f"\n[*] Total patches applied: {applied_count}, already active: {already_applied_count}")
    if applied_count > 0:
        BIN_PATH.write_bytes(data)
        print("[*] Saved patched binary.")

    # Always re-sign ad-hoc with required entitlements
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
