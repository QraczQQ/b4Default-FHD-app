# -*- coding: utf-8 -*-
"""Resolve the active Default-FHD skin without hard-coding its old branding."""
import glob
import os

from Components.config import config


SKIN_ROOT = '/usr/share/enigma2'


def resolve_skin_path():
    configured = getattr(getattr(config, 'skin', None), 'primary_skin', None)
    configured = getattr(configured, 'value', '') or ''
    if configured:
        candidate = configured if os.path.isabs(configured) else os.path.join(SKIN_ROOT, configured)
        if os.path.basename(candidate) != 'skin.xml':
            candidate = os.path.join(candidate, 'skin.xml')
        if os.path.isfile(candidate) and 'Default-FHD' in candidate:
            return candidate
    candidates = sorted(glob.glob(os.path.join(SKIN_ROOT, 'Default-FHD*', 'skin.xml')))
    if candidates:
        return candidates[0]
    return os.path.join(SKIN_ROOT, 'Default-FHD', 'skin.xml')


SKIN_PATH = resolve_skin_path()
SKIN_DIR = os.path.dirname(SKIN_PATH)
