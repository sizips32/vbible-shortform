#!/usr/bin/env python3
"""State helper for the higgsfield-shortform pipeline.

Stdlib only. Owns all state transitions, gate enforcement, atomic writes,
and corruption recovery so the markdown orchestrator never edits JSON by hand.
"""
import argparse
import json
import os
import sys
import tempfile
from datetime import datetime
from pathlib import Path

STEPS = [
    ("1", "intake", True),
    ("2", "breakdown", True),
    ("3", "style", True),
    ("4", "prompt", False),
    ("5", "render", True),
    ("6", "curate", True),
    ("7", "post", False),
]

PER_EPISODE_LIMIT = 650
CHANNEL_INDEX = Path("projects") / "vbible-students" / "episodes-index.json"


def project_dir(slug):
    return Path.cwd() / "projects" / slug


def state_path(slug):
    return project_dir(slug) / "state.json"


def _new_state(slug, logline):
    return {
        "slug": slug,
        "logline": logline,
        "currentStep": 1,
        "createdAt": datetime.now().isoformat(timespec="seconds"),
        "steps": {
            num: {"name": name, "gate": gate, "status": "pending",
                  "gateApproved": False, "output": None}
            for num, name, gate in STEPS
        },
    }


def load(slug):
    """Load state, recovering from .bak if the primary file is corrupt."""
    p = state_path(slug)
    if not p.exists():
        return None
    try:
        return json.loads(p.read_text())
    except (json.JSONDecodeError, ValueError):
        bak = p.with_suffix(".json.bak")
        if bak.exists():
            data = json.loads(bak.read_text())
            _atomic_write(slug, data)
            return data
        raise


def _atomic_write(slug, data):
    p = state_path(slug)
    p.parent.mkdir(parents=True, exist_ok=True)
    if p.exists():
        p.with_suffix(".json.bak").write_text(p.read_text())
    fd, tmp = tempfile.mkstemp(dir=str(p.parent), suffix=".tmp")
    try:
        with os.fdopen(fd, "w") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        os.replace(tmp, p)
    finally:
        if os.path.exists(tmp):
            os.unlink(tmp)


def cmd_init(args):
    p = state_path(args.slug)
    if p.exists() and not args.force:
        print(f"project '{args.slug}' already exists", file=sys.stderr)
        return 1
    pd = project_dir(args.slug)
    (pd / "briefs").mkdir(parents=True, exist_ok=True)
    (pd / "assets").mkdir(parents=True, exist_ok=True)
    _atomic_write(args.slug, _new_state(args.slug, args.logline))
    print(str(p))
    return 0


def cmd_read(args):
    s = load(args.slug)
    if s is None:
        print(f"no project '{args.slug}'", file=sys.stderr)
        return 2
    if args.field:
        print(s.get(args.field, ""))
    else:
        print(json.dumps(s, ensure_ascii=False, indent=2))
    return 0


def cmd_set_output(args):
    s = load(args.slug)
    if s is None:
        return 2
    if not args.no_verify and not Path(args.file).exists():
        print(f"output file does not exist: {args.file} (use --no-verify to override)",
              file=sys.stderr)
        return 5
    step = s["steps"][args.step]
    step["status"] = "done"
    step["output"] = args.file
    _atomic_write(args.slug, s)
    return 0


def _clips_credits(slug):
    """Per-cut + total credits, read fresh from clips.json (the SSOT). No
    separate ledger -> no drift with the render record."""
    cp = project_dir(slug) / "assets" / "clips.json"
    if not cp.exists():
        return None
    clips = json.loads(cp.read_text()).get("clips", [])
    rows = [(c.get("cut"), c.get("type"), float(c.get("creditsUsed") or 0)) for c in clips]
    return rows, sum(r[2] for r in rows)


def cmd_credits(args):
    res = _clips_credits(args.slug)
    if res is None:
        print(f"no clips.json for '{args.slug}'", file=sys.stderr)
        return 2
    rows, total = res
    for cut, typ, cr in rows:
        if cr:
            print(f"  {cut}\t{typ}\t{cr:g}")
    over = total > PER_EPISODE_LIMIT
    print(f"total\t{total:g} / {PER_EPISODE_LIMIT}" + ("\tOVER LIMIT" if over else ""))
    return 7 if over else 0


