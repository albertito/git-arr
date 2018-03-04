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
    import markdown.treeprocessors
except ImportError:
    markdown = None

import base64
import mimetypes
import string
import os.path

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
    extensions = [
        "markdown.extensions.fenced_code",
        "markdown.extensions.tables",
        RewriteLocalLinksExtension(),
    ]
    return markdown.markdown(s, extensions = extensions)

def embed_image_blob(fname, image_data):
    mimetype = mimetypes.guess_type(fname)[0]
    return '<img style="max-width:100%;" src="data:{0};base64,{1}" />'.format( \
                                    mimetype, base64.b64encode(image_data))

def is_binary(s):
    # Git considers a blob binary if NUL in first ~8KB, so do the same.
    return '\0' in s[:8192]

def hexdump(s):
    graph = string.ascii_letters + string.digits + string.punctuation + ' '
    offset = 0
    while s:
        t = s[:16]
        hexvals = ['%.2x' % ord(c) for c in t]
        text = ''.join(c if c in graph else '.' for c in t)
        yield offset, ' '.join(hexvals[:8]), ' '.join(hexvals[8:]), text
        offset += 16
        s = s[16:]


if markdown:
    class RewriteLocalLinks(markdown.treeprocessors.Treeprocessor):
        """Rewrites relative links to files, to match git-arr's links.

        A link of "[example](a/file.md)" will be rewritten such that it links to
        "a/f=file.md.html".

        Note that we're already assuming a degree of sanity in the HTML, so we
        don't re-check that the path is reasonable.
        """
        def run(self, root):
            for child in root:
                if child.tag == "a":
                    self.rewrite_href(child)

                # Continue recursively.
                self.run(child)

        def rewrite_href(self, tag):
            """Rewrite an <a>'s href."""
            target = tag.get("href")
            if not target:
                return
            if "://" in target or target.startswith("/"):
                return

            head, tail = os.path.split(target)
            new_target = os.path.join(head, "f=" + tail + ".html")
            tag.set("href", new_target)


    class RewriteLocalLinksExtension(markdown.Extension):
        def extendMarkdown(self, md, md_globals):
            md.treeprocessors.add(
                    "RewriteLocalLinks", RewriteLocalLinks(), "_end")

