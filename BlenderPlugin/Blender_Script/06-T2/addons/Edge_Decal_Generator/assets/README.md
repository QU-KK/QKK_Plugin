# Bundled Edge Decal assets

- `materials/edge_decal_materials.blend` contains the factory decal materials.
- `textures/` contains every external image used by those materials.
- `presets/` contains read-only factory preset JSON files.
- `manifest.json` connects the library, presets, and optional texture-name
  overrides. Factory materials and their images remain external until generated
  decal geometry first uses the related preset.

The manifest may also contain material-specific `uv_pins`. They are inserted
only when the current scene has no pins for that material. Existing pins are
never replaced, so users may customize or rename the factory layout safely.

At runtime the add-on matches them by filename against
`assets/textures`, with explicit `textures` mappings available for exceptions.