def cmd_finalize(args):
    """Record a completed episode into the channel index — measured values only
    (slug, logline, dates, credits, runtime, steps done). No fabricated metrics."""
    s = load(args.slug)
    if s is None:
        return 2
    credits = _clips_credits(args.slug)
    cp = project_dir(args.slug) / "assets" / "clips.json"
    runtime = json.loads(cp.read_text()).get("totalRuntimeSec") if cp.exists() else None
    entry = {
        "slug": args.slug,
        "logline": s.get("logline"),
        "createdAt": s.get("createdAt"),
        "completedAt": datetime.now().isoformat(timespec="seconds"),
        "credits": credits[1] if credits else None,
        "runtimeSec": runtime,
        "stepsDone": [n for n, st in s["steps"].items() if st["status"] == "done"],
    }
    idx = CHANNEL_INDEX
    data = json.loads(idx.read_text()) if idx.exists() else {"episodes": []}
    data["episodes"] = [e for e in data["episodes"] if e.get("slug") != args.slug] + [entry]
    idx.parent.mkdir(parents=True, exist_ok=True)
    tmp = idx.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2))
    os.replace(tmp, idx)
    print(str(idx))
    return 0


def cmd_approve(args):
    s = load(args.slug)
    if s is None:
        return 2
    step = s["steps"][args.step]
    if step["status"] != "done":
        print(f"step {args.step} not done yet", file=sys.stderr)
        return 4
    step["gateApproved"] = True
    _atomic_write(args.slug, s)
    return 0


def cmd_advance(args):
    s = load(args.slug)
    if s is None:
        return 2
    cur = str(s["currentStep"])
    step = s["steps"][cur]
    if step["status"] != "done":
        print(f"step {cur} not done", file=sys.stderr)
        return 3
    if step["gate"] and not step["gateApproved"]:
        print(f"step {cur} gate not approved", file=sys.stderr)
        return 3
    if s["currentStep"] >= 7:
        print("7", file=sys.stderr)
        return 0
    s["currentStep"] += 1
    _atomic_write(args.slug, s)
    print(s["currentStep"])
    return 0


def cmd_resume(args):
    s = load(args.slug)
    if s is None:
        return 2
    cur = str(s["currentStep"])
    step = s["steps"][cur]
    print(f"{cur}\t{step['name']}\t{step['status']}")
    return 0


def build_parser():
    p = argparse.ArgumentParser(prog="state.py")
    sub = p.add_subparsers(dest="cmd", required=True)

    pi = sub.add_parser("init")
    pi.add_argument("slug")
    pi.add_argument("--logline", required=True)
    pi.add_argument("--force", action="store_true")
    pi.set_defaults(func=cmd_init)

    pr = sub.add_parser("read")
    pr.add_argument("slug")
    pr.add_argument("--field")
    pr.set_defaults(func=cmd_read)

    ps = sub.add_parser("set-output")
    ps.add_argument("slug")
    ps.add_argument("step")
    ps.add_argument("--file", required=True)
    ps.add_argument("--no-verify", action="store_true",
                    help="skip output-file existence check")
    ps.set_defaults(func=cmd_set_output)

    pc = sub.add_parser("credits")
    pc.add_argument("slug")
    pc.set_defaults(func=cmd_credits)

    pf = sub.add_parser("finalize")
    pf.add_argument("slug")
    pf.set_defaults(func=cmd_finalize)

    pa = sub.add_parser("approve")
    pa.add_argument("slug")
    pa.add_argument("step")
    pa.set_defaults(func=cmd_approve)

    pv = sub.add_parser("advance")
    pv.add_argument("slug")
    pv.set_defaults(func=cmd_advance)

    pu = sub.add_parser("resume")
    pu.add_argument("slug")
    pu.set_defaults(func=cmd_resume)

    return p


def main(argv=None):
    args = build_parser().parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
