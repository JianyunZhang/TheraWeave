from pathlib import Path

import pytest

from theraweave import core


def test_transient_windows_publication_error_retries_without_overwriting(tmp_path, monkeypatch):
    source, target = tmp_path / "source", tmp_path / "target"
    source.mkdir()
    (source / "data").write_text("complete", encoding="utf-8")
    real_rename, calls = Path.rename, []
    def transient(self, destination):
        calls.append(destination)
        if len(calls) == 1:
            error = PermissionError("synthetic transient conflict")
            error.winerror = 5
            raise error
        return real_rename(self, destination)
    monkeypatch.setattr(core, "_ON_WINDOWS", True)
    monkeypatch.setattr(core.time, "sleep", lambda seconds: None)
    monkeypatch.setattr(Path, "rename", transient)
    core.publish_directory(source, target)
    assert len(calls) == 2 and (target / "data").read_text(encoding="utf-8") == "complete"


def test_persistent_publication_error_is_bounded_and_existing_target_is_protected(tmp_path, monkeypatch):
    source, target = tmp_path / "source", tmp_path / "target"
    source.mkdir()
    calls = []
    def denied(self, destination):
        calls.append(destination)
        error = PermissionError("synthetic persistent failure")
        error.winerror = 32
        raise error
    monkeypatch.setattr(core, "_ON_WINDOWS", True)
    monkeypatch.setattr(core.time, "sleep", lambda seconds: None)
    monkeypatch.setattr(Path, "rename", denied)
    with pytest.raises(PermissionError):
        core.publish_directory(source, target)
    assert len(calls) == 5 and source.exists() and not target.exists()
    target.mkdir()
    with pytest.raises(FileExistsError):
        core.publish_directory(source, target)
    assert len(calls) == 5
