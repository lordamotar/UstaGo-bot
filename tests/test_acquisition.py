"""Parsing of /start deep links (no database needed)."""
import pytest

from bot.utils.acquisition import normalize_tag, parse_start_payload, pretty_source, source_label


@pytest.mark.parametrize("args,expected", [
    (None, ("direct", None)),
    ("", ("direct", None)),
    ("   ", ("direct", None)),
    ("ref_12345", ("referral", "12345")),
    ("ref_", ("other", "ref_")),
    ("ref_abc", ("other", "ref_abc")),
    ("ref_1" + "0" * 20, ("other", "ref_1" + "0" * 20)),   # not a Telegram id
    ("src_Instagram", ("campaign", "instagram")),
    ("src_flyer-Almaty_2", ("campaign", "flyer-almaty_2")),
    ("src_", ("other", "src_")),
    ("src_!!!", ("other", "src_!!!")),
    ("hello", ("other", "hello")),
])
def test_parse_start_payload(args, expected):
    assert parse_start_payload(args) == expected


def test_payload_is_cut_to_a_safe_length():
    kind, value = parse_start_payload("x" * 500)
    assert kind == "other" and len(value) == 64


def test_tag_is_normalized_and_limited():
    assert normalize_tag("  Ins ta/gram! ") == "instagram"
    assert len(normalize_tag("a" * 200)) == 40
    assert normalize_tag("!!!") == ""


def test_source_labels():
    assert source_label("direct", None) == "direct"
    assert source_label("referral", "1", inviter_found=True) == "referral"
    assert source_label("referral", "1", inviter_found=False) == "direct"   # unknown inviter: not counted as an invitation
    assert source_label("campaign", "insta") == "src:insta"
    assert source_label("other", "zzz") == "other"


def test_pretty_source():
    assert "до учёта" in pretty_source(None)
    assert pretty_source("src:insta") == "Кампания: insta"
    assert pretty_source("referral") == "Приглашение друга"
