from __future__ import annotations

from pathlib import Path

from django.conf import settings
from django.contrib.staticfiles.storage import StaticFilesStorage

_ROOT = Path(__file__).resolve().parent.parent


def _git_version() -> str:
    try:
        head = (_ROOT / ".git" / "HEAD").read_text().strip()
        if head.startswith("ref: "):
            ref_path = _ROOT / ".git" / head[5:]
            if ref_path.exists():
                return ref_path.read_text().strip()[:7]
            for line in (_ROOT / ".git" / "packed-refs").read_text().splitlines():
                if not line.startswith("#") and line.endswith(head[5:]):
                    return line.split()[0][:7]
            return "0"
        return head[:7]
    except OSError:
        return "0"


_VERSION: str = getattr(settings, "STATIC_VERSION", "") or _git_version()


class VersionedStaticFilesStorage(StaticFilesStorage):
    def url(self, name: str | None) -> str:
        base = super().url(name)
        return f"{base}?v={_VERSION}"
