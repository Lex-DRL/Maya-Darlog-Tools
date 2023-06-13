# encoding: utf-8
"""
Ensure that UV-set with a given index has a specific name.
"""

__author__ = 'Lex Darlog (DRL)'

from pprint import pformat
import re

from pymel import core as _pm
from pymel.core import nodetypes as _nt

from darlog_maya.py23 import *
from darlog_maya.typing_poly import *
from darlog_maya.undo import undoable_context as _undoable_context

try:
	import typing as _t
	_h_poly_object = _t.Union[_nt.Transform, _nt.Mesh]
	_h_poly_comp = _t.Union[_pm.MeshVertex, _pm.MeshFace, _pm.MeshVertexFace, _pm.MeshEdge, _pm.MeshUV]
	_h_poly_selection_str_none = _t.Union[_h_poly_object, _h_poly_comp, _t.AnyStr, None]
except ImportError:
	pass

_re_valid_uv_set_name = re.compile('[_a-zA-Z][a-zA-Z_0-9]+$')


# region Included common utility functions


# TODO: extract to a lib


def __comp_to_mesh(component):  # type: (_h_poly_comp) -> _nt.Mesh
	assert isinstance(component, _t_poly_comp)
	return component.node()


def __transform_to_child_meshes_gen(
	transform, all_descendents=False, no_intermediate_shapes=True
):  # type: (_nt.Transform, bool, bool) -> _t.Generator[_nt.Mesh, _t.Any, None]
	return (
		x for x in _pm.listRelatives(transform, shapes=1, allDescendents=all_descendents, noIntermediate=no_intermediate_shapes)
		if isinstance(x, _nt.Mesh)
	)


def __to_meshes_gen_with_duplicates(
	items, all_transform_descendents=True
):  # type: (_t.Iterable[_h_poly_selection_str_none], bool) -> _t.Generator[_t.Tuple[bool, _t.Any], _t.Any, None]
	if items is None:
		return

	if isinstance(items, _t_str):
		items = [items, ]

	try:
		iter_items = list(items)
	except TypeError:
		iter_items = [items, ]

	for item in _pm.ls(iter_items):
		if item is None:
			# print("None: {}".format(repr(item)))
			continue
		if isinstance(item, _nt.Mesh):
			# print("Mesh: {}".format(repr(item)))
			yield False, item
			continue
		if isinstance(item, _t_poly_comp):
			# print("Mesh component: {}".format(repr(item)))
			yield False, item.node()
			continue
		if isinstance(item, _nt.Transform):
			# print("Transform: {}".format(repr(item)))
			for child_mesh in __transform_to_child_meshes_gen(item, all_descendents=all_transform_descendents):
				yield False, child_mesh
			continue

		# print("Unsupported selection type: {}".format(repr(item)))
		yield True, item  # invalid input


def __to_meshes(
	items, all_transform_descendents=True
):  # type: (_t.Iterable[_h_poly_selection_str_none], bool) -> _t.Tuple[_t.List[_nt.Mesh], _t.List[_t.Any]]
	seen = set()  # type: _t.Set[_nt.Mesh]
	meshes = list()  # type: _t.List[_nt.Mesh]
	error_input = list()  # type: _t.List[_t.Any]
	for is_error, mesh in __to_meshes_gen_with_duplicates(items, all_transform_descendents=all_transform_descendents):
		if is_error:
			error_input.append(mesh)
			continue
		if mesh in seen:
			continue

		assert isinstance(mesh, _nt.Mesh)
		meshes.append(mesh)
		seen.add(mesh)

	assert all(isinstance(x, _nt.Mesh) for x in meshes)
	return list(meshes), list(error_input)


def __mesh_to_transform_if_only_one(mesh):  # type: (_nt.Mesh) -> _h_poly_object
	"""
	Convert mesh to it's transform if the given mesh is the only child
	(ignoring intermediate shapes, but including any other child transforms).
	"""
	assert isinstance(mesh, _nt.Mesh)
	transform = mesh.getTransform()  # type: _nt.Transform
	if any(
		True for x in
		_pm.listRelatives(transform, children=1, allDescendents=False)
		if isinstance(x, _nt.Transform)
	):
		# There are other child transforms
		return mesh

	transform_meshes = list(__transform_to_child_meshes_gen(transform, all_descendents=False))
	if not(
		len(transform_meshes) == 1 and transform_meshes[0] == mesh
	):
		# We aren't the only shape here
		return mesh

	return transform


