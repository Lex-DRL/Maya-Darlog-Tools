# encoding: utf-8
"""
This is a self-contained module which auto-detects and sets Maya project when scene is opened.
It also provides HUD (heads-up display within viewport) to see the active project.

INSTALLATION:
0. Close all opened Maya instances.

1. Put the script into your `<Maya Prefs>/scripts` folder (by default: My Documents/maya/scripts"")

2. Search for `userSetup.py` file within Maya Prefs folder.
	- There should be either no such file or only one
	- If multiple such files are found, you should know what you're doing and also know which one you need to modify.

3. If no such file is found, create a new one in `<Maya Prefs>/scripts` folder. Otherwise, open an existing one.

4. Add the following lines to the `userSetup.py` file (without quotes):
```
import darlog_maya_autoproject
darlog_maya_autoproject.enable()
darlog_maya_autoproject.HUD.add()
```

5. If you don't need the bundled HUD (displayed at the bottom of viewport), you can comment out the last line.
	- To comment it out, put a hash sign (#) at the very start of the line.

6. If you've done everything right, the HUD should appear at the bottom of viewport,
and the following lines should appear in Script Editor log:

[Darlog AutoProject] Project-setter enabled.
[Darlog AutoProject] HUD added.
"""

__author__ = 'Lex Darlog (DRL)'

# Supporting both Py2/Py3 doesn't worth it. So this script assumes Maya 2022 and above,
# relying on Py3:
import typing as _t

import pymel.core as pm


def _dataclass_fallback(cls=None, **kwargs):
	"""Dummy decorator (it does nothing) to be used as fallback when built-in dataclasses are unavailable."""
	def wrap(_cls):
		return _cls
	if cls is None:
		return wrap
	return cls


try:
	from dataclasses import dataclass
except ImportError:
	# We shouldn't get here since first maya version with built-in Py3 support (2022)
	# already has Py3.7, and it has dataclasses. But just to be safe:
	dataclass = _dataclass_fallback


_tPath = _t.Optional[pm.Path]
_tOptString = _t.Optional[_t.AnyStr]
_tOptInt = _t.Optional[int]


WORKSPACE_FILE = 'workspace.mel'
FAILSAFE_DIR_DEPTH = 999  # to prevent crashing due to infinite loop, cap max parent-dir-seek attempts to this number
LOG_PREFIX = '[Darlog AutoProject] '


def get_current_project_path() -> pm.Path:
	path: pm.Path = pm.workspace.path
	if path:
		path = path.abspath()
	return path


def get_abs_scene_path() -> _tPath:
	scene_path: pm.Path = pm.sceneName()
	if not scene_path:
		# We're probably in a new scene
		return None
	scene_path: pm.Path = scene_path.abspath()  # Yes, we need to do it AFTER the first check.
	if not(scene_path and scene_path.isfile() and not scene_path.isdir()):
		# Again, we got an empty path (though... it's unclear how we got it HERE, after satisfying first check)
		return None
	return scene_path


def _rel_or_abs_path(parent_path: pm.Path, abs_path: pm.Path):
	rel_path: pm.Path = abs_path.relpath(parent_path)
	return abs_path if str(rel_path).replace('\\', '/').startswith('../') else rel_path


def get_rel_or_abs_scene_path() -> _t.Union[pm.Path, _t.AnyStr]:
	"""
	Get the currently opened scene path - but there are 3 cases:

		- scene path is under project: `Path` object, relative path
		- it's outside the project dir or project itself (somehow) isn't set: `Path` object, absolute path
		- new scene: string, '...'
	"""
	scene_path = get_abs_scene_path()
	if scene_path is None:
		return '...'

	project_path = get_current_project_path()
	if not project_path:
		return scene_path
	return _rel_or_abs_path(project_path, scene_path)


def _del_script_job(job_id: _tOptInt):
	"""Returns whether the job was removed."""
	if job_id is None or not pm.scriptJob(exists=job_id):
		return False
	pm.scriptJob(kill=job_id)
	return True


