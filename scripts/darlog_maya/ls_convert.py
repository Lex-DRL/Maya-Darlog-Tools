# encoding: utf-8
"""
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass as _dataclass

from pymel import core as _pm
from pymel.core import nodetypes as _nt

from darlog_maya.py23 import *
from darlog_maya.typing_poly import *

import typing as _t
_h_transform_input = _t.Union[_nt.Transform, _t.AnyStr]
_h_transform_input_seq = _t.Union[_h_transform_input, _t.Sequence[_h_transform_input]]
_h_input = _t.Union[_pm.PyNode, _t.AnyStr, None]
_h_input_seq = _t.Union[_h_input, _t.Sequence[_h_input]]

_TShape = _t.TypeVar('TShape', bound=_nt.Shape)

_h_geo_object = _t.Union[_nt.Transform, _TShape]
_h_geo_selection_input = _t.Union[_h_geo_object, _pm.Component, _t.AnyStr, None]
_h_geo_selection_input_seq = _t.Union[_h_geo_selection_input, _t.Sequence[_h_geo_selection_input]]

_h_poly_object = _t.Union[_nt.Transform, _nt.Mesh]
_h_poly_comp = _t.Union[_pm.MeshVertex, _pm.MeshFace, _pm.MeshVertexFace, _pm.MeshEdge, _pm.MeshUV]
_h_poly_selection_input = _t.Union[_h_poly_object, _h_poly_comp, _t.AnyStr, None]
_h_poly_selection_input_seq = _t.Union[_h_poly_selection_input, _t.Sequence[_h_poly_selection_input]]

_h_shape_type_arg = _t.Union[_t.Type[_TShape], _t.Tuple[_t.Type[_TShape], ...]]
_h_comp_type_arg = _t.Union[_t.Type[_pm.Component], _t.Tuple[_t.Type[_pm.Component], ...]]


def cleanup_input(items: _h_input_seq) -> _t.List[_pm.PyNode]:
	if items is None:
		return list()

	if isinstance(items, _t_str):
		items = [items, ]

	try:
		items = list(items)
	except TypeError:
		items = [items, ]

	items = [x for x in items if x is not None]
	return _pm.ls(items)


@_dataclass(init=False)
class _FromToShape(ABC):
	"""An ABC designed to perform component/shape/transform conversions on an arbitrary shape type."""

	no_intermediate_shapes = True

	def __init__(self, no_intermediate_shapes: bool = True):  # to help IDE identify there _IS_ indeed a right init method.
		super(_FromToShape, self).__init__()
		self.no_intermediate_shapes = no_intermediate_shapes

	@staticmethod
	@abstractmethod
	def _shape_type() -> _h_shape_type_arg:
		raise NotImplementedError()

	@staticmethod
	@abstractmethod
	def _comp_type() -> _h_comp_type_arg:
		raise NotImplementedError()

	@classmethod
	def _comp_to_shape(cls, component: _pm.Component) -> _TShape:
		assert isinstance(component, cls._comp_type())
		return component.node()

	def _transforms_to_child_shapes_gen(
		self, transform_nodes: _h_transform_input_seq, all_descendents=False
	) -> _t.Generator[_TShape, _t.Any, None]:
		shape_type = self._shape_type()
		return (
			x for x in _pm.listRelatives(
				transform_nodes, shapes=1, allDescendents=all_descendents, noIntermediate=self.no_intermediate_shapes
			) if isinstance(x, shape_type)
		)

	def __to_shape_gen_with_possible_duplicates(
		self, items: _h_geo_selection_input_seq, all_transform_descendents=True
	) -> _t.Generator[_t.Tuple[bool, _t.Any], _t.Any, None]:
		"""
		Low-level function converting from a valid selection to shapes.

		``shape_type`` must be a subclass or tuple of subclasses of ``nt.Shape``.

		``comp_type`` must similarly contain all the component types for the given ``shape_type``.

		First element of yielded result is whether the given item is an error input.
		"""
		shape_type = self._shape_type()
		comp_type = self._comp_type()

		for item in cleanup_input(items):
			if isinstance(item, shape_type):
				# print("Shape: {}".format(repr(item)))
				yield False, item
				continue
			if isinstance(item, comp_type):
				# print("Shape component: {}".format(repr(item)))
				yield False, item.node()
				continue
			if isinstance(item, _nt.Transform):
				# print("Transform: {}".format(repr(item)))
				for child_mesh in self._transforms_to_child_shapes_gen(item, all_descendents=all_transform_descendents):
					yield False, child_mesh
				continue

			# print("Unsupported selection type: {}".format(repr(item)))
			yield True, item  # invalid input

	def _to_shapes(
		self, items: _h_geo_selection_input_seq, all_transform_descendents=True
	) -> _t.Tuple[_t.List[_TShape], _t.List[_t.Any]]:
		seen = set()  # type: _t.Set[_TShape]
		shapes = list()  # type: _t.List[_TShape]
		error_input = list()  # type: _t.List[_t.Any]
		for is_error, shape in self.__to_shape_gen_with_possible_duplicates(
			items, all_transform_descendents=all_transform_descendents
		):
			if is_error:
				error_input.append(shape)
				continue
			if shape in seen:
				continue

			shapes.append(shape)
			seen.add(shape)

		shape_type = self._shape_type()
		assert all(isinstance(x, shape_type) for x in shapes)
		return list(shapes), list(error_input)

	def _shape_to_transform_if_only_one(self, shape: _TShape) -> _h_geo_object:
		"""
		Convert shape to it's transform if the given shape is the only child.
		"""
		assert isinstance(shape, self._shape_type())
		transform = shape.getTransform()  # type: _nt.Transform
		if any(
			isinstance(x, _nt.Transform) for x in
			_pm.listRelatives(transform, children=1, allDescendents=False)
		):
			# There are other child transforms
			return shape

		transform_shapes = list(self._transforms_to_child_shapes_gen(transform, all_descendents=False))
		if not (
			len(transform_shapes) == 1 and transform_shapes[0] == shape
		):
			# We aren't the only shape here
			return shape

		return transform


class FromToMesh(_FromToShape):
	"""Convert between poly-shape, it's transform and components."""

	@staticmethod
	def _shape_type():
		return _nt.Mesh

	@staticmethod
	def _comp_type():
		return _t_poly_comp

	@classmethod
	def comp_to_mesh(cls, component: _pm.Component) -> _nt.Mesh:
		return cls._comp_to_shape(component)

	def transforms_to_child_meshes_gen(
		self, transform_nodes: _h_transform_input_seq, all_descendents=False
	) -> _t.Generator[_nt.Mesh, _t.Any, None]:
		return self._transforms_to_child_shapes_gen(transform_nodes, all_descendents=all_descendents)

	def to_meshes(
		self, items: _h_poly_selection_input_seq, all_transform_descendents=True
	) -> _t.Tuple[_t.List[_nt.Mesh], _t.List[_t.Any]]:
		return self._to_shapes(items, all_transform_descendents=all_transform_descendents)

	def mesh_to_transform_if_only_one(self, mesh: _nt.Mesh) -> _h_poly_object:
		"""
		Convert mesh to it's transform if the given mesh is the only child.
		"""
		return self._shape_to_transform_if_only_one(mesh)
