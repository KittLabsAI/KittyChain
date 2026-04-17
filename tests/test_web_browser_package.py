import importlib
import time


def test_web_browser_package_exports_main_tool_and_subprocess():
    module = importlib.import_module("kittychain.tools.web_browser")

    assert hasattr(module, "WebBrowserTool")
    assert hasattr(module, "main")
    assert hasattr(module, "subprocess")


def test_web_browser_cleanup_stale_sessions_closes_expired_session(monkeypatch):
    module = importlib.import_module("kittychain.tools.web_browser")

    closed = []
    monkeypatch.setattr(module, "_close_session", lambda session, timeout: closed.append((session, timeout)))

    module._ACTIVE_SESSIONS.clear()
    module._ACTIVE_SESSIONS["stale-session"] = time.time() - 999

    module.cleanup_stale_sessions(max_idle_seconds=10, timeout=7)

    assert closed == [("stale-session", 7)]
    assert "stale-session" not in module._ACTIVE_SESSIONS


def test_web_browser_cleanup_all_sessions_closes_everything(monkeypatch):
    module = importlib.import_module("kittychain.tools.web_browser")

    closed = []
    monkeypatch.setattr(module, "_close_session", lambda session, timeout: closed.append((session, timeout)))

    module._ACTIVE_SESSIONS.clear()
    module._ACTIVE_SESSIONS["s1"] = 1.0
    module._ACTIVE_SESSIONS["s2"] = 2.0

    module.cleanup_all_sessions(timeout=9)

    assert closed == [("s1", 9), ("s2", 9)]
    assert module._ACTIVE_SESSIONS == {}
