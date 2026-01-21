from autocoder.server.settings_store import AdvancedSettings, apply_advanced_settings_env, save_advanced_settings


def test_advanced_settings_env_includes_review_and_locks():
    s = AdvancedSettings(
        review_enabled=True,
        review_mode="gate",
        review_timeout_s=12,
        review_model="sonnet",
        review_consensus="all",
        codex_model="gpt-5.2",
        codex_reasoning_effort="high",
        gemini_model="gemini-3-pro-preview",
        locks_enabled=True,
        worker_verify=True,
        qa_fix_enabled=True,
        qa_model="sonnet",
        qa_max_sessions=3,
        qa_subagent_enabled=True,
        qa_subagent_max_iterations=2,
        controller_enabled=True,
        controller_model="haiku",
        controller_max_sessions=2,
        planner_enabled=True,
        planner_model="sonnet",
        planner_synthesizer="claude",
        planner_timeout_s=123,
        initializer_synthesizer="claude",
        initializer_timeout_s=333,
        initializer_stage_threshold=150,
        initializer_enqueue_count=40,
        logs_prune_artifacts=True,
        diagnostics_fixtures_dir="C:/tmp/autocoder-e2e",
    )
    env = s.to_env()
    assert env["AUTOCODER_REVIEW_ENABLED"] == "1"
    assert env["AUTOCODER_REVIEW_MODE"] == "gate"
    assert env["AUTOCODER_REVIEW_TIMEOUT_S"] == "12"
    assert env["AUTOCODER_REVIEW_MODEL"] == "sonnet"
    assert env["AUTOCODER_REVIEW_CONSENSUS"] == "all"
    assert env["AUTOCODER_CODEX_MODEL"] == "gpt-5.2"
    assert env["AUTOCODER_CODEX_REASONING_EFFORT"] == "high"
    assert env["AUTOCODER_GEMINI_MODEL"] == "gemini-3-pro-preview"
    assert env["AUTOCODER_LOCKS_ENABLED"] == "1"
    assert env["AUTOCODER_WORKER_VERIFY"] == "1"
    assert env["AUTOCODER_QA_FIX_ENABLED"] == "1"
    assert env["AUTOCODER_QA_MODEL"] == "sonnet"
    assert env["AUTOCODER_QA_MAX_SESSIONS"] == "3"
    assert env["AUTOCODER_QA_SUBAGENT_ENABLED"] == "1"
    assert env["AUTOCODER_QA_SUBAGENT_MAX_ITERATIONS"] == "2"
    assert env["AUTOCODER_CONTROLLER_ENABLED"] == "1"
    assert env["AUTOCODER_CONTROLLER_MODEL"] == "haiku"
    assert env["AUTOCODER_CONTROLLER_MAX_SESSIONS"] == "2"
    assert env["AUTOCODER_PLANNER_ENABLED"] == "1"
    assert env["AUTOCODER_PLANNER_MODEL"] == "sonnet"
    assert env["AUTOCODER_PLANNER_SYNTHESIZER"] == "claude"
    assert env["AUTOCODER_PLANNER_TIMEOUT_S"] == "123"
    assert env["AUTOCODER_INITIALIZER_SYNTHESIZER"] == "claude"
    assert env["AUTOCODER_INITIALIZER_TIMEOUT_S"] == "333"
    assert env["AUTOCODER_INITIALIZER_STAGE_THRESHOLD"] == "150"
    assert env["AUTOCODER_INITIALIZER_ENQUEUE_COUNT"] == "40"
    assert env["AUTOCODER_LOGS_PRUNE_ARTIFACTS"] == "1"
    assert env["AUTOCODER_DIAGNOSTICS_FIXTURES_DIR"] == "C:/tmp/autocoder-e2e"


def test_apply_advanced_settings_env_does_not_override_when_not_persisted(tmp_path, monkeypatch):
    monkeypatch.setenv("AUTOCODER_SETTINGS_DB_PATH", str(tmp_path / "settings.db"))
    env = {"AUTOCODER_REVIEW_MODEL": "opus", "AUTOCODER_CODEX_MODEL": "gpt-5.2"}
    out = apply_advanced_settings_env(env.copy())
    assert out["AUTOCODER_REVIEW_MODEL"] == "opus"
    assert out["AUTOCODER_CODEX_MODEL"] == "gpt-5.2"


def test_apply_advanced_settings_env_overrides_env_when_persisted(tmp_path, monkeypatch):
    monkeypatch.setenv("AUTOCODER_SETTINGS_DB_PATH", str(tmp_path / "settings.db"))
    save_advanced_settings(
        AdvancedSettings(
            review_model="sonnet",
            codex_model="",  # blank should not override env
        )
    )
    env = {"AUTOCODER_REVIEW_MODEL": "opus", "AUTOCODER_CODEX_MODEL": "gpt-5.2"}
    out = apply_advanced_settings_env(env.copy())
    assert out["AUTOCODER_REVIEW_MODEL"] == "sonnet"
    assert out["AUTOCODER_CODEX_MODEL"] == "gpt-5.2"
