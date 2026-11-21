# Gemini.app Repair Kit (macOS)

Community binary patches for `/Applications/Gemini.app` (`com.google.GeminiMacOS`, Apple Silicon / ARM64, tested on version `1.147.5.1526` on macOS 15.8.3) that fix startup hangs, missing UI icons/avatars, clipped top-navbar pills, and account-switching freezes.

> **Disclaimer:** This is an unofficial community patch kit. It modifies your local `/Applications/Gemini.app` binary and re-signs it ad-hoc. No proprietary Google binaries are included in this repository.

## What This Fixes

1. **Patch 1 (`0x034F68E0`) — Startup AB-BA Deadlock**
   - Skips the background `SpellCheckerWarmUpTask` that deadlocks against main-thread `OmnichatWindow` initialization on launch.
2. **Patch 2 (`0x034CEBF4`) — Missing Icons & Profile Avatar**
   - Disables `CALayerFlippedContentsWorkaround.install()`, which erroneously calls `[layer setNeedsDisplay]` on `SwiftUI.ImageLayer` instances on macOS `< 26.2` and wipes their rendered contents.
3. **Patch 3a–3d (`0x0568B88C`–`0x0568B900`) — Top Navbar Pill Clipping & Alignment**
   - Clamps toolbar font scale and icon button scale to `1.0`, sets toolbar pill height to `36.0pt`, and sets top padding to `6.0pt` so titlebar pills are not vertically clipped.
4. **Patch 4 (`0x027B652C`) — Account Switch / Add Account Freeze**
   - Fixes a 3-way lock inversion deadlock in `ClearcutServiceImpl.shouldSendCrashesAndUsageData` by bypassing a lazy `NSUserDefaults.setBool(true, ...)` write that triggered `NSUserDefaultsDidChangeNotification` synchronously onto the main thread while Clearcut held its lock.

## Quick Start

```bash
git clone https://github.com/jnvhr/gemini-repair-kit.git
cd gemini-repair-kit
python3 scripts/patch_gemini.py
```

`scripts/patch_gemini.py` will:
1. Quit `Gemini` if it is currently running.
2. Back up your local `/Applications/Gemini.app/Contents/MacOS/Gemini` to `scripts/Gemini.backup` (ignored by git).
3. Apply all 7 byte patches (with unique-pattern fallback for minor build offset shifts).
4. Re-sign `/Applications/Gemini.app` ad-hoc with `scripts/gemini_entitlements.plist` and verify the signature.

### Note on macOS Keychain Prompts

Because patching changes the binary and re-signs it ad-hoc, its `cdhash` changes from Google's original signature. The first time you launch or switch into each Google account after patching, macOS will ask for your login Keychain password for Gemini's credential stores (`DeviceAccountUUIDStore`, `DeviceAccountKeyStore`, `OnboardingCohort.PROD`). Click **Always Allow** once per account and macOS will remember this patched binary's `cdhash` on future switches.

## Repository Contents

| Path | Purpose |
|---|---|
| `scripts/patch_gemini.py` | In-place patcher with unique-pattern fallback and ad-hoc re-signing |
| `scripts/gemini_entitlements.plist` | Entitlements used for ad-hoc re-signing (sandbox disabled to match original app) |
| `scripts/apply_ui_patches.py`, `scripts/update_patch3d.py` | Individual UI patch scripts kept for reference |
| `restore_gemini.py` | Exact-version (`1.147.5.1526`) restore/check/dry-run tool (requires a local `original-backup/Gemini` binary) |
| `SHA256SUMS` | SHA-256 integrity manifest |

## Restore & Verification (`restore_gemini.py`)

If you keep a pristine `1.147.5.1526` binary in `original-backup/Gemini`:

```bash
python3 restore_gemini.py --check    # verify installed app has all 7 patches + valid signature
python3 restore_gemini.py --dry-run  # validate backup and print patch plan
python3 restore_gemini.py            # quit Gemini first; restore + patch + sign
```

## License

[MIT](LICENSE)
