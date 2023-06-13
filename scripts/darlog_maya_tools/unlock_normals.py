# encoding: utf-8
"""
Based on `lockNormals_toHS` script by: Buliarca Cristian (buliarca@yahoo.com)
http://buliarca.blog124.fc2.com/
https://www.highend3d.com/maya/script/lockednormals-to-hard-soft-edge-for-maya

Completely rewritten using PyMel by Lex Darlog (aka DRL)
https://github.com/Lex-DRL
"""

import math

from pymel import core as pm
from pymel.core import ui
from pymel.core import windows as win
from pymel.core import nodetypes as nt
from pymel.core import datatypes as dt

try:
	import typing as _t
	_t_poly_objects = _t.Iterable[_t.Union[nt.Transform, nt.Mesh]]
except ImportError:
	pass

try:
	unicode = unicode
except Exception:
	unicode = str


class _StaticWindowContainer:
	"""
	The main container for window with execution progress.
	"""
	def __init__(self):
		super(_StaticWindowContainer, self).__init__()
		self.__reset()

	def __reset(self):
		self.__win = None  # type: ui.Window
		self.__text = None  # type: ui.Text
		self.__progress_bar_total = None  # type: ui.ProgressBar
		self.__progress_bar_stage = None  # type: ui.ProgressBar

	def init(self):
		with win.window(title="Converting locked normals to Soft/Hard Edges") as window:  # type: ui.Window
			self.__win = window
			with win.columnLayout(adjustableColumn=True):
				self.__text = win.text(label='  Step 1 of 2  ', align='center')  # type: ui.Text
				self.__progress_bar_total = win.progressBar(maxValue=10, width=400, isInterruptable=True)  # type: ui.ProgressBar
				self.__progress_bar_stage = win.progressBar(maxValue=10, width=400, isInterruptable=True)  # type: ui.ProgressBar
		window.show()

	def close(self):
		if self.__win is None:
			return
		window = self.window
		if win.window(window, q=True, ex=True):
			window.delete()
		self.__reset()

	@property
	def window(self):  # type: () -> ui.Window
		if self.__win is None:
			self.init()
		assert isinstance(self.__win, ui.Window)
		return self.__win

	@property
	def label_widget(self):  # type: () -> ui.Text
		if self.__win is None or self.__text is None:
			self.init()
		assert isinstance(self.__text, ui.Text)
		return self.__text

	@property
	def total_progress_bar(self):  # type: () -> ui.ProgressBar
		if self.__win is None or self.__progress_bar_total is None:
			self.init()
		assert isinstance(self.__progress_bar_total, ui.ProgressBar)
		return self.__progress_bar_total

	@property
	def stage_progress_bar(self):  # type: () -> ui.ProgressBar
		if self.__win is None or self.__progress_bar_stage is None:
			self.init()
		assert isinstance(self.__progress_bar_stage, ui.ProgressBar)
		return self.__progress_bar_stage

	@property
	def label(self):  # type: () -> str
		return self.label_widget.getLabel()

	@label.setter
	def label(self, value):  # type: (str) -> ...
		self.label_widget.setLabel(unicode(value))

	@property
	def total_progress(self):  # type: () -> int
		return self.total_progress_bar.getProgress()

	@total_progress.setter
	def total_progress(self, value):  # type: (int) -> ...
		value = min(self.stage_max, value)
		value = max(0, value)
		self.total_progress_bar.setProgress(value)

	@property
	def total_max(self):  # type: () -> int
		return self.total_progress_bar.getMaxValue()

	@total_max.setter
	def total_max(self, value):  # type: (int) -> ...
		self.total_progress_bar.setMaxValue(max(1, value))

	@property
	def stage_progress(self):  # type: () -> int
		return self.stage_progress_bar.getProgress()

	@stage_progress.setter
	def stage_progress(self, value):  # type: (int) -> ...
		value = min(self.stage_max, value)
		value = max(0, value)
		self.stage_progress_bar.setProgress(value)

	@property
	def stage_max(self):  # type: () -> int
		return self.stage_progress_bar.getMaxValue()

	@stage_max.setter
	def stage_max(self, value):  # type: (int) -> ...
		self.stage_progress_bar.setMaxValue(max(1, value))