# endregion


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


def _mesh_uv_sets(mesh):  # type: (_nt.Mesh) -> _t.List[str]
	return mesh.getUVSetNames()


def _rename_uv_set_in_mesh(mesh, index, new_name):  # type: (_nt.Mesh, int, str) -> ...
	current_uv_sets = _mesh_uv_sets(mesh)
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
	items, index=0, name='map1', all_transform_descendents=True
):  # type: (_t.Iterable[_h_poly_selection_str_none], int, _t.AnyStr, bool) -> _t.List[_nt.Mesh]
	"""
	Error-check all the inputs and then list the shapes pending for UV-rename.

	The pre-check is done in order to list problematic meshes if any issue is found.
	Which, in turn, is done to auto-select them.
	"""
	if not isinstance(index, int):
		raise TypeError("UV-set index must be an int. Got {}: {}".format(type(index), repr(index)))

	if not isinstance(name, _t_str):
		raise TypeError("UV-set name must be a string. Got: {}".format(repr(name)))
	if not _re_valid_uv_set_name.match(name):
		raise ValueError("Invalid UV-set name: {}".format(repr(name)))

	if items is None:
		return list()

	if isinstance(items, _t_str):
		items = [items, ]

	try:
		items_list = list(items)
	except TypeError:
		items_list = [items, ]

	if not items_list:
		return list()

	meshes, error_input = __to_meshes(items_list, all_transform_descendents=all_transform_descendents)
	if error_input:
		raise ValueError(
			"Unsupported value: {}".format(repr(error_input[0]))
			if len(error_input) == 1 else
			"Unsupported values: {}".format(pformat(error_input))
		)

	assert len(error_input) == 0

	meshes_for_rename = list()  # type: _t.List[_nt.Mesh]
	meshes_with_name_clashes = list()  # type: _t.List[_t.Tuple[_nt.Mesh, _t.List[str]]]
	meshes_with_wrong_uv_sets = list(meshes_with_name_clashes)
	for mesh in meshes:
		uv_sets = _mesh_uv_sets(mesh)
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
	items, index=0, name='map1', all_transform_descendents=True, do_print=True
):  # type: (_t.Iterable[_h_poly_selection_str_none], int, _t.AnyStr, bool, bool) -> _t.List[_h_poly_object]
	try:
		meshes_for_rename = _list_meshes_for_uv_rename(
			items, index=index, name=name, all_transform_descendents=all_transform_descendents
		)
	except InvalidUVSet as e:
		_pm.select([__mesh_to_transform_if_only_one(mesh) for mesh in e.meshes], r=1)
		raise e

	if not meshes_for_rename:
		if do_print:
			print("All the meshes have UV-set <{}> named {}".format(index, repr(name)))
		return list()

	res = [__mesh_to_transform_if_only_one(mesh) for mesh in meshes_for_rename]
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
):  # type: (int, _t.AnyStr, bool, bool) -> _t.List[_h_poly_object]
	return verify_on_objects_or_components(
		_pm.ls(sl=1),
		index=index, name=name,
		all_transform_descendents=all_transform_descendents, do_print=do_print
	)


def rename_on_objects_or_components(
	items, index=0, name='map1', all_transform_descendents=True, do_print=True
):  # type: (_t.Iterable[_h_poly_selection_str_none], int, _t.AnyStr, bool, bool) -> _t.List[_h_poly_object]
	try:
		meshes_for_rename = _list_meshes_for_uv_rename(
			items, index=index, name=name, all_transform_descendents=all_transform_descendents
		)
	except InvalidUVSet as e:
		_pm.select([__mesh_to_transform_if_only_one(mesh) for mesh in e.meshes], r=1)
		raise e

	if not meshes_for_rename:
		if do_print:
			print("All the meshes have UV-set <{}> named {}".format(index, repr(name)))
		return list()

	res = [__mesh_to_transform_if_only_one(mesh) for mesh in meshes_for_rename]

	with _undoable_context("uvSetsRenameChunk"):
		for mesh in meshes_for_rename:
			_rename_uv_set_in_mesh(mesh, index, name)
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
):  # type: (int, _t.AnyStr, bool, bool) -> _t.List[_h_poly_object]
	return rename_on_objects_or_components(
		_pm.ls(sl=1),
		index=index, name=name,
		all_transform_descendents=all_transform_descendents, do_print=do_print
	)
