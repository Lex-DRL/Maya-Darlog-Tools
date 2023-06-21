# encoding: utf-8
"""
Copy UVs between sets on multiple shapes at once.
"""

__author__ = 'Lex Darlog (DRL)'

from pprint import pformat as _pformat

from pymel import core as _pm
from pymel.core import nodetypes as _nt

from darlog_maya.ls_convert import (
	FromToMesh,

	_h_poly_selection_input,
	_h_poly_selection_input_seq,
	_h_poly_grouped_output,
)
from darlog_maya.py23 import _t_str, _zip
from darlog_maya.typing_poly import _t_poly_object_or_comp
from darlog_maya.user_interaction import print
from darlog_maya.uv_set import (
	InvalidUVSet,
	default_set_name,
	mesh_uv_sets,
	mesh_uv_set_current,
	mesh_uv_set_by_index,
	is_valid_name,

	_is_uv_set_exists_by_index as _exists_by_index,
	_is_uv_set_exists_by_name as _exists_by_name,

	_h_uv_set,
	_t_uv_set
)

try:
	import typing as _t
except ImportError:
	pass


_converter = FromToMesh(no_intermediate_shapes=True)


def _dummy_str(uv_set: _t.AnyStr):
	return uv_set


def __is_ok_target_uv_set_by_index(mesh: _nt.Mesh, uv_set: int) -> bool:
	assert isinstance(uv_set, int)
	all_uv_sets = mesh_uv_sets(mesh)
	# we should fail when (n=2 and uv_set=3) or (n=2 and uv_set=-3)
	return len(all_uv_sets) >= abs(uv_set)


def _group_by_meshes_for_transfer(
	items: _h_poly_selection_input_seq, from_set: _t.Optional[_h_uv_set], to_set: _t.Optional[_h_uv_set],
	all_transform_descendents=True
) -> _h_poly_grouped_output:
	"""
	Pre-verify input arguments and group the items by their shape.
	"""
	for s_type_upper, s_type, set_arg in [
		('Source', 'source', from_set),
		('Target', 'target', to_set),
	]:
		if not(
			isinstance(set_arg, _t_uv_set) or (set_arg is None)
		):
			raise TypeError("{} UV-set must be either int or string. Got {}: {}".format(
				s_type_upper, type(set_arg), repr(set_arg)
			))
		if isinstance(set_arg, _t_str) and not is_valid_name(set_arg):
			raise ValueError("Invalid {} UV-set name: {}".format(s_type, repr(set_arg)))

	grouped_by_mesh, error_input = _converter.group_by_mesh(items, all_transform_descendents=all_transform_descendents)
	if error_input:
		raise ValueError("Unsupported selection: {}".format(
			repr(error_input[0]) if len(error_input) == 1 else _pformat(error_input)
		))

	assert not error_input

	error_meshes_no_src_set: _t.List[_nt.Mesh] = list()
	error_meshes_no_trg_set: _t.List[_nt.Mesh] = list()
	error_clash_meshes: _t.List[_nt.Mesh] = list()
	error_clash_set_names: _t.List[_t.AnyStr] = list()

	is_ok_src_f = _exists_by_index if isinstance(from_set, int) else _exists_by_name
	if from_set is None:
		is_ok_src_f = lambda *args: True
	is_ok_trg_f = __is_ok_target_uv_set_by_index if isinstance(to_set, int) else _exists_by_name
	if to_set is None:
		is_ok_trg_f = lambda *args: True

	get_source_uv_set_f = _factory_source_uv_set_name_getter(from_set)
	get_target_uv_set_f = _factory_target_uv_set_name_getter(to_set)

	for mesh in grouped_by_mesh.keys():
		was_error = False
		if not is_ok_src_f(mesh, from_set):
			error_meshes_no_src_set.append(mesh)
			was_error = True
		if not is_ok_trg_f(mesh, to_set):
			error_meshes_no_trg_set.append(mesh)
			was_error = True
		if was_error:
			continue

		src_name = get_source_uv_set_f(mesh)
		trg_name, make_new = get_target_uv_set_f(mesh)
		if src_name == trg_name:
			error_clash_meshes.append(mesh)
			error_clash_set_names.append(src_name)

	for s_type, set_arg, error_meshes in [
		('source', from_set, error_meshes_no_src_set),
		('target', to_set, error_meshes_no_trg_set),
	]:
		if error_meshes:
			raise InvalidUVSet.set_does_not_exist(error_meshes, set_arg, uv_set_label=s_type)

	if error_clash_meshes:
		raise InvalidUVSet(error_clash_meshes, "Can't copy UVs from {} UV-set to itself on the following {}:\n{}".format(
			'current' if from_set is None else ('<{}>'.format(from_set) if isinstance(from_set, int) else repr(from_set)),
			'poly-shape' if len(error_clash_meshes) == 1 else 'poly-shapes',
			'\n'.join(
				'\t{}\t>\t{}'.format(repr(uv_name), mesh)
				for mesh, uv_name in _zip(error_clash_meshes, error_clash_set_names)
			)
		))

	assert not (error_meshes_no_src_set or error_meshes_no_trg_set or error_clash_meshes)
	return grouped_by_mesh


