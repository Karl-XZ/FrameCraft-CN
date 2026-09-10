from __future__ import annotations

import json
import tempfile
import unittest
import wave
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

from backend.app import aliyun_speech, science_content
from backend.app.ingest import build_audio_scene_seed, build_subtitle_cues, infer_semantic_motion, segment_script_for_tts
from backend.app.managed_faceless_builder import render_semantic_science_markup


def wav_bytes(duration_s: float = 0.25) -> bytes:
    with tempfile.NamedTemporaryFile(suffix=".wav") as handle:
        with wave.open(handle.name, "wb") as output:
            output.setnchannels(1)
            output.setsampwidth(2)
            output.setframerate(16000)
            output.writeframes(b"\x00\x00" * int(16000 * duration_s))
        return Path(handle.name).read_bytes()


class SciencePipelineTests(unittest.TestCase):
    def test_script_segmentation_preserves_text(self):
        text = "第一句解释现象。第二句解释原因。第三句给出结论。"
        segments = segment_script_for_tts(text, target_chars=12)
        self.assertEqual("".join(segments), text)
        self.assertGreaterEqual(len(segments), 2)

    def test_semantic_motion_classifies_script_content(self):
        self.assertEqual(infer_semantic_motion("阳光经过大气，随后发生散射。", 1), "mechanism")
        self.assertEqual(infer_semantic_motion("日落路径相比正午更长。", 2), "comparison")
        self.assertEqual(infer_semantic_motion("这个过程经历三个阶段。", 3), "timeline")

    def test_semantic_motion_has_distinct_markup(self):
        base = {
            "headline": "光的传播",
            "subline": "观察传播路径",
            "core_title": "传播",
            "steps": ["光源", "大气", "散射", "观察者"],
        }
        outputs = {
            motion: render_semantic_science_markup({**base, "semantic_motion": motion})
            for motion in ("mechanism", "scale", "comparison", "timeline", "system")
        }
        self.assertEqual(len(set(outputs.values())), 5)
        self.assertTrue(all('class="science-board' in markup for markup in outputs.values()))

    def test_caption_does_not_isolate_comma_lead_in(self):
        words = [
            {"text": "与此同时，", "start": 0.0, "end": 0.5},
            {"text": "海底热液", "start": 0.5, "end": 1.1},
            {"text": "也会补充矿物。", "start": 1.1, "end": 2.0},
        ]
        cues = build_subtitle_cues(words)
        self.assertFalse(any(cue["text"] == "与此同时，" for cue in cues))

    def test_caption_merges_too_short_trailing_fragment(self):
        words = [
            {"text": "海水不断蒸发，盐分却大多留在海", "start": 0.0, "end": 2.9},
            {"text": "里。", "start": 2.9, "end": 3.15},
        ]
        cues = build_subtitle_cues(words)
        self.assertEqual(len(cues), 1)
        self.assertEqual(cues[0]["text"], "海水不断蒸发，盐分却大多留在海里。")

    def test_media_scenes_break_on_complete_sentences(self):
        words = [
            {"text": "海水为什么是咸的？", "start": 0.0, "end": 1.8},
            {"text": "雨水会溶解岩石中的矿物盐。", "start": 1.8, "end": 7.8},
            {"text": "河流将盐分带入海洋。", "start": 7.8, "end": 13.4},
            {"text": "海水蒸发后盐分继续留存。", "start": 13.4, "end": 19.2},
        ]
        seed = build_audio_scene_seed(words)
        self.assertEqual(seed["scene_count"], 3)
        self.assertLessEqual(max(scene["duration_s"] for scene in seed["scenes"]), 8.5)

    @patch.object(aliyun_speech, "speech_settings")
    @patch.object(aliyun_speech.requests, "request")
    def test_aliyun_tts_downloads_audio(self, request: Mock, settings: Mock):
        settings.return_value = {
            "api_key": "test",
            "base_url": "https://speech.example/api/v1",
            "compatible_base_url": "https://speech.example/compatible-mode/v1",
            "tts_model": "qwen3-tts-flash",
            "tts_voice": "Cherry",
            "asr_model": "qwen3-asr-flash",
        }
        request.side_effect = [
            Mock(ok=True, status_code=200, json=lambda: {"request_id": "r1", "output": {"audio": {"url": "https://audio.example/a.wav"}}}),
            Mock(ok=True, status_code=200, content=wav_bytes(), raise_for_status=lambda: None),
        ]
        with tempfile.TemporaryDirectory() as temp:
            output = Path(temp) / "voice.wav"
            meta = aliyun_speech.synthesize_speech("天空为什么是蓝色的？", output)
            self.assertTrue(output.is_file())
            self.assertEqual(meta["provider"], "aliyun-bailian")
            self.assertGreater(meta["duration_s"], 0)

    @patch.object(aliyun_speech, "speech_settings")
    @patch.object(aliyun_speech.requests, "request")
    def test_aliyun_asr_returns_transcript(self, request: Mock, settings: Mock):
        settings.return_value = {
            "api_key": "test",
            "base_url": "https://speech.example/api/v1",
            "compatible_base_url": "https://speech.example/compatible-mode/v1",
            "tts_model": "qwen3-tts-flash",
            "tts_voice": "Cherry",
            "asr_model": "qwen3-asr-flash",
        }
        request.return_value = Mock(ok=True, status_code=200, json=lambda: {"id": "a1", "choices": [{"message": {"content": "光在大气中发生散射。"}}]})
        with tempfile.TemporaryDirectory() as temp:
            audio = Path(temp) / "input.wav"
            audio.write_bytes(wav_bytes())
            result = aliyun_speech.transcribe_audio_cloud(audio, Path(temp) / "asr")
            self.assertEqual(result["text"], "光在大气中发生散射。")
            self.assertEqual(result["provider"], "aliyun-bailian")

    @patch.object(science_content, "_probe_public_url", return_value="https://example.org/source")
    @patch.object(science_content, "deepseek_settings", return_value={"pro_model": "deepseek-v4-pro"})
    @patch.object(science_content, "create_client")
    def test_topic_mode_creates_structured_brief(self, client: Mock, _settings: Mock, _probe: Mock):
        content = '{"title":"蓝天的颜色","audience":"大众","takeaway":"理解散射","chapters":[{"title":"现象","narration":"抬头看天空，它通常呈现蓝色。","visual_claim":"阳光进入大气","motion":"system","evidence_ids":["S1"]},{"title":"路径","narration":"不同颜色的光会经历不同程度的散射。","visual_claim":"短波更易散开","motion":"mechanism","evidence_ids":["S1"]},{"title":"结论","narration":"我们看到的蓝光来自四面八方。","visual_claim":"散射光进入眼睛","motion":"system","evidence_ids":[]}],"sources":[{"id":"S1","claim":"散射","organization":"示例机构","page":"来源页","url":"https://example.org/source"}]}'
        client.return_value.chat.completions.create.return_value = SimpleNamespace(
            choices=[SimpleNamespace(message=SimpleNamespace(content=content))]
        )
        brief = science_content.generate_science_brief("天空为什么是蓝色", "面向大众", 45)
        self.assertEqual(len(brief["chapters"]), 3)
        self.assertTrue(brief["sources"][0]["url_verified"])

    @patch.object(science_content, "deepseek_settings", return_value={"pro_model": "deepseek-v4-pro"})
    @patch.object(science_content, "create_client")
    def test_long_topic_brief_accepts_wrapped_compression(self, client: Mock, _settings: Mock):
        compact = {
            "brief": {
                "chapters": [
                    {"title": "现象", "narration": "天空通常呈蓝色。", "visual_claim": "蓝天", "motion": "system", "evidence_ids": []},
                    {"title": "散射", "narration": "短波蓝光更易散开。", "visual_claim": "散射", "motion": "mechanism", "evidence_ids": []},
                    {"title": "结论", "narration": "散射光从各处进入眼睛。", "visual_claim": "观察", "motion": "system", "evidence_ids": []},
                ]
            }
        }
        client.return_value.chat.completions.create.return_value = SimpleNamespace(
            choices=[SimpleNamespace(message=SimpleNamespace(content=json.dumps(compact, ensure_ascii=False)))]
        )
        original = {
            "title": "蓝天",
            "sources": [{"id": "S1"}],
            "chapters": [
                {"narration": "这是一段很长的原始讲稿。" * 20},
                {"narration": "继续解释其中的科学机制。" * 20},
                {"narration": "最后给出清晰的科学结论。" * 20},
            ],
        }
        fitted = science_content._fit_narration_length(original, 100)
        self.assertEqual(len(fitted["chapters"]), 3)
        self.assertEqual(fitted["sources"], [{"id": "S1"}])


if __name__ == "__main__":
    unittest.main()
