#!/usr/bin/env python
# encoding: utf-8
"""
Copy a selected file into `incrementalSave` as a new version.
"""

__author__ = 'Lex Darlog (DRL)'


import typing as _t

import errno as _errno
from itertools import chain as _chain
import os as _os
from pathlib import Path as _Path
import re as _re
import shutil as _shutil
import sys as _sys


_re_match_flags = _re.IGNORECASE if _os.name == 'nt' else 0

_incremental_subdir = 'incrementalSave'
_supported_extensions = {'.ma', '.mb', '.mel'}


def _out_file_path(out_dir: _Path, src_base_name: _t.AnyStr, src_ext: _t.AnyStr) -> _Path:
	match_regex = "{}\\.([0-9]+){}$".format(_re.escape(src_base_name), _re.escape(src_ext))
	match = _re.compile(match_regex, flags=_re_match_flags).match

	existing_files_and_match = ((x, match(x.name)) for x in out_dir.iterdir() if x.is_file())
	existing_files_and_id = (((x, int(m.group(1))) for x, m in existing_files_and_match if m))

	# In order to keep `existing_files_and_id` a generator, here's some jumping through the hoops
	# to detect whether sequence is empty or not:
	file_sequence_non_empty = False
	try:
		seq_iter = iter(existing_files_and_id)
		first_item = next(seq_iter)
		file_sequence_non_empty = True
		existing_files_and_id = _chain([first_item], seq_iter)
	except StopIteration:
		file_sequence_non_empty = False

	if file_sequence_non_empty:
		max_file, max_id = max(existing_files_and_id, key=lambda x_i: x_i[1])
	else:
		max_id = 0

	new_id_str = str(max(max_id + 1, 1)).zfill(4)
	new_name = f"{src_base_name}.{new_id_str}{src_ext}"

	return out_dir / new_name


def copy_single_file(file_path_str: str) -> _t.Tuple[_Path, bool]:
	assert file_path_str and isinstance(file_path_str, str), f"Non-empty string expected. Got:\n{file_path_str!r}"

	src_path = _Path(file_path_str).resolve()

	if not src_path.suffix.lower() in _supported_extensions:
		return src_path, False

	src_dir = src_path.parent

	out_dir = src_dir / _incremental_subdir / src_path.name
	if not out_dir.exists():
		out_dir.mkdir(parents=True)
	if not out_dir.is_dir():
		raise OSError(_errno.ENOTDIR, _os.strerror(_errno.ENOTDIR), str(out_dir))

	new_path = _out_file_path(out_dir, src_path.stem, src_path.suffix)
	src_path_s, new_path_s = str(src_path), str(new_path)
	try:
		_shutil.copy2(src_path_s, new_path_s, follow_symlinks=True)
	except OSError:
		# Fallback for Windows:
		_shutil.copy(src_path_s, new_path_s, follow_symlinks=True)

	return new_path, True


def copy(*file_paths: _t.AnyStr):
	if not file_paths:
		return

	assert all(x and isinstance(x, str) for x in file_paths), f"Non-empty strings expected. Got:\n{file_paths!r}"

	print("\nCopying:\n")
	copied_n = 0
	skipped_n = 0
	for file_path in file_paths:
		out_path, ok = copy_single_file(file_path)
		msg = str(out_path)
		if not ok:
			msg = f" [SKIPPED] >{msg}"
		print(msg)
		copied_n += bool(ok)
		skipped_n += not ok

	final_msg = f"\nCopied file{'s' if copied_n else ''}: {copied_n}"
	if skipped_n > 0:
		final_msg = f"{final_msg}\nSkipped: {skipped_n}"
	print(final_msg)


def _run():
	import traceback as _traceback

	try:
		copy(*_sys.argv[1:])
	except OSError as e:
		error_str = e.strerror
		error_str = '\n[ERROR {}] {}'.format(
			e.errno,
			error_str if error_str else _os.strerror(e.errno)
		)
		filename = e.filename
		if filename:
			error_str = '{}:\n{}'.format(error_str, filename)
		print(error_str)
	except Exception as e:
		print("".join(
			_traceback.format_exception(type(e), e, e.__traceback__)
		))

	input("Press Enter to exit...")


if __name__ == '__main__':
	_run()
