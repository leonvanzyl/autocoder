from autocoder.server.settings_store import AdvancedSettings


def test_advanced_settings_env_includes_review_and_locks():
    s = AdvancedSettings(
        review_enabled=True,
        review_mode="gate",
        review_type="multi_cli",
        review_command="echo ok",
        review_timeout_s=12,
        review_model="sonnet",
        review_agents="codex,gemini",
        review_consensus="all",
        codex_model="gpt-5.2",
        codex_reasoning_effort="high",
        gemini_model="gemini-3-pro-preview",
        locks_enabled=True,
        worker_verify=True,
        worker_provider="multi_cli",
        worker_patch_max_iterations=3,
        worker_patch_agents="codex,gemini",
        qa_fix_enabled=True,
        qa_model="sonnet",
        qa_max_sessions=3,
        qa_subagent_enabled=True,
        qa_subagent_max_iterations=2,
        qa_subagent_provider="multi_cli",
        qa_subagent_agents="codex,gemini",
        controller_enabled=True,
        controller_model="haiku",
        controller_max_sessions=2,
        planner_enabled=True,
        planner_model="sonnet",
        planner_agents="codex,gemini",
        planner_synthesizer="claude",
        planner_timeout_s=123,
        logs_prune_artifacts=True,
        diagnostics_fixtures_dir="C:/tmp/autocoder-e2e",
    )
    env = s.to_env()
    assert env["AUTOCODER_REVIEW_ENABLED"] == "1"
    assert env["AUTOCODER_REVIEW_MODE"] == "gate"
    assert env["AUTOCODER_REVIEW_TYPE"] == "multi_cli"
    assert env["AUTOCODER_REVIEW_COMMAND"] == "echo ok"
    assert env["AUTOCODER_REVIEW_TIMEOUT_S"] == "12"
    assert env["AUTOCODER_REVIEW_MODEL"] == "sonnet"
    assert env["AUTOCODER_REVIEW_AGENTS"] == "codex,gemini"
    assert env["AUTOCODER_REVIEW_CONSENSUS"] == "all"
    assert env["AUTOCODER_CODEX_MODEL"] == "gpt-5.2"
    assert env["AUTOCODER_CODEX_REASONING_EFFORT"] == "high"
    assert env["AUTOCODER_GEMINI_MODEL"] == "gemini-3-pro-preview"
    assert env["AUTOCODER_LOCKS_ENABLED"] == "1"
    assert env["AUTOCODER_WORKER_VERIFY"] == "1"
    assert env["AUTOCODER_WORKER_PROVIDER"] == "multi_cli"
    assert env["AUTOCODER_WORKER_PATCH_MAX_ITERATIONS"] == "3"
    assert env["AUTOCODER_WORKER_PATCH_AGENTS"] == "codex,gemini"
    assert env["AUTOCODER_QA_FIX_ENABLED"] == "1"
    assert env["AUTOCODER_QA_MODEL"] == "sonnet"
    assert env["AUTOCODER_QA_MAX_SESSIONS"] == "3"
    assert env["AUTOCODER_QA_SUBAGENT_ENABLED"] == "1"
    assert env["AUTOCODER_QA_SUBAGENT_MAX_ITERATIONS"] == "2"
    assert env["AUTOCODER_QA_SUBAGENT_PROVIDER"] == "multi_cli"
    assert env["AUTOCODER_QA_SUBAGENT_AGENTS"] == "codex,gemini"
    assert env["AUTOCODER_CONTROLLER_ENABLED"] == "1"
    assert env["AUTOCODER_CONTROLLER_MODEL"] == "haiku"
    assert env["AUTOCODER_CONTROLLER_MAX_SESSIONS"] == "2"
    assert env["AUTOCODER_PLANNER_ENABLED"] == "1"
    assert env["AUTOCODER_PLANNER_MODEL"] == "sonnet"
    assert env["AUTOCODER_PLANNER_AGENTS"] == "codex,gemini"
    assert env["AUTOCODER_PLANNER_SYNTHESIZER"] == "claude"
    assert env["AUTOCODER_PLANNER_TIMEOUT_S"] == "123"
    assert env["AUTOCODER_LOGS_PRUNE_ARTIFACTS"] == "1"
    assert env["AUTOCODER_DIAGNOSTICS_FIXTURES_DIR"] == "C:/tmp/autocoder-e2e"
