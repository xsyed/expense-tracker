from __future__ import annotations

import re

from .models import MerchantRule

_PHONE_RE = re.compile(r"\b\d{3}[-.]?\d{3,4}[-.]?\d{4}\b")
_LONG_DIGITS_RE = re.compile(r"\b\d{10,}\b")
_URL_RE = re.compile(r"https?://\S+|www\.\S+|\S+\.(?:com|co|ca)/\S+")
_STORE_REF_RE = re.compile(r"#\d+\w*")
_STAR_CODE_RE = re.compile(r"\*[a-z0-9]{5,}")
_MASKED_CARD_RE = re.compile(r"\*{3,}\d+")
_DOLLAR_RE = re.compile(r"\$[\d.]+")
_LOCATION_RE = re.compile(
    r"\b(?:toronto|vancouver|calgary|edmonton|ottawa|montreal|mississauga|brampton|hamilton|winnipeg"
    r"|on|ab|bc|qc|sk|mb|ns|nb|nl|pe|nt|yt|nu|ca)\b"
)
_STAR_SEP_RE = re.compile(r"\*")
_MULTI_SPACE_RE = re.compile(r"\s+")
_TRAILING_PUNCT_RE = re.compile(r"[,;:\-.]+$")


def normalize_merchant(description: str) -> str:
    text = description.lower()
    text = _PHONE_RE.sub("", text)
    text = _LONG_DIGITS_RE.sub("", text)
    text = _URL_RE.sub("", text)
    text = _STORE_REF_RE.sub("", text)
    text = _STAR_CODE_RE.sub("", text)
    text = _MASKED_CARD_RE.sub("", text)
    text = _DOLLAR_RE.sub("", text)
    text = _LOCATION_RE.sub("", text)
    text = _STAR_SEP_RE.sub(" ", text)
    text = _MULTI_SPACE_RE.sub(" ", text)
    text = _TRAILING_PUNCT_RE.sub("", text)
    text = text.strip()
    if not text:
        return description.lower().strip()
    return text


def load_merchant_rules(user_id: int) -> dict[str, int]:
    return dict(MerchantRule.objects.filter(user_id=user_id).values_list("normalized_name", "category_id"))


def match_merchant(description: str, rules: dict[str, int]) -> int | None:
    return rules.get(normalize_merchant(description))
