"""
Python wrapper for git.

This module is a light Python API for interfacing with it. It calls the git
command line tool directly, so please be careful with using untrusted
parameters.
"""

import functools
import sys
import io
import time
import os
import subprocess
from collections import defaultdict
import email.utils
import datetime
import urllib.request, urllib.parse, urllib.error
from html import escape
from typing import Any, Dict, IO, Iterable, List, Optional, Tuple, Union


# Path to the git binary.
GIT_BIN = "git"


def run_git(
    repo_path: str, params, stdin: bytes = None, silent_stderr=False, raw=False
) -> Union[IO[str], IO[bytes]]:
    """Invokes git with the given parameters.

    This function invokes git with the given parameters, and returns a
    file-like object with the output (from a pipe).
    """
    start = time.time()
    out = _run_git(
        repo_path, params, stdin, silent_stderr=silent_stderr, raw=raw
    )
    end = time.time()

    if os.environ.get("GIT_ARR_DEBUG"):
        sys.stderr.write(
            "%.4fs  %s  %s\n"
            % (end - start, repo_path[-30:], " ".join(params))
        )

    return out


def _run_git(
    repo_path: str, params, stdin: bytes = None, silent_stderr=False, raw=False
) -> Union[IO[str], IO[bytes]]:
    """Invokes git with the given parameters.

    This is the real run_git function, which is called by run_git().
    """
    params = [GIT_BIN, "--git-dir=%s" % repo_path] + list(params)

    stderr = None
    if silent_stderr:
        stderr = subprocess.PIPE

    if not stdin:
        p = subprocess.Popen(
            params, stdin=None, stdout=subprocess.PIPE, stderr=stderr
        )
    else:
        p = subprocess.Popen(
            params,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=stderr,
        )

        assert p.stdin is not None
        p.stdin.write(stdin)
        p.stdin.close()

    assert p.stdout is not None

    if raw:
        return p.stdout

    return io.TextIOWrapper(
        p.stdout, encoding="utf8", errors="backslashreplace"
    )


class GitCommand(object):
    """Convenient way of invoking git."""

    def __init__(self, path: str, cmd: str):
        self._override = True
        self._path = path
        self._cmd = cmd
        self._args: List[str] = []
        self._kwargs: Dict[str, str] = {}
        self._stdin_buf: Optional[bytes] = None
        self._raw = False
        self._override = False

    def __setattr__(self, k, v):
        if k == "_override" or self._override:
            self.__dict__[k] = v
            return
        k = k.replace("_", "-")
        self._kwargs[k] = v

    def arg(self, a: str):
        """Adds an argument."""
        self._args.append(a)

    def raw(self, b: bool):
        """Request raw rather than utf8-encoded command output."""
        self._override = True
        self._raw = b
        self._override = False

    def stdin(self, s: bytes):
        """Sets the contents we will send in stdin."""
        self._override = True
        self._stdin_buf = s
        self._override = False

    def run(self):
        """Runs the git command."""
        params = [self._cmd]

        for k, v in list(self._kwargs.items()):
            dash = "--" if len(k) > 1 else "-"
            if v is None:
                params.append("%s%s" % (dash, k))
            else:
                params.append("%s%s=%s" % (dash, k, str(v)))

        params.extend(self._args)

        return run_git(self._path, params, self._stdin_buf, raw=self._raw)


class SimpleNamespace(object):
    """An entirely flexible object, which provides a convenient namespace."""

    def __init__(self, **kwargs):
        self.__dict__.update(kwargs)


