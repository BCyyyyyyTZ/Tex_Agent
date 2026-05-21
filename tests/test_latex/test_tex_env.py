from __future__ import annotations

from latex.tex_env import TexEnvStatus, probe_tex_env


def test_probe_tex_env_returns_model(monkeypatch) -> None:
    def fake_which(name: str):
        if name == "chktex":
            return "/usr/bin/chktex"
        return None

    monkeypatch.setattr("latex.tex_env.shutil.which", fake_which)
    env = probe_tex_env()
    assert isinstance(env, TexEnvStatus)
    assert env.chktex is True
    assert env.latexmk is False
    assert env.paths["chktex"] == "/usr/bin/chktex"
