"""
Miscellaneous utilities.

These are mostly used in templates, for presentation purposes.
"""

try:
    import pygments
    from pygments import highlight
    from pygments import lexers
    from pygments.formatters import HtmlFormatter
except ImportError:
    pygments = None


def shorten(s, width = 60):
    if len(s) < 60:
        return s
    return s[:57] + "..."

def can_colorize(s):
    """True if we can colorize the string, False otherwise."""
    if pygments is None:
        return False

    # Pygments can take a huge amount of time with long files, or with very
    # long lines; these are heuristics to try to avoid those situations.
    if len(s) > (512 * 1024):
        return False

    # If any of the first 5 lines is over 300 characters long, don't colorize.
    start = 0
    for i in range(5):
        pos = s.find('\n', start)
        if pos == -1:
            break

        if pos - start > 300:
            return False
        start = pos + 1

    return True

def colorize_diff(s):
    lexer = lexers.DiffLexer(encoding = 'utf-8')
    formatter = HtmlFormatter(encoding = 'utf-8',
                    cssclass = 'source_code')

    return highlight(s, lexer, formatter)

def colorize_blob(fname, s):
    try:
        lexer = lexers.guess_lexer_for_filename(fname, s, encoding = 'utf-8')
    except lexers.ClassNotFound:
        # Only try to guess lexers if the file starts with a shebang,
        # otherwise it's likely a text file and guess_lexer() is prone to
        # make mistakes with those.
        lexer = lexers.TextLexer(encoding = 'utf-8')
        if s.startswith('#!'):
            try:
                lexer = lexers.guess_lexer(s[:80], encoding = 'utf-8')
            except lexers.ClassNotFound:
                pass

    formatter = HtmlFormatter(encoding = 'utf-8',
                    cssclass = 'source_code',
                    linenos = 'table')

    return highlight(s, lexer, formatter)

