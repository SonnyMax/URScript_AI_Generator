import pytest
from urscript_app.validator.validate import validate


VALID_BASIC = """
def program():
  home = [0.0, -1.5708, 0.0, -1.5708, 0.0, 0.0]
  movej(home, a=0.5, v=0.5)
end
"""

VALID_WITH_IO = """
def program():
  set_digital_out(0, True)
  sleep(0.5)
  set_digital_out(0, False)
end
"""

MISSING_END = """
def program():
  movej([0.0, 0.0, 0.0, 0.0, 0.0, 0.0], a=0.5, v=0.5)
"""

NO_DEF = "movej([0.0]*6, a=0.5, v=0.5)"

NESTED_IF_MISSING_END = """
def program():
  if True:
    movej([0.0, 0.0, 0.0, 0.0, 0.0, 0.0], a=0.5, v=0.5)
end
"""

BANNED_SOCKET = """
def program():
  socket_open("192.168.1.1", 80)
end
"""

ACCEL_TOO_HIGH = """
def program():
  movej([0.0, 0.0, 0.0, 0.0, 0.0, 0.0], a=5.0, v=0.5)
end
"""

VEL_TOO_HIGH = """
def program():
  movej([0.0, 0.0, 0.0, 0.0, 0.0, 0.0], a=0.5, v=5.0)
end
"""

WORKSPACE_EXCEEDED = """
def program():
  p1 = p[2.0, 2.0, 2.0, 0.0, 0.0, 0.0]
  movel(p1, a=0.5, v=0.2)
end
"""


def test_valid_basic():
    r = validate(VALID_BASIC)
    assert r.valid


def test_valid_with_io():
    r = validate(VALID_WITH_IO)
    assert r.valid


def test_missing_end_is_error():
    r = validate(MISSING_END)
    assert not r.valid
    assert any("end" in e.message.lower() or "unclosed" in e.message.lower() for e in r.errors)


def test_no_def_wrapper_is_error():
    r = validate(NO_DEF)
    assert not r.valid
    assert any("def" in e.message.lower() for e in r.errors)


def test_nested_if_missing_end():
    r = validate(NESTED_IF_MISSING_END)
    assert not r.valid


def test_banned_socket():
    r = validate(BANNED_SOCKET)
    assert not r.valid
    assert any("socket_open" in e.message for e in r.errors)


def test_accel_too_high():
    r = validate(ACCEL_TOO_HIGH)
    assert not r.valid
    assert any("acceleration" in e.message.lower() for e in r.errors)


def test_velocity_too_high():
    r = validate(VEL_TOO_HIGH)
    assert not r.valid
    assert any("velocity" in e.message.lower() for e in r.errors)


def test_workspace_exceeded():
    r = validate(WORKSPACE_EXCEEDED)
    assert not r.valid
    assert any("radius" in e.message.lower() or "workspace" in e.message.lower() for e in r.errors)
