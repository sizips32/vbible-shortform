#!/usr/bin/env python3
"""Deterministic QA gate for the V-Bible pipeline.

Stdlib + ffprobe. Mechanically checkable invariants only — elementId matching,
one speaker per lipsync cut, Korean dialogue, budget sum, 9:16/length, JSON
schema. The vbible-qa LLM agent runs *after* this and owns the perceptual
judgments this script cannot make (character drift, glasses present, style).

Each check returns (ok: bool, messages: list[str]). A message is a finding,
not a log line — empty messages == clean.
"""
import argparse
import json
import re
import subprocess
import sys
from pathlib import Path

PER_EPISODE_LIMIT = 650
HANGUL = re.compile(r"[가-힣]")
PLACEHOLDER = re.compile(r"<<<[0-9a-f-]{36}>>>")
VIDEO_KINDS = ("i2v", "lipsync")


def load_json(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def valid_element_ids(refs):
    return {r["elementId"] for r in refs["refs"]}


# ---------------------------------------------------------------- checks
def check_korean(texts):
    """Every non-empty text must contain Hangul (invariant 2-1)."""
    msgs = [f"non-Korean / no Hangul: {t!r}" for t in texts if t and t.strip() and not HANGUL.search(t)]
    return (not msgs, msgs)


def check_element_ids(keyframes, refs):
    """keyframes.json elementIds ⊆ channel bible, and placeholder count == person
    count (invariant 2-2). talkinghead cuts must be exactly one person."""
    valid = valid_element_ids(refs)
    msgs = []
    for kf in keyframes["keyframes"]:
        cut, ids = kf["cut"], kf.get("elementIds", [])
        for eid in ids:
            if eid not in valid:
                msgs.append(f"{cut}: unknown elementId {eid}")
        ph = len(PLACEHOLDER.findall(kf.get("imagePrompt", "")))
        if kf.get("type") == "talkinghead":
            if len(ids) != 1:
                msgs.append(f"{cut}: talkinghead must be 1 person, got {len(ids)}")
        else:  # scene: placeholder count must equal person count
            chars = kf.get("characters", [])
            if ph != len(ids) or len(ids) != len(chars):
                msgs.append(f"{cut}: scene placeholders={ph} elementIds={len(ids)} chars={len(chars)} (must match)")
    return (not msgs, msgs)


def check_one_speaker(clips):
    """Each lipsync cut has a single speaker (invariant 2-4)."""
    msgs = []
    for c in clips["clips"]:
        if c.get("type") == "lipsync":
            ch = c.get("char")
            if not isinstance(ch, str) or not ch.strip():
                msgs.append(f"{c.get('cut')}: lipsync needs exactly one named speaker, got {ch!r}")
    return (not msgs, msgs)


def check_dialogue_policy(clips):
    """i2v cuts must carry a separate Korean TTS track and discard embedded
    audio; lipsync cuts must reference a TTS/audio media (invariant 2-1)."""
    msgs = []
    for c in clips["clips"]:
        t = c.get("type")
        if t == "i2v":
            if not c.get("ttsPath"):
                msgs.append(f"{c.get('cut')}: i2v missing narration ttsPath")
            if "discard" not in str(c.get("embeddedAudio", "")).lower():
                msgs.append(f"{c.get('cut')}: i2v embeddedAudio not marked discard")
        elif t == "lipsync":
            if not (c.get("audioMediaId") or c.get("ttsPath")):
                msgs.append(f"{c.get('cut')}: lipsync missing Korean audio source")
    return (not msgs, msgs)


def check_budget(clips, limit=PER_EPISODE_LIMIT):
    total = sum(float(c.get("creditsUsed") or 0) for c in clips["clips"])
    ok = total <= limit
    return (ok, [] if ok else [f"budget {total} > {limit} per-episode limit"])


def check_mapping(clips, keyframes):
    """Every lipsync cut maps to a talkinghead keyframe jobId; every i2v cut to
    a scene keyframe (boundary cross-check, stage 5)."""
    kf_by_cut = {k["cut"]: k for k in keyframes["keyframes"]}
    msgs = []
    for c in clips["clips"]:
        if c.get("type") not in VIDEO_KINDS:
            continue
        kf = kf_by_cut.get(c["cut"])
        if not kf:
            msgs.append(f"{c['cut']}: no keyframe for rendered cut")
    return (not msgs, msgs)


def ffprobe_dims(path):
    out = subprocess.run(
        ["ffprobe", "-v", "error", "-select_streams", "v:0",
         "-show_entries", "stream=width,height", "-of", "json", str(path)],
        capture_output=True, text=True,
    )
    try:
        s = json.loads(out.stdout)["streams"][0]
        return int(s["width"]), int(s["height"])
    except (KeyError, IndexError, ValueError, json.JSONDecodeError):
        return None


def ffprobe_duration(path):
    out = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration",
         "-of", "default=nk=1:nw=1", str(path)],
        capture_output=True, text=True,
    )
    try:
        return float(out.stdout.strip())
    except ValueError:
        return None


