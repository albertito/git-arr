"""
Miscellaneous utilities.

These are mostly used in templates, for presentation purposes.
"""

try:
    import pygments  # type: ignore
    from pygments import highlight  # type: ignore
    from pygments import lexers  # type: ignore
    from pygments.formatters import HtmlFormatter  # type: ignore

    _html_formatter = HtmlFormatter(
        encoding="utf-8",
        cssclass="source_code",
        linenos="table",
        anchorlinenos=True,
        lineanchors="line",
    )
except ImportError:
    pygments = None

try:
    import markdown  # type: ignore
    import markdown.treeprocessors  # type: ignore
except ImportError:
    markdown = None


import base64
import functools
import mimetypes
import string
import inspect
import sys
import time
import os
import os.path

import git


def shorten(s: str, width=60):
    if len(s) < 60:
        return s
    return s[:57] + "..."


@functools.lru_cache
def can_colorize(s: str):
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
        pos = s.find("\n", start)
        if pos == -1:
            break

        if pos - start > 300:
            return False
        start = pos + 1

    return True


def can_markdown(repo: git.Repo, fname: str):
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

    return ("." in fname) and (
        fname.split(".")[-1].lower() in ["jpg", "jpeg", "png", "gif"]
    )


@functools.lru_cache
def colorize_diff(s: str) -> str:
    lexer = lexers.DiffLexer(encoding="utf-8")
    formatter = HtmlFormatter(encoding="utf-8", cssclass="source_code")

    return highlight(s, lexer, formatter)


@functools.lru_cache
def colorize_blob(fname, s: str) -> str:
    try:
        lexer = lexers.guess_lexer_for_filename(fname, s, encoding="utf-8")
    except lexers.ClassNotFound:
        # Only try to guess lexers if the file starts with a shebang,
        # otherwise it's likely a text file and guess_lexer() is prone to
        # make mistakes with those.
        lexer = lexers.TextLexer(encoding="utf-8")
        if s.startswith("#!"):
            try:
                lexer = lexers.guess_lexer(s[:80], encoding="utf-8")
            except lexers.ClassNotFound:
                pass

    return highlight(s, lexer, _html_formatter)


def embed_image_blob(fname: str, image_data: bytes) -> str:
    mimetype = mimetypes.guess_type(fname)[0]
    b64img = base64.b64encode(image_data).decode("ascii")
    return '<img style="max-width:100%;" src="data:{0};base64,{1}" />'.format(
        mimetype, b64img
    )


@functools.lru_cache
def is_binary(b: bytes):
    # Git considers a blob binary if NUL in first ~8KB, so do the same.
    return b"\0" in b[:8192]


@functools.lru_cache
def hexdump(s: bytes):
    graph = string.ascii_letters + string.digits + string.punctuation + " "
    b = s.decode("latin1")
    offset = 0
    while b:
        t = b[:16]
        hexvals = ["%.2x" % ord(c) for c in t]
        text = "".join(c if c in graph else "." for c in t)
        yield offset, " ".join(hexvals[:8]), " ".join(hexvals[8:]), text
        offset += 16
        b = b[16:]


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
        def extendMarkdown(self, md):
            md.treeprocessors.register(
                RewriteLocalLinks(), "RewriteLocalLinks", 1000
            )

    _md_extensions = [
        "markdown.extensions.fenced_code",
        "markdown.extensions.tables",
        RewriteLocalLinksExtension(),
    ]

    @functools.lru_cache
    def markdown_blob(s: str) -> str:
        return markdown.markdown(s, extensions=_md_extensions)

else:

    @functools.lru_cache
    def markdown_blob(s: str) -> str:
        raise RuntimeError("markdown_blob() called without markdown support")


def log_timing(*log_args):
    "Decorator to log how long a function call took."
    if not os.environ.get("GIT_ARR_DEBUG"):
        return lambda f: f

    def log_timing_decorator(f):
        argspec = inspect.getfullargspec(f)
        idxs = [argspec.args.index(arg) for arg in log_args]

        @functools.wraps(f)
        def wrapper(*args, **kwargs):
            start = time.time()
            result = f(*args, **kwargs)
            end = time.time()

            f_args = [args[i] for i in idxs]
            sys.stderr.write(
                "%.4fs  %s %s\n" % (end - start, f.__name__, " ".join(f_args))
            )
            return result

        return wrapper

    return log_timing_decorator


try:
    import xattr

    def set_xattr_oid(path: str, oid: str):
        """Set the xattr 'user.git-arr.oid' on the given path."""
        try:
            xattr.setxattr(path, "user.git-arr.oid", oid.encode("utf-8"))
        except OSError as e:
            print(f"{path}: error writing xattr: {e}")

    def get_xattr_oid(path: str) -> str:
        """Get the xattr 'user.git-arr.oid' from the given path."""
        try:
            return xattr.getxattr(path, "user.git-arr.oid").decode("utf-8")
        except OSError as e:
            return ""

except ImportError:

    def set_xattr_oid(path: str, oid: str):
        """Set the xattr 'user.git-arr.oid' on the given path."""
        pass

    def get_xattr_oid(path: str) -> str:
        """Get the xattr 'user.git-arr.oid' from the given path."""
        return ""
