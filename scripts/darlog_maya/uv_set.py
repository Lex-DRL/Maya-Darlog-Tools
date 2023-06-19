# encoding: utf-8
"""
"""

import re as _re

from pymel import core as _pm
from pymel.core import nodetypes as _nt

from darlog_maya.py23 import _t_str

try:
	import typing as _t
except ImportError:
	pass


_h_uv_set = _t.Union[int, _t.AnyStr]

_t_uv_set = tuple([int] + list(_t_str))


class InvalidUVSet(RuntimeError):
	"""Thrown to indicate meshes which have some issue with their UV-set which prevents them from being renamed."""
	def __init__(
		self,
		meshes: _t.Iterable[_nt.Mesh],
		*args, **kwargs
	):
		super(InvalidUVSet, self).__init__(*args, **kwargs)
		self.meshes = self.__to_meshes_list(meshes)

	@staticmethod
	def __to_meshes_list(meshes: _t.Iterable[_nt.Mesh]) -> _t.List[_nt.Mesh]:
		if meshes is None:
			return list()

		if isinstance(meshes, _nt.Mesh):
			return [meshes, ]

		if isinstance(meshes, _t_str):
			try:
				return _pm.ls(meshes)
			except Exception:
				return list()

		# noinspection PyBroadException
		try:
			return list(meshes)
		except Exception:
			return list()

	@classmethod
	def set_does_not_exist(cls, meshes: _t.Iterable[_nt.Mesh], uv_set: _t.Optional[_h_uv_set], uv_set_label=''):
		clean_meshes = cls.__to_meshes_list(meshes)
		n = len(clean_meshes)

		try:
			uv_set_label = uv_set_label.strip()
		except Exception:
			uv_set_label = ''

		missing_set = "<{}> UV-set".format(uv_set_label) if uv_set_label else "UV-set"
		if isinstance(uv_set, _t_uv_set):
			missing_set = "{} {}".format(
				missing_set,
				"with index = {}".format(uv_set) if isinstance(uv_set, int) else "named {}".format(repr(uv_set))
			)

		return cls(
			clean_meshes,
			"{} have a {}".format(
				"{} shapes don't".format(n) if n > 1 else "{}: doesn't".format(repr(clean_meshes[0])),
				missing_set
			)
		)


_re_valid_uv_set_name = _re.compile('[_a-zA-Z][a-zA-Z_0-9]+$')


is_valid_name = _re_valid_uv_set_name.match


def default_set_name(index: int):
	if index < 0:
		raise ValueError("Default names are defined for positive indices. Got: {}".format(index))
	if index == 0:
		return 'map1'
	return 'uvSet{}'.format(index)


def mesh_uv_sets(mesh: _nt.Mesh) -> _t.List[_t.AnyStr]:
	return mesh.getUVSetNames()


def mesh_uv_set_by_index(mesh: _nt.Mesh, uv_set: int, error_uv_set_label='') -> _t.AnyStr:
	all_uv_sets = mesh_uv_sets(mesh)
	try:
		return all_uv_sets[uv_set]
	except IndexError:
		raise InvalidUVSet.set_does_not_exist([mesh], uv_set, uv_set_label=error_uv_set_label)


def mesh_uv_set_current(mesh: _nt.Mesh) -> _t.AnyStr:
	assert isinstance(mesh, _nt.Mesh)
	try:
		return mesh.getCurrentUVSetName()
	except Exception:
		raise InvalidUVSet.set_does_not_exist([mesh], None, uv_set_label='current')


def _is_uv_set_exists_by_index(mesh: _nt.Mesh, uv_set: int) -> bool:
	all_uv_sets = mesh_uv_sets(mesh)
	try:
		uv_set_name = all_uv_sets[uv_set]
		return True
	except IndexError:
		return False


def _is_uv_set_exists_by_name(mesh: _nt.Mesh, uv_set: _t.AnyStr) -> bool:
	all_uv_sets = mesh_uv_sets(mesh)
	return uv_set in all_uv_sets


def is_uv_set_exists(mesh: _nt.Mesh, uv_set: _h_uv_set) -> bool:
	return _is_uv_set_exists_by_index(mesh, uv_set) if isinstance(uv_set, int) else _is_uv_set_exists_by_name(mesh, uv_set)


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