class smstr:
    """A "smart" string, containing many representations for ease of use."""

    raw: str  # string, probably utf8-encoded, good enough to show.
    url: str  # escaped for safe embedding in URLs (not human-readable).
    html: str  # HTML-embeddable representation.

    def __init__(self, s: str):
        self.raw = s

    # Note we don't define __repr__() or __str__() to prevent accidental
    # misuse. It does mean that some uses become more annoying, so it's a
    # tradeoff that may change in the future.

    @staticmethod
    def from_url(url):
        """Returns an smstr() instance from an url-encoded string."""
        return smstr(urllib.request.url2pathname(url))

    def split(self, sep):
        """Like str.split()."""
        return [smstr(s) for s in self.raw.split(sep)]

    def __add__(self, other):
        if isinstance(other, smstr):
            other = other.raw
        return smstr(self.raw + other)

    @functools.cached_property
    def url(self):
        return urllib.request.pathname2url(self.raw)

    @functools.cached_property
    def html(self):
        """Returns an html representation of the unicode string."""
        html = ""
        for c in escape(self.raw):
            if c in "\t\r\n\r\f\a\b\v\0":
                esc_c = c.encode("unicode-escape").decode("utf8")
                html += '<span class="ctrlchr">%s</span>' % esc_c
            else:
                html += c

        return html


def unquote(s: str):
    """Git can return quoted file names, unquote them. Always return a str."""
    if not (s[0] == '"' and s[-1] == '"'):
        # Unquoted strings are always safe, no need to mess with them
        return s

    # The string will be of the form `"<escaped>"`, where <escaped> is a
    # backslash-escaped representation of the name of the file.
    # Examples:  "with\ttwo\ttabs" , "\303\261aca-utf8", "\361aca-latin1"

    # Get rid of the quotes, we never want them in the output.
    s = s[1:-1]

    # Un-escape the backslashes.
    # latin1 is ok to use here because in Python it just maps the code points
    # 0-255 to the bytes 0x-0xff, which is what we expect.
    s = s.encode("latin1").decode("unicode-escape")

    # Convert to utf8.
    s = s.encode("latin1").decode("utf8", errors="backslashreplace")

    return s


class Repo:
    """A git repository."""

    def __init__(self, path: str, name=None, info=None):
        self.path = path
        self.name = name
        self.info: Any = info or SimpleNamespace()

    def cmd(self, cmd):
        """Returns a GitCommand() on our path."""
        return GitCommand(self.path, cmd)

    @functools.lru_cache
    def _for_each_ref(self, pattern=None, sort=None, count=None):
        """Returns a list of references."""
        cmd = self.cmd("for-each-ref")
        if sort:
            cmd.sort = sort
        if count:
            cmd.count = count
        if pattern:
            cmd.arg(pattern)

        refs = []
        for l in cmd.run():
            obj_id, obj_type, ref = l.split()
            refs.append((obj_id, obj_type, ref))
        return refs

    @functools.cache
    def branch_names(self):
        """Get the names of the branches."""
        refs = self._for_each_ref(pattern="refs/heads/", sort="-authordate")
        return [ref[len("refs/heads/") :] for _, _, ref in refs]

    @functools.cache
    def main_branch(self):
        """Get the name of the main branch."""
        bs = self.branch_names()
        for branch in ["master", "main"]:
            if branch in bs:
                return branch
        if bs:
            return bs[0]
        return None

    @functools.cache
    def tags(self, sort="-taggerdate"):
        """Get the (name, obj_id) of the tags."""
        refs = self._for_each_ref(pattern="refs/tags/", sort=sort)
        return [(ref[len("refs/tags/") :], obj_id) for obj_id, _, ref in refs]

    @functools.lru_cache
    def commit_ids(self, ref, limit=None):
        """Generate commit ids."""
        cmd = self.cmd("rev-list")
        if limit:
            cmd.max_count = limit

        cmd.arg(ref)
        cmd.arg("--")

        return [l.rstrip("\n") for l in cmd.run()]

    @functools.lru_cache
    def commit(self, commit_id):
        """Return a single commit."""
        cs = list(self.commits(commit_id, limit=1))
        if len(cs) != 1:
            return None
        return cs[0]

    @functools.lru_cache
    def commits(self, ref, limit, offset=0):
        """Generate commit objects for the ref."""
        cmd = self.cmd("rev-list")
        cmd.max_count = limit + offset

        cmd.header = None

        cmd.arg(ref)
        cmd.arg("--")

        info_buffer = ""
        count = 0
        commits = []
        for l in cmd.run():
            if "\0" in l:
                pre, post = l.split("\0", 1)
                info_buffer += pre

                count += 1
                if count > offset:
                    commits.append(Commit.from_str(self, info_buffer))

                # Start over.
                info_buffer = post
            else:
                info_buffer += l

        if info_buffer:
            count += 1
            if count > offset:
                commits.append(Commit.from_str(self, info_buffer))

        return commits

    @functools.lru_cache
    def diff(self, ref):
        """Return a Diff object for the ref."""
        cmd = self.cmd("diff-tree")
        cmd.patch = None
        cmd.numstat = None
        cmd.find_renames = None
        if self.info.root_diff:
            cmd.root = None
        # Note we intentionally do not use -z, as the filename is just for
        # reference, and it is safer to let git do the escaping.

        cmd.arg(ref)

        return Diff.from_str(cmd.run())

    @functools.lru_cache
    def refs(self):
        """Return a dict of obj_id -> ref."""
        cmd = self.cmd("show-ref")
        cmd.dereference = None

        r = defaultdict(list)
        for l in cmd.run():
            l = l.strip()
            obj_id, ref = l.split(" ", 1)
            r[obj_id].append(ref)

        return r

    @functools.lru_cache
    def tree(self, ref):
        """Returns a Tree instance for the given ref."""
        return Tree(self, ref)

    @functools.lru_cache
    def blob(self, path, ref):
        """Returns a Blob instance for the given path."""
        cmd = self.cmd("cat-file")
        cmd.raw(True)
        cmd.batch = "%(objectsize)"

        # Format: <ref>:<path>
        # Construct it in binary since the path might not be utf8.
        cmd.stdin(ref.encode("utf8") + b":" + path)

        out = cmd.run()
        head = out.readline()
        if not head or head.strip().endswith(b"missing"):
            return None

        return Blob(out.read()[: int(head)])

    @functools.cache
    def last_commit_timestamp(self):
        """Return the timestamp of the last commit."""
        refs = self._for_each_ref(
            pattern="refs/heads/", sort="-committerdate", count=1
        )
        for obj_id, _, _ in refs:
            commit = self.commit(obj_id)
            return commit.committer_epoch
        return -1


