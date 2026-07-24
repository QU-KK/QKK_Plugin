#

## 2.17.0
> 2025-07-29

* raise minimum Blender version to 4.3 and update supplied example assets accordingly

* Export
	- Decal Bake tool
		- resolve long standing 'bake-through' issues
		- add new Bake Demo file and *tutorial* video
	- Atlas Export tool
		- fix .obj and .gltf exporters

* Project, Slice, EPanel, GPanel too tools
	- clear decal vgroups if present, and unnecessary mesh attributes present on the source object, but not needed on the newly created projected / panel decal geo

* redo Decals collection creation now called _Decals
 	- support per-scene _Decals collection
	- update example files accordingly

* sidebar panel
  - remove dedicated Creation, Export and Help panels
	  - move them as toggle-able sub-panels into the main DECALmachine panel
  - move Examples .blend files and 3rd party decal pack links into new Resources sup-panel
  - mark the asset update panel's button red, if there are update-able assets in the assets location or in the current file to indicate that 
  - avoid showing unsaved warning in when example files are loaded

* modernize internals managing addon checks, globals, icons and asset validation and more
* remove old pre-4.2 example files


## 2.14.2
> 2025-06-07

* generalize mouse scrolling
	- support apple magic mouse scrolling, track pad, up and down keys and plus and minus keys
	
* Decal Baking
	- support custom export folder
	
* fix issues when transferring UVs from target to decals
	- Adjust Decal, Re-Apply Decal, Unwrap Panel tools
		- avoid disabling *NormalUVTransfer* mod if decal is flat shaded, as that would undo the UV transfer too

	- Project tool
		- set up *UVTransfer* on projected decal, if un-projected decal has one set up already

	- UVTransfer tool
		- ensure NormalUVTransfer mod is actually enabled
			- it may not be if the decal is flat shaded

* fix potential 2d line drawing issues in MatchMaterial (for Panel Decals) and TrimCut (in Ortho View)

* Blender 4.5
	- fix potential decal projection issues
	- support point drawing in vulkan and metal


## 2.14.1
> 2025-05-25

* Project
	- prevent showing misleading message about supposed legacy decals, when when force-selecting projection target object
	- improve default projection behaviour when decal is bigger than the target object	
	
* Remove Decal Orphans
	- fix exception when encountering instanced/linked decal meshes


## 2.14.0
> 2025-05-09
	
* avoid detecting linked decal materials as legacy decal materials, as updating them while linked would fail

* asset drop cleanup handler
	- trigger when collection assets are dropped as well
	
* Adjust Decal tool
	- fix exception when *PIL* is not installed
	
* Project tool  
	- fix exception in `ALT` projecting on mesh with complex mod stack resulting in loose or degenerate geo
	
* Decal Creation
	- fix exception when loading decal source image with upper case file extension
	
* (Batch) Insert Decal tool
	- fix exception trying to bring in a legacy decal from a (still legacy) library, that was manipulated to seem as if it was updated
	
* Trimsheet Creation 
	- fix exception when duplicating trimsheet object
	
* PIL 
	- add workaround for installation failure due to debug output string decoding issues
	
* modernize sidebar panels via `layout.panel` elements


## 2.13.0
> 2024-11-18

* raise minimum version to 4.2
	- supplied decals are now ready to be used in 4.2 without and asset update
	- in 4.3 require asset update due to new 'Diffuse Roughness' parameter in Principled BSDF shader

* Pie menu
	- add Select tool
		- previously it was only keymapped to double LMB

* Select Decal(s) tool
	- with decaal parent(s) selected support filtering by decal type in redo panel
		- so Simple, Subset, Panel, Info or any combination

* Adjust tool
	- support adjusting Info Decal alpha using 'A' key
		- limit to a minimum of 0.1
		- support toggling flat/smooth shading using `F` key
			- when flat shaded disable normal transfer mod too
			- expose and support toggling normal transfer mod only when decal is smooth shaded
	- only expose adjustment modes and mode hints, that are actually available based on the selected decals
	- indicate if glossy rays, parallax, normal transfer of invert is used by the selection of decals
		- support "Mixed" selections
		- when toggling mixed selections, sync the toggled prop
		- always ensure a displace and normal transfer mod is present

