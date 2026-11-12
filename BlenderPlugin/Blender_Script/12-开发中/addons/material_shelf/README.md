# Material Shelf 1.9.2

Install material_shelf-1.9.2.zip with Preferences > Get Extensions > Install from Disk, then restart Blender.
Open from the 3D View material button or N sidebar > Material Shelf.

Browse native material previews. Preview resolution appears above thumbnail size.
Shift-click adds to selection; Ctrl-click subtracts. Drag in blank grid space for box selection.
Long-press a material to reorder or move selected materials into a folder.
Click a folder to select it, double-click to enter, and right-click for folder actions.
Drag materials onto All to return them to the root directory.
Duplicate and copy/paste retain the source folder. Folder duplication creates independent materials and node groups.
Selecting an object outlines its materials and adds dashed outlines to folders containing those materials.
Right-click blank preview space for New Material, Delete Unused, Merge Duplicates and Sort A閳ユ彣.
Double-click a material to open a shader window. On Windows, the initial size is one-third of Blender's
window width and height. Position and size are remembered until the project changes.
The Outliner Object Materials popover has been removed.
Right-click > Save as material asset opens the folder chooser. Choose Separate projects or Combined project in its export options.
Image textures are packed into the exported blend file. External IES/OSL sources are embedded as text.
Movie and sequence textures are rejected with an explanation. Export refuses to overwrite existing files.
Press A over the preview grid to select all materials in the current folder and filter.

Minimum compatibility target is Blender 4.5. Runtime tests use Blender 5.2.3 LTS on Windows.


## Material protection and folder tabs (1.9.2)
The top-right status button reads Blender material users and use_fake_user.
Click it to toggle fake-user protection. This manual override lasts until the automatic protection option changes.
Automatic protection defaults on: unused materials receive fake-user protection.
Assigned materials return to normal user-count display.
Turning automatic protection off/on applies to all local unused materials.
Save the blend file to persist materials and settings.
Folder tabs remain open when returning to All. Click a tab to switch or its X to close it.
Drag selected materials onto a folder tab to move them out of the previous folder.
Tabs wrap in narrow panels. This release contains no online presence module.


1.9.2 adds two-level folders, folder Shift/Ctrl and box selection, compact tabs, a selection trash button below Thumbnail Size, and official Blender protection icon assets. New Folder is also available in the blank-area menu.


## Changes in 1.9.2
Box selection can start in the extended blank preview area, including blank toolbar/tab space.
Resolution switches retain valid native preview pixels and fall back between image/icon buffers.
Long-press and drag onto a viewport object to assign the material. Shift-drop targets a face.
In mesh Edit Mode, drops target the hovered face. For modified objects, use Edit Mode for face drops.
Outliner drops delegate to Blender's native material drop operator; end-to-end pointer testing remains pending.
Preview fallback/resolution caching, whole-object/face assignment and viewport ray targeting were tested on 5.2.3.


1.9.2 adds localized drag status hints (Shift for face assignment, selected face regions, folder moves, Escape/right-click cancellation). Undo checkpoints now preserve the edit-mode baseline and use descriptive operation labels. Reassigning an unchanged material and moving materials to their existing folder do not create additional undo steps.


## Changes in 1.9.2
- Invalid Outliner material drops show a localized explanation.
- Preview tiles indicate waiting/generating/failure; material context menus provide single-preview retry.
- The persistent Loading overlay was removed in 1.9.2. Background preview generation continues without a blocking overlay.
- Object-user counts and data-user counts are labeled separately.
- Asset export checks missing image/UDIM tiles and external IES/OSL sources, validates temporary files,
  and reports the number of files, materials and images saved.
- Regression checks cover four-step undo/redo through folder duplication, moving, face assignment and deletion.
- Tests cover embedded UDIM tiles and embedded IES/OSL source text in nested node groups.
  Cross-renderer shader execution and real-project performance are not claimed.
