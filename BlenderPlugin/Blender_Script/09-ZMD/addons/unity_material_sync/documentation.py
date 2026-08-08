import os
import re
from html import escape
from pathlib import Path

try:
    import bpy
except ImportError:
    bpy = None


DOCUMENTATION_FILENAME = "README.md"
HTML_DOCUMENTATION_FILENAME = "index.html"


def documentation_path():
    return os.path.join(os.path.dirname(__file__), DOCUMENTATION_FILENAME)


def html_documentation_path(output_dir=None):
    output_dir = output_dir or os.path.join(os.path.dirname(__file__), "docs")
    return os.path.join(output_dir, HTML_DOCUMENTATION_FILENAME)


def load_documentation_text():
    with open(documentation_path(), "r", encoding="utf-8") as doc_file:
        return doc_file.read()


def markdown_to_html_document(markdown_text):
    headings = markdown_headings(markdown_text)
    toc = markdown_to_html_toc(headings)
    body = markdown_to_html_body(markdown_text)
    return f"""<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Unity 材质同步文档</title>
  <style>
    :root {{ color-scheme: dark; }}
    body {{ margin: 0; background: #0f172a; color: #dbeafe; font-family: "Microsoft YaHei", "Segoe UI", sans-serif; line-height: 1.65; }}
    .page {{ display: grid; grid-template-columns: 260px minmax(0, 1fr); gap: 32px; max-width: 1280px; margin: 0 auto; padding: 32px 32px 56px; }}
    .toc {{ position: sticky; top: 24px; align-self: start; max-height: calc(100vh - 48px); overflow-y: auto; padding: 18px; border: 1px solid #334155; border-radius: 12px; background: #111827; }}
    .toc-title {{ margin: 0 0 12px; color: #93c5fd; font-size: 15px; font-weight: 700; }}
    .toc a {{ display: block; color: #cbd5e1; text-decoration: none; padding: 4px 0; font-size: 13px; }}
    .toc a:hover {{ color: #60a5fa; }}
    .toc-level-1 {{ font-weight: 700; }}
    .toc-level-2 {{ padding-left: 12px !important; }}
    .toc-level-3, .toc-level-4, .toc-level-5, .toc-level-6 {{ padding-left: 24px !important; }}
    main {{ min-width: 0; padding: 28px 34px; border: 1px solid #334155; border-radius: 14px; background: #111827; }}
    h1, h2, h3 {{ line-height: 1.25; }}
    h1 {{ color: #f8fafc; border-bottom: 1px solid #334155; padding-bottom: 12px; }}
    h2 {{ margin-top: 32px; color: #bfdbfe; border-bottom: 1px solid #1e293b; padding-bottom: 6px; }}
    h3 {{ color: #93c5fd; }}
    code {{ background: #1e293b; color: #fef3c7; padding: 2px 5px; border-radius: 4px; }}
    pre {{ background: #020617; color: #f8fafc; padding: 14px 16px; border-radius: 8px; overflow-x: auto; }}
    pre code {{ background: transparent; padding: 0; }}
    img {{ max-width: 100%; border: 1px solid #334155; border-radius: 8px; }}
    blockquote {{ border-left: 4px solid #334155; margin-left: 0; padding-left: 16px; color: #cbd5e1; }}
    @media (max-width: 860px) {{ .page {{ display: block; padding: 20px; }} .toc {{ position: static; margin-bottom: 20px; }} main {{ padding: 22px; }} }}
  </style>
</head>
<body>
<div class="page">
{toc}
<main>
{body}
</main>
</div>
</body>
</html>
"""


def markdown_headings(markdown_text):
    headings = []
    in_code_block = False
    for raw_line in markdown_text.splitlines():
        stripped = raw_line.strip()
        if stripped.startswith("```"):
            in_code_block = not in_code_block
            continue
        if in_code_block or not stripped.startswith("#"):
            continue
        level = min(len(stripped) - len(stripped.lstrip("#")), 6)
        text = stripped.lstrip("#").strip()
        if text:
            headings.append((level, text, heading_id(text)))
    return headings


