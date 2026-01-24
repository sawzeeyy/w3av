import pytest
import sys

from io import StringIO
from sawari.core.argparser import parse_arguments


def test_argparser_version(monkeypatch):
    """Test --version flag"""
    monkeypatch.setattr(sys, 'argv', ['sawari', '--version'])

    with pytest.raises(SystemExit) as exc_info:
        parse_arguments()

    assert exc_info.value.code == 0


def test_argparser_no_mode(monkeypatch):
    """Test running without mode shows help"""
    monkeypatch.setattr(sys, 'argv', ['sawari'])

    with pytest.raises(SystemExit) as exc_info:
        parse_arguments()

    assert exc_info.value.code == 0


def test_argparser_inspect_get_types(monkeypatch):
    """Test inspect mode with --get-types doesn't require input"""
    monkeypatch.setattr(sys, 'argv', ['sawari', 'inspect', '--get-types'])

    args = parse_arguments()

    assert args.mode == 'inspect'
    assert args.get_types is True
    assert args.javascript == ''


def test_argparser_urls_mode_requires_input(monkeypatch):
    """Test urls mode requires input"""
    monkeypatch.setattr(sys, 'argv', ['sawari', 'urls'])
    monkeypatch.setattr(sys.stdin, 'isatty', lambda: True)

    with pytest.raises(SystemExit):
        parse_arguments()


def test_argparser_strings_min_validation(monkeypatch):
    """Test strings mode validates min parameter"""
    test_input = StringIO("const x = 'test';")
    monkeypatch.setattr(sys, 'argv', ['sawari', 'strings', '--min', '0'])
    monkeypatch.setattr(sys, 'stdin', test_input)
    monkeypatch.setattr(sys.stdin, 'isatty', lambda: False)

    with pytest.raises(SystemExit):
        parse_arguments()


def test_argparser_strings_min_max_validation(monkeypatch):
    """Test strings mode validates min < max"""
    test_input = StringIO("const x = 'test';")
    monkeypatch.setattr(sys, 'argv', ['sawari', 'strings', '--min', '10',
                                      '--max', '5'])
    monkeypatch.setattr(sys, 'stdin', test_input)
    monkeypatch.setattr(sys.stdin, 'isatty', lambda: False)

    with pytest.raises(SystemExit):
        parse_arguments()


def test_argparser_query_requires_query_param(monkeypatch):
    """Test query mode requires --query parameter"""
    test_input = StringIO("const x = 'test';")
    monkeypatch.setattr(sys, 'argv', ['sawari', 'query'])
    monkeypatch.setattr(sys, 'stdin', test_input)
    monkeypatch.setattr(sys.stdin, 'isatty', lambda: False)

    with pytest.raises(SystemExit):
        parse_arguments()


def test_argparser_positional_input(monkeypatch, tmp_path):
    """Test positional input argument"""
    test_file = tmp_path / "test.js"
    test_file.write_text("const x = 5;")

    monkeypatch.setattr(sys, 'argv', ['sawari', 'strings', str(test_file)])

    args = parse_arguments()

    assert args.mode == 'strings'
    assert args.javascript == "const x = 5;"


def test_argparser_flag_input(monkeypatch, tmp_path):
    """Test --input flag"""
    test_file = tmp_path / "test.js"
    test_file.write_text("const y = 10;")

    monkeypatch.setattr(sys, 'argv', ['sawari', 'strings', '--input',
                                      str(test_file)])

    args = parse_arguments()

    assert args.mode == 'strings'
    assert args.javascript == "const y = 10;"


def test_argparser_stdin_input(monkeypatch):
    """Test stdin input"""
    test_input = StringIO("const z = 15;")
    monkeypatch.setattr(sys, 'argv', ['sawari', 'strings'])
    monkeypatch.setattr(sys, 'stdin', test_input)
    monkeypatch.setattr(sys.stdin, 'isatty', lambda: False)

    args = parse_arguments()

    assert args.mode == 'strings'
    assert args.javascript == "const z = 15;"


def test_argparser_context_invalid_format(monkeypatch):
    """Test --context with invalid format raises error"""
    test_input = StringIO("const x = 1;")
    monkeypatch.setattr(sys, 'argv', ['sawari', 'urls', '--context', 'INVALID'])
    monkeypatch.setattr(sys, 'stdin', test_input)
    monkeypatch.setattr(sys.stdin, 'isatty', lambda: False)

    with pytest.raises(SystemExit):
        parse_arguments()