Window = _StaticWindowContainer()


def _vf_normal(vf):  # type: (pm.MeshVertexFace) -> dt.Vector
	normal_comps = pm.polyNormalPerVertex(vf, query=True, xyz=True)  # type: _t.List[float]
	return dt.Vector(*normal_comps[:3]).normal()


_almost_same_dir_angle_deg = 1.5
_cos_almost_same_dir = math.cos(math.radians(_almost_same_dir_angle_deg))


def _vertex_hard_edges(vtx, min_angle_cos=_cos_almost_same_dir):  # type: (pm.MeshVertex, float) -> _t.List[pm.MeshEdge]
	hard_edges = []  # type: _t.List[pm.MeshEdge]
	vtx_faces = pm.ls(pm.polyListComponentConversion(vtx, toVertexFace=True), fl=1)  # type: _t.List[pm.MeshVertexFace]
	prev_normal = _vf_normal(vtx_faces[-1])
	for vf in vtx_faces:
		cur_normal = _vf_normal(vf)
		if prev_normal.dot(cur_normal) > min_angle_cos:
			hard_edges.append(
				pm.ls(pm.polyListComponentConversion(vf, toEdge=True), fl=1)[0]
			)
		prev_normal = cur_normal

	return hard_edges


def _run_on_shapes_with_window_initialized(shapes):  # type: (_t.Sequence[nt.Mesh]) -> ...
	n_shapes = len(shapes)
	Window.total_max = n_shapes
	Window.total_progress = 0
	for shape_i, shape in enumerate(shapes):
		Window.label = '  Step 1 of 2 for: {s} ({i}/{n})  '.format(s=shape, i=shape_i, n=n_shapes)
		Window.total_progress = shape_i
		Window.stage_progress = 0

		verts = shape.vtx  # type: pm.MeshVertex
		Window.stage_max = len(verts)

		hard_edges = []  # type: _t.List[pm.MeshEdge]
		for vtx_i, vtx in enumerate(verts):
			Window.stage_progress = vtx_i
			hard_edges.extend(_vertex_hard_edges(vtx))

		Window.label = '  Step 2 of 2 for: {s} ({i}/{n})'.format(s=shape, i=shape_i, n=n_shapes)
		Window.stage_max = len(hard_edges)
		Window.stage_progress = 0
		pm.polyNormalPerVertex(shape, unFreezeNormal=True)
		pm.polySoftEdge(shape, angle=180)  # make all edges soft
		if hard_edges:
			pm.select(hard_edges, r=True)
			pm.polySoftEdge(a=0)
		Window.stage_progress = len(hard_edges)
	Window.total_progress = n_shapes


def to_mesh_shapes_gen(
	sel  # type: _t_poly_objects
):
	"""Force-convert selection to poly-shapes (meshes)."""
	for item in sel:
		if isinstance(item, nt.Mesh):
			yield item
			continue
		if isinstance(item, nt.Transform):
			for shape in item.getShapes():
				if isinstance(shape, nt.Mesh):
					yield shape
		# just skip whatever is left


def run_on_objects(objects):  # type: (_t_poly_objects) -> ...
	try:
		Window.close()
	except Exception:
		pass
	Window.init()

	shapes = list(to_mesh_shapes_gen(objects))
	if not shapes:
		Window.label = "You need to have at least one object selected"
		return

	try:
		_run_on_shapes_with_window_initialized(shapes)
		Window.close()
	except Exception as e:
		Window.label = "Unexpected error (see console)"
		raise e


def run():
	sel = pm.ls(sl=True, fl=True, shapes=True, transforms=True)
	run_on_objects(sel)
	pm.select(sel, r=True)
