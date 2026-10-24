# -*- coding: utf-8 -*-
"""
AItoB WebUI Asset Injector
Applies custom.css and loader.js to Open WebUI container
"""
import os
import sys
import shutil

STATIC_DIR = "/app/build/static/aitob"
INDEX_HTML = "/app/build/index.html"
CSS_SOURCE = "/aitob-webui/custom.css"
JS_SOURCE = "/aitob-webui/loader.js"

def apply_inside_container():
    if not os.path.exists(INDEX_HTML):
        print(f"Error: {INDEX_HTML} not found. Are you inside the Open WebUI container?")
        return False

    os.makedirs(STATIC_DIR, exist_ok=True)
    
    # Try finding source files
    css_src = None
    js_src = None
    candidates = [
        ("/app/build/static/aitob/custom.css", "/app/build/static/aitob/loader.js"),
        ("/aitob-webui/custom.css", "/aitob-webui/loader.js"),
        ("/app/backend/data/custom.css", "/app/backend/data/loader.js"),
        ("/tmp/custom.css", "/tmp/loader.js")
    ]
    for c_css, c_js in candidates:
        if os.path.exists(c_css) and os.path.exists(c_js):
            css_src = c_css
            js_src = c_js
            break
            
    if not css_src:
        print("Warning: Source custom.css and loader.js not found in standard paths.")
        return False

    if css_src != os.path.join(STATIC_DIR, "custom.css"):
        shutil.copyfile(css_src, os.path.join(STATIC_DIR, "custom.css"))
        shutil.copyfile(js_src, os.path.join(STATIC_DIR, "loader.js"))
        print(f"Copied custom.css and loader.js to {STATIC_DIR}")
    else:
        print(f"Assets already in {STATIC_DIR}")

    with open(INDEX_HTML, "r", encoding="utf-8") as f:
        html = f.read()

    tags = (
        '<!-- AItoB Injected Assets -->\n'
        '<link rel="stylesheet" href="/static/aitob/custom.css">\n'
        '<script src="/static/aitob/loader.js" defer></script>\n'
        '<!-- End AItoB Assets -->'
    )

    if "/static/aitob/loader.js" not in html:
        if "</head>" in html:
            html = html.replace("</head>", f"{tags}\n</head>")
            with open(INDEX_HTML, "w", encoding="utf-8") as f:
                f.write(html)
            print("Successfully injected AItoB tags into index.html")
        else:
            print("Warning: </head> not found in index.html")
    else:
        print("AItoB tags already present in index.html")

    return True

if __name__ == "__main__":
    apply_inside_container()

