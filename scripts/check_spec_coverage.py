#!/usr/bin/env python3
"""Fail if any METHOD + path in ``spec/openapi.json`` has no SDK method.

Usage: ``python scripts/check_spec_coverage.py [path/to/openapi.json]``
(defaults to the bundled snapshot). Exit code 1 on any gap.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Set, Tuple

from stampmitra._ops import OPERATIONS

HTTP_METHODS = {"get", "post", "put", "patch", "delete"}
ROOT = Path(__file__).resolve().parent.parent


def spec_operations(spec_path: Path) -> Set[Tuple[str, str]]:
    spec = json.loads(spec_path.read_text(encoding="utf-8"))
    return {(m.upper(), p) for p, item in spec["paths"].items() for m in item if m in HTTP_METHODS}


def main(argv: list[str]) -> int:
    spec_path = Path(argv[1]) if len(argv) > 1 else ROOT / "spec" / "openapi.json"
    spec_ops = spec_operations(spec_path)
    sdk_ops = {(op.method, op.path): op.name for op in OPERATIONS}
    missing = sorted(spec_ops - set(sdk_ops))
    extra = sorted(set(sdk_ops) - spec_ops)
    print(f"spec operations: {len(spec_ops)}; SDK operations: {len(sdk_ops)}")
    for method, path in missing:
        print(f"MISSING in SDK: {method} {path}")
    for method, path in extra:
        print(f"NOT in spec (SDK only): {method} {path} ({sdk_ops[(method, path)]})")
    if missing:
        print("FAIL: update src/stampmitra/_ops.py and the resource classes.")
        return 1
    print("OK: every spec operation has an SDK method.")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