* Project tool
	- support Shrinkwrapping (modifier level shrinkrawp) of Panel Decals (on MESH objects)
		- useful to better fit underlying curved geo, while requiring less height to distance the decal
	- support projecting on non-mesh objects too: CURVE, SURFACE and META
	- ensure normal transfer mod is disabled when projecting on flat shaded objects
	- improve user feedback, should projecting fail

* Slice, EPanel, GPanel tools
	- support Panel Decal creation on non-mesh objects too: CURVE, SURFACE and META
	- avoid always smooth shading panel decal, make it dependent on decal target/parent object
	- ensure normal transfer mod is disabled when creating panel decal on flat shaded objects, or on non-mesh objects

*  Unwrap tool (Panel Unwrap
	- support ALT mode Shrinkwrap (mesh level shrinkrwap) on non-mesh objects too: CURVE, SURFACE and META
	- avoid always smooth shading panel decal, make it dependent on decal target/parent object
	- fix issue in ALT mode (shrinkwrap) when panel decal origin is not aligned with parent object

* ReApply tool
	- enforce flat/smooth shading based on decal target/parent
	- ensure normal transfer mod is disabled on flat shaded objects and enabled on smooth shaded objects

* GPanel tool
	- support Blender 4.3's new Grease Panel

* Material Overrides
	- add dedicated Coat preset
	- expose Coat Weight prop for all presets
	- support overriding materials in assembly assets / instance collections
	- fix potential exception when removing override

* avoid re-sorting decals in collections, when they aren't actually on the viewlayer
	- this is especially important for decals in asset collections, which by default are excluded from the viewlayer

* indicate in 3D view's sidebar and addon preferences when an update is available
	- previously this was only shown in the pie menu

* Atlasing
	- support tga format

* GetSupport tool
	- detect workspace filtering, when enabled

* previous silent 2.12.0.hotfix releases:
	- Atlas Creation
		- fix typo resulting in *ao_curve_height* maps not being created (already fixed in previous 2.12.0.hotifix releasse
	- TrimSheet Creation
		- fix exception when adding emission map
	- fix transmission related issues when matching trim decals or storing subset component on library decal


## 2.12.0
> 2024-08-17

* support Blender 4.2
	- require asset update due to new Thin Film material properties
	- require blend file update accordingly too
		- when updating legacy blend files, take material overrides and under-coating into account now too
	- remove ability to switch between (legacy) alpha blend and hashed alpha methods
		- normal mapped decals will always use dithered, and info decals use blended surface render method now
	- update transmissive material matching for Eevee Next related API changes

* Decal Creation and Decal Baking
	- directly expose CPU/GPU selection in the side bar

* update example .blend files for Blender 4.2, countering Blender's automatic node tree changes resulting in black decals
	- Example_Decal_Basics.blends
	- Example_Decal_Asset.blend
	- Example_Decal_Bake.blend
	- Example_Trim_Sheet_Asset.blend

* general code cleanup


## 2.11.2
> 2024-04-08

* ImportTrimsheet
	- if exception in Blender 4.0 and 4.1 due to change in node input names
* fix new manually added atlas not appearing among registered atlases until Blender re-start
* fix new manually added trim sheet not appearing among registered libs until Blender re-start
* update integrated updater to expose the Re-Scan button even no update is found yet


## 2.11.1
> 2024-03-27

* fix issue when upgrading decals in Blender 4.1 where decal materials in decal .blend files end up with indexed name
	- this is due to an undocumented and unannounced change in Blender behavior, where Blender no longer allows for *name-swapping*
	- see https://projects.blender.org/blender/blender/issues/119139
* support appending wrongly saved decal materials when using Slice, GPanel, Epanel or Adjust to bring in panel decal materials
* UpdateDecalLibrary / BatchUpdater
	- in Blender 4.1 avoid adding Auto Smooth mod on Decals
* Insert / BatchInsert
	- remove Auto Smooth mod, when Blender has added it (as it does on Decals previously updated in Blender 4.0)
* fix issue, in custom updater, when Blender preferences are auto-saved


## 2.11
> 2024-03-19

* support Blender 4.1
    - fix 4.1 issues due to API changes in regards to Auto Smooth and custom normals

* addon preferences
    - place Get Support button at top of addon prefs
    - add custom updater
        - NOTE: since it's only introduced now in 2.11, it will only be of use for upcoming releases, so can't be used to install this very 2.11 update yet
        - allows for very easy addon update installation from .zip file, and from inside of Blender, instead of manually from the file browser
        - finds matching .zip file(s) in home and Downloads folder
        - allows selecting one of them them or manually selecting a file in any other location
        - extracts the file to a temporary location, and installs update when quitting Blender
        - like a manual update installation from the filebrowser, this maintains previous addon settings and custom keys
        - see installation instructions for details
        - supports - and defaults to - keeping the current assets to prevent accidental loss

* handlers
    - rework when and how handler logic is executed
    - add asset drop cleanup handler (previously in MACHIN3tools) to automatically unlink decal backup objects after dropping an asset using decals with backups from the asset browser

* fix exception when auto matching materials to 'None' or 'Default' pseudo materials, while material override is in use


## 2.10
> 2024-01-22

* deeply refactor decal and trimsheet asset registration and validation
  - comprehensively analyze the entire assets location and sort and categorize everything
* UpdateDecalLibrary tool
  - introduce universal update op, that deals with all versions 1.8 - 2.5
  - keep custom subset component inputs, that may have been stored in a library decal .blend file
  - support fixing and/or updating ambiguous libaries (with multiple version files)
  - support updating libraries, where each decal's version differs from the indicated library version (due to user-manipulated) version file)
  - deal with various potential update failure cases and support skipping individual decals if something goes wrong
    - decal.blend, decal.png or any of the supplied textures are corrupt/0kb files
    - any expected texture is missing
    - decal object can't be found in the decal.blend
    - decal material can't be found in the decal.blend
    - decal object and decal material version mismatch
    - decal version not set on decal object or decal material
    - decal version and library version mismatch, due to user-manipulated version indicator file
  - move skipped decals into dedicated Decals_Skipped or Trims_Skipped folders in the assets root directory
    - and generate a log.txt file detailing why a specific decal was skipped
  - automatically remove Clutter (files or folders in locations were they shouldn't be)
  - support updating empty libraries
* UpdateBlendFile tool
  - in addition to the fading labels drawn in the viewport pointing out the presense of legacy decals in the blend file, now list them all in the update panel of the sidebar
  - also indicate whether these decals are actually registered, and so update-able to a new version
  - remove `ALT` path-based fallback method
  - support re-setup of Subset components in trim sheet materials, when the default color mix node approach was used
* BatchUpdate tool
  - automatically remove clutter (files or folders in locations were they shouldn't be)
  - at the end pop a single message covering all the successful and failed
  - write update log file into DECALmachine/logs folder
* validate decal or trimsheet is current, and not a legacy decal or trimsheet when using
  - Adjust Decal tool
  - Re-Apply tool
  - Project tool
  - Insert and Batch Insert decal tools
  - OverrideMaterials tool
  - Material Match tool
  - materials deduplication
  - TrimUnwrap tool
  - InitTrimSheetMaterial tool
  - Setup Subset (Trimssheet) tool
* TrimUnwrap tool
  - fix panel unwrapping somethings affecting UVs outside the selected faces due to issue introduced in Blender 4
    - this issue has already been fixed in Blender by now, but is not released
* Trimcut tool
  -  fix TrimCut tool issue in Blender 4, due to legacy face map code
* fix importing of 2.9 decal or trimsheet libs in Blender 4

* addon preferences
  - show info box about skipped (at update attempt) decals if present
  - add DeClutter tool, if any clutter is detected
  - Quarantine tool
    - simplify into a single op call, for removal of all qurantine-able
    - no longer consider ambiguous libraries as quarantine-able, they can now be updated/fixed by the UpdateDecalLibrary tool
    - recognize obsolete libraries as such, and quarantine them accordingly
      - these are pre-1.8 libraeries, that can't be user-updated anymore, they were seen as just corrupt previously
    - generate log file for each quanrantined library
    - at the end pop a single message covering each quarantined librarry
    - write update log file into DECALmachine/logs folder
  - declutter when changing the assets path
  - explain and show how to get support directly in the addon prefs, when there are any issues in the assets location detected
    - hint: using the GetSupport tool, and via email

* GetSupport tool
  - generate extensive output about state of assets location
    - including details about any legacy, next-gen, obsolete, corrupt, invalid, skipped and quarantined assets
    - as well as about any clutter, which are files and folders in locations where they shouldn't be
    - include shortened versions of _Skipped and _Quarantined libary log files

## -------------------------------------------------------------------------------------------------------------------
