"""Tests for Agentic Ducky Script Extensions."""

from rng_operator.hygienic_actuator.ducky_parser import DuckyScriptParser

def test_wait_for_image_parsing():
    parser = DuckyScriptParser()
    cmds = parser.parse("WAIT_FOR_IMAGE submit_button")
    assert len(cmds) == 1
    cmd = cmds[0]
    assert cmd.kind == "wait_for_image"
    assert cmd.string_chars == "submit_button"

def test_assert_visible_parsing():
    parser = DuckyScriptParser()
    cmds = parser.parse("ASSERT_VISIBLE success_icon")
    assert len(cmds) == 1
    cmd = cmds[0]
    assert cmd.kind == "assert_visible"
    assert cmd.string_chars == "success_icon"

def test_mixed_script_parsing():
    script = """
    WAIT_FOR_IMAGE login_screen
    STRING mypassword
    ENTER
    ASSERT_VISIBLE dashboard
    """
    parser = DuckyScriptParser()
    cmds = parser.parse(script)
    assert len(cmds) == 4
    assert cmds[0].kind == "wait_for_image"
    assert cmds[1].kind == "string"
    assert cmds[2].kind == "keyboard"
    assert cmds[3].kind == "assert_visible"
