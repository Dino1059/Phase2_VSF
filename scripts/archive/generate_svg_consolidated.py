import json

def generate_svg():
    with open('/tmp/excalidraw_consolidated_v3.json') as f:
        elements = json.load(f)

    svg_parts = [
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 4800 1080" width="4800" height="1080" style="background:#ffffff; font-family:sans-serif;">'
    ]

    for el in elements:
        bg = el.get("backgroundColor", "#ffffff")
        sc = el.get("strokeColor", "#1e1e1e")
        if el["type"] == "rectangle":
            sw = el.get("strokeWidth", 1)
            svg_parts.append(f'<rect x="{el["x"]}" y="{el["y"]}" width="{el["width"]}" height="{el["height"]}" fill="{bg}" stroke="{sc}" stroke-width="{sw}" rx="4" />')
            if el.get("text"):
                lines = el["text"].split("\n")
                startY = el["y"] + 24
                for idx, line in enumerate(lines):
                    line_esc = line.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
                    svg_parts.append(f'<text x="{el["x"] + 14}" y="{startY + idx * 20}" font-size="13" fill="{sc}" font-weight="500">{line_esc}</text>')
        elif el["type"] == "text":
            text_esc = el["text"].replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
            svg_parts.append(f'<text x="{el["x"]}" y="{el["y"]}" font-size="{el.get("fontSize", 14)}" fill="{sc}" font-weight="bold">{text_esc}</text>')

    svg_parts.append('</svg>')
    
    with open("docs/UI_UX_CONSOLIDATED_WORKFLOW_V3.svg", "w", encoding="utf-8") as f:
        f.write("\n".join(svg_parts))
    print("SVG generated successfully at docs/UI_UX_CONSOLIDATED_WORKFLOW_V3.svg")

if __name__ == "__main__":
    generate_svg()
