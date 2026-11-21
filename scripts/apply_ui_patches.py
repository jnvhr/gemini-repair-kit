from pathlib import Path

BIN_PATH = Path("/Applications/Gemini.app/Contents/MacOS/Gemini")

with BIN_PATH.open("r+b") as f:
    # Assert Patch 1 (SpellCheckerWarmUpTask deadlock fix) is already present
    f.seek(0x034F68E0)
    p1 = f.read(4)
    assert p1 == bytes.fromhex("07000014"), f"Unexpected Patch 1 bytes: {p1.hex()}"

    patches = [
        (
            "Patch 2 (CALayerFlippedContentsWorkaround.install)",
            0x034CEBF4,
            bytes.fromhex("fd7bbfa9"),
            bytes.fromhex("c0035fd6"),
        ),
        (
            "Patch 3a (clampedToolbarFontScale)",
            0x0568B88C,
            bytes.fromhex("e8e702b2a89999f288fee7f20101679e"),
            bytes.fromhex("01106e1e0020611e20cc601ec0035fd6"),
        ),
        (
            "Patch 3b (iconButtonSize)",
            0x0568B8A8,
            bytes.fromhex("e8e702b2a89999f288fee7f20101679e"),
            bytes.fromhex("01106e1e1f2003d51f2003d51f2003d5"),
        ),
        (
            "Patch 3c (toolbarPillHeight)",
            0x0568B8C8,
            bytes.fromhex("e8e702b2a89999f288fee7f2"),
            bytes.fromhex("4808e8d20001679ec0035fd6"),
        ),
        (
            "Patch 3d (toolbarPillTopPadding)",
            0x0568B900,
            bytes.fromhex("e8e702b2a89999f2"),
            bytes.fromhex("00e4006fc0035fd6"),
        ),
    ]

    # Validate all expected byte sequences before writing anything
    for name, off, expected, replacement in patches:
        assert len(expected) == len(replacement), f"Length mismatch for {name}"
        f.seek(off)
        actual = f.read(len(expected))
        assert actual == expected, (
            f"{name} at {hex(off)}: expected {expected.hex()}, got {actual.hex()}"
        )

    # Apply all patches
    for name, off, _, replacement in patches:
        f.seek(off)
        f.write(replacement)
        print(f"Applied {name} at {hex(off)}: {replacement.hex()}")

print("All assertions passed and patches written cleanly.")
