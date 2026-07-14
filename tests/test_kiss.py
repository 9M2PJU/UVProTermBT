import random

from uvprotermbt.kiss import FEND, KissDecoder, encode_frame


def test_encode_escapes_special_bytes():
    payload = bytes([0x01, FEND, 0x02, 0xDB, 0x03])
    frame = encode_frame(payload)
    assert frame == bytes([0xC0, 0x00, 0x01, 0xDB, 0xDC, 0x02, 0xDB, 0xDD, 0x03, 0xC0])


def test_decode_single_frame_one_chunk():
    payload = b"hello"
    frame = encode_frame(payload)
    dec = KissDecoder()
    frames = dec.feed(frame)
    assert len(frames) == 1
    assert frames[0].port == 0
    assert frames[0].command == 0
    assert frames[0].payload == payload


def test_decode_multiple_frames_one_chunk():
    data = encode_frame(b"one") + encode_frame(b"two") + encode_frame(b"three")
    dec = KissDecoder()
    frames = dec.feed(data)
    assert [f.payload for f in frames] == [b"one", b"two", b"three"]


def test_decode_skips_empty_frame():
    data = bytes([FEND, FEND]) + encode_frame(b"real")
    dec = KissDecoder()
    frames = dec.feed(data)
    assert len(frames) == 1
    assert frames[0].payload == b"real"


def test_decode_fragmented_across_feeds():
    payload = bytes(range(50))
    data = encode_frame(payload)
    for split in range(len(data) + 1):
        dec = KissDecoder()
        frames = dec.feed(data[:split])
        frames += dec.feed(data[split:])
        assert len(frames) == 1, f"split={split}"
        assert frames[0].payload == payload, f"split={split}"


def test_decode_malformed_escape_resyncs():
    # FESC followed by a byte that isn't TFEND/TFESC discards the
    # in-progress frame; decoding resyncs on the next FEND.
    bad = bytes([FEND, 0x00, 0x01, 0xDB, 0x99, 0x02])
    good = encode_frame(b"ok")
    dec = KissDecoder()
    frames = dec.feed(bad + good)
    assert len(frames) == 1
    assert frames[0].payload == b"ok"


def test_decode_large_payload():
    payload = bytes((i * 37) % 256 for i in range(300))
    data = encode_frame(payload)
    dec = KissDecoder()
    frames = dec.feed(data)
    assert len(frames) == 1
    assert frames[0].payload == payload


def test_decode_fuzz_noise_with_embedded_frames():
    rng = random.Random(1234)
    known_payloads = [bytes(rng.randrange(256) for _ in range(rng.randrange(1, 40))) for _ in range(20)]

    stream = bytearray()
    for payload in known_payloads:
        # Random noise between frames, avoiding accidental FEND bytes so
        # noise can't be mistaken for real frame boundaries in this check.
        noise_len = rng.randrange(0, 10)
        stream += bytes(rng.randrange(1, 0xC0) for _ in range(noise_len))
        stream += encode_frame(payload)

    dec = KissDecoder()
    frames: list = []
    data = bytes(stream)
    pos = 0
    while pos < len(data):
        chunk_len = rng.randrange(1, 8)
        chunk = data[pos : pos + chunk_len]
        frames += dec.feed(chunk)
        pos += chunk_len

    assert [f.payload for f in frames] == known_payloads
