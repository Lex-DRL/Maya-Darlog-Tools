# encoding: utf-8
"""
"""

__author__ = 'Lex Darlog (DRL)'

import typing as _t

from pymel import core as _pm

from darlog_maya_tools.references import import_all_references as _import_all_references

_t_j = _t.Union[_pm.nt.Joint, _pm.nt.Transform]
_i_f = _t.Union[int, float]

# noinspection PyBroadException
try:
	_unicode = unicode
	_str_t = (str, unicode)
except Exception:
	_unicode = str
	_str_t = (str, )


_baked_attribs = 'tx ty tz rx ry rz sx sy sz v'.split()


_force_set_attribs = {
	'v': 1
}

_deleted_sets = {'AllSet', 'ControlSet', 'DeformSet', 'Sets'}


def _join_node_path(*parts):  # type: (str) -> str
	if not parts:
		return ''
	parts = [x for x in parts if isinstance(x, _str_t) and x]
	try:
		return '|'.join(parts)
	except Exception:
		return _unicode('|').join(_unicode(x) for x in parts)


def _get_root_objects_under_group(group_path: str) -> _t.List[_pm.nt.Transform]:
	"""Get immediate children under a group at path. If group is empty, list all the objects in world."""
	if not(group_path and isinstance(group_path, _str_t)):
		# Our parent is world
		return [x for x in _pm.ls(tr=1) if x.getParent() is None]

	parent_group: _pm.nt.Transform = _pm.PyNode(group_path)
	assert isinstance(parent_group, _pm.nt.Transform), "<{}> must be a transform object".format(group_path)
	return [
		x
		for x in _pm.listRelatives(parent_group, children=True, allDescendents=False, noIntermediate=True)
		if isinstance(x, _pm.nt.Transform)
	]


def _get_root_geo_objects(global_group: str, geometry_group: str) -> _t.List[_pm.nt.Transform]:
	return [
		x
		for x in _get_root_objects_under_group(_join_node_path(global_group, geometry_group))
		if _is_geo_obj(x)
	]


def _get_root_joints(global_group: str, joints_group: str) -> _t.List[_t_j]:
	return [
		x
		for x in _get_root_objects_under_group(_join_node_path(global_group, joints_group))
		if _is_baked_joint(x)
	]


def _is_geo_obj(obj):
	return isinstance(obj, _pm.nt.Transform) and _pm.listRelatives(obj, shapes=1, allDescendents=False, noIntermediate=True)


def _is_baked_joint(joint):
	"""Is a viable object type to be within joint hierarchy?"""
	return isinstance(joint, _pm.nt.Joint) or type(joint) == _pm.nt.Transform


def _bake_keys(joints: _t.List[_t_j], frame_range: _t.Tuple[_i_f, _i_f] = None):
	if frame_range is None:
		frame_range = (
			_pm.playbackOptions(q=True, min=True),
			_pm.playbackOptions(q=True, max=True)
		)
	return _pm.bakeResults(
		joints,
		simulation=True, t=frame_range, sampleBy=1, at=_baked_attribs,
		disableImplicitControl=True, preserveOutsideKeys=False, sparseAnimCurveBake=False,
		removeBakedAttributeFromLayer=True, bakeOnOverrideLayer=False, minimizeRotation=True,
	)


def _cleanup_joints(
	root_joints: _t.List[_t_j], frame_range: _t.Tuple[_i_f, _i_f] = None, remove_animation=False
):
	"""
	- Bake animation
	- Disconnect from rig
	- Remove non-joints and non-transforms from hierarchy
	- Unparent
	"""
	assert bool(root_joints), "No root joints found!"
	assert all(_is_baked_joint(x) for x in root_joints), "Invalid objects as root joints: {}".format(root_joints)

	all_children: _t.List[_pm.nt.Transform] = list(root_joints)
	all_children.extend(_pm.listRelatives(
		root_joints, children=True, allDescendents=True, noIntermediate=True
	))
	baked_joints: _t.List[_pm.nt.Joint] = [x for x in all_children if _is_baked_joint(x)]
	assert bool(baked_joints), "No joints found!"

	baked_joints_set = set(baked_joints)
	non_joints = [x for x in all_children if x not in baked_joints_set]

	if remove_animation and frame_range is None:
		first_frame = _pm.playbackOptions(q=True, min=True)
		frame_range = (first_frame, first_frame + 1)
	_bake_keys(baked_joints, frame_range=frame_range)
	if non_joints:
		_pm.delete(non_joints)

	for j in baked_joints_set:
		for attr_nm, val in _force_set_attribs.items():
			attr: _pm.Attribute = j.attr(attr_nm)
			attr.disconnect(inputs=True)
			attr.set(val)

	if remove_animation:
		for j in baked_joints_set:
			for attr_nm in _baked_attribs:
				attr: _pm.Attribute = j.attr(attr_nm)
				attr.disconnect(inputs=True)

	_pm.parent(root_joints, world=True)
	return list(baked_joints_set)


def _cleanup_sets():
	del_sets = [x for x in _pm.ls(sets=1) if type(x) == _pm.nt.ObjectSet and x.name() in _deleted_sets]
	if del_sets:
		_pm.delete(del_sets)


def cleanup_rig(
	global_group='Group', joints_group='DeformationSystem', geometry_group='Geometry',
	frame_range: _t.Tuple[_i_f, _i_f] = None, remove_animation=False, remove_geo=False
):
	"""
	Cleanup (Advanced Skeleton) rig for export:
	- Import all references, remove namespaces
	- Bake animation on joints
	- Unparent root joints and skinned geo
	- Remove the rest of the rig
	"""
	_import_all_references(confirm_load=False)

	root_joints = _get_root_joints(global_group, joints_group)
	root_geo_objects = _get_root_geo_objects(global_group, geometry_group)

	baked_joints = _cleanup_joints(root_joints, frame_range=frame_range, remove_animation=remove_animation)

	if root_geo_objects:
		if remove_geo:
			_pm.delete(root_geo_objects)
		else:
			_pm.parent(root_geo_objects, world=True)

	all_out_objects = list(baked_joints)
	if not remove_geo:
		all_out_objects.extend(root_geo_objects)
		all_out_objects.extend(
			x for x in _pm.listRelatives(root_geo_objects, children=True, allDescendents=True, noIntermediate=True)
			if _is_geo_obj(x)
		)

	if global_group:
		parent_group: _pm.nt.Transform = _pm.PyNode(global_group)
		_pm.delete(parent_group)

	_cleanup_sets()

	_pm.select(all_out_objects, r=1)
