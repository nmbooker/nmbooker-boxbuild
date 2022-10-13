def heredoc(astring: str) -> str:
    r"""Unindent an indented multi-line string.

    This is to allow multi-line strings to be indented similar to
    Python code without the indentation making it into the final result.
    Line endings are preserved as written.

    >>> indented_multiline('''
        hello:
         world
        ''')
    'hello:\n world\n'

    It's not possible to directly build a string whose last line
    does not end with a new line, but you can use .rstrip('\n')
    on the result if that's what you want.  I anticipate you'll be building
    a text file using this so a trailing newline is nearly always what
    you want.
    """
    lines = astring.splitlines(keepends=True)
    first_line = lines[0]
    content_lines = lines[1:-1]
    last_line = lines[-1]
    assert first_line.isspace(), 'first line must be all whitespace'
    assert last_line.isspace(), 'last line must be all whitespace'
    indentation_template = last_line.rstrip('\n')
    assert all(l.startswith(indentation_template) for l in content_lines), \
        'all content lines must begin with same whitespace as last one'
    unindented_lines = \
        [l.removeprefix(indentation_template) for l in content_lines]
    return ''.join(unindented_lines)