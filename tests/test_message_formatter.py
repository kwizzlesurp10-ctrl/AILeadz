"""
Tests for livebench/agent/message_formatter.py
"""

from __future__ import annotations

import base64

import pytest

from livebench.agent.message_formatter import (
    format_result_for_logging,
    format_tool_result_message,
    _format_image_message,
    _format_multimodal_message,
    _format_text_message,
)


# ---------------------------------------------------------------------------
# format_result_for_logging
# ---------------------------------------------------------------------------

class TestFormatResultForLogging:
    def test_pdf_images_omits_binary(self):
        result = {
            "type": "pdf_images",
            "images": [b"fake_image_1", b"fake_image_2"],
            "approximate_pages": 8,
        }
        logged = format_result_for_logging(result)
        assert "pdf_images" in logged
        assert "binary data omitted" in logged
        assert "image_count" in logged
        assert "approximate_pages" in logged
        assert "fake_image" not in logged

    def test_pptx_images_omits_binary(self):
        result = {
            "type": "pptx_images",
            "images": [b"slide1", b"slide2", b"slide3"],
            "slide_count": 3,
        }
        logged = format_result_for_logging(result)
        assert "pptx_images" in logged
        assert "binary data omitted" in logged
        assert "slide_count" in logged
        assert "slide1" not in logged

    def test_image_type_omits_binary(self):
        result = {"type": "image", "image_data": "data:image/png;base64,abc123"}
        logged = format_result_for_logging(result)
        assert "image" in logged
        assert "binary data omitted" in logged

    def test_plain_text_result(self):
        result = "Hello, world!"
        logged = format_result_for_logging(result)
        assert logged == "Hello, world!"

    def test_long_text_is_truncated(self):
        result = "x" * 2000
        logged = format_result_for_logging(result)
        assert len(logged) <= 1015  # 1000 chars + "... (truncated)"
        assert "truncated" in logged

    def test_short_text_not_truncated(self):
        result = "short text"
        logged = format_result_for_logging(result)
        assert logged == "short text"
        assert "truncated" not in logged

    def test_dict_result_not_binary(self):
        result = {"status": "ok", "value": 42}
        logged = format_result_for_logging(result)
        # Falls through to str(result)
        assert "ok" in logged

    def test_pdf_approximate_pages_fallback(self):
        result = {
            "type": "pdf_images",
            "images": [b"p1", b"p2"],
            # no 'approximate_pages' key — should default to image_count * 4
        }
        logged = format_result_for_logging(result)
        assert "approximate_pages" in logged
        # 2 images * 4 = 8
        assert "8" in logged


# ---------------------------------------------------------------------------
# _format_multimodal_message
# ---------------------------------------------------------------------------

class TestFormatMultimodalMessage:
    def test_pdf_images_structure(self):
        images = [b"\x89PNG\r\n", b"\x89PNG\r\n"]
        tool_result = {
            "type": "pdf_images",
            "images": images,
            "image_count": 2,
            "approximate_pages": 8,
        }
        msg = _format_multimodal_message("read_file", tool_result, activity_completed=False)

        assert msg["role"] == "user"
        content = msg["content"]
        assert isinstance(content, list)
        # First element is a text summary
        assert content[0]["type"] == "text"
        assert "PDF" in content[0]["text"]
        # Remaining are image_url entries
        assert len(content) == 3  # 1 text + 2 images
        for img_item in content[1:]:
            assert img_item["type"] == "image_url"
            assert img_item["image_url"]["url"].startswith("data:image/png;base64,")

    def test_pptx_images_structure(self):
        images = [b"slide_data"]
        tool_result = {
            "type": "pptx_images",
            "images": images,
            "slide_count": 1,
        }
        msg = _format_multimodal_message("read_pptx", tool_result, activity_completed=False)
        content = msg["content"]
        assert content[0]["type"] == "text"
        assert "PowerPoint" in content[0]["text"] or "slides" in content[0]["text"].lower()

    def test_activity_completed_message_appended(self):
        tool_result = {
            "type": "pdf_images",
            "images": [b"img"],
            "image_count": 1,
            "approximate_pages": 4,
        }
        msg = _format_multimodal_message("read_file", tool_result, activity_completed=True)
        assert "completed" in msg["content"][0]["text"].lower()

    def test_images_are_base64_encoded(self):
        raw = b"binary image data"
        expected_b64 = base64.b64encode(raw).decode("utf-8")
        tool_result = {"type": "pdf_images", "images": [raw], "image_count": 1, "approximate_pages": 4}
        msg = _format_multimodal_message("read_file", tool_result, activity_completed=False)
        img_item = msg["content"][1]
        assert expected_b64 in img_item["image_url"]["url"]

    def test_unknown_type_falls_back_gracefully(self):
        tool_result = {"type": "unknown_type", "images": [b"x"]}
        msg = _format_multimodal_message("tool", tool_result, activity_completed=False)
        assert msg["role"] == "user"
        assert isinstance(msg["content"], list)


