#!/usr/bin/env python3
"""Increase the patch part of VERSION and print the new value."""
from __future__ import print_function

import os
import re
import sys


VERSION_RE = re.compile(r'^(\d+)\.(\d+)\.(\d+)$')


def main():
    repository = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    path = os.path.join(repository, 'VERSION')
    with open(path, 'r') as version_file:
        current = version_file.read().strip()
    match = VERSION_RE.match(current)
    if not match:
        raise SystemExit('Invalid VERSION: %s' % current)
    major, minor, patch = (int(value) for value in match.groups())
    version = '%d.%d.%d' % (major, minor, patch + 1)
    with open(path, 'w') as version_file:
        version_file.write(version + '\n')
    print(version)


if __name__ == '__main__':
    main()
