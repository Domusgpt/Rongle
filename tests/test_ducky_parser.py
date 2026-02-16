"""Tests for DuckyScriptParser — scancode correctness, commands, combos."""

import struct
import pytest
from rongle_operator.hygienic_actuator.ducky_parser import (
    DuckyScriptParser,
    KeyboardReport,
    MouseReport,
    Modifier,
    ParsedCommand,
    _SCANCODE_MAP,
    _SHIFTED_MAP,
    _SPECIAL_KEYS,
    _MODIFIER_ALIASES,
)
from rongle_operator.hygienic_actuator.humanizer import Humanizer


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------
@pytest.fixture
def parser():
    return DuckyScriptParser(screen_w=1920, screen_h=1080)


# ---------------------------------------------------------------------------
# Scancode map coverage
# ---------------------------------------------------------------------------
class TestScancodeMaps:
    def test_lowercase_letters_mapped(self):
        for ch in "abcdefghijklmnopqrstuvwxyz":
            assert ch in _SCANCODE_MAP, f"Missing scancode for '{ch}'"
            assert 0x04 <= _SCANCODE_MAP[ch] <= 0x1D

    def test_digits_mapped(self):
        for ch in "1234567890":
            assert ch in _SCANCODE_MAP, f"Missing scancode for '{ch}'"

    def test_punctuation_mapped(self):
        for ch in "-=[]\\;',./":
            assert ch in _SCANCODE_MAP, f"Missing scancode for '{ch}'"

    def test_shifted_chars_mapped(self):
        for ch in "!@#$%^&*()_+{}|:\"~<>?":
            assert ch in _SHIFTED_MAP, f"Missing shifted map for '{ch}'"
            mod, code = _SHIFTED_MAP[ch]
            assert mod == Modifier.LEFT_SHIFT
            assert code > 0

    def test_special_keys_mapped(self):
        required = [
            "ENTER", "ESCAPE", "BACKSPACE", "TAB", "SPACE",
            "F1", "F2", "F3", "F4", "F5", "F6",
            "F7", "F8", "F9", "F10", "F11", "F12",
            "INSERT", "HOME", "PAGEUP", "DELETE", "END", "PAGEDOWN",
            "RIGHT", "LEFT", "DOWN", "UP",
        ]
        for key in required:
            assert key in _SPECIAL_KEYS, f"Missing special key: {key}"

    def test_modifier_aliases(self):
        assert "CTRL" in _MODIFIER_ALIASES
        assert "SHIFT" in _MODIFIER_ALIASES
        assert "ALT" in _MODIFIER_ALIASES
        assert "GUI" in _MODIFIER_ALIASES
        assert "WINDOWS" in _MODIFIER_ALIASES
        assert "COMMAND" in _MODIFIER_ALIASES

    def test_aliases_resolve_same(self):
        assert _MODIFIER_ALIASES["GUI"] == _MODIFIER_ALIASES["WINDOWS"]
        assert _MODIFIER_ALIASES["GUI"] == _MODIFIER_ALIASES["COMMAND"]
        assert _MODIFIER_ALIASES["CTRL"] == _MODIFIER_ALIASES["CONTROL"]


# ---------------------------------------------------------------------------
# KeyboardReport
# ---------------------------------------------------------------------------
class TestKeyboardReport:
    def test_pack_size(self):
        report = KeyboardReport(modifier=0, keys=[0x04])
        packed = report.pack()
        assert len(packed) == 8

    def test_release_is_zeros(self):
        release = KeyboardReport.release()
        assert release == b"\x00" * 8
        assert len(release) == 8

    def test_modifier_in_first_byte(self):
        report = KeyboardReport(modifier=Modifier.LEFT_CTRL, keys=[0x04])
        packed = report.pack()
        assert packed[0] == Modifier.LEFT_CTRL

    def test_key_in_third_byte(self):
        report = KeyboardReport(modifier=0, keys=[0x28])  # ENTER
        packed = report.pack()
        assert packed[2] == 0x28

    def test_multiple_keys(self):
        report = KeyboardReport(modifier=0, keys=[0x04, 0x05, 0x06])
        packed = report.pack()
        assert packed[2] == 0x04
        assert packed[3] == 0x05
        assert packed[4] == 0x06


