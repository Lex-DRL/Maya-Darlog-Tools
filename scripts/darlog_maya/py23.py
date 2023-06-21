# encoding: utf-8
"""
"""

__all__ = [
	'_py2', '_py3', '_py310',
	'_unicode', '_t_str',
	'_zip', '_zip_longest',
	'_range', '_raw_input', '_reload',
]

import sys as __sys


_py2 = __sys.version_info[0] == 2
_py3 = __sys.version_info[0] == 3
_py310 = __sys.version_info[0:2] >= (3, 10)

try:
	_unicode = unicode
	_t_str = (str, unicode)
except NameError:
	_unicode = str
	_t_str = (str, )

try:
	from itertools import izip as _zip
except ImportError:
	_zip = zip

try:
	from itertools import izip_longest as _zip_longest
except ImportError:
	from itertools import zip_longest as _zip_longest

try:
	_range = xrange
except NameError:
	_range = range

try:
	_raw_input = raw_input
except NameError:
	_raw_input = input

try:
	_reload = reload
except NameError:
	from importlib import reload as _reload
