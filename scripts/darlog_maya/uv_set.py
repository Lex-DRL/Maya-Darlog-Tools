# encoding: utf-8
"""
"""

import re as _re

from pymel import core as _pm
from pymel.core import nodetypes as _nt

try:
	import typing as _t
except ImportError:
	pass


class InvalidUVSet(RuntimeError):
	"""Thrown to indicate meshes which have some issue with their UV-set which prevents them from being renamed."""
	def __init__(
		self,
		meshes,  # type: _t.Iterable[_nt.Mesh]
		*args, **kwargs
	):
		super(InvalidUVSet, self).__init__(*args, **kwargs)

		# noinspection PyBroadException
		try:
			meshes = list(meshes)
		except Exception:
			meshes = list()
		self.meshes = meshes  # type: _t.List[_nt.Mesh]


def mesh_uv_sets(mesh: _nt.Mesh) -> _t.List[str]:
	return mesh.getUVSetNames()


_re_valid_uv_set_name = _re.compile('[_a-zA-Z][a-zA-Z_0-9]+$')


is_valid_name = _re_valid_uv_set_name.match


def _rename_uv_set_in_mesh_by_src_name(mesh: _nt.Mesh, old_name: _t.AnyStr, new_name: _t.AnyStr):
	if old_name == new_name:
		return

	# mesh.renameUVSet(old_name, new_name)  # doesn't save undo
	try:
		_pm.polyUVSet(mesh, rename=True, uvSet=old_name, newUVSet=new_name)
	except Exception:
		print("{}:\tInternal error: unable to perform UV-set rename {} > {}".format(
			repr(mesh), repr(old_name), repr(new_name)
		))
		raise


def _rename_uv_set_in_mesh_by_index(mesh: _nt.Mesh, index: int, new_name: str):
	current_uv_sets = mesh_uv_sets(mesh)
	try:
		old_name = current_uv_sets[index]
	except IndexError:
		raise InvalidUVSet([mesh], "{}: the shape doesn't have a UV-set with index: {}".format(repr(mesh), repr(index)))

	if old_name == new_name:
		return

	# mesh.renameUVSet(old_name, new_name)  # doesn't save undo
	try:
		_pm.polyUVSet(mesh, rename=True, uvSet=old_name, newUVSet=new_name)
	except Exception:
		print("{}:\tInternal error: unable to perform <{}> UV-set rename {} > {}".format(
			repr(mesh), index, repr(old_name), repr(new_name)
		))
		raise


def rename_uv_set_in_mesh(mesh: _nt.Mesh, uv_set: _t.Union[int, _t.AnyStr], new_name: _t.AnyStr):
	if isinstance(uv_set, int):
		return _rename_uv_set_in_mesh_by_index(mesh, uv_set, new_name)
	return _rename_uv_set_in_mesh_by_src_name(mesh, uv_set, new_name)


def rename_uv_set_in_meshes(meshes: _t.Iterable[_nt.Mesh], uv_set: _t.Union[int, _t.AnyStr], new_name: _t.AnyStr):
	rename_f = _rename_uv_set_in_mesh_by_index if isinstance(uv_set, int) else _rename_uv_set_in_mesh_by_src_name
	for mesh in meshes:
		rename_f(mesh, uv_set, new_name)

