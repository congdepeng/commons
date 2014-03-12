# A one-time script to migrate twitter/commons pants code to pantsbuild/pants.

from __future__ import nested_scopes, generators, division, absolute_import, with_statement, \
                       print_function, unicode_literals

import os
import re
import sys


PANTS_ROOT = os.path.dirname(os.path.realpath(__file__))
SRC_ROOT = os.path.dirname(os.path.dirname(PANTS_ROOT))

KNOWN_STD_LIBS = set(["abc", "anydbm", "argparse", "array", "asynchat", "asyncore", "atexit", "base64",
                      "BaseHTTPServer", "bisect", "bz2", "calendar", "cgitb", "cmd", "codecs",
                      "collections", "commands", "compileall", "ConfigParser", "contextlib", "Cookie",
                      "copy", "cPickle", "cProfile", "cStringIO", "csv", "datetime", "dbhash", "dbm",
                      "decimal", "difflib", "dircache", "dis", "doctest", "dumbdbm", "EasyDialogs",
                      "errno", "exceptions", "filecmp", "fileinput", "fnmatch", "fractions",
                      "functools", "gc", "gdbm", "getopt", "getpass", "gettext", "glob", "grp", "gzip",
                      "hashlib", "heapq", "hmac", "imaplib", "imp", "inspect", "itertools", "json",
                      "linecache", "locale", "logging", "mailbox", "math", "mhlib", "mmap",
                      "multiprocessing", "operator", "optparse", "os", "pdb", "pickle", "pipes",
                      "pkgutil", "platform", "plistlib", "pprint", "profile", "pstats", "pwd", "pyclbr",
                      "pydoc", "Queue", "random", "re", "readline", "resource", "rlcompleter",
                      "robotparser", "sched", "select", "shelve", "shlex", "shutil", "signal",
                      "SimpleXMLRPCServer", "site", "sitecustomize", "smtpd", "smtplib", "socket",
                      "SocketServer", "sqlite3", "string", "StringIO", "struct", "subprocess", "sys",
                      "sysconfig", "tabnanny", "tarfile", "tempfile", "textwrap", "threading", "time",
                      "timeit", "trace", "traceback", "unittest", "urllib", "urllib2", "urlparse",
                      "usercustomize", "uuid", "warnings", "weakref", "webbrowser", "whichdb", "xml",
                      "xmlrpclib", "zipfile", "zipimport", "zlib", 'builtins', '__builtin__'])

PANTS_PACKAGE = 'twitter.pants'

IMPORT_RE = re.compile(r'import\s+(.*)')
FROM_IMPORT_RE = re.compile(r'from\s+(.*)\s+import\s+(.*)')

def has_continuation(line):
  return line.endswith('\\')

HEADER_COMMENT = [
  '# Copyright Pants, Inc. See LICENSE file for license details.'
]

FUTURE_IMPORTS = [
  'from __future__ import nested_scopes, generators, division, absolute_import, with_statement, \\',
  '                       print_function, unicode_literals'
]

class Import(object):
  def __init__(self, symbol):
    self._symbol = symbol.strip()
    if self._symbol.startswith(PANTS_PACKAGE):
      self._symbol = self._symbol[8:]

  def package(self):
    return self._symbol

  def sort_key(self):
    return 'AAA' + self._symbol

  def __str__(self):
    return 'import %s' % self._symbol


class FromImport(object):
  def __init__(self, frm, symbols):
    self._from = frm.strip()
    if self._from.startswith(PANTS_PACKAGE):
      self._from = self._from[8:]
    self._symbols = [s.strip() for s in symbols]

  def package(self):
    return self._from

  def sort_key(self):
    return 'ZZZ' + self._from

  def __str__(self):
    return 'from %s import %s' % (self._from, ', '.join(sorted(self._symbols)))


class PantsSourceFile(object):
  def __init__(self, path):
    self._path = path
    self._package = os.path.relpath(os.path.dirname(os.path.abspath(path)), SRC_ROOT).replace(os.path.sep, '.')
    self._old_lines = []
    self._stdlib_imports = []
    self._thirdparty_imports = []
    self._pants_imports = []
    self._body = []

  def process(self):
    self.load()
    self.parse_header()
    self.save()

  def load(self):
    with open(self._path, 'r') as infile:
      self._old_lines = [line.rstrip() for line in infile.read().splitlines()]

  def parse_header(self):
    # Find first non-header-comment line.
    p = next(i for i, line in enumerate(self._old_lines) if line and not line.startswith('#'))
    content_lines = self._old_lines[p:]

    def add_import(imp):
      s = imp.package()
      if s.split('.', 1)[0] in KNOWN_STD_LIBS:
        self._stdlib_imports.append(imp)
      elif s.startswith(PANTS_PACKAGE):
        self._pants_imports.append(imp)
      else:
        self._thirdparty_imports.append(imp)

    def is_import(line):
      m = IMPORT_RE.match(line)
      if m:
        add_import(Import(m.group(1)))
        return True
      else:
        return False

    def is_from_import(line):
      def absify(imp):
        if imp.startswith('.'):
          return '%s.' %self._package + imp[1:]
        else:
          return imp
      m = FROM_IMPORT_RE.match(line)
      if m:
        if not m.group(1) == '__future__':
          add_import(FromImport(absify(m.group(1)), m.group(2).split(',')))
        return True
      else:
        return False

    # Parse imports.
    lines_iter = iter(content_lines)
    line = ''
    line_parts = []
    while not line or is_import(line) or is_from_import(line):
      line_parts = [lines_iter.next()]
      while has_continuation(line_parts[-1]):
        line_parts.append(lines_iter.next())
      line = ' '.join([x[:-1].strip() for x in line_parts[:-1]] + [line_parts[-1].strip()])

    self._body = [''] + line_parts + list(lines_iter)

  def process_imports(self, imports):
    def absify_import(imp):
      if imp.startswith('from .'):
        return 'from %s.' % self._package + imp[6:]
      else:
        return imp
    abs_imports = map(absify_import, imports)
    return sorted(filter(None, abs_imports))

  def save(self):
    sorted_stdlib_imports = map(str, sorted(self._stdlib_imports, key=lambda x: x.sort_key()))
    sorted_thirdparty_imports = map(str, sorted(self._thirdparty_imports, key=lambda x: x.sort_key()))
    sorted_pants_imports = map(str, sorted(self._pants_imports, key=lambda x: x.sort_key()))
    with open(self._path, 'w') as outfile:
      for lines in [HEADER_COMMENT, FUTURE_IMPORTS, sorted_stdlib_imports,
                    sorted_thirdparty_imports, sorted_pants_imports, self._body]:
        for line in lines:
          outfile.write(line)
          outfile.write('\n')
        if lines:
          outfile.write('\n')


def handle_path(path):
  if os.path.isfile(path):
    print('PROCESSING: %s' % path)
    srcfile = PantsSourceFile(path)
    srcfile.process()
  else:
    for path in os.listdir(path):
      handle_path(path)

if __name__ == '__main__':
  path = sys.argv[1]
  handle_path(path)