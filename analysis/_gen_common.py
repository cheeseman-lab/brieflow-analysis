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


def load_interview(interview_path: Path, notebook: str) -> tuple[dict, dict]:
    """Read the screen's interview.json, filter to one notebook's rows.

    Returns (interview, inputs):
      - interview: the full interview dict (kept for write-back via write_interview_values)
      - inputs:    flat dict mapping `param_name` → resolved value.

    Resolution rule per row:
      - If `value` is set (operator/auto-probe/tuned-confirmed/gen), use it.
      - Else if bucket is `auto` or `override`, fall back to the parsed
        `default` field from the CSV taxonomy (so e.g. `nuclei_flow_threshold`
        gets 0.4 even when the operator didn't touch it).
      - Else (bucket=user or tuned, with value=None): stays None. User-bucket
        nulls become "required" errors; tuned-bucket nulls drive review_required.
    """
    with open(interview_path) as f:
        interview = json.load(f)
    inputs: dict = {}
    for row in interview.get("params", []):
        if row.get("notebook") != notebook:
            continue
        name = row["param_name"]
        value = row.get("value")
        if value is None and row.get("bucket") in ("auto", "override"):
            value = _parse_csv_default(row.get("default"))
        inputs[name] = value
    return interview, inputs


def _parse_csv_default(default_str):
    """Parse the CSV `default` string into a Python value. Returns None for
    sentinels that mean 'no literal default' (e.g. 'auto-derived', '—').
    Handles numbers, bools, nulls, and simple list/dict literals via yaml."""
    if default_str is None:
        return None
    s = str(default_str).strip()
    if s == "" or s in ("—", "-", "auto-derived", "derived"):
        return None
    if s.lower() == "null":
        return None
    if s.lower() == "true":
        return True
    if s.lower() == "false":
        return False
    try:
        import yaml
        return yaml.safe_load(s)
    except Exception:
        return s


def write_interview_values(
    interview: dict,
    interview_path: Path,
    notebook: str,
    updates: dict,
    source: str = "gen",
) -> None:
    """Write back gen-derived values into interview.json (atomic).

    `updates` maps param_name → value. For each param that exists in the
    interview under the given notebook, sets `value`, `value_source`, and
    `set_at`. Unknown param_names are silently skipped (the gen may compute
    helper values that aren't in the taxonomy).
    """
    from datetime import datetime, timezone
    import os

    now = datetime.now(timezone.utc).isoformat(timespec="seconds")
    updated = 0
    for row in interview.get("params", []):
        if row.get("notebook") != notebook:
            continue
        if row["param_name"] in updates:
            row["value"] = updates[row["param_name"]]
            row["value_source"] = source
            row["set_at"] = now
            updated += 1

    tmp = interview_path.with_suffix(interview_path.suffix + ".tmp")
    tmp.write_text(json.dumps(interview, indent=2) + "\n")
    os.replace(tmp, interview_path)


def write_config_section(config_path: Path, sections: dict) -> None:
    """Merge `sections` into `config.yml` and atomic-write back.

    `sections` is a dict of top-level config keys (e.g. {"all": {...},
    "preprocess": {...}}) — each gen writes only the section(s) it owns; other
    sections from prior gen runs are preserved. Last-write wins on key
    conflicts within a section (so re-running a gen overwrites that section
    cleanly).

    This is what makes each gen self-sufficient: a standalone gen run produces
    an in-place config.yml that's correct for that phase, and subsequent gens
    layer their sections on top without clobbering.
    """
    import os

    import yaml

    existing: dict = {}
    if config_path.exists():
        with open(config_path) as f:
            loaded = yaml.safe_load(f)
            if isinstance(loaded, dict):
                existing = loaded
    for key, value in sections.items():
        existing[key] = value
    config_path.parent.mkdir(parents=True, exist_ok=True)
    tmp = config_path.with_suffix(config_path.suffix + ".tmp")
    with open(tmp, "w") as f:
        yaml.safe_dump(existing, f, sort_keys=False, default_flow_style=False)
    os.replace(tmp, config_path)
