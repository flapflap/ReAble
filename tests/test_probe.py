import struct
import zlib

from reable.probe import classify


def test_classify_known_containers():
    assert classify(b"") == "empty"
    assert classify(struct.pack("<I", 100) + bytes.fromhex("0000000001000000") + b"x" * 100) == "ni-classic"
    assert classify(bytes.fromhex("0200000003000000") + struct.pack("<I", 20) + bytes.fromhex("0007") + zlib.compress(b"{}")) == "ni-msgpack"
    z = zlib.compress(b'{"a":1}')
    assert classify(struct.pack("<IIII", 0x688ad5, 1, len(z) + 4, 7) + z) == "izotope"
    assert classify(b"VstW" + b"\0" * 20) == "juce-vstw"
    assert classify(b"CcnK" + b"\0" * 20) == "fxp"
    assert classify(b'<?xml version="1.0"?>') == "xml"
    assert classify(b"B$iN" + bytes.fromhex("0100000002000000") + b"\x01" * 30) == "ni-tagged"
    assert classify(bytes(range(200, 256)) * 3) == "opaque"
