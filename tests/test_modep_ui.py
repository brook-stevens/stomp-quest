import json

import modep_ui


def test_render_frame_returns_16_bit_frame():
    frame = modep_ui.render_frame("Test Board", 12.3)

    assert len(frame) == 320 * 240 * 2


def test_read_feedback_expires_after_two_seconds(tmp_path):
    feedback_file = tmp_path / "feedback.json"
    feedback_file.write_text(json.dumps({"message": "Next", "timestamp": 10.0}))

    assert modep_ui.read_feedback(str(feedback_file), now=11.9) == "Next"
    assert modep_ui.read_feedback(str(feedback_file), now=12.0) is None


def test_write_frame_skips_unchanged_bytes(tmp_path):
    framebuffer = tmp_path / "framebuffer"
    frame = b"frame"

    cached = modep_ui.write_frame(frame, str(framebuffer))
    cached = modep_ui.write_frame(frame, str(framebuffer), cached)

    assert cached == frame
    assert framebuffer.read_bytes() == frame
