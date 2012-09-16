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

def has_colorizer():
    return pygments is not None

def colorize_diff(s):
    lexer = lexers.DiffLexer(encoding = 'utf-8')
    formatter = HtmlFormatter(encoding = 'utf-8',
                    cssclass = 'source_code')

    return highlight(s, lexer, formatter)

def colorize_blob(fname, s):
    try:
        lexer = lexers.guess_lexer_for_filename(fname, s)
    except lexers.ClassNotFound:
        lexer = lexers.TextLexer(encoding = 'utf-8')
    formatter = HtmlFormatter(encoding = 'utf-8',
                    cssclass = 'source_code',
                    linenos = 'table')

    return highlight(s, lexer, formatter)

