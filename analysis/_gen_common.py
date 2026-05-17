"""Shared output schema + helpers for gen_*.py marimo-extracted scripts.

Every gen_*.py emits a single JSON object on stdout when invoked with
--verbose-json. The schema is the contract the plugin's orchestrator
(orchestrate.py) and the email-ping flow (brieflow_review.py) read.

Schema:
{
  "status": "success" | "needs_review" | "failed",
  "outputs": {                       # config sections this script produces
    "preprocess": {...},
    "sbs": {...},
    ...
  },
  "metrics": {                       # numeric summaries for the operator
    "n_tiles": ...,
    "alignment_error_px": ...,
    ...
  },
  "visualizations": [                # PNG paths for review email
    {"path": "/path/to/viz.png", "caption": "..."},
    ...
  ],
  "review_required": bool,           # plugin pauses when True
  "review_prompt": "..."             # what the operator should look at
}

Exit code: 0 always (status field carries success/failure semantics) —
non-zero exit is reserved for "script crashed unexpectedly."
"""

from __future__ import annotations

import json
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass
class GenResult:
    status: str = "success"  # "success" | "needs_review" | "failed"
    outputs: dict[str, Any] = field(default_factory=dict)
    metrics: dict[str, Any] = field(default_factory=dict)
    visualizations: list[dict[str, str]] = field(default_factory=list)
    review_required: bool = False
    review_prompt: str = ""
    error: str = ""  # populated when status == "failed"

    def to_json(self) -> str:
        d = {
            "status": self.status,
            "outputs": self.outputs,
            "metrics": self.metrics,
            "visualizations": self.visualizations,
            "review_required": self.review_required,
            "review_prompt": self.review_prompt,
        }
        if self.status == "failed":
            d["error"] = self.error
        return json.dumps(d, indent=2, sort_keys=True, default=str)


def emit(result: GenResult) -> int:
    """Write GenResult JSON to stdout. Always returns exit code 0 — failure
    semantics live in the JSON `status` field, not exit code."""
    sys.stdout.write(result.to_json())
    sys.stdout.write("\n")
    sys.stdout.flush()
    return 0


def emit_failure(error_msg: str, review_prompt: str = "") -> int:
    """Convenience: emit a failed-status result with an error message.
    Plugin orchestrator escalates on status=failed."""
    return emit(
        GenResult(
            status="failed",
            error=error_msg,
            review_prompt=review_prompt
            or f"Script failed: {error_msg}. Manual investigation required.",
        )
    )


def add_arg_verbose_json(parser) -> None:
    """Add the --verbose-json flag (true by default — gen_* scripts always
    emit JSON; the flag exists for symmetry with future modes)."""
    parser.add_argument(
        "--verbose-json",
        action="store_true",
        default=True,
        help="Emit verbose JSON result to stdout (default: on).",
    )


def load_manifest(manifest_path: Path) -> dict:
    """Load the screen manifest YAML produced by brieflow-init."""
    import yaml

    with open(manifest_path) as f:
        return yaml.safe_load(f)


def manifest_default(manifest: dict, *keys: str, default: Any = None) -> Any:
    """Safely traverse a nested manifest dict; return default on any miss."""
    cur: Any = manifest
    for k in keys:
        if not isinstance(cur, dict) or k not in cur:
            return default
        cur = cur[k]
    return cur