def check_format(path, min_sec=10, max_sec=120):
    """9:16 aspect + plausible shortform length, via ffprobe."""
    msgs = []
    dims = ffprobe_dims(path)
    if not dims:
        return (False, [f"{path}: ffprobe could not read video stream"])
    w, h = dims
    if abs(w / h - 9 / 16) > 0.02:
        msgs.append(f"{path}: aspect {w}x{h} is not 9:16")
    dur = ffprobe_duration(path)
    if dur is None:
        msgs.append(f"{path}: no duration")
    elif not (min_sec <= dur <= max_sec):
        msgs.append(f"{path}: duration {dur:.1f}s outside [{min_sec},{max_sec}]")
    return (not msgs, msgs)


def check_schema(obj, required, label="object"):
    msgs = [f"{label}: missing key '{k}'" for k in required if k not in obj]
    return (not msgs, msgs)


# ---------------------------------------------------------------- stages
def run_stage(stage, project_dir, refs_path, preview=None):
    pd = Path(project_dir)
    refs = load_json(refs_path)
    results = []

    def add(name, res):
        results.append((name, res[0], res[1]))

    if stage == 2:
        shot = (pd / "briefs" / "shotlist.md")
        if shot.exists():
            import assemble
            dlg = assemble.parse_shotlist_dialogue(shot.read_text(encoding="utf-8"))
            add("korean-dialogue", check_korean(list(dlg.values())))
    if stage == 3:
        kf = load_json(pd / "briefs" / "keyframes.json")
        add("element-ids", check_element_ids(kf, refs))
        add("keyframe-korean", check_korean([k.get("imagePrompt", "") for k in kf["keyframes"]]))
    if stage == 5:
        clips = load_json(pd / "assets" / "clips.json")
        kf = load_json(pd / "briefs" / "keyframes.json")
        add("one-speaker", check_one_speaker(clips))
        add("dialogue-policy", check_dialogue_policy(clips))
        add("budget", check_budget(clips))
        add("mapping", check_mapping(clips, kf))
        target = preview or (pd / "clips" / "PREVIEW.mp4")
        if Path(target).exists():
            add("format-9x16", check_format(target))
    return results


def main(argv=None):
    p = argparse.ArgumentParser(prog="qa_checks.py")
    p.add_argument("project_dir")
    p.add_argument("--stage", type=int, required=True, choices=[2, 3, 5])
    p.add_argument("--refs", default="projects/vbible-students/assets/reference-media.json")
    p.add_argument("--preview", help="mp4 to ffprobe (default clips/PREVIEW.mp4)")
    p.add_argument("--json", action="store_true")
    a = p.parse_args(argv)
    results = run_stage(a.stage, a.project_dir, a.refs, a.preview)
    failed = [r for r in results if not r[1]]
    if a.json:
        print(json.dumps(
            [{"check": n, "pass": ok, "findings": m} for n, ok, m in results],
            ensure_ascii=False, indent=2))
    else:
        for name, ok, msgs in results:
            print(f"[{'PASS' if ok else 'FAIL'}] {name}")
            for m in msgs:
                print(f"    - {m}")
        print(f"\n{'FAIL' if failed else 'PASS'}: stage {a.stage} "
              f"({len(results) - len(failed)}/{len(results)} checks clean)")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    sys.exit(main())