def _factory_source_uv_set_name_getter(from_set: _t.Optional[_h_uv_set]) -> _t.Callable[[_nt.Mesh], _t.AnyStr]:
	"""
	To avoid unnecessary work per each item, it's better to first build a function
	for a given (fixed) uv-set argument and just call it within loop unconditionally.
	This factory does just that.

	The returned function takes mesh and returns uv-set name as a string.
	"""
	if from_set is None:
		return mesh_uv_set_current

	def get_source_uv_set_str(mesh: _nt.Mesh) -> _t.AnyStr:
		return from_set

	def get_source_uv_set_int(mesh: _nt.Mesh) -> _t.AnyStr:
		return mesh_uv_set_by_index(mesh, from_set, error_uv_set_label='source')

	return get_source_uv_set_int if isinstance(from_set, int) else get_source_uv_set_str


def _factory_target_uv_set_name_getter(to_set: _t.Optional[_h_uv_set]) -> _t.Callable[[_nt.Mesh], _t.Tuple[_t.AnyStr, bool]]:
	"""
	Similar factory for target uv-set name getter.

	The created function takes mesh and returns two values:

		- ``string``: uv-set name
		- ``bool``: whether this set should be created as new one.
	"""
	def get_target_uv_set_always_new(mesh: _nt.Mesh) -> _t.Tuple[_t.AnyStr, bool]:
		mesh_sets = mesh_uv_sets(mesh)
		return default_set_name(len(mesh_sets)), True

	if to_set is None:
		return get_target_uv_set_always_new

	def get_target_uv_set_str(mesh: _nt.Mesh) -> _t.Tuple[_t.AnyStr, bool]:
		mesh_sets = mesh_uv_sets(mesh)
		return to_set, to_set in mesh_sets

	if not isinstance(to_set, int):
		assert isinstance(to_set, _t_str)
		return get_target_uv_set_str

	assert isinstance(to_set, int)

	new_set_name = ''
	required_set_count = 0
	if to_set < 0:
		required_set_count = abs(to_set)
	else:
		new_set_name = default_set_name(to_set)
		required_set_count = to_set

	def get_target_uv_set_int_positive(mesh: _nt.Mesh) -> _t.Tuple[_t.AnyStr, bool]:
		mesh_sets = mesh_uv_sets(mesh)
		n = len(mesh_sets)
		if n < required_set_count:
			raise InvalidUVSet.set_does_not_exist([mesh], to_set, uv_set_label='target')
		if n == required_set_count:
			return new_set_name, True
		return mesh_sets[to_set], False

	def get_target_uv_set_int_negative(mesh: _nt.Mesh) -> _t.Tuple[_t.AnyStr, bool]:
		mesh_sets = mesh_uv_sets(mesh)
		n = len(mesh_sets)
		if n < required_set_count:
			raise InvalidUVSet.set_does_not_exist([mesh], to_set, uv_set_label='target')
		return mesh_sets[to_set], False

	if to_set < 0:
		return get_target_uv_set_int_negative
	return get_target_uv_set_int_positive


