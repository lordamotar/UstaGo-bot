"""Where a user came from: parsing of the /start deep-link payload.

Links look like  https://t.me/<bot>?start=<payload>  with payload one of:
    ref_<telegram_id>   a user's referral link
    src_<tag>           a campaign link (instagram, flyer_almaty, ...), made in the admin panel
    (nothing)           the user found the bot on their own
"""
import re
from typing import Optional, Tuple

SOURCE_DIRECT = "direct"
SOURCE_REFERRAL = "referral"
SOURCE_OTHER = "other"
CAMPAIGN_PREFIX = "src:"

_TAG_RE = re.compile(r"[^a-z0-9_-]")
MAX_TAG_LEN = 40


def normalize_tag(raw: str) -> str:
    """Campaign tag in canonical form: lower case, only [a-z0-9_-], at most MAX_TAG_LEN characters."""
    return _TAG_RE.sub("", (raw or "").strip().lower())[:MAX_TAG_LEN]


def parse_start_payload(args: Optional[str]) -> Tuple[str, Optional[str]]:
    """Returns (kind, value): kind is 'direct' | 'referral' | 'campaign' | 'other'.

    referral -> value is the inviter's telegram id (str of digits); campaign -> the normalized tag;
    other -> the raw payload (cut to 64 characters); direct -> None.
    """
    payload = (args or "").strip()
    if not payload:
        return "direct", None
    if payload.startswith("ref_"):
        value = payload[4:]
        if value.isdigit() and len(value) <= 15:
            return "referral", value
        return "other", payload[:64]
    if payload.startswith("src_"):
        tag = normalize_tag(payload[4:])
        if tag:
            return "campaign", tag
        return "other", payload[:64]
    return "other", payload[:64]


def source_label(kind: str, value: Optional[str] = None, inviter_found: bool = True) -> str:
    """The string stored in users.acquisition_source."""
    if kind == "referral":
        return SOURCE_REFERRAL if inviter_found else SOURCE_DIRECT
    if kind == "campaign":
        return CAMPAIGN_PREFIX + value
    if kind == "other":
        return SOURCE_OTHER
    return SOURCE_DIRECT


def pretty_source(source: Optional[str]) -> str:
    """Human-readable name for the panel."""
    if not source:
        return "Неизвестно (до учёта источников)"
    if source == SOURCE_DIRECT:
        return "Напрямую (без ссылки)"
    if source == SOURCE_REFERRAL:
        return "Приглашение друга"
    if source == SOURCE_OTHER:
        return "Другая ссылка"
    if source.startswith(CAMPAIGN_PREFIX):
        return "Кампания: " + source[len(CAMPAIGN_PREFIX):]
    return source
