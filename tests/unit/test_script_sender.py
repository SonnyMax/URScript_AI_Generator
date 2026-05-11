import socket
import pytest
from unittest.mock import patch, MagicMock
from urscript_app.robot.script_sender import send_script, ScriptSendError, _ensure_wrapped


def test_ensure_wrapped_adds_def():
    code = "movej([0]*6, a=0.5, v=0.5)"
    result = _ensure_wrapped(code)
    assert result.startswith("def program():")
    assert "end" in result


def test_ensure_wrapped_leaves_existing_def():
    code = "def my_prog():\n  movej([0]*6, a=0.5, v=0.5)\nend"
    result = _ensure_wrapped(code)
    assert result.startswith("def my_prog():")


def test_ensure_wrapped_ends_with_newline():
    result = _ensure_wrapped("movej([0]*6)")
    assert result.endswith("\n")


def test_send_script_success():
    with patch("socket.create_connection") as mock_conn:
        mock_sock = MagicMock()
        mock_conn.return_value.__enter__ = lambda s: mock_sock
        mock_conn.return_value.__exit__ = MagicMock(return_value=False)
        send_script("def p():\n  movej([0]*6)\nend")
        mock_sock.sendall.assert_called_once()


def test_send_script_raises_on_connection_error():
    with patch("socket.create_connection", side_effect=OSError("refused")):
        with pytest.raises(ScriptSendError):
            send_script("def p():\nend")
