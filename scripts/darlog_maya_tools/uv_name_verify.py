# encoding: utf-8
"""
Ensure that UV-set with a given index has a specific name.
"""

__author__ = 'Lex Darlog (DRL)'

from pprint import pformat as _pformat

from pymel import core as _pm
from pymel.core import nodetypes as _nt

from darlog_maya.ls_convert import (
	cleanup_input,
	FromToMesh,

	_h_poly_object,
	_h_poly_selection_input_seq,
)
from darlog_maya.py23 import *
from darlog_maya.undo import undoable_context as _undoable_context
from darlog_maya.user_interaction import print
from darlog_maya.uv_set import InvalidUVSet, mesh_uv_sets, is_valid_name, rename_uv_set_in_meshes

try:
	import typing as _t
except ImportError:
	pass

_converter = FromToMesh(no_intermediate_shapes=True)


def _rename_uv_set_in_mesh(mesh: _nt.Mesh, index: int, new_name: str):
	current_uv_sets = mesh_uv_sets(mesh)
	old_name = current_uv_sets[index]
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


def _list_meshes_for_uv_rename(
	items: _h_poly_selection_input_seq,
	index=0, name='map1', all_transform_descendents=True
) -> _t.List[_nt.Mesh]:
	"""
	Error-check all the inputs and then list the shapes pending for UV-rename.

	The pre-check is done in order to list problematic meshes if any issue is found.
	Which, in turn, is done to auto-select them.
	"""
	if not isinstance(index, int):
		raise TypeError("UV-set index must be an int. Got {}: {}".format(type(index), repr(index)))

	if not isinstance(name, _t_str):
		raise TypeError("UV-set name must be a string. Got: {}".format(repr(name)))
	if not is_valid_name(name):
		raise ValueError("Invalid UV-set name: {}".format(repr(name)))

	items_list = cleanup_input(items)

	if not items_list:
		return list()

	meshes, error_input = _converter.to_meshes(items_list, all_transform_descendents=all_transform_descendents)
	if error_input:
		raise ValueError(
			"Unsupported value: {}".format(repr(error_input[0]))
			if len(error_input) == 1 else
			"Unsupported values: {}".format(_pformat(error_input))
		)

	assert len(error_input) == 0

	meshes_for_rename = list()  # type: _t.List[_nt.Mesh]
	meshes_with_name_clashes = list()  # type: _t.List[_t.Tuple[_nt.Mesh, _t.List[str]]]
	meshes_with_wrong_uv_sets = list(meshes_with_name_clashes)
	for mesh in meshes:
		uv_sets = mesh_uv_sets(mesh)
		try:
			current_set = uv_sets[index]
		except IndexError:
			meshes_with_wrong_uv_sets.append(
				(mesh, uv_sets)
			)
			continue

		if current_set == name:
			continue
		if name in set(uv_sets):
			meshes_with_name_clashes.append(
				(mesh, uv_sets)
			)
			continue

		meshes_for_rename.append(mesh)

	if meshes_with_wrong_uv_sets:
		bad_meshes = (mesh for mesh, uv_sets in meshes_with_wrong_uv_sets)
		msg = "The following {} have a UV-set with index of {}:\n{}".format(
			"shape doesn't" if len(meshes_with_wrong_uv_sets) == 1 else "shapes don't",
			index,
			'\n'.join(
				"\t{}\t>\t{}".format(repr(mesh), uv_sets) for mesh, uv_sets in meshes_with_wrong_uv_sets
			)
		)
		raise InvalidUVSet(bad_meshes, msg)
	assert len(meshes_with_wrong_uv_sets) == 0

	if meshes_with_name_clashes:
		bad_meshes = (mesh for mesh, uv_sets in meshes_with_name_clashes)
		msg = "The following {} a {} UV-set:\n{}".format(
			"shape already has" if len(meshes_with_name_clashes) == 1 else "shapes already have",
			repr(name),
			'\n'.join(
				"\t{}\t>\t{}".format(repr(mesh), uv_sets) for mesh, uv_sets in meshes_with_name_clashes
			)
		)
		raise InvalidUVSet(bad_meshes, msg)
	assert len(meshes_with_name_clashes) == 0

	return meshes_for_rename


def verify_on_objects_or_components(
	items: _h_poly_selection_input_seq,
	index=0, name='map1', all_transform_descendents=True, do_print=True
) -> _t.List[_h_poly_object]:
	try:
		meshes_for_rename = _list_meshes_for_uv_rename(
			items, index=index, name=name, all_transform_descendents=all_transform_descendents
		)
	except InvalidUVSet as e:
		_pm.select([_converter.mesh_to_transform_if_only_one(mesh) for mesh in e.meshes], r=1)
		raise e

	if not meshes_for_rename:
		if do_print:
			print("All the meshes have UV-set <{}> named {}".format(index, repr(name)))
		return list()

	res = [_converter.mesh_to_transform_if_only_one(mesh) for mesh in meshes_for_rename]
	_pm.select(res, r=1)

	if do_print:
		print(
			"UV-set <{}> on {} isn't named {}".format(
				index,
				repr(res[0]) if len(res) == 1 else "{} selected objects".format(len(res)),
				repr(name)
			)
		)
	return res


def verify_on_selection(
	index=0, name='map1', all_transform_descendents=True, do_print=True
) -> _t.List[_h_poly_object]:
	return verify_on_objects_or_components(
		_pm.ls(sl=1),
		index=index, name=name,
		all_transform_descendents=all_transform_descendents, do_print=do_print
	)


def rename_on_objects_or_components(
	items: _h_poly_selection_input_seq,
	index=0, name='map1', all_transform_descendents=True, do_print=True
) -> _t.List[_h_poly_object]:
	try:
		meshes_for_rename = _list_meshes_for_uv_rename(
			items, index=index, name=name, all_transform_descendents=all_transform_descendents
		)
	except InvalidUVSet as e:
		_pm.select([_converter.mesh_to_transform_if_only_one(mesh) for mesh in e.meshes], r=1)
		raise e

	if not meshes_for_rename:
		if do_print:
			print("All the meshes have UV-set <{}> named {}".format(index, repr(name)))
		return list()

	res = [_converter.mesh_to_transform_if_only_one(mesh) for mesh in meshes_for_rename]

	with _undoable_context("uvSetsRenameChunk"):
		rename_uv_set_in_meshes(meshes_for_rename, index, name)
		_pm.select(res, r=1)

	if do_print:
		print(
			"UV-set <{}> on {} was renamed to {}".format(
				index,
				repr(res[0]) if len(res) == 1 else "{} selected objects".format(len(res)),
				repr(name)
			)
		)
	return res


def rename_on_selection(
	index=0, name='map1', all_transform_descendents=True, do_print=True
) -> _t.List[_h_poly_object]:
	return rename_on_objects_or_components(
		_pm.ls(sl=1),
		index=index, name=name,
		all_transform_descendents=all_transform_descendents, do_print=do_print
	)
