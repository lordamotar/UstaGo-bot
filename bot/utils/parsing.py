import re
from typing import Optional

_AMOUNT_RE = re.compile(r"\d(?:[\d\s  ]*\d)?")


def parse_amount(text: Optional[str]) -> Optional[int]:
    """Extracts the first amount from free text.

    "15000" -> 15000, "5 000 тг" -> 5000, "от 5 000 до 7 000" -> 5000, "договорная" -> None.
    """
    match = _AMOUNT_RE.search(text or "")
    if not match:
        return None
    return int(re.sub(r"\D", "", match.group()))
