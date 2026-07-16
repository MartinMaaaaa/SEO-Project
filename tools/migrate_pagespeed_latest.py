#!/usr/bin/env python3
"""Back up and compact legacy PageSpeed history into latest-only storage."""

from __future__ import annotations

import json
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from apps.api.services.pagespeed_service import compact_legacy_history


def main() -> None:
    result = compact_legacy_history()
    # The result contains counts and a sanitized relative backup reference only.
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
