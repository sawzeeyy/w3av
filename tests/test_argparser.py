import pytest
import sys

from io import StringIO
from w3av.core.argparser import parse_arguments


def test_argparser_version(monkeypatch):
    """Test --version flag"""
    monkeypatch.setattr(sys, 'argv', ['w3av', '--version'])

    with pytest.raises(SystemExit) as exc_info:
        parse_arguments()

    assert exc_info.value.code == 0


def test_argparser_no_mode(monkeypatch):
    """Test running without mode shows help"""
    monkeypatch.setattr(sys, 'argv', ['w3av'])

    with pytest.raises(SystemExit) as exc_info:
        parse_arguments()

    assert exc_info.value.code == 0


def test_argparser_inspect_get_types(monkeypatch):
    """Test inspect mode with --get-types doesn't require input"""
    monkeypatch.setattr(sys, 'argv', ['w3av', 'inspect', '--get-types'])

    args = parse_arguments()

    assert args.mode == 'inspect'
    assert args.get_types is True
    assert args.javascript == ''


def test_argparser_urls_mode_requires_input(monkeypatch):
    """Test urls mode requires input"""
    monkeypatch.setattr(sys, 'argv', ['w3av', 'urls'])
    monkeypatch.setattr(sys.stdin, 'isatty', lambda: True)

    with pytest.raises(SystemExit):
        parse_arguments()


def test_argparser_strings_min_validation(monkeypatch):
    """Test strings mode validates min parameter"""
    test_input = StringIO("const x = 'test';")
    monkeypatch.setattr(sys, 'argv', ['w3av', 'strings', '--min', '0'])
    monkeypatch.setattr(sys, 'stdin', test_input)
    monkeypatch.setattr(sys.stdin, 'isatty', lambda: False)

    with pytest.raises(SystemExit):
        parse_arguments()


def test_argparser_strings_min_max_validation(monkeypatch):
    """Test strings mode validates min < max"""
    test_input = StringIO("const x = 'test';")
    monkeypatch.setattr(sys, 'argv', ['w3av', 'strings', '--min', '10',
                                      '--max', '5'])
    monkeypatch.setattr(sys, 'stdin', test_input)
    monkeypatch.setattr(sys.stdin, 'isatty', lambda: False)

    with pytest.raises(SystemExit):
        parse_arguments()


def test_argparser_query_requires_query_param(monkeypatch):
    """Test query mode requires --query parameter"""
    test_input = StringIO("const x = 'test';")
    monkeypatch.setattr(sys, 'argv', ['w3av', 'query'])
    monkeypatch.setattr(sys, 'stdin', test_input)
    monkeypatch.setattr(sys.stdin, 'isatty', lambda: False)

    with pytest.raises(SystemExit):
        parse_arguments()


def test_argparser_positional_input(monkeypatch, tmp_path):
    """Test positional input argument"""
    test_file = tmp_path / "test.js"
    test_file.write_text("const x = 5;")

    monkeypatch.setattr(sys, 'argv', ['w3av', 'strings', str(test_file)])

    args = parse_arguments()

    assert args.mode == 'strings'
    assert args.javascript == "const x = 5;"


def test_argparser_flag_input(monkeypatch, tmp_path):
    """Test --input flag"""
    test_file = tmp_path / "test.js"
    test_file.write_text("const y = 10;")

    monkeypatch.setattr(sys, 'argv', ['w3av', 'strings', '--input',
                                      str(test_file)])

    args = parse_arguments()

    assert args.mode == 'strings'
    assert args.javascript == "const y = 10;"


def test_argparser_stdin_input(monkeypatch):
    """Test stdin input"""
    test_input = StringIO("const z = 15;")
    monkeypatch.setattr(sys, 'argv', ['w3av', 'strings'])
    monkeypatch.setattr(sys, 'stdin', test_input)
    monkeypatch.setattr(sys.stdin, 'isatty', lambda: False)

    args = parse_arguments()

    assert args.mode == 'strings'
    assert args.javascript == "const z = 15;"


def test_argparser_context_invalid_format(monkeypatch):
    """Test --context with invalid format raises error"""
    test_input = StringIO("const x = 1;")
    monkeypatch.setattr(sys, 'argv', ['w3av', 'urls', '--context', 'INVALID'])
    monkeypatch.setattr(sys, 'stdin', test_input)
    monkeypatch.setattr(sys.stdin, 'isatty', lambda: False)

    with pytest.raises(SystemExit):
        parse_arguments()


def test_argparser_context_empty_string(monkeypatch):
    """Test --context with empty string raises error"""
    test_input = StringIO("const x = 1;")
    monkeypatch.setattr(sys, 'argv', ['w3av', 'urls', '--context', ''])
    monkeypatch.setattr(sys, 'stdin', test_input)
    monkeypatch.setattr(sys.stdin, 'isatty', lambda: False)

    with pytest.raises(SystemExit):
        parse_arguments()


def test_argparser_context_valid_json(monkeypatch):
    """Test --context with valid JSON string"""
    test_input = StringIO("const x = 1;")
    monkeypatch.setattr(sys, 'argv', ['w3av', 'urls', '--context', '{"BASE_URL":"https://test.com"}'])
    monkeypatch.setattr(sys, 'stdin', test_input)
    monkeypatch.setattr(sys.stdin, 'isatty', lambda: False)

    args = parse_arguments()

    assert args.mode == 'urls'
    assert args.context == {'BASE_URL': 'https://test.com'}


def test_argparser_context_valid_keyvalue(monkeypatch):
    """Test --context with valid KEY=VALUE format"""
    test_input = StringIO("const x = 1;")
    monkeypatch.setattr(sys, 'argv', ['w3av', 'urls', '--context', 'BASE_URL=https://test.com'])
    monkeypatch.setattr(sys, 'stdin', test_input)
    monkeypatch.setattr(sys.stdin, 'isatty', lambda: False)

    args = parse_arguments()

    assert args.mode == 'urls'
    assert args.context == {'BASE_URL': 'https://test.com'}


def test_argparser_context_policy_valid(monkeypatch):
    """Test --context-policy with valid values"""
    test_input = StringIO("const x = 1;")

    for policy in ['merge', 'override', 'only']:
        monkeypatch.setattr(sys, 'argv', ['w3av', 'urls', '--context-policy', policy])
        monkeypatch.setattr(sys, 'stdin', test_input)
        monkeypatch.setattr(sys.stdin, 'isatty', lambda: False)

        args = parse_arguments()
        assert args.context_policy == policy

        # Reset stdin for next iteration
        test_input.seek(0)


def test_argparser_context_policy_invalid(monkeypatch):
    """Test --context-policy with invalid value raises error"""
    test_input = StringIO("const x = 1;")
    monkeypatch.setattr(sys, 'argv', ['w3av', 'urls', '--context-policy', 'invalid'])
    monkeypatch.setattr(sys, 'stdin', test_input)
    monkeypatch.setattr(sys.stdin, 'isatty', lambda: False)

    with pytest.raises(SystemExit):
        parse_arguments()
