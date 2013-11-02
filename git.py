"""
Python wrapper for git.

This module is a light Python API for interfacing with it. It calls the git
command line tool directly, so please be careful with using untrusted
parameters.
"""

import sys
import io
import subprocess
from collections import defaultdict
import email.utils
import datetime
import urllib
from cgi import escape


# Path to the git binary.
GIT_BIN = "git"

class EncodeWrapper:
    """File-like wrapper that returns data utf8 encoded."""
    def __init__(self, fd, encoding = 'utf8', errors = 'replace'):
        self.fd = fd
        self.encoding = encoding
        self.errors = errors

    def __iter__(self):
        for line in self.fd:
            yield line.decode(self.encoding, errors = self.errors)

    def read(self):
        """Returns the whole content."""
        s = self.fd.read()
        return s.decode(self.encoding, errors = self.errors)

    def readline(self):
        """Returns a single line."""
        s = self.fd.readline()
        return s.decode(self.encoding, errors = self.errors)


def run_git(repo_path, params, stdin = None, silent_stderr = False):
    """Invokes git with the given parameters.

    This function invokes git with the given parameters, and returns a
    file-like object with the output (from a pipe).
    """
    params = [GIT_BIN, '--git-dir=%s' % repo_path] + list(params)

    stderr = None
    if silent_stderr:
        stderr = subprocess.PIPE

    if not stdin:
        p = subprocess.Popen(params,
                stdin = None, stdout = subprocess.PIPE, stderr = stderr)
    else:
        p = subprocess.Popen(params,
                stdin = subprocess.PIPE, stdout = subprocess.PIPE,
                stderr = stderr)
        p.stdin.write(stdin)
        p.stdin.close()

    # We need to wrap stdout if we want to decode it as utf8, subprocess
    # doesn't support us telling it the encoding.
    if sys.version_info.major == 3:
        return io.TextIOWrapper(p.stdout, encoding = 'utf8',
                errors = 'replace')
    else:
        return EncodeWrapper(p.stdout)


class GitCommand (object):
    """Convenient way of invoking git."""
    def __init__(self, path, cmd, *args, **kwargs):
        self._override = True
        self._path = path
        self._cmd = cmd
        self._args = list(args)
        self._kwargs = {}
        self._stdin_buf = None
        self._override = False
        for k, v in kwargs:
            self.__setattr__(k, v)

    def __setattr__(self, k, v):
        if k == '_override' or self._override:
            self.__dict__[k] = v
            return
        k = k.replace('_', '-')
        self._kwargs[k] = v

    def arg(self, a):
        """Adds an argument."""
        self._args.append(a)

    def stdin(self, s):
        """Sets the contents we will send in stdin."""
        self._override = True
        self._stdin_buf = s
        self._override = False

    def run(self):
        """Runs the git command."""
        params = [self._cmd]

        for k, v in self._kwargs.items():
            dash = '--' if len(k) > 1 else '-'
            if v is None:
                params.append('%s%s' % (dash, k))
            else:
                params.append('%s%s=%s' % (dash, k, str(v)))

        params.extend(self._args)

        return run_git(self._path, params, self._stdin_buf)


class SimpleNamespace (object):
    """An entirely flexible object, which provides a convenient namespace."""
    def __init__(self, **kwargs):
        self.__dict__.update(kwargs)


class smstr:
    """A "smart" string, containing many representations for ease of use.

    This is a string class that contains:
        .raw     -> raw string, authoritative source.
        .unicode -> unicode representation, may not be perfect if .raw is not
                    proper utf8 but should be good enough to show.
        .url     -> escaped for safe embedding in URLs, can be not quite
                    readable.
        .html    -> an HTML-embeddable representation.
    """
    def __init__(self, raw):
        if not isinstance(raw, str):
            raise TypeError("The raw string must be instance of 'str'")
        self.raw = raw
        self.unicode = raw.decode('utf8', errors = 'replace')
        self.url = urllib.pathname2url(raw)
        self.html = self._to_html()

    def __cmp__(self, other):
        return cmp(self.raw, other.raw)

    # Note we don't define __repr__() or __str__() to prevent accidental
    # misuse. It does mean that some uses become more annoying, so it's a
    # tradeoff that may change in the future.

    @staticmethod
    def from_url(url):
        """Returns an smstr() instance from an url-encoded string."""
        return smstr(urllib.url2pathname(url))

    def split(self, sep):
        """Like str.split()."""
        return [ smstr(s) for s in self.raw.split(sep) ]

    def __add__(self, other):
        if isinstance(other, smstr):
            other = other.raw
        return smstr(self.raw + other)

    def _to_html(self):
        """Returns an html representation of the unicode string."""
        html = u''
        for c in escape(self.unicode):
            if c in '\t\r\n\r\f\a\b\v\0':
                esc_c = c.encode('ascii').encode('string_escape')
                html += '<span class="ctrlchr">%s</span>' % esc_c
            else:
                html += c

        return html


