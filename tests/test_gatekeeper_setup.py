from pathlib import Path

import autocoder.core.gatekeeper as gatekeeper_mod
from autocoder.core.gatekeeper import Gatekeeper


def test_select_node_install_command_prefers_pnpm_lock(tmp_path, monkeypatch):
    (tmp_path / "package.json").write_text("{}", encoding="utf-8")
    (tmp_path / "pnpm-lock.yaml").write_text("lock", encoding="utf-8")

    monkeypatch.setattr(gatekeeper_mod.shutil, "which", lambda name: "x" if name == "pnpm" else None)
    assert Gatekeeper._select_node_install_command(Path(tmp_path)) == "pnpm install --frozen-lockfile"


def test_select_node_install_command_prefers_yarn_lock(tmp_path, monkeypatch):
    (tmp_path / "package.json").write_text("{}", encoding="utf-8")
    (tmp_path / "yarn.lock").write_text("lock", encoding="utf-8")

    monkeypatch.setattr(gatekeeper_mod.shutil, "which", lambda name: "x" if name == "yarn" else None)
    assert Gatekeeper._select_node_install_command(Path(tmp_path)) == "yarn install --frozen-lockfile"


def test_select_node_install_command_uses_npm_ci_when_lockfile_present(tmp_path, monkeypatch):
    (tmp_path / "package.json").write_text("{}", encoding="utf-8")
    (tmp_path / "package-lock.json").write_text("lock", encoding="utf-8")

    monkeypatch.setattr(gatekeeper_mod.shutil, "which", lambda name: "x" if name == "npm" else None)
    assert Gatekeeper._select_node_install_command(Path(tmp_path)) == "npm ci"


def test_select_node_install_command_falls_back_to_npm_install(tmp_path, monkeypatch):
    (tmp_path / "package.json").write_text("{}", encoding="utf-8")

    monkeypatch.setattr(gatekeeper_mod.shutil, "which", lambda name: "x" if name == "npm" else None)
    assert Gatekeeper._select_node_install_command(Path(tmp_path)) == "npm install"