def markdown_to_html_toc(headings):
    links = [
        f'<a class="toc-level-{level}" href="#{escape(anchor)}">{escape(text)}</a>'
        for level, text, anchor in headings
    ]
    return '<nav class="toc">\n<p class="toc-title">目录</p>\n' + "\n".join(links) + "\n</nav>"


def markdown_to_html_body(markdown_text):
    html_lines = []
    in_code_block = False
    in_list = False
    code_lines = []

    def close_list():
        nonlocal in_list
        if in_list:
            html_lines.append("</ul>")
            in_list = False

    def flush_code():
        nonlocal code_lines
        html_lines.append("<pre><code>" + escape("\n".join(code_lines)) + "</code></pre>")
        code_lines = []

    for raw_line in markdown_text.splitlines():
        line = raw_line.rstrip()
        stripped = line.strip()

        if stripped.startswith("```"):
            if in_code_block:
                flush_code()
            else:
                close_list()
            in_code_block = not in_code_block
            continue

        if in_code_block:
            code_lines.append(line)
            continue

        if not stripped:
            close_list()
            continue

        if stripped.startswith("![") and "](" in stripped and stripped.endswith(")"):
            close_list()
            alt_text = stripped[2:stripped.index("]")]
            image_path = stripped[stripped.index("](") + 2:-1]
            html_lines.append(f'<p><img src="{escape(_html_image_path(image_path))}" alt="{escape(alt_text)}"></p>')
            continue

        if stripped.startswith("#"):
            close_list()
            level = min(len(stripped) - len(stripped.lstrip("#")), 6)
            heading = stripped.lstrip("#").strip()
            if heading:
                html_lines.append(
                    f'<h{level} id="{escape(heading_id(heading))}">{_inline_markdown_to_html(heading)}</h{level}>'
                )
            continue

        if stripped.startswith(("- ", "* ")):
            if not in_list:
                html_lines.append("<ul>")
                in_list = True
            html_lines.append(f"<li>{_inline_markdown_to_html(stripped[2:].strip())}</li>")
            continue

        close_list()
        html_lines.append(f"<p>{_inline_markdown_to_html(stripped)}</p>")

    if in_code_block:
        flush_code()
    close_list()
    return "\n".join(html_lines)


def _html_image_path(image_path):
    normalized = image_path.replace("\\", "/")
    if normalized.startswith("docs/"):
        return normalized[len("docs/"):]
    return normalized


def heading_id(text):
    normalized = text.strip().lower().replace(" ", "-")
    return re.sub(r"[^\w\-\u4e00-\u9fff]+", "", normalized)


def _inline_markdown_to_html(text):
    escaped = escape(text)
    return re.sub(r"`([^`]+)`", r"<code>\1</code>", escaped)


def build_documentation_html(output_dir=None):
    output_dir = output_dir or os.path.join(os.path.dirname(__file__), "docs")
    os.makedirs(output_dir, exist_ok=True)
    html_path = html_documentation_path(output_dir)
    with open(html_path, "w", encoding="utf-8", newline="\n") as html_file:
        html_file.write(markdown_to_html_document(load_documentation_text()))
    return html_path


def documentation_url():
    return Path(build_documentation_html()).resolve().as_uri()


if bpy is not None:
    class WM_OT_open_unity_material_sync_docs(bpy.types.Operator):
        bl_idname = "wm.open_unity_material_sync_docs"
        bl_label = "打开文档"
        bl_description = "打开 Unity 材质同步插件文档"

        def execute(self, context):
            path = documentation_path()
            if not os.path.exists(path):
                self.report({"ERROR"}, f"文档文件不存在：{path}")
                return {"CANCELLED"}

            bpy.ops.wm.url_open(url=documentation_url())
            return {"FINISHED"}
else:
    WM_OT_open_unity_material_sync_docs = None


classes = tuple(
    cls for cls in (WM_OT_open_unity_material_sync_docs,)
    if cls is not None
)


def register():
    for cls in classes:
        bpy.utils.register_class(cls)


def unregister():
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)