def unquote(s):
    """Git can return quoted file names, unquote them. Always return a str."""
    if not (s[0] == '"' and s[-1] == '"'):
        # Unquoted strings are always safe, no need to mess with them; just
        # make sure we return str.
        s = s.encode('ascii')
        return s

    # Get rid of the quotes, we never want them in the output, and convert to
    # a raw string, un-escaping the backslashes.
    s = s[1:-1].decode('string-escape')

    return s


class Repo:
    """A git repository."""

    def __init__(self, path, branch = None, name = None, info = None):
        self.path = path
        self.branch = branch

        # We don't need these, but provide them for the users' convenience.
        self.name = name
        self.info = info or SimpleNamespace()

    def cmd(self, cmd):
        """Returns a GitCommand() on our path."""
        return GitCommand(self.path, cmd)

    def for_each_ref(self, pattern = None, sort = None, count = None):
        """Returns a list of references."""
        cmd = self.cmd('for-each-ref')
        if sort:
            cmd.sort = sort
        if count:
            cmd.count = count
        if pattern:
            cmd.arg(pattern)

        for l in cmd.run():
            obj_id, obj_type, ref = l.split()
            yield obj_id, obj_type, ref

    def branches(self, sort = '-authordate'):
        """Get the (name, obj_id) of the branches."""
        refs = self.for_each_ref(pattern = 'refs/heads/', sort = sort)
        for obj_id, _, ref in refs:
            yield ref[len('refs/heads/'):], obj_id

    def branch_names(self):
        """Get the names of the branches."""
        return ( name for name, _ in self.branches() )

    def tags(self, sort = '-taggerdate'):
        """Get the (name, obj_id) of the tags."""
        refs = self.for_each_ref(pattern = 'refs/tags/', sort = sort)
        for obj_id, _, ref in refs:
            yield ref[len('refs/tags/'):], obj_id

    def tag_names(self):
        """Get the names of the tags."""
        return ( name for name, _ in self.tags() )

    def new_in_branch(self, branch):
        """Returns a new Repo, but on the specific branch."""
        return Repo(self.path, branch = branch, name = self.name,
                    info = self.info)

    def commit_ids(self, ref, limit = None):
        """Generate commit ids."""
        cmd = self.cmd('rev-list')
        if limit:
            cmd.max_count = limit

        cmd.arg(ref)

        for l in cmd.run():
            yield l.rstrip('\n')

    def commit(self, commit_id):
        """Return a single commit."""
        cs = list(self.commits(commit_id, limit = 1))
        if len(cs) != 1:
            return None
        return cs[0]

    def commits(self, ref, limit = None, offset = 0):
        """Generate commit objects for the ref."""
        cmd = self.cmd('rev-list')
        if limit:
            cmd.max_count = limit + offset

        cmd.header = None

        cmd.arg(ref)

        info_buffer = ''
        count = 0
        for l in cmd.run():
            if '\0' in l:
                pre, post = l.split('\0', 1)
                info_buffer += pre

                count += 1
                if count > offset:
                    yield Commit.from_str(self, info_buffer)

                # Start over.
                info_buffer = post
            else:
                info_buffer += l

        if info_buffer:
            count += 1
            if count > offset:
                yield Commit.from_str(self, info_buffer)

    def diff(self, ref):
        """Return a Diff object for the ref."""
        cmd = self.cmd('diff-tree')
        cmd.patch = None
        cmd.numstat = None
        cmd.find_renames = None
        # Note we intentionally do not use -z, as the filename is just for
        # reference, and it is safer to let git do the escaping.

        cmd.arg(ref)

        return Diff.from_str(cmd.run())

    def refs(self):
        """Return a dict of obj_id -> ref."""
        cmd = self.cmd('show-ref')
        cmd.dereference = None

        r = defaultdict(list)
        for l in cmd.run():
            l = l.strip()
            obj_id, ref = l.split(' ', 1)
            r[obj_id].append(ref)

        return r

    def tree(self, ref = None):
        """Returns a Tree instance for the given ref."""
        if not ref:
            ref = self.branch
        return Tree(self, ref)

    def blob(self, path, ref = None, raw = False):
        """Returns the contents of the given path."""
        if not ref:
            ref = self.branch
        cmd = self.cmd('cat-file')
        cmd.batch = None

        if isinstance(ref, unicode):
            ref = ref.encode('utf8')
        cmd.stdin('%s:%s' % (ref, path))

        out = cmd.run()
        head = out.readline()
        if not head or head.strip().endswith('missing'):
            return None

        # Raw option in case we need a binary blob and not a utf-8 encoded one.
        if raw:
            return out.fd.read()

        return out.read()

    def last_commit_timestamp(self):
        """Return the timestamp of the last commit."""
        refs = self.for_each_ref(pattern = 'refs/heads/',
                sort = '-committerdate', count = 1)
        for obj_id, _, _ in refs:
            commit = self.commit(obj_id)
            return commit.committer_epoch
        return -1


