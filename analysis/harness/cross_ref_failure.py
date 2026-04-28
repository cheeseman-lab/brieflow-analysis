#!/usr/bin/env python3
"""
Cross-reference failed convert_sbs jobs across four data sources:

  1. Snakemake's parent-reported errors  (logs/preprocess_sbs_phenotype-*.log)
  2. sacct State / ExitCode / sub-step presence
  3. Output files on disk (brieflow_output_tile/...)
  4. Per-rule slurm log existence (slurm/slurm_output/rule/rule_convert_sbs/*.log)

Produces one definitive table answering, per slurm task:
  did the parent report it failed? did slurm say so? did the python step run?
  is the output on disk? is the per-rule log present?

Run from analysis/.
"""
from __future__ import annotations
import csv
import re
import subprocess
import sys
from pathlib import Path

ANALYSIS = Path(__file__).resolve().parent.parent

def _latest(pattern: str, base: Path) -> Path | None:
    cands = sorted(base.glob(pattern), key=lambda p: p.stat().st_mtime)
    return cands[-1] if cands else None

def parse_snakemake_errors(toplog: Path) -> dict[str, dict]:
    """slurm jobid -> {snakemake_jobid, output, input_count}"""
    errors: dict[str, dict] = {}
    text = toplog.read_text()
    pattern = re.compile(
        r"Error in rule convert_sbs:\s*\n"
        r"\s*message:.*?'([^']+)'.*?\n"
        r"\s*jobid:\s*(\d+)\s*\n"
        r"\s*input:\s*(.+?)\n"
        r"\s*output:\s*(\S+)",
        re.DOTALL,
    )
    for m in pattern.finditer(text):
        slurm_jid, snake_jid, inp, out = m.group(1), m.group(2), m.group(3), m.group(4)
        errors[slurm_jid] = {
            "snake_jobid": snake_jid,
            "output": out,
            "input_count": len(inp.split(",")),
        }
    return errors

def pull_sacct(jids: list[str]) -> dict[str, dict]:
    out = subprocess.run(
        ["sacct", "--parsable2", "--noheader",
         "--format=JobID,State,ExitCode",
         "-j", ",".join(jids)],
        capture_output=True, text=True, check=False,
    ).stdout
    parent = {}
    has_pystep: dict[str, bool] = {}
    for line in out.splitlines():
        parts = line.split("|")
        if len(parts) < 3: continue
        jid, state, ec = parts[0], parts[1], parts[2]
        if "." in jid.rsplit("_", 1)[-1]:
            stem = jid.rsplit(".", 1)[0]
            if jid.endswith(".0"):
                has_pystep[stem] = True
        else:
            parent[jid] = {"State": state, "ExitCode": ec}
    for j in parent:
        parent[j]["has_py_substep"] = has_pystep.get(j, False)
    return parent

def main():
    toplog = _latest("logs/preprocess_sbs_phenotype-*.log", ANALYSIS)
    if not toplog:
        print("No flow.sh log found.", file=sys.stderr); sys.exit(1)
    print(f"# Source flow.sh log: {toplog}")
    errors = parse_snakemake_errors(toplog)
    if not errors:
        print("# No 'Error in rule convert_sbs:' blocks found in the flow.sh log.")
        return

    sacct = pull_sacct(list(errors.keys()))

    print(f"\n{'slurm_jid':<14} {'snake':<6} {'sacct.State':<12} {'EC':<5} "
          f"{'.0_step':<8} {'on_disk':<8} {'rule_log':<9} output")
    print("-" * 110)

    n_total = 0
    n_sacct_completed = 0
    n_disk_present = 0
    n_log_present = 0
    n_pystep_yes = 0

    for slurm_jid in sorted(errors.keys(),
                            key=lambda j: tuple(int(x) if x.isdigit() else x
                                                for x in re.split(r"[_]", j))):
        e = errors[slurm_jid]
        s = sacct.get(slurm_jid, {})
        out_path = ANALYSIS / e["output"]
        log_path = ANALYSIS / "slurm/slurm_output/rule/rule_convert_sbs" / f"{slurm_jid}.log"

        on_disk = out_path.exists()
        log_exists = log_path.exists()
        py = s.get("has_py_substep", False)

        n_total += 1
        if s.get("State", "").startswith("COMPLETED"): n_sacct_completed += 1
        if on_disk: n_disk_present += 1
        if log_exists: n_log_present += 1
        if py: n_pystep_yes += 1

        print(f"{slurm_jid:<14} {e['snake_jobid']:<6} "
              f"{s.get('State','-'):<12} {s.get('ExitCode','-'):<5} "
              f"{('YES' if py else 'NO'):<8} "
              f"{('YES' if on_disk else 'NO'):<8} "
              f"{('YES' if log_exists else 'NO'):<9} {e['output']}")

    print("-" * 110)
    print(f"\n# Summary: {n_total} jobs reported FAILED by snakemake's parent")
    print(f"#   sacct State=COMPLETED:        {n_sacct_completed:>3} / {n_total}")
    print(f"#   .0 python sub-step recorded:  {n_pystep_yes:>3} / {n_total}")
    print(f"#   output file on disk:          {n_disk_present:>3} / {n_total}")
    print(f"#   per-rule slurm log present:   {n_log_present:>3} / {n_total}")

if __name__ == "__main__":
    main()
