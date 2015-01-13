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

try:
    import markdown
except ImportError:
    markdown = None

import base64
import mimetypes

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

def can_markdown(repo, fname):
    """True if we can process file through markdown, False otherwise."""
    if markdown is None:
        return False

    if not repo.info.embed_markdown:
        return False

    return fname.endswith(".md")

def can_embed_image(repo, fname):
    """True if we can embed image file in HTML, False otherwise."""
    if not repo.info.embed_images:
        return False

    return (('.' in fname) and
            (fname.split('.')[-1].lower() in [ 'jpg', 'jpeg', 'png', 'gif' ]))

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
                    linenos = 'table',
                    anchorlinenos = True,
                    lineanchors = 'line')

    return highlight(s, lexer, formatter)

def markdown_blob(s):
    return markdown.markdown(s)

def embed_image_blob(fname, image_data):
    mimetype = mimetypes.guess_type(fname)[0]
    return '<img style="max-width:100%;" src="data:{0};base64,{1}" />'.format( \
                                    mimetype, base64.b64encode(image_data))

