# -*- coding: utf-8 -*-
"""Moved to blender/lib/clip_publish.py.

This shim keeps `import publish` working in the Martin clips' *_publish.py.
It cannot be named publish.py in lib as well: the clip scripts put their own
folder first on sys.path, so `from publish import ...` would find this file.
"""
import os
import sys

sys.path.insert(0, os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "lib"))
from clip_publish import publish, timeline, FPS, BG      # noqa: F401,E402
