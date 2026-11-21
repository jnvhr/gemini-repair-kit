from pathlib import Path

BIN_PATH = Path("/Applications/Gemini.app/Contents/MacOS/Gemini")
OFFSET = 0x0568B900
EXPECTED = bytes.fromhex("00e4006fc0035fd6")
REPLACEMENT = bytes.fromhex("0010631e")

with BIN_PATH.open("r+b") as f:
    f.seek(OFFSET)
    actual = f.read(len(EXPECTED))
    assert actual == EXPECTED, (
        f"Unexpected bytes at {hex(OFFSET)}: expected {EXPECTED.hex()}, got {actual.hex()}"
    )
    f.seek(OFFSET)
    f.write(REPLACEMENT)

print(f"Updated Patch 3d at {hex(OFFSET)}: {REPLACEMENT.hex()}")