class Commit(object):
    """A git commit."""

    def __init__(
        self,
        repo,
        commit_id,
        parents,
        tree,
        author,
        author_epoch,
        author_tz,
        committer,
        committer_epoch,
        committer_tz,
        message,
    ):
        self._repo = repo
        self.id = commit_id
        self.parents = parents
        self.tree = tree
        self.author = author
        self.author_epoch = author_epoch
        self.author_tz = author_tz
        self.committer = committer
        self.committer_epoch = committer_epoch
        self.committer_tz = committer_tz
        self.message = message

        self.author_name, self.author_email = email.utils.parseaddr(
            self.author
        )

        self.committer_name, self.committer_email = email.utils.parseaddr(
            self.committer
        )

        self.subject, self.body = self.message.split("\n", 1)

        self.author_date = Date(self.author_epoch, self.author_tz)
        self.committer_date = Date(self.committer_epoch, self.committer_tz)

        # Only get this lazily when we need it; most of the time it's not
        # required by the caller.
        self._diff = None

    def __repr__(self):
        return "<C %s p:%s a:%s s:%r>" % (
            self.id[:7],
            ",".join(p[:7] for p in self.parents),
            self.author_email,
            self.subject[:20],
        )

    @property
    def diff(self):
        """Return the diff for this commit, in unified format."""
        if not self._diff:
            self._diff = self._repo.diff(self.id)
        return self._diff

    @staticmethod
    def from_str(repo, buf):
        """Parses git rev-list output, returns a commit object."""
        if "\n\n" in buf:
            # Header, commit message
            header, raw_message = buf.split("\n\n", 1)
        else:
            # Header only, no commit message
            header, raw_message = buf.rstrip(), "    "

        header_lines = header.split("\n")
        commit_id = header_lines.pop(0)

        header_dict = defaultdict(list)
        for line in header_lines:
            k, v = line.split(" ", 1)
            header_dict[k].append(v)

        tree = header_dict["tree"][0]
        parents = set(header_dict["parent"])

        authorhdr = header_dict["author"][0]
        author, author_epoch, author_tz = authorhdr.rsplit(" ", 2)

        committerhdr = header_dict["committer"][0]
        committer, committer_epoch, committer_tz = committerhdr.rsplit(" ", 2)

        # Remove the first four spaces from the message's lines.
        message = ""
        for line in raw_message.split("\n"):
            message += line[4:] + "\n"

        return Commit(
            repo,
            commit_id=commit_id,
            tree=tree,
            parents=parents,
            author=author,
            author_epoch=author_epoch,
            author_tz=author_tz,
            committer=committer,
            committer_epoch=committer_epoch,
            committer_tz=committer_tz,
            message=message,
        )


