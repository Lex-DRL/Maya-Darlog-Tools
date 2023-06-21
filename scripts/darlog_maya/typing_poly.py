# encoding: utf-8
"""
Type hints for Maya's polygon-related objects/components.
"""

__all__ = [
	'_t_transform', '_t_poly_shape', '_t_mesh', '_t_poly_object', '_t_poly_comp',
]

from pymel import core as __pm
from pymel.core import nodetypes as __nt


_t_transform = __nt.Transform
_t_poly_shape = _t_mesh = __nt.Mesh
_t_poly_object = (__nt.Transform, __nt.Mesh)
_t_poly_comp = (
	__pm.MeshVertex,
	__pm.MeshFace,
	__pm.MeshVertexFace,
	__pm.MeshEdge,
	__pm.MeshUV,
)
_t_poly_object_or_comp = (
	__nt.Transform,
	__nt.Mesh,

	__pm.MeshVertex,
	__pm.MeshFace,
	__pm.MeshVertexFace,
	__pm.MeshEdge,
	__pm.MeshUV,
)