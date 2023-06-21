# encoding: utf-8
"""
"""

import sys as _sys

from darlog_maya.py23 import *

try:
	import typing as _t
except ImportError:
	pass


# noinspection PyShadowingBuiltins
def print(*values: object, sep: _t.Optional[_t.AnyStr] = ' ', end: _t.Optional[_t.AnyStr] = '\n'):
	"""This print, unlike the built-in one, displays the result right in Maya's status line (not only in script editor)."""
	if sep is None:
		sep = ' '
	if end is None:
		end = '\n'

	str_type = type(sep)
	try:
		msg = sep.join(str_type(x) for x in values)
	except UnicodeError:
		msg = sep.join(_unicode(x) for x in values)

	try:
		msg = '{}{}'.format(msg, end)
	except UnicodeError:
		msg = _unicode('{}{}').format(msg, end)

	_sys.stdout.write(msg)
