#!/usr/bin/env python3
"""Assemble V-Bible cuts into a PREVIEW.mp4 + Korean .srt sidecar.

Stdlib + ffmpeg only. Split into pure planning functions (testable without
ffmpeg) and a thin runner that shells out to ffmpeg.

Invariant 2-1 is enforced *mechanically* here:
  - i2v cuts take audio ONLY from the Korean ElevenLabs TTS track. The
    seedance-embedded (non-Korean) audio is never mapped into the output —
    the filter graph references the mp4 video stream and the mp3 audio stream,
    so the embedded audio is dropped by construction.
  - lipsync cuts keep their embedded audio (wan2_7 = the uploaded Korean TTS,
    proven Korean-preserving at corr 0.999-1.000 in ep-00).

Subtitles (.srt) are a sidecar file only — never burned into the video
(invariant 2-3: no on-screen text; captions live in the NLE).
"""
import argparse
import json
import re
import shutil
import subprocess
import sys
import urllib.request
from pathlib import Path

W, H, FPS, LUFS = 1080, 1920, 30, -14.0
VIDEO_KINDS = ("i2v", "lipsync")  # narration-tts rows are audio companions -> skipped


# ---------------------------------------------------------------- io helpers
def load_json(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def repo_rel(path, *bases):
    """Resolve a possibly repo-root-relative path against several bases."""
    p = Path(path)
    if p.is_absolute() and p.exists():
        return p
    for b in (Path.cwd(), *bases):
        cand = Path(b) / path
        if cand.exists():
            return cand
    return Path(path)  # let caller report the miss


# ---------------------------------------------------------------- planning
def select_order(clips, order=None):
    """Return video-type clips in playback order.

    order: explicit list of cut ids (from curate/selects.json). When absent we
    fall back to clips.json array order — correct only when no cut was dropped
    or reordered, so curate should always emit an explicit order for ep-N.
    """
    vids = [c for c in clips if c.get("type") in VIDEO_KINDS]
    if order:
        by_cut = {}
        for c in vids:
            by_cut.setdefault(c["cut"], c)  # first video row per cut id
        return [by_cut[cut] for cut in order if cut in by_cut]
    return vids


def resolve_video(clip, project_dir):
    """Locate the local rendered mp4 for a clip. None -> caller may download."""
    project_dir = Path(project_dir)
    lp = clip.get("localPath")
    if lp:
        cand = repo_rel(lp, project_dir, project_dir.parent.parent)
        if cand.exists():
            return cand
    hits = sorted((project_dir / "clips").glob(f"{clip['type']}_{clip['cut']}_*.mp4"))
    return hits[0] if hits else None


def resolve_tts(clip, project_dir):
    project_dir = Path(project_dir)
    tp = clip.get("ttsPath")
    if not tp:
        return None
    cand = repo_rel(tp, project_dir, project_dir.parent.parent)
    return cand if cand.exists() else Path(tp)


def build_segments(clips, project_dir, order=None):
    """Ordered list of segment plans. Raises on a missing video input.

    Each segment: {cut, kind, video:Path, audio_kind:'embedded'|'tts',
                   audio:Path|None, duration:float}.
    audio_kind is the invariant-2-1 decision: i2v -> tts, lipsync -> embedded.
    """
    segs = []
    for clip in select_order(clips, order):
        kind = clip["type"]
        video = resolve_video(clip, project_dir)
        dur = float(clip.get("videoDurationSec") or 0) or None
        seg = {"cut": clip["cut"], "kind": kind, "video": video, "duration": dur}
        if kind == "i2v":
            seg["audio_kind"] = "tts"
            seg["audio"] = resolve_tts(clip, project_dir)
        else:  # lipsync keeps the wan2_7-embedded Korean audio
            seg["audio_kind"] = "embedded"
            seg["audio"] = None
        segs.append(seg)
    return segs


# ---------------------------------------------------------------- subtitles
def parse_shotlist_dialogue(md_text):
    """Extract {cut_id: korean_text} from the shotlist 대사표 markdown table.

    Detects the dialogue column by header (cell containing '대사') so the parse
    survives added/removed columns.
    """
    out, dlg_idx = {}, None
    for line in md_text.splitlines():
        if not line.lstrip().startswith("|"):
            continue
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        if dlg_idx is None:
            for i, c in enumerate(cells):
                if "대사" in c:
                    dlg_idx = i
                    break
            continue
        if cells and re.fullmatch(r"C\d+", cells[0]) and dlg_idx < len(cells):
            out[cells[0]] = cells[dlg_idx]
    return out


def _srt_tc(sec):
    ms = int(round(sec * 1000))
    h, ms = divmod(ms, 3600_000)
    m, ms = divmod(ms, 60_000)
    s, ms = divmod(ms, 1000)
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"


def build_srt(segments, dialogue):
    """SRT keyed off real rendered durations (segment.duration), text from the
    shotlist. Aligned to a hard-cut concat; crossfades shift the timeline."""
    blocks, t = [], 0.0
    for i, seg in enumerate(segments, 1):
        dur = seg.get("duration") or 0.0
        text = dialogue.get(seg["cut"], "").strip()
        if text:
            blocks.append(f"{i}\n{_srt_tc(t)} --> {_srt_tc(t + dur)}\n{text}\n")
        t += dur
    return "\n".join(blocks) + ("\n" if blocks else "")


# ---------------------------------------------------------------- ffmpeg cmd
def _seg_filters(segments):
    """Return (inputs, filter_lines, vlabels, alabels). Pure — no ffmpeg call.

    inputs is the ordered -i list. For i2v the mp4 contributes only its video
    stream ([vi:v]); audio comes from the appended mp3 ([ai:a]) -> embedded
    non-Korean audio is dropped by construction (invariant 2-1).
    """
    inputs, filt, vlabels, alabels, idx = [], [], [], [], 0
    for i, seg in enumerate(segments):
        vi = idx
        inputs.append(str(seg["video"]))
        idx += 1
        if seg["audio_kind"] == "tts":
            ai = idx
            inputs.append(str(seg["audio"]))
            idx += 1
            asrc = f"[{ai}:a]"
        else:
            asrc = f"[{vi}:a]"
        dur = seg.get("duration")
        vtrim = f",trim=0:{dur},setpts=PTS-STARTPTS" if dur else ""
        atrim = f",apad,atrim=0:{dur},asetpts=N/SR/TB" if dur else ""
        filt.append(
            f"[{vi}:v]scale={W}:{H}:force_original_aspect_ratio=decrease,"
            f"pad={W}:{H}:(ow-iw)/2:(oh-ih)/2,setsar=1,fps={FPS}"
            f"{vtrim},format=yuv420p[v{i}]"
        )
        filt.append(
            f"{asrc}aresample=48000,aformat=sample_fmts=fltp:"
            f"channel_layouts=stereo{atrim}[a{i}]"
        )
        vlabels.append(f"[v{i}]")
        alabels.append(f"[a{i}]")
    return inputs, filt, vlabels, alabels


def build_ffmpeg_cmd(segments, out_path, crossfade=0.0):
    inputs, filt, vlabels, alabels = _seg_filters(segments)
    n = len(segments)
    if crossfade and n > 1:
        prev, offset = vlabels[0], (segments[0].get("duration") or 0) - crossfade
        for i in range(1, n):
            lbl = f"[vx{i}]"
            filt.append(
                f"{prev}{vlabels[i]}xfade=transition=fade:"
                f"duration={crossfade}:offset={offset}{lbl}"
            )
            prev = lbl
            offset += (segments[i].get("duration") or 0) - crossfade
        vout = prev
        preva = alabels[0]
        for i in range(1, n):
            lbl = f"[ax{i}]"
            filt.append(f"{preva}{alabels[i]}acrossfade=d={crossfade}{lbl}")
            preva = lbl
        filt.append(f"{preva}loudnorm=I={LUFS}:TP=-1.5:LRA=11[ao]")
    else:
        concat_in = "".join(vlabels[i] + alabels[i] for i in range(n))
        filt.append(f"{concat_in}concat=n={n}:v=1:a=1[vc][apre]")
        filt.append(f"[apre]loudnorm=I={LUFS}:TP=-1.5:LRA=11[ao]")
        vout = "[vc]"
    cmd = ["ffmpeg", "-y"]
    for p in inputs:
        cmd += ["-i", p]
    cmd += [
        "-filter_complex", ";".join(filt),
        "-map", vout, "-map", "[ao]",
        "-c:v", "libx264", "-crf", "18", "-preset", "medium", "-pix_fmt", "yuv420p",
        "-c:a", "aac", "-b:a", "192k", "-movflags", "+faststart",
        str(out_path),
    ]
    return cmd


# ---------------------------------------------------------------- runner
def _ffprobe_duration(path):
    out = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration",
         "-of", "default=nk=1:nw=1", str(path)],
        capture_output=True, text=True,
    )
    try:
        return float(out.stdout.strip())
    except ValueError:
        return None