def test_argparser_context_empty_string(monkeypatch):
    """Test --context with empty string raises error"""
    test_input = StringIO("const x = 1;")
    monkeypatch.setattr(sys, 'argv', ['sawari', 'urls', '--context', ''])
    monkeypatch.setattr(sys, 'stdin', test_input)
    monkeypatch.setattr(sys.stdin, 'isatty', lambda: False)

    with pytest.raises(SystemExit):
        parse_arguments()


def test_argparser_context_valid_json(monkeypatch):
    """Test --context with valid JSON string"""
    test_input = StringIO("const x = 1;")
    monkeypatch.setattr(sys, 'argv', ['sawari', 'urls', '--context', '{"BASE_URL":"https://test.com"}'])
    monkeypatch.setattr(sys, 'stdin', test_input)
    monkeypatch.setattr(sys.stdin, 'isatty', lambda: False)

    args = parse_arguments()

    assert args.mode == 'urls'
    assert args.context == {'BASE_URL': 'https://test.com'}


def test_argparser_context_valid_keyvalue(monkeypatch):
    """Test --context with valid KEY=VALUE format"""
    test_input = StringIO("const x = 1;")
    monkeypatch.setattr(sys, 'argv', ['sawari', 'urls', '--context', 'BASE_URL=https://test.com'])
    monkeypatch.setattr(sys, 'stdin', test_input)
    monkeypatch.setattr(sys.stdin, 'isatty', lambda: False)

    args = parse_arguments()

    assert args.mode == 'urls'
    assert args.context == {'BASE_URL': 'https://test.com'}


def test_argparser_context_policy_valid(monkeypatch):
    """Test --context-policy with valid values"""
    test_input = StringIO("const x = 1;")

    for policy in ['merge', 'override', 'only']:
        monkeypatch.setattr(sys, 'argv', ['sawari', 'urls', '--context-policy', policy])
        monkeypatch.setattr(sys, 'stdin', test_input)
        monkeypatch.setattr(sys.stdin, 'isatty', lambda: False)

        args = parse_arguments()
        assert args.context_policy == policy

        # Reset stdin for next iteration
        test_input.seek(0)


def test_argparser_context_policy_invalid(monkeypatch):
    """Test --context-policy with invalid value raises error"""
    test_input = StringIO("const x = 1;")
    monkeypatch.setattr(sys, 'argv', ['sawari', 'urls', '--context-policy', 'invalid'])
    monkeypatch.setattr(sys, 'stdin', test_input)
    monkeypatch.setattr(sys.stdin, 'isatty', lambda: False)

    with pytest.raises(SystemExit):
        parse_arguments()


def test_argparser_unicode_decode_error_stdin(monkeypatch, capsys):
    """Test that invalid UTF-8 in stdin is handled gracefully"""
    # Mock stdin to return bytes that are invalid UTF-8
    class MockStdin:
        def read(self):
            raise UnicodeDecodeError('utf-8', b'\x80', 0, 1, 'invalid start byte')
        def isatty(self):
            return False

    monkeypatch.setattr(sys, 'argv', ['sawari', 'urls'])
    monkeypatch.setattr(sys, 'stdin', MockStdin())

    # Needs to raise SystemExit because parser.error exits
    with pytest.raises(SystemExit) as exc:
        parse_arguments()

    assert exc.value.code != 0

    # Check stderr for the error message
    captured = capsys.readouterr()
    assert "Input is not valid UTF-8" in captured.err


def test_argparser_unicode_decode_error_file(monkeypatch, tmp_path, capsys):
    """Test that invalid UTF-8 in file input is handled gracefully"""
    # Create a binary file with invalid UTF-8
    bad_file = tmp_path / "bad.js"
    bad_file.write_bytes(b"\x80\x81\xFF")

    monkeypatch.setattr(sys, 'argv', ['sawari', 'urls', '--input', str(bad_file)])

    # Verify SystemExit
    with pytest.raises(SystemExit) as exc:
        parse_arguments()

    assert exc.value.code != 0

    captured = capsys.readouterr()
    assert "Input is not valid UTF-8" in captured.err
