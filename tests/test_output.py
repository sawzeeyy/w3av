import pytest
from io import StringIO
from w3av.core.output import write_output


def test_write_output_to_stream():
    """Test writing output to a stream"""
    output_stream = StringIO()
    data = ["line1", "line2", "line3"]

    write_output(output_stream, data)

    result = output_stream.getvalue()
    assert "line1" in result
    assert "line2" in result
    assert "line3" in result


def test_write_output_single_line():
    """Test writing single line output"""
    output_stream = StringIO()
    data = ["single line"]

    write_output(output_stream, data)

    result = output_stream.getvalue()
    assert result == "single line\n"


def test_write_output_empty_list():
    """Test writing empty list"""
    output_stream = StringIO()
    data = []

    write_output(output_stream, data)

    result = output_stream.getvalue()
    assert result == "\n"


def test_write_output_with_newlines():
    """Test output is properly formatted with newlines"""
    output_stream = StringIO()
    data = ["line1", "line2"]

    write_output(output_stream, data)

    result = output_stream.getvalue()
    lines = result.strip().split('\n')
    assert len(lines) == 2


def test_write_output_none_stream():
    """Test writing to None stream (should exit)"""
    data = ["line1", "line2"]

    with pytest.raises(SystemExit):
        write_output(None, data)


def test_write_output_special_characters():
    """Test writing output with special characters"""
    output_stream = StringIO()
    data = ["special: <>&\"'", "unicode: 你好"]

    write_output(output_stream, data)

    result = output_stream.getvalue()
    assert "special: <>&\"'" in result
    assert "unicode: 你好" in result