class Commit (object):
    """A git commit."""

    def __init__(self, repo,
            commit_id, parents, tree,
            author, author_epoch, author_tz,
            committer, committer_epoch, committer_tz,
            message):
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

        self.author_name, self.author_email = \
                email.utils.parseaddr(self.author)

        self.committer_name, self.committer_email = \
                email.utils.parseaddr(self.committer)

        self.subject, self.body = self.message.split('\n', 1)

        self.author_date = Date(self.author_epoch, self.author_tz)
        self.committer_date = Date(self.committer_epoch, self.committer_tz)


        # Only get this lazily when we need it; most of the time it's not
        # required by the caller.
        self._diff = None

    def __repr__(self):
        return '<C %s p:%s a:%s s:%r>' % (
                self.id[:7],
                ','.join(p[:7] for p in self.parents),
                self.author_email,
                self.subject[:20])

    @property
    def diff(self):
        """Return the diff for this commit, in unified format."""
        if not self._diff:
            self._diff = self._repo.diff(self.id)
        return self._diff

    @staticmethod
    def from_str(repo, buf):
        """Parses git rev-list output, returns a commit object."""
        if '\n\n' in buf:
            # Header, commit message
            header, raw_message = buf.split('\n\n', 1)
        else:
            # Header only, no commit message
            header, raw_message = buf.rstrip(), '    '

        header_lines = header.split('\n')
        commit_id = header_lines.pop(0)

        header_dict = defaultdict(list)
        for line in header_lines:
            k, v = line.split(' ', 1)
            header_dict[k].append(v)

        tree = header_dict['tree'][0]
        parents = set(header_dict['parent'])
        author, author_epoch, author_tz = \
                header_dict['author'][0].rsplit(' ', 2)
        committer, committer_epoch, committer_tz = \
                header_dict['committer'][0].rsplit(' ', 2)

        # Remove the first four spaces from the message's lines.
        message = ''
        for line in raw_message.split('\n'):
            message += line[4:] + '\n'

        return Commit(repo,
                commit_id = commit_id, tree = tree, parents = parents,
                author = author,
                author_epoch = author_epoch, author_tz = author_tz,
                committer = committer,
                committer_epoch = committer_epoch, committer_tz = committer_tz,
                message = message)

class Date:
    """Handy representation for a datetime from git."""
    def __init__(self, epoch, tz):
        self.epoch = int(epoch)
        self.tz = tz
        self.utc = datetime.datetime.fromtimestamp(self.epoch)

        self.tz_sec_offset_min = int(tz[1:3]) * 60 + int(tz[4:])
        if tz[0] == '-':
            self.tz_sec_offset_min = -self.tz_sec_offset_min

        self.local = self.utc + datetime.timedelta(
                                    minutes = self.tz_sec_offset_min)

        self.str = self.utc.strftime('%a, %d %b %Y %H:%M:%S +0000 ')
        self.str += '(%s %s)' % (self.local.strftime('%H:%M'), self.tz)

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
            return Diff(None, [], '')

        # First, --numstat information.
        changes = []
        l = next(lines)
        while l != '\n':
            l = l.rstrip('\n')
            added, deleted, fname = l.split('\t', 2)
            added = added.replace('-', '0')
            deleted = deleted.replace('-', '0')
            fname = smstr(unquote(fname))
            changes.append((int(added), int(deleted), fname))
            l = next(lines)

        # And now the diff body. We just store as-is, we don't really care for
        # the contents.
        body = ''.join(lines)

        return Diff(ref_id, changes, body)


class Tree:
    """ A git tree."""

    def __init__(self, repo, ref):
        self.repo = repo
        self.ref = ref

    def ls(self, path, recursive = False):
        """Generates (type, name, size) for each file in path."""
        cmd = self.repo.cmd('ls-tree')
        cmd.long = None
        if recursive:
            cmd.r = None
            cmd.t = None

        cmd.arg(self.ref)
        cmd.arg(path)

        for l in cmd.run():
            _mode, otype, _oid, size, name = l.split(None, 4)
            if size == '-':
                size = None
            else:
                size = int(size)

            # Remove the quoting (if any); will always give us a str.
            name = unquote(name.strip('\n'))

            # Strip the leading path, the caller knows it and it's often
            # easier to work with this way.
            name = name[len(path):]

            # We use a smart string for the name, as it's often tricky to
            # manipulate otherwise.
            yield otype, smstr(name), size

