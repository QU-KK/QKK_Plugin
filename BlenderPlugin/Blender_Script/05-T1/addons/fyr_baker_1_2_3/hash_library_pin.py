"""Where ``fyr_geometry_hash.dll`` may be loaded from, and which exact file.

This file is the release pin. In a source checkout and in the direct-channel
archive it holds the development values below. ``scripts/package_extension.py``
REWRITES it in the staged copy of the Superhive archive (``publish-baker.ps1
-Superhive``), so the marketplace build ships:

* ``DEVELOPMENT_SEARCH = False``: the DLL is loaded only from the backend
  install folder the signed installer recorded in the registry
  (``HKCU``/``HKLM\\SOFTWARE\\FyrPlugins\\FyrBaker``, value ``InstallPath``).
  No path inside the add-on folder and no repository build folder is looked at.
* ``EXPECTED_SHA256``: the SHA-256 of the exact signed DLL inside the backend
  installer built in the same run. A DLL whose bytes differ is never loaded.

Kept free of ``bpy`` and of the rest of the add-on so the packaging script and
the tests can read it.
"""

#: True: also search the add-on's own ``bin/windows-x64`` folder and the
#: repository's ``backend/build/Release`` folder (source checkout and the
#: direct-channel archive, which bundles the DLL inside the add-on). The
#: Superhive build sets this to False.
DEVELOPMENT_SEARCH = True

#: Lowercase hex SHA-256 the DLL must match before it is loaded. Empty means
#: "not pinned", which is only honoured while DEVELOPMENT_SEARCH is True.
EXPECTED_SHA256 = ""
