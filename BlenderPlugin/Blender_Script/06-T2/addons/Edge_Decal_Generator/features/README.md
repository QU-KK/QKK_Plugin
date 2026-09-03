# Feature layout

- `core_state.py` – state, source bevel synchronization helpers, object settings, regeneration, decal object management.
- `geometry.py` – chain traversal, strip construction, width solving, AO/crevice filtering, amount/slice trimming.
- `uv_processing.py` – UV island handling, quadrify, density, placement, unwrap and post-processing.
- `generation.py` – scene properties and all non-interactive generation operators.
- `presets.py` – versioned global JSON presets and sidebar preset controls.
- `uv_pins.py` – UV pin models, overlay, shortcuts, modal tool and application.
- `ui_sections.py` – reusable sidebar drawing functions.
- `interactive.py` – viewport interactive generation, stroke editing, slice/trim and undo.
- `layers.py` – layer operations, section removal and primary sidebar panel.
- `lifecycle.py` – live-sync timers, handlers, class registry, keymaps and register/unregister.

The files are loaded into one shared package namespace. This intentionally avoids circular-import regressions while separating the code by feature. A later refactor can replace shared loading with explicit imports once each feature has a stable public interface.