def _copy_uv(
	items: _h_poly_selection_input_seq, from_set: _t.Optional[_h_uv_set], to_set: _t.Optional[_h_uv_set],
	all_transform_descendents=True
) -> _t.List[_nt.Mesh]:
	grouped_by_mesh = _group_by_meshes_for_transfer(
		items, from_set=from_set, to_set=to_set,
		all_transform_descendents=all_transform_descendents
	)
	if not grouped_by_mesh:
		return list()

	get_source_uv_set_f = _factory_source_uv_set_name_getter(from_set)
	get_target_uv_set_f = _factory_target_uv_set_name_getter(to_set)

	for mesh, mesh_items in grouped_by_mesh.items():
		source_set_name = get_source_uv_set_f(mesh)
		target_set_name, make_new = get_target_uv_set_f(mesh)
		_pm.polyCopyUV(mesh_items, uvSetNameInput=source_set_name, uvSetName=target_set_name, createNewMap=make_new)

	return list(grouped_by_mesh.keys())


_h_uv_as_vf = _t.Union[_t.List[_pm.MeshVertexFace], _h_poly_selection_input]


def _convert_uv_to_vf_gen(
	items: _h_poly_selection_input_seq
) -> _t.Generator[_t.Tuple[bool, _h_uv_as_vf], _t.Any, None]:
	"""
	Since Maya's UVs are locked per-set, we need to pre-convert all the actual UVs to vertex faces
	to restore selection after transfer.
	"""
	for item in items:
		if not isinstance(item, _pm.MeshUV):
			yield True, item
			continue

		vertex_faces: _t.List[_pm.MeshVertexFace] = _pm.polyListComponentConversion(item, fromUV=True, toVertexFace=True)
		yield False, vertex_faces


def _restore_uv_from_vf_back(flat_items: _t.Iterable[_t.Tuple[bool, _h_uv_as_vf]]):
	for is_intact, item in flat_items:
		if is_intact:
			yield item
		for uv in _pm.polyListComponentConversion(item, fromVertexFace=True, toUV=True):
			yield uv


def copy_uv(
	items: _h_poly_selection_input_seq, from_set: _t.Optional[_h_uv_set] = None, to_set: _t.Optional[_h_uv_set] = None,
	all_transform_descendents=True, do_print=True
) -> _t.List[_nt.Mesh]:
	"""
	Batch-copy UVs between sets for multiple poly-shapes at once.

	Unfortunately, not undoable :(
	"""

	pre_selection_uv_as_vf = list(_convert_uv_to_vf_gen(_pm.ls(sl=1)))

	# with _undoable_context("uvSetsBulkCopyChunk"):  # not undoable :(

	try:
		meshes = _copy_uv(items, from_set, to_set, all_transform_descendents=all_transform_descendents)
	except InvalidUVSet as e:
		_pm.select([_converter.mesh_to_transform_if_only_one(mesh) for mesh in e.meshes], r=1)
		raise e

	copy_from_to_suffix = ''
	if do_print:
		copy_from = ''
		if from_set is not None:
			copy_from = " from <{}>".format(from_set) if isinstance(from_set, int) else " from {}".format((repr(from_set)))
		copy_to = ''
		if to_set is not None:
			copy_to = " to <{}>".format(to_set) if isinstance(to_set, int) else " to {}".format((repr(to_set)))
		copy_from_to_suffix = '{}{} set'.format(copy_from, copy_to) if (copy_from or copy_to) else ''

	if not meshes:
		if do_print:
			print("No poly-objects/components selected to copy UVs{}".format(copy_from_to_suffix))
		return list()

	try:
		restored_selection_with_uv = [
			_converter.mesh_to_transform_if_only_one(x) if isinstance(x, _nt.Mesh) else x
			for x in _restore_uv_from_vf_back(pre_selection_uv_as_vf)
		]
		_pm.select(restored_selection_with_uv, r=1)
	except Exception:
		pass

	if do_print:
		print("UVs on {} were copied{}".format(
			repr(meshes[0]) if len(meshes) == 1 else "{} poly-shapes".format(len(meshes)),
			copy_from_to_suffix
		))
	return meshes


def copy_uv_on_selection(
	from_set: _t.Optional[_h_uv_set] = None, to_set: _t.Optional[_h_uv_set] = None,
	all_transform_descendents=True, do_print=True
) -> _t.List[_nt.Mesh]:
	return copy_uv(
		(x for x in _pm.ls(sl=1) if isinstance(x, _t_poly_object_or_comp)),
		from_set=from_set, to_set=to_set,
		all_transform_descendents=all_transform_descendents, do_print=do_print
	)
