from sawari.core.comment import remove_comment_delimiter


def test_line_comment_with_domain():
    comment = '// //google.com'
    assert remove_comment_delimiter(comment) == ('//google.com', True)


def test_line_comment_with_ip_address():
    comment = '// //255.255.255.255'
    assert remove_comment_delimiter(comment) == ('//255.255.255.255', True)


def test_line_comment():
    comment = '// test'
    assert remove_comment_delimiter(comment) == ('test', True)


def test_line_comment_minified():
    comment = '//test'
    assert remove_comment_delimiter(comment) == ('test', True)


def test_line_comment_with_extra_slash():
    comment = '/// test'
    assert remove_comment_delimiter(comment) == ('test', True)


def test_line_comment_nested():
    comment = '// // test'
    assert remove_comment_delimiter(comment) == ('test', True)


def test_line_comment_nested_minified():
    comment = '////test'
    assert remove_comment_delimiter(comment) == ('test', True)


def test_multiline_comment():
    comment = '/* test */'
    assert remove_comment_delimiter(comment) == ('test', True)


def test_multiline_comment_minified():
    comment = '/*test*/'
    assert remove_comment_delimiter(comment) == ('test', True)


def test_multiline_comment_nested():
    comment = '/* /* test */ */'
    assert remove_comment_delimiter(comment) == ('test', True)


def test_multiline_comment_nested_minified():
    comment = '/*/*test*/*/'
    assert remove_comment_delimiter(comment) == ('test', True)


def test_multiline_comment_with_nested_line_comment():
    comment = '/* //test */'
    assert remove_comment_delimiter(comment) == ('test', True)


def test_multiline_comment_with_nested_line_comment_minified():
    comment = '/*//test*/'
    assert remove_comment_delimiter(comment) == ('test', True)


def test_multiline_comment_nested_with_nested_line_comment():
    comment = '/* /* // // test */ */'
    assert remove_comment_delimiter(comment) == ('test', True)


def test_multiline_comment_nested_with_nested_line_comment_minified():
    comment = '/*/*////test*/*/'
    assert remove_comment_delimiter(comment) == ('test', True)


def test_multiline_comment_nested_with_nested_line_comment_minified__():
    comment = '/*/*///// test /*/*/'
    assert remove_comment_delimiter(comment) == ('test', True)
