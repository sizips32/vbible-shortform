#!/usr/bin/env python3
"""v2 harness tests — pure planning + deterministic QA against ep-00 real data.

Run from repo root:  python3 -m unittest discover -s tests -v
"""
import re
import sys
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "lib"))

import assemble  # noqa: E402
import qa_checks  # noqa: E402
import state  # noqa: E402

EP = REPO / "projects" / "vbible-ep-00-cast-intro"
REFS = REPO / "projects" / "vbible-students" / "assets" / "reference-media.json"


def clips():
    return assemble.load_json(EP / "assets" / "clips.json")["clips"]


class TestSegments(unittest.TestCase):
    def setUp(self):
        self.segs = assemble.build_segments(clips(), EP)

    def test_order_and_count_skips_narration(self):
        # 6 video cuts; the 2 narration-tts companion rows are dropped.
        self.assertEqual([s["cut"] for s in self.segs],
                         ["C1", "C2", "C3", "C4", "C5", "C6"])

    def test_audio_policy_per_kind(self):
        by = {s["cut"]: s for s in self.segs}
        for cut in ("C1", "C6"):  # i2v -> Korean TTS track
            self.assertEqual(by[cut]["audio_kind"], "tts")
            self.assertTrue(str(by[cut]["audio"]).endswith(".mp3"))
        for cut in ("C2", "C3", "C4", "C5"):  # lipsync -> embedded Korean audio
            self.assertEqual(by[cut]["audio_kind"], "embedded")
            self.assertIsNone(by[cut]["audio"])

    def test_local_videos_resolve(self):
        for s in self.segs:
            self.assertIsNotNone(s["video"], f"{s['cut']} mp4 not resolved")
            self.assertTrue(Path(s["video"]).exists())

    def test_explicit_order_reorders(self):
        segs = assemble.build_segments(clips(), EP, order=["C6", "C1"])
        self.assertEqual([s["cut"] for s in segs], ["C6", "C1"])


class TestInvariant21(unittest.TestCase):
    """i2v output audio comes ONLY from the mp3 TTS track; the seedance-embedded
    (non-Korean) mp4 audio is never mapped. lipsync keeps the mp4 (Korean) audio."""

    def test_i2v_audio_source_is_mp3_not_embedded(self):
        segs = assemble.build_segments(clips(), EP)
        inputs, filt, _, _ = assemble._seg_filters(segs)
        for i, seg in enumerate(segs):
            line = next(l for l in filt if l.endswith(f"[a{i}]"))
            m = re.match(r"\[(\d+):a\]", line)
            assert m is not None, f"unparsable audio filter: {line}"
            src = int(m.group(1))
            if seg["kind"] == "i2v":
                self.assertTrue(inputs[src].endswith(".mp3"),
                                f"{seg['cut']} i2v audio not from TTS mp3")
            else:
                self.assertTrue(inputs[src].endswith(".mp4"),
                                f"{seg['cut']} lipsync audio not embedded")

    def test_cmd_has_one_mp3_input_per_i2v(self):
        segs = assemble.build_segments(clips(), EP)
        cmd = assemble.build_ffmpeg_cmd(segs, "/tmp/out.mp4")
        mp3s = [a for a in cmd if a.endswith(".mp3")]
        self.assertEqual(len(mp3s), sum(1 for s in segs if s["kind"] == "i2v"))


class TestSubtitles(unittest.TestCase):
    def test_dialogue_parses_korean(self):
        dlg = assemble.parse_shotlist_dialogue(
            (EP / "briefs" / "shotlist.md").read_text(encoding="utf-8"))
        self.assertEqual(set(dlg), {"C1", "C2", "C3", "C4", "C5", "C6"})
        self.assertTrue(dlg["C1"].startswith("안녕하세요"))
        self.assertTrue(qa_checks.HANGUL.search(dlg["C3"]))

    def test_srt_timing_uses_real_durations(self):
        segs = assemble.build_segments(clips(), EP)  # 8/9/8/9/8/8 = 50s
        dlg = assemble.parse_shotlist_dialogue(
            (EP / "briefs" / "shotlist.md").read_text(encoding="utf-8"))
        srt = assemble.build_srt(segs, dlg)
        self.assertIn("00:00:00,000 --> 00:00:08,000", srt)  # C1 = 8s, not shotlist 11s
        self.assertIn("00:00:42,000 --> 00:00:50,000", srt)  # C6 ends at 50s


class TestQAChecks(unittest.TestCase):
    def setUp(self):
        self.refs = qa_checks.load_json(REFS)
        self.kf = qa_checks.load_json(EP / "briefs" / "keyframes.json")
        self.clips = {"clips": clips()}

    def test_element_ids_pass(self):
        ok, msgs = qa_checks.check_element_ids(self.kf, self.refs)
        self.assertTrue(ok, msgs)

    def test_element_ids_catch_unknown(self):
        bad = {"keyframes": [{"cut": "C9", "type": "talkinghead",
                              "characters": ["x"], "elementIds": ["deadbeef"],
                              "imagePrompt": ""}]}
        ok, msgs = qa_checks.check_element_ids(bad, self.refs)
        self.assertFalse(ok)
        self.assertTrue(any("unknown elementId" in m for m in msgs))

    def test_one_speaker_pass(self):
        self.assertTrue(qa_checks.check_one_speaker(self.clips)[0])

    def test_dialogue_policy_pass(self):
        self.assertTrue(qa_checks.check_dialogue_policy(self.clips)[0])

    def test_budget_total_123(self):
        ok, _ = qa_checks.check_budget(self.clips)
        self.assertTrue(ok)
        total = sum(float(c.get("creditsUsed") or 0) for c in self.clips["clips"])
        self.assertEqual(total, 123)

    def test_korean_flags_latin(self):
        ok, msgs = qa_checks.check_korean(["안녕하세요", "hello world"])
        self.assertFalse(ok)
        self.assertEqual(len(msgs), 1)

    def test_mapping_pass(self):
        self.assertTrue(qa_checks.check_mapping(self.clips, self.kf)[0])


class TestStateCredits(unittest.TestCase):
    def test_clips_credits_sum(self):
        import os
        os.chdir(REPO)
        _, total = state._clips_credits("vbible-ep-00-cast-intro")
        self.assertEqual(total, 123)


if __name__ == "__main__":
    unittest.main()
