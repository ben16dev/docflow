import sys
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from utils import platform_open


def test_open_path_uses_startfile_on_windows(monkeypatch):
    monkeypatch.setattr(platform_open.sys, "platform", "win32")
    startfile = MagicMock()
    monkeypatch.setattr(platform_open.os, "startfile", startfile, raising=False)

    target = Path("C:/logs/docflow.log")
    platform_open.open_path(target)

    startfile.assert_called_once_with(str(target))


def test_open_path_uses_open_on_darwin(monkeypatch):
    monkeypatch.setattr(platform_open.sys, "platform", "darwin")
    popen = MagicMock()
    monkeypatch.setattr(platform_open.subprocess, "Popen", popen)

    target = Path("/tmp/docflow.log")
    platform_open.open_path(target)

    popen.assert_called_once_with(["open", str(target)])


def test_open_path_uses_xdg_open_on_linux(monkeypatch):
    monkeypatch.setattr(platform_open.sys, "platform", "linux")
    popen = MagicMock()
    monkeypatch.setattr(platform_open.subprocess, "Popen", popen)

    target = Path("/tmp/docflow.log")
    platform_open.open_path(target)

    popen.assert_called_once_with(["xdg-open", str(target)])