# ---------------------------------------------------------------------------
# MouseReport
# ---------------------------------------------------------------------------
class TestMouseReport:
    def test_pack_size(self):
        report = MouseReport(buttons=0, dx=10, dy=-5, wheel=0)
        packed = report.pack()
        assert len(packed) == 4

    def test_release_is_zeros(self):
        assert MouseReport.release() == b"\x00" * 4

    def test_negative_deltas(self):
        report = MouseReport(buttons=0, dx=-50, dy=-100, wheel=0)
        packed = report.pack()
        # Unpack as signed bytes
        buttons, dx, dy, wheel = struct.unpack("Bbbb", packed)
        assert dx == -50
        assert dy == -100

    def test_button_byte(self):
        report = MouseReport(buttons=1, dx=0, dy=0, wheel=0)
        packed = report.pack()
        assert packed[0] == 1  # left button


# ---------------------------------------------------------------------------
# STRING command
# ---------------------------------------------------------------------------
class TestStringCommand:
    def test_string_basic(self, parser):
        cmds = parser.parse("STRING hello")
        assert len(cmds) == 1
        assert cmds[0].kind == "string"
        assert cmds[0].string_chars == "hello"

    def test_stringln_adds_newline(self, parser):
        cmds = parser.parse("STRINGLN hello")
        assert len(cmds) == 1
        assert cmds[0].string_chars == "hello\n"

    def test_string_preserves_case(self, parser):
        cmds = parser.parse("STRING Hello World")
        assert cmds[0].string_chars == "Hello World"

    def test_char_to_report_lowercase(self, parser):
        report = parser.char_to_report("a")
        assert report.modifier == Modifier.NONE
        assert report.keys[0] == 0x04

    def test_char_to_report_uppercase(self, parser):
        report = parser.char_to_report("A")
        assert report.modifier == Modifier.LEFT_SHIFT
        assert report.keys[0] == 0x04

    def test_char_to_report_shifted_symbol(self, parser):
        report = parser.char_to_report("!")
        assert report.modifier == Modifier.LEFT_SHIFT
        assert report.keys[0] == 0x1E  # '1' scancode

    def test_string_to_reports_length(self, parser):
        reports = parser.string_to_reports("abc")
        assert len(reports) == 3


# ---------------------------------------------------------------------------
# DELAY command
# ---------------------------------------------------------------------------
class TestDelayCommand:
    def test_delay_parsed(self, parser):
        cmds = parser.parse("DELAY 500")
        assert len(cmds) == 1
        assert cmds[0].kind == "delay"
        assert cmds[0].delay_ms == 500

    def test_delay_zero(self, parser):
        cmds = parser.parse("DELAY 0")
        assert cmds[0].delay_ms == 0


# ---------------------------------------------------------------------------
# MOUSE commands
# ---------------------------------------------------------------------------
class TestMouseCommands:
    def test_mouse_move_returns_points(self, parser):
        cmds = parser.parse("MOUSE_MOVE 500 300")
        assert len(cmds) == 1
        assert cmds[0].kind == "mouse_move"
        assert cmds[0].mouse_points is not None
        assert len(cmds[0].mouse_points) > 0

    def test_mouse_click_left(self, parser):
        cmds = parser.parse("MOUSE_CLICK LEFT")
        assert len(cmds) == 1
        assert cmds[0].kind == "mouse_click"
        assert cmds[0].mouse_button == 1

    def test_mouse_click_right(self, parser):
        cmds = parser.parse("MOUSE_CLICK RIGHT")
        assert cmds[0].mouse_button == 2

    def test_mouse_click_middle(self, parser):
        cmds = parser.parse("MOUSE_CLICK MIDDLE")
        assert cmds[0].mouse_button == 4

    def test_mouse_click_default_left(self, parser):
        cmds = parser.parse("MOUSE_CLICK")
        assert cmds[0].mouse_button == 1

    def test_mouse_move_updates_cursor(self, parser):
        parser.parse("MOUSE_MOVE 100 200")
        assert parser._cursor_x == 100.0
        assert parser._cursor_y == 200.0


