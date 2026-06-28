import pytest
from pathlib import Path

from scripts.eml import eml_a_pdf


@pytest.fixture(autouse=True)
def clear_browser_cache():
    eml_a_pdf._HEADLESS_BROWSER_CACHE = None
    yield
    eml_a_pdf._HEADLESS_BROWSER_CACHE = None


def test_darwin_finds_chrome_in_applications(monkeypatch):
    monkeypatch.setattr(eml_a_pdf.platform, "system", lambda: "Darwin")
    chrome_path = Path("/Applications/Google Chrome.app/Contents/MacOS/Google Chrome")

    monkeypatch.setattr(
        eml_a_pdf,
        "_is_executable",
        lambda path: Path(path) == chrome_path,
    )

    assert eml_a_pdf._find_headless_browser() == str(chrome_path)


def test_darwin_finds_edge_in_user_applications(monkeypatch):
    monkeypatch.setattr(eml_a_pdf.platform, "system", lambda: "Darwin")
    edge_path = Path.home() / "Applications/Microsoft Edge.app/Contents/MacOS/Microsoft Edge"

    monkeypatch.setattr(
        eml_a_pdf,
        "_is_executable",
        lambda path: Path(path) == edge_path,
    )

    assert eml_a_pdf._find_headless_browser() == str(edge_path)


def test_darwin_prefers_chrome_over_edge(monkeypatch):
    monkeypatch.setattr(eml_a_pdf.platform, "system", lambda: "Darwin")
    chrome_path = Path("/Applications/Google Chrome.app/Contents/MacOS/Google Chrome")
    edge_path = Path("/Applications/Microsoft Edge.app/Contents/MacOS/Microsoft Edge")

    monkeypatch.setattr(
        eml_a_pdf,
        "_is_executable",
        lambda path: Path(path) in {chrome_path, edge_path},
    )

    assert eml_a_pdf._find_headless_browser() == str(chrome_path)


def test_darwin_no_browser_raises(monkeypatch):
    monkeypatch.setattr(eml_a_pdf.platform, "system", lambda: "Darwin")
    monkeypatch.setattr(eml_a_pdf, "_is_executable", lambda path: False)

    with pytest.raises(RuntimeError, match="No se encontró Google Chrome"):
        eml_a_pdf._find_headless_browser()


def test_windows_existing_paths(monkeypatch):
    monkeypatch.setattr(eml_a_pdf.platform, "system", lambda: "Windows")
    chrome_path = Path(r"C:\Program Files\Google\Chrome\Application\chrome.exe")

    monkeypatch.setattr(eml_a_pdf, "_which_candidates", lambda *names: [])
    monkeypatch.setattr(
        eml_a_pdf,
        "_is_executable",
        lambda path: Path(path) == chrome_path,
    )

    assert eml_a_pdf._find_headless_browser() == str(chrome_path)


def test_linux_which_chromium(monkeypatch):
    monkeypatch.setattr(eml_a_pdf.platform, "system", lambda: "Linux")
    chromium_path = Path("/usr/bin/chromium")

    monkeypatch.setattr(
        eml_a_pdf,
        "_which_candidates",
        lambda *names: [chromium_path] if "chromium" in names else [],
    )
    monkeypatch.setattr(
        eml_a_pdf,
        "_is_executable",
        lambda path: Path(path) == chromium_path,
    )

    assert eml_a_pdf._find_headless_browser() == str(chromium_path)


def test_expanduser_in_candidates(monkeypatch):
    monkeypatch.setattr(eml_a_pdf.platform, "system", lambda: "Darwin")
    user_chrome = Path("~/Applications/Google Chrome.app/Contents/MacOS/Google Chrome")
    expected = user_chrome.expanduser()

    monkeypatch.setattr(
        eml_a_pdf,
        "_is_executable",
        lambda path: Path(path) == expected,
    )

    assert eml_a_pdf._find_headless_browser() == str(expected)


def test_browser_result_is_cached(monkeypatch):
    monkeypatch.setattr(eml_a_pdf.platform, "system", lambda: "Darwin")
    chrome_path = Path("/Applications/Google Chrome.app/Contents/MacOS/Google Chrome")
    calls = {"count": 0}

    def fake_is_executable(path):
        calls["count"] += 1
        return Path(path) == chrome_path

    monkeypatch.setattr(eml_a_pdf, "_is_executable", fake_is_executable)

    first = eml_a_pdf._find_headless_browser()
    count_after_first = calls["count"]
    second = eml_a_pdf._find_headless_browser()

    assert first == second == str(chrome_path)
    assert calls["count"] == count_after_first
