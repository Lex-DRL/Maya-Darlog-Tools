# encoding: utf-8
"""
Utility functions to work with undo stack.
"""

from contextlib import contextmanager as _contextmanager

from pymel import core as __pm

from darlog_maya.py23 import *

try:
	import typing as _t
except ImportError:
	pass


@_contextmanager
def undoable_context(
	chunk_name=None  # type: _t.AnyStr
):
	"""Context manager wrapping a set of commands into a singe undo entry."""
	try:
		if isinstance(chunk_name, _t_str) and chunk_name:
			__pm.undoInfo(chunkName=chunk_name, openChunk=True)
		else:
			__pm.undoInfo(openChunk=True)
		yield
	finally:
		__pm.undoInfo(closeChunk=True)
