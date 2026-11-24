"""Protect bake destinations owned by other projects in the open blend file."""

from __future__ import annotations

import os
from pathlib import Path

from . import udim, validation


def _same_project(left, right) -> bool:
    if left is right:
        return True
    return (
        hasattr(left, "as_pointer")
        and hasattr(right, "as_pointer")
        and left.as_pointer() == right.as_pointer()
    )


def validate_project_output_ownership(
    project,
    *,
    output_paths=None,
    projects=None,
    output_dir_for=None,
    resolve_path=None,
    udim_occupancy=None,
    probe_filesystem=True,
    other_udim_occupancy_for=None,
) -> validation.ValidationReport:
    """Compare intended writes with other projects' planned and recorded outputs.

    Blender callers discover projects in every loaded scene. Plain-data callers
    supply projects and path resolvers. No directories, files or ownership caches
    are created. UI callers can disable filesystem probes; bake preflight also
    resolves symlinks. ``output_paths`` checks a prepared job's concrete targets,
    including automatically discovered UDIM tiles and Cycles material outputs.

    ``other_udim_occupancy_for(other) -> occupancy`` makes the comparison tile-aware
    on BOTH sides. Without it the other project's paths are planned with its tile
    occupancy unknown, and an Automatic-mode texture set then resolves to no tiles
    at all -- the untokenized ``Set_Normal.tga`` -- which never string-matches this
    project's concrete ``Set_Normal.1002.tga``, so a real overlap on tile 1002 sailed
    through until that project had baked once and recorded its files. Bake preflight
    passes it (one occupancy scan per other project, with the depsgraph it already
    has); the per-redraw UI check does not, and keeps its cheaper, tile-blind view.
    """
    report = validation.ValidationReport()
    if projects is None:
        # Protocol projects and unit-test fixtures have no owning Blender scene.
        if getattr(project, "id_data", None) is None:
            return report
        import bpy
        from . import export

        projects = (
            candidate
            for scene in bpy.data.scenes
            for candidate in getattr(getattr(scene, "fyr_baker_settings", None), "projects", ())
        )
        output_dir_for = export.resolved_project_output_dir
        resolve_path = bpy.path.abspath

    others = [candidate for candidate in projects if not _same_project(project, candidate)]
    if not others:
        return report
    if output_dir_for is None:
        raise ValueError("An output directory resolver is required")
    resolve_path = resolve_path or (lambda value: value)

    def path_key(value):
        path = Path(resolve_path(str(value)))
        if probe_filesystem:
            try:
                path = path.resolve()
            except (OSError, RuntimeError, ValueError):
                # Another project's unfinished/invalid path must not crash the
                # active project's panel. Its own output-root validation reports it.
                pass
        return os.path.normcase(os.path.abspath(path))

    def planned_paths(candidate, occupancy=None):
        directory = Path(output_dir_for(candidate))
        return (
            directory / name
            for name in validation.project_output_file_names(candidate, occupancy=occupancy)
        )

    if output_paths is None:
        output_paths = planned_paths(project, udim_occupancy)
    intended = {path_key(path): str(path) for path in output_paths if str(path).strip()}
    if not intended:
        return report

    for other in others:
        other_occupancy = None
        if other_udim_occupancy_for is not None:
            try:
                other_occupancy = other_udim_occupancy_for(other)
            except Exception:
                # Another project's broken UVs must not stop this one's bake; the
                # comparison just falls back to the tile-blind view for that project.
                other_occupancy = None
        reserved = {path_key(path) for path in planned_paths(other, other_occupancy)}
        reserved.update(
            path_key(path)
            for item in getattr(other, "latest_outputs", ())
            if (path := str(getattr(item, "file_path", "") or "").strip())
        )
        collisions = sorted(intended.keys() & reserved)
        # Some older tracked rows store a logical UDIM path. Protect its concrete
        # tiles without listing directories on every UI redraw.
        collisions = sorted(set(collisions) | {
            key for key in intended
            if os.path.normcase(udim.logical_udim_path(key)) in reserved
        })
        if not collisions:
            continue
        first_path = intended[collisions[0]]
        extra = f" (and {len(collisions) - 1} more file(s))" if len(collisions) > 1 else ""
        report.error(
            "project.outputs.owned_by_other_project",
            f"Bake output '{first_path}'{extra} is also used by project '{other.name}'. "
            "Baking would overwrite that project's textures. Choose a different output "
            "folder or change the project or texture-set name so their output paths differ.",
            subject=str(getattr(project, "name", "") or ""),
            field="output_root",
        )
    return report


def validate_prepared_output_ownership(project, prepared, *, depsgraph=None) -> validation.ValidationReport:
    paths = [target.path for group in prepared.job.groups for target in group.outputs]
    for spec in getattr(prepared, "material_bake_specs", ()):
        paths.append(spec.output_path)
        if spec.final_output_path:
            paths.append(spec.final_output_path)
    if depsgraph is None:
        return validate_project_output_ownership(project, output_paths=paths)
    from . import export

    return validate_project_output_ownership(
        project,
        output_paths=paths,
        other_udim_occupancy_for=lambda other: export.collect_udim_occupancy(other, depsgraph),
    )
