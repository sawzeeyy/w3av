import pytest
import sys
from io import StringIO
from weav.core.argparser import parse_arguments, ArgumentParser


def test_argparser_version(monkeypatch):
    """Test --version flag"""
    monkeypatch.setattr(sys, 'argv', ['weav', '--version'])

    with pytest.raises(SystemExit) as exc_info:
        parse_arguments()

    assert exc_info.value.code == 0


def test_argparser_no_mode(monkeypatch):
    """Test running without mode shows help"""
    monkeypatch.setattr(sys, 'argv', ['weav'])

    with pytest.raises(SystemExit) as exc_info:
        parse_arguments()

    assert exc_info.value.code == 0


def test_argparser_inspect_get_types(monkeypatch):
    """Test inspect mode with --get-types doesn't require input"""
    monkeypatch.setattr(sys, 'argv', ['weav', 'inspect', '--get-types'])

    args = parse_arguments()

    assert args.mode == 'inspect'
    assert args.get_types is True
    assert args.javascript == ''


def test_argparser_urls_mode_requires_input(monkeypatch):
    """Test urls mode requires input"""
    monkeypatch.setattr(sys, 'argv', ['weav', 'urls'])
    monkeypatch.setattr(sys.stdin, 'isatty', lambda: True)

    with pytest.raises(SystemExit):
        parse_arguments()


def test_argparser_strings_min_validation(monkeypatch):
    """Test strings mode validates min parameter"""
    test_input = StringIO("const x = 'test';")
    monkeypatch.setattr(sys, 'argv', ['weav', 'strings', '--min', '0'])
    monkeypatch.setattr(sys, 'stdin', test_input)
    monkeypatch.setattr(sys.stdin, 'isatty', lambda: False)

    with pytest.raises(SystemExit):
        parse_arguments()


def test_argparser_strings_min_max_validation(monkeypatch):
    """Test strings mode validates min < max"""
    test_input = StringIO("const x = 'test';")
    monkeypatch.setattr(sys, 'argv', ['weav', 'strings', '--min', '10', '--max', '5'])
    monkeypatch.setattr(sys, 'stdin', test_input)
    monkeypatch.setattr(sys.stdin, 'isatty', lambda: False)

    with pytest.raises(SystemExit):
        parse_arguments()


def test_argparser_query_requires_query_param(monkeypatch):
    """Test query mode requires --query parameter"""
    test_input = StringIO("const x = 'test';")
    monkeypatch.setattr(sys, 'argv', ['weav', 'query'])
    monkeypatch.setattr(sys, 'stdin', test_input)
    monkeypatch.setattr(sys.stdin, 'isatty', lambda: False)

    with pytest.raises(SystemExit):
        parse_arguments()


def test_argparser_positional_input(monkeypatch, tmp_path):
    """Test positional input argument"""
    test_file = tmp_path / "test.js"
    test_file.write_text("const x = 5;")

    monkeypatch.setattr(sys, 'argv', ['weav', 'strings', str(test_file)])

    args = parse_arguments()

    assert args.mode == 'strings'
    assert args.javascript == "const x = 5;"


def test_argparser_flag_input(monkeypatch, tmp_path):
    """Test --input flag"""
    test_file = tmp_path / "test.js"
    test_file.write_text("const y = 10;")

    monkeypatch.setattr(sys, 'argv', ['weav', 'strings', '--input', str(test_file)])

    args = parse_arguments()

    assert args.mode == 'strings'
    assert args.javascript == "const y = 10;"


def test_argparser_stdin_input(monkeypatch):
    """Test stdin input"""
    test_input = StringIO("const z = 15;")
    monkeypatch.setattr(sys, 'argv', ['weav', 'strings'])
    monkeypatch.setattr(sys, 'stdin', test_input)
    monkeypatch.setattr(sys.stdin, 'isatty', lambda: False)

    args = parse_arguments()

    assert args.mode == 'strings'
    assert args.javascript == "const z = 15;"
