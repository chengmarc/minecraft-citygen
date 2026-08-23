"""sign_text reads both the legacy (1.19.4) and modern sign schemas."""
from engine.world.marker_extract import sign_text


def test_reads_legacy_text1_4():
    be = {
        "Text1": '{"text":"01_big"}',
        "Text2": '{"text":"_2x2"}',
        "Text3": '{"text":"_deadend"}',
        "Text4": '{"text":""}',
    }
    assert sign_text(be) == "01_big _2x2 _deadend"


def test_reads_modern_front_back_text():
    be = {"front_text": {"messages": ["stack: 5-7", "", "appearance: 4-6", ""]}}
    assert sign_text(be) == "stack: 5-7 appearance: 4-6"


def test_empty_sign_is_empty_string():
    assert sign_text({"Text1": '{"text":""}', "Text2": '""'}) == ""