def _download(url, dest):
    dest.parent.mkdir(parents=True, exist_ok=True)
    with urllib.request.urlopen(url) as r, open(dest, "wb") as f:
        shutil.copyfileobj(r, f)
    return dest


def assemble(project_dir, order=None, out=None, crossfade=0.0,
             srt_only=False, dry_run=False):
    project_dir = Path(project_dir)
    clips_data = load_json(project_dir / "assets" / "clips.json")
    clips = clips_data["clips"]
    if order is None:
        sel = project_dir / "briefs" / "selects.json"
        if sel.exists():
            order = load_json(sel).get("order")
    segs = build_segments(clips, project_dir, order)

    # Fill missing inputs: download from url when a local mp4 is absent.
    raw = {c["cut"]: c for c in clips if c.get("type") in VIDEO_KINDS}
    for seg in segs:
        if seg["video"] is None:
            url = raw.get(seg["cut"], {}).get("url")
            if not url:
                raise SystemExit(f"no local mp4 and no url for cut {seg['cut']}")
            seg["video"] = _download(url, project_dir / "clips" / f"_dl_{seg['cut']}.mp4")
        if seg["audio_kind"] == "tts" and (seg["audio"] is None or not Path(seg["audio"]).exists()):
            raise SystemExit(f"i2v cut {seg['cut']} missing Korean TTS track (invariant 2-1)")
        if not seg.get("duration") and not dry_run:
            seg["duration"] = _ffprobe_duration(seg["video"])

    out = Path(out) if out else project_dir / "clips" / "PREVIEW.mp4"
    srt = out.with_suffix(".srt")
    shot = project_dir / "briefs" / "shotlist.md"
    dialogue = parse_shotlist_dialogue(shot.read_text(encoding="utf-8")) if shot.exists() else {}
    srt.write_text(build_srt(segs, dialogue), encoding="utf-8")
    print(f"srt   -> {srt}")
    if srt_only:
        return 0

    cmd = build_ffmpeg_cmd(segs, out, crossfade)
    if crossfade:
        print("WARN: crossfade shifts the timeline; .srt is aligned to hard cuts.",
              file=sys.stderr)
    if dry_run:
        print(" ".join(cmd))
        return 0
    if not shutil.which("ffmpeg"):
        raise SystemExit("ffmpeg not found on PATH — install ffmpeg to assemble")
    print(f"assembling {len(segs)} cuts -> {out}")
    r = subprocess.run(cmd)
    if r.returncode == 0:
        print(f"video -> {out}")
    return r.returncode


def main(argv=None):
    p = argparse.ArgumentParser(prog="assemble.py")
    p.add_argument("project_dir", help="projects/<epSlug>")
    p.add_argument("--order", help="comma-separated cut ids, e.g. C1,C2,C3")
    p.add_argument("--out", help="output mp4 (default clips/PREVIEW.mp4)")
    p.add_argument("--crossfade", type=float, default=0.0, help="seconds (opt-in)")
    p.add_argument("--srt-only", action="store_true")
    p.add_argument("--dry-run", action="store_true", help="print ffmpeg cmd, no run")
    a = p.parse_args(argv)
    order = a.order.split(",") if a.order else None
    return assemble(a.project_dir, order, a.out, a.crossfade, a.srt_only, a.dry_run)


if __name__ == "__main__":
    sys.exit(main())