class Date:
    """Handy representation for a datetime from git."""

    def __init__(self, epoch, tz):
        self.epoch = int(epoch)
        self.tz = tz
        self.utc = datetime.datetime.utcfromtimestamp(self.epoch)

        self.tz_sec_offset_min = int(tz[1:3]) * 60 + int(tz[4:])
        if tz[0] == "-":
            self.tz_sec_offset_min = -self.tz_sec_offset_min

        self.local = self.utc + datetime.timedelta(
            minutes=self.tz_sec_offset_min
        )

        self.str = self.utc.strftime("%a, %d %b %Y %H:%M:%S +0000 ")
        self.str += "(%s %s)" % (self.local.strftime("%H:%M"), self.tz)

    def __str__(self):
        return self.str


class Diff:
    """A diff between two trees."""

    def __init__(self, ref, changes, body):
        """Constructor.

        - ref: reference id the diff refers to.
        - changes: [ (added, deleted, filename), ... ]
        - body: diff body, as text, verbatim.
        """
        self.ref = ref
        self.changes = changes
        self.body = body

    @staticmethod
    def from_str(buf):
        """Parses git diff-tree output, returns a Diff object."""
        lines = iter(buf)
        try:
            ref_id = next(lines)
        except StopIteration:
            # No diff; this can happen in merges without conflicts.
            return Diff(None, [], "")

        # First, --numstat information.
        changes = []
        l = next(lines)
        while l != "\n":
            l = l.rstrip("\n")
            added, deleted, fname = l.split("\t", 2)
            added = added.replace("-", "0")
            deleted = deleted.replace("-", "0")
            fname = smstr(unquote(fname))
            changes.append((int(added), int(deleted), fname))
            l = next(lines)

        # And now the diff body. We just store as-is, we don't really care for
        # the contents.
        body = "".join(lines)

        return Diff(ref_id, changes, body)


class Tree:
    """A git tree."""

    def __init__(self, repo: Repo, ref: str):
        self.repo = repo
        self.ref = ref

    @functools.lru_cache
    def ls(
        self, path, recursive=False
    ) -> Iterable[Tuple[str, smstr, Optional[int]]]:
        """Generates (type, name, size) for each file in path."""
        cmd = self.repo.cmd("ls-tree")
        cmd.long = None
        if recursive:
            cmd.r = None
            cmd.t = None

        cmd.arg(self.ref)
        if not path:
            cmd.arg(".")
        else:
            cmd.arg(path)

        files = []
        for l in cmd.run():
            _mode, otype, _oid, size, name = l.split(None, 4)
            if size == "-":
                size = None
            else:
                size = int(size)

            # Remove the quoting (if any); will always give us a str.
            name = unquote(name.strip("\n"))

            # Strip the leading path, the caller knows it and it's often
            # easier to work with this way.
            name = name[len(path) :]

            # We use a smart string for the name, as it's often tricky to
            # manipulate otherwise.
            files.append((otype, smstr(name), size))

        return files


class Blob:
    """A git blob."""

    def __init__(self, raw_content: bytes):
        self.raw_content = raw_content
        self._utf8_content = None

    @property
    def utf8_content(self):
        if not self._utf8_content:
            self._utf8_content = self.raw_content.decode("utf8", "replace")
        return self._utf8_content
