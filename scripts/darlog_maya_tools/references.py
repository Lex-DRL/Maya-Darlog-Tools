# encoding: utf-8
"""
"""

__author__ = 'Lex Darlog (DRL)'

try:
	# support type hints in Python 3:
	# noinspection PyUnresolvedReferences
	import typing as _t
except ImportError:
	pass

from pymel import core as _pm

from darlog_maya.user_interaction import print

# noinspection PyBroadException
try:
	_unicode = unicode
except Exception:
	_unicode = str


def _import_single_ref(ref, del_ref_namespaces=True):  # type: (_pm.FileReference, bool) -> str
	if not ref.isLoaded():
		print("Reference {} <{}> isn't loaded. Loading it...".format(
			repr(ref.refNode.name()),
			ref.path
		))
		ref.load(loadReferenceDepth='all')
	ns = ref.fullNamespace
	ref.importContents(removeNamespace=del_ref_namespaces)
	return ns


def _confirm_loading_refs_dialog(refs_not_loaded):  # type: (_t.List[_pm.FileReference]) -> bool
	multi = len(refs_not_loaded) > 1
	user_input = _pm.confirmDialog(
		title='Confirm', icon='information',
		message=(
			_unicode(
				"The following {ref_isnt} loaded yet:\n{paths}\n\n"
				"Loading {it} now might take a long time.\n"
				"You better off re-opening the scene.\n\n"
				"Load {it}?"
			).format(
				ref_isnt="references aren't" if multi else "reference isn't",
				paths=_unicode('\n').join(ref.path for ref in refs_not_loaded),
				it="them" if multi else "it",
			)
		),
		button=['Yes', 'No'],
		defaultButton='Yes', cancelButton='No', dismissString='No'
	)
	return user_input == 'Yes'


def import_all_references(
	loaded=True, unloaded=True, confirm_load=True,
	del_ref_namespaces=True, del_scene_namespaces=None,
):
	"""Import all the references into the scene. Optionally, gets rid of namespaces."""
	refs = _pm.listReferences(references=True, loaded=loaded, unloaded=unloaded)  # type: _t.List[_pm.FileReference]
	refs_unloaded = [x for x in refs if not x.isLoaded()]
	if refs_unloaded and confirm_load:
		if not _confirm_loading_refs_dialog(refs_unloaded):
			refs_unloaded_set = set(refs_unloaded)
			refs = [x for x in refs if x not in refs_unloaded_set]

	ref_files_to_load = [ref.path for ref in refs]
	namespaces = set()  # type: _t.Set[str]
	while refs:
		namespaces.add(
			_import_single_ref(refs.pop(), del_ref_namespaces=del_ref_namespaces)
		)
		refs = _pm.listReferences(references=True, loaded=loaded, unloaded=unloaded)

	if not(del_ref_namespaces or del_scene_namespaces):
		return ref_files_to_load

	for ns_str in list(sorted(namespaces)):
		try:
			ns = _pm.Namespace(ns_str)
		except ValueError:
			namespaces.remove(ns_str)
			continue
		namespaces.update(_unicode(x) for x in ns.listNamespaces(recursive=True))

	if del_scene_namespaces is None:
		del_scene_namespaces = del_ref_namespaces
	if del_scene_namespaces:
		root_namespace = _pm.Namespace('')
		namespaces.update(_unicode(x) for x in root_namespace.listNamespaces(recursive=True))

	namespaces = {x.lstrip(':') for x in namespaces}
	namespaces = {_unicode(x) for x in namespaces if x}
	for ns_str in list(sorted(namespaces, reverse=True)):
		try:
			ns = _pm.Namespace(ns_str)  # type: _pm.Namespace
		except ValueError:
			continue
		ns.move(ns.getParent(), force=True)
		ns.remove()

	return ref_files_to_load
