import asyncio
import threading

from autocoder.generation import multi_model
from autocoder.generation.multi_model import MultiModelGenerateConfig, generate_multi_model_artifact


def test_generate_multi_model_artifact_claude_synth_inside_event_loop(tmp_path, monkeypatch):
    called = {}

    async def fake_synthesize(prompt: str, model: str, workdir, timeout_s: int):
        called["thread"] = threading.current_thread().name
        return True, "OK", ""

    monkeypatch.setattr(multi_model, "_claude_synthesize", fake_synthesize)

    out_path = tmp_path / "plan.md"
    cfg = MultiModelGenerateConfig(agents=[], synthesizer="claude", timeout_s=10)

    async def runner():
        generate_multi_model_artifact(
            project_dir=tmp_path,
            kind="plan",
            user_prompt="test",
            cfg=cfg,
            output_path=out_path,
            drafts_root=tmp_path / "drafts",
            synthesize=True,
        )

    asyncio.run(runner())

    assert out_path.exists()
    assert out_path.read_text(encoding="utf-8") == "OK"
    assert called
    assert called["thread"] != "MainThread"

