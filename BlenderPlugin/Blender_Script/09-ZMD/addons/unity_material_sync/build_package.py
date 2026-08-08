import argparse
import os
import runpy
import zipfile

try:
    from . import documentation
except ImportError:
    import documentation


ADDON_DIR = os.path.dirname(__file__)
ADDON_NAME = os.path.basename(ADDON_DIR)
PROJECT_ROOT = os.path.abspath(os.path.join(ADDON_DIR, "..", ".."))
DEFAULT_DIST_DIR = os.path.join(PROJECT_ROOT, "dist")
EXCLUDED_DIR_NAMES = {".git", "__pycache__"}
EXCLUDED_FILE_SUFFIXES = (".pyc", ".pyo")


def addon_version():
    init_globals = runpy.run_path(os.path.join(ADDON_DIR, "__init__.py"))
    version = init_globals["bl_info"]["version"]
    return ".".join(str(part) for part in version)


def iter_package_files():
    for dirpath, dirnames, filenames in os.walk(ADDON_DIR):
        dirnames[:] = [
            dirname for dirname in dirnames
            if dirname not in EXCLUDED_DIR_NAMES
        ]

        for filename in filenames:
            if filename.endswith(EXCLUDED_FILE_SUFFIXES):
                continue

            full_path = os.path.join(dirpath, filename)
            relative_path = os.path.relpath(full_path, ADDON_DIR)
            archive_path = os.path.join(ADDON_NAME, relative_path).replace(os.sep, "/")
            yield full_path, archive_path


def build_package(output_dir=None):
    output_dir = output_dir or DEFAULT_DIST_DIR
    os.makedirs(output_dir, exist_ok=True)
    documentation.build_documentation_html()

    zip_path = os.path.join(output_dir, f"{ADDON_NAME}-{addon_version()}.zip")
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as archive:
        for full_path, archive_path in iter_package_files():
            archive.write(full_path, archive_path)

    return zip_path


def main():
    parser = argparse.ArgumentParser(description="Build Unity Material Sync addon zip.")
    parser.add_argument(
        "--output-dir",
        default=DEFAULT_DIST_DIR,
        help="Directory where the addon zip will be written.",
    )
    args = parser.parse_args()

    zip_path = build_package(args.output_dir)
    print(zip_path)


if __name__ == "__main__":
    main()