# ---------------------------------------------------------------------------
# Modifier combos
# ---------------------------------------------------------------------------
class TestModifierCombos:
    def test_ctrl_c(self, parser):
        cmds = parser.parse("CTRL c")
        assert len(cmds) == 1
        assert cmds[0].kind == "keyboard"
        report = cmds[0].keyboard_report
        assert report.modifier & Modifier.LEFT_CTRL
        assert report.keys[0] == _SCANCODE_MAP["c"]

    def test_gui_r(self, parser):
        cmds = parser.parse("GUI r")
        assert len(cmds) == 1
        report = cmds[0].keyboard_report
        assert report.modifier & Modifier.LEFT_GUI
        assert report.keys[0] == _SCANCODE_MAP["r"]

    def test_ctrl_alt_delete(self, parser):
        cmds = parser.parse("CTRL ALT DELETE")
        report = cmds[0].keyboard_report
        assert report.modifier & Modifier.LEFT_CTRL
        assert report.modifier & Modifier.LEFT_ALT
        assert report.keys[0] == _SPECIAL_KEYS["DELETE"]

    def test_shift_tab(self, parser):
        cmds = parser.parse("SHIFT TAB")
        report = cmds[0].keyboard_report
        assert report.modifier & Modifier.LEFT_SHIFT
        assert report.keys[0] == _SPECIAL_KEYS["TAB"]

    def test_single_enter(self, parser):
        cmds = parser.parse("ENTER")
        report = cmds[0].keyboard_report
        assert report.keys[0] == _SPECIAL_KEYS["ENTER"]

    def test_single_escape(self, parser):
        cmds = parser.parse("ESCAPE")
        report = cmds[0].keyboard_report
        assert report.keys[0] == _SPECIAL_KEYS["ESCAPE"]


# ---------------------------------------------------------------------------
# REPEAT command
# ---------------------------------------------------------------------------
class TestRepeatCommand:
    def test_repeat_duplicates(self, parser):
        cmds = parser.parse("STRING a\nREPEAT 3")
        assert len(cmds) == 4  # 1 original + 3 repeats
        for cmd in cmds:
            assert cmd.kind == "string"
            assert cmd.string_chars == "a"

    def test_repeat_no_prior(self, parser):
        cmds = parser.parse("REPEAT 5")
        assert len(cmds) == 0  # nothing to repeat


# ---------------------------------------------------------------------------
# Comments
# ---------------------------------------------------------------------------
class TestComments:
    def test_rem_ignored(self, parser):
        cmds = parser.parse("REM this is a comment\nSTRING hello")
        assert len(cmds) == 1
        assert cmds[0].kind == "string"

    def test_empty_lines_ignored(self, parser):
        cmds = parser.parse("\n\n\nSTRING test\n\n")
        assert len(cmds) == 1


# ---------------------------------------------------------------------------
# Multi-line scripts
# ---------------------------------------------------------------------------
class TestMultiLineScripts:
    def test_full_script(self, parser):
        script = """
        GUI r
        DELAY 500
        STRING notepad
        ENTER
        DELAY 1000
        STRING Hello World
        """
        cmds = parser.parse(script)
        assert len(cmds) == 5
        assert cmds[0].kind == "keyboard"  # GUI r
        assert cmds[1].kind == "delay"     # DELAY 500
        assert cmds[2].kind == "string"    # STRING notepad
        assert cmds[3].kind == "keyboard"  # ENTER
        assert cmds[4].kind == "string"    # STRING Hello World

    def test_raw_line_preserved(self, parser):
        cmds = parser.parse("STRING test line")
        assert cmds[0].raw_line == "STRING test line"