@dataclass  # Just to have nicer repr
class _HUD:
	"""
	A class dealing with in-viewport HUD.

	There supposed to be only one instance of this class, but this protection isn't enforced as singleton:
	it's expected the user interacts with the class only through the pre-initialized `HUD` instance within the module.
	"""

	PROJECT_HUD_NAME: str = 'DarlogProjectPathHUD'
	SCENE_HUD_NAME: str = 'DarlogProjectSceneHUD'

	@staticmethod
	def _del_hud_if_exists(hud_name: str):
		"""Returns whether HUD was removed."""
		if not pm.headsUpDisplay(hud_name, q=True, exists=True):
			return False
		pm.headsUpDisplay(hud_name, remove=True)
		return True

	@staticmethod
	def _refresh_hud_if_exists(hud_name: str):
		if not pm.headsUpDisplay(hud_name, q=True, exists=True):
			return
		pm.headsUpDisplay(hud_name, refresh=True)

	@staticmethod
	def _add_hud(
		hud_name: str,
		func: _t.Callable,
		label: _tOptString,
		event: str = 'SceneOpened',
		section: int = 5,  # bottom-left corner
	):
		next_free_block = pm.headsUpDisplay(nextFreeBlock=section)
		kwargs = dict(
			section=section,
			block=next_free_block,
			command=func,
			event=event
		)
		if label:
			kwargs['label'] = label
		return pm.headsUpDisplay(hud_name, **kwargs)

	__job_id_refresh_scene_on_project_change: _tOptInt = None

	def _del_scene_refresh_job(self):
		_del_script_job(self.__job_id_refresh_scene_on_project_change)
		self.__job_id_refresh_scene_on_project_change = None

	def _add_scene_refresh_job(self):
		self._del_scene_refresh_job()
		self.__job_id_refresh_scene_on_project_change = pm.scriptJob(
			compressUndo=True, event=('workspaceChanged', self.refresh_scene)
		)

	def _add_project_hud(self):
		return self._add_hud(
			self.PROJECT_HUD_NAME, get_current_project_path,
			label='Project:', event='workspaceChanged'
		)

	def _add_scene_hud(self):
		return self._add_hud(
			self.SCENE_HUD_NAME, get_rel_or_abs_scene_path,
			label='Scene:', event='SceneOpened'
		)

	def _delete_immediate(self):
		self._del_scene_refresh_job()
		deleted_scene = self._del_hud_if_exists(self.SCENE_HUD_NAME)
		deleted_proj = self._del_hud_if_exists(self.PROJECT_HUD_NAME)
		if deleted_scene or deleted_proj:
			print(f"\n{LOG_PREFIX}HUD removed.")

	def _add_immediate(self):
		self._delete_immediate()
		self._add_project_hud()
		self._add_scene_hud()
		self._add_scene_refresh_job()
		print(f"\n{LOG_PREFIX}HUD added.")

	def delete(self):
		"""Remove Project/Scene HUD from viewport, if exists (if not, no error is thrown)."""
		pm.evalDeferred(self._delete_immediate)

	def add(self):
		"""Add Project/Scene HUD to viewport, if it's not there yet (if it already is, no error is thrown)."""
		pm.evalDeferred(self._add_immediate)

	def refresh_project(self):
		self._refresh_hud_if_exists(self.PROJECT_HUD_NAME)

	def refresh_scene(self):
		self._refresh_hud_if_exists(self.SCENE_HUD_NAME)

	def refresh(self):
		self.refresh_project()
		self.refresh_scene()


@dataclass
class _AutoSetProjectJob:
	"""Supposed to be used only internally, and as a static class."""

	@staticmethod
	def _detect_project_dir_from_active_scene() -> _t.Tuple[_tPath, _tOptString]:
		"""
		For the opened scene, iteratively walk up to find it's project dir (the one with workspace file).
		If scene or project not found (or max walk depth is exceeded), return `None`.

		The second returned argument is an optional warning message (if encountered).
		"""
		scene_path = get_abs_scene_path()
		if scene_path is None:
			# We're probably in a new scene
			return None, None

		assert (scene_path and isinstance(scene_path, pm.Path)), f"\n{LOG_PREFIX}Invalid scene path:\n\t{scene_path!r}"

		# Initially, assume the "previous checked dir path" to be the scene's one:
		last_dir = scene_path

		for i in range(FAILSAFE_DIR_DEPTH):
			checked_dir: pm.Path = last_dir.parent

			if (
				# A comprehensive set of conditions, but all they check is if the parent dir is invalid:
				not checked_dir
				or checked_dir.samepath(last_dir)
				or not (
					checked_dir.isdir() or checked_dir.islink()
				)
				or checked_dir.isfile()
			):
				# We've somehow encountered an invalid parent dir.
				# Don't throw an error, but at least let's log it:
				return None, (
					f"Invalid parent dir:"
					f"\n\t{checked_dir!r}"
					f"\nScene path is treated as absolute."
				)

			workspace_file: pm.Path = checked_dir / WORKSPACE_FILE
			if (
				workspace_file
				and workspace_file.isfile()
				and not workspace_file.isdir()  # just to be safe if path is a soft-link
			):
				return checked_dir, None

			last_dir = checked_dir

		return None, None

	@classmethod
	def _job_func(cls):
		"""The actual job function to be called every time a scene is opened."""
		project, warning = cls._detect_project_dir_from_active_scene()
		if warning:
			print(f"\n{LOG_PREFIX}{warning}")
		if project is None or project.samepath(pm.workspace.path):
			# We're leaving the project as-is
			return

		leading_line = '' if warning else '\n'
		pm.workspace.open(project)
		print(f"{leading_line}{LOG_PREFIX}Project path set to:\n\t{project}\n")

	__job_id: _tOptInt = None

	@classmethod
	def disable(cls):
		if _del_script_job(cls.__job_id):
			print(f"\n{LOG_PREFIX}Project-setter disabled.")
		cls.__job_id = None

	@classmethod
	def enable(cls):
		cls.disable()
		cls.__job_id = pm.scriptJob(
			compressUndo=True, event=('SceneOpened', cls._job_func)
		)
		print(f"\n{LOG_PREFIX}Project-setter enabled.")


HUD = _HUD()


def enable():
	"""
	Enable project auto-setter.

	This function alone doesn't affect bundled HUD. To enable it, do:
	`darlog_maya_autoproject.HUD.add()`
	"""
	pm.evalDeferred(_AutoSetProjectJob.enable)


def disable():
	"""
	Disable project auto-setter.

	This function alone doesn't affect bundled HUD. To disable it, do:
	`darlog_maya_autoproject.HUD.delete()`
	"""
	pm.evalDeferred(_AutoSetProjectJob.disable)
