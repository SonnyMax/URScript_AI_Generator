import threading
import pytest
from unittest.mock import MagicMock, patch


def _make_supervisor():
    # Import fresh to avoid singleton state
    from urscript_app.robot import safety
    sup = safety.SafetySupervisor()
    return sup


def test_stop_not_requested_initially():
    sup = _make_supervisor()
    assert not sup.is_stop_requested()


def test_request_stop_sets_flag():
    sup = _make_supervisor()
    with patch("urscript_app.robot.safety.get_rtde_client") as mock_client:
        mock_client.return_value.stop_motion = MagicMock()
        with patch("urscript_app.robot.script_sender.send_script"):
            sup.request_stop()
    assert sup.is_stop_requested()


def test_stop_is_idempotent():
    sup = _make_supervisor()
    with patch("urscript_app.robot.safety.get_rtde_client") as mock_client:
        mock_client.return_value.stop_motion = MagicMock()
        with patch("urscript_app.robot.script_sender.send_script"):
            sup.request_stop()
            sup.request_stop()
    assert sup.is_stop_requested()


def test_clear_resets_flag():
    sup = _make_supervisor()
    with patch("urscript_app.robot.safety.get_rtde_client") as mock_client:
        mock_client.return_value.stop_motion = MagicMock()
        with patch("urscript_app.robot.script_sender.send_script"):
            sup.request_stop()
    sup.clear()
    assert not sup.is_stop_requested()


def test_thread_safety():
    sup = _make_supervisor()
    results = []

    def set_stop():
        with patch("urscript_app.robot.safety.get_rtde_client") as mock_client:
            mock_client.return_value.stop_motion = MagicMock()
            with patch("urscript_app.robot.script_sender.send_script"):
                sup.request_stop()
        results.append(sup.is_stop_requested())

    threads = [threading.Thread(target=set_stop) for _ in range(10)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert all(results)