# ---------------------------------------------------------------------------
# _format_image_message
# ---------------------------------------------------------------------------

class TestFormatImageMessage:
    def test_structure(self):
        tool_result = {"type": "image", "image_data": "data:image/png;base64,abc"}
        msg = _format_image_message("read_image", tool_result, activity_completed=False)
        assert msg["role"] == "user"
        content = msg["content"]
        assert content[0]["type"] == "text"
        assert content[1]["type"] == "image_url"
        assert content[1]["image_url"]["url"] == "data:image/png;base64,abc"

    def test_activity_completed_text_appended(self):
        tool_result = {"type": "image", "image_data": "data:image/png;base64,abc"}
        msg = _format_image_message("read_image", tool_result, activity_completed=True)
        assert "completed" in msg["content"][0]["text"].lower()


# ---------------------------------------------------------------------------
# _format_text_message
# ---------------------------------------------------------------------------

class TestFormatTextMessage:
    def test_basic_text_result(self):
        msg = _format_text_message("some_tool", "the output", {}, activity_completed=False)
        assert msg["role"] == "user"
        assert "the output" in msg["content"]

    def test_decide_activity_work(self):
        msg = _format_text_message(
            "decide_activity",
            "result",
            {"activity": "work"},
            activity_completed=False,
        )
        assert "WORK" in msg["content"]

    def test_decide_activity_learn(self):
        msg = _format_text_message(
            "decide_activity",
            "result",
            {"activity": "learn"},
            activity_completed=False,
        )
        assert "LEARN" in msg["content"]

    def test_activity_completed_flag(self):
        msg = _format_text_message("other_tool", "done", {}, activity_completed=True)
        assert "completed" in msg["content"].lower()


# ---------------------------------------------------------------------------
# format_tool_result_message (dispatcher)
# ---------------------------------------------------------------------------

class TestFormatToolResultMessage:
    def test_dispatches_pdf_images(self):
        tool_result = {
            "type": "pdf_images",
            "images": [b"data"],
            "image_count": 1,
            "approximate_pages": 4,
        }
        msg = format_tool_result_message("read_file", tool_result, {}, activity_completed=False)
        assert isinstance(msg["content"], list)

    def test_dispatches_pptx_images(self):
        tool_result = {"type": "pptx_images", "images": [b"slide"], "slide_count": 1}
        msg = format_tool_result_message("read_pptx", tool_result, {}, activity_completed=False)
        assert isinstance(msg["content"], list)

    def test_dispatches_image(self):
        tool_result = {"type": "image", "image_data": "data:image/png;base64,xyz"}
        msg = format_tool_result_message("read_img", tool_result, {}, activity_completed=False)
        assert isinstance(msg["content"], list)

    def test_dispatches_text_for_plain_string(self):
        msg = format_tool_result_message("my_tool", "plain text result", {}, activity_completed=False)
        assert isinstance(msg["content"], str)
        assert "plain text result" in msg["content"]

    def test_dispatches_text_for_non_binary_dict(self):
        tool_result = {"type": "some_other", "data": "value"}
        msg = format_tool_result_message("my_tool", tool_result, {}, activity_completed=False)
        assert isinstance(msg["content"], str)
