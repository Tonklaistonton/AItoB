import os
import re
import urllib.request
import threading
import http.server
import socketserver
import functools

def test_html_structure():
    path = os.path.join(os.path.dirname(__file__), "index.html")
    assert os.path.exists(path), "index.html must exist"

    with open(path, "r", encoding="utf-8") as f:
        html = f.read()

    # 1. Pain Point
    assert 'id="pain-point"' in html, "Missing Pain Point section"
    assert "ข้อมูลลับส่งออก Cloud ไม่ได้" in html
    assert "เสียเวลากับงานเอกสารซ้ำซาก" in html

    # 2. AItoB Solution
    assert 'id="solution"' in html, "Missing Solution section"
    assert "Private Local AI" in html
    assert "Tailored Local AI Appliance" in html

    # 3. How It Works (5 steps)
    assert 'id="how-it-works"' in html, "Missing How It Works section"
    for step in ["Hardware", "Local AI", "Permission", "RAG", "Workflow"]:
        assert step in html, f"Missing pipeline step: {step}"

    # 4. Prototype / Result / ROI
    assert 'id="prototype"' in html, "Missing Prototype section"
    assert 'id="roi-calculator"' in html, "Missing ROI Calculator"
    assert 'id="res-payback"' in html, "Missing dynamic payback calculation"
    assert 'data-scenario="finance"' in html, "Missing scenario data attributes"
    assert "calculateROI" in html

    # 5. Business + Vision
    assert 'id="business"' in html, "Missing Business section"
    assert "Audit & Architecture Blueprint" in html
    assert "Turnkey Private AI Appliance" in html
    assert "Roadmap" in html or "วิสัยทัศน์" in html

    # Pitch Deck Mode (Modal + 6 slides)
    assert 'id="deck-modal"' in html, "Missing Pitch Deck Modal"
    for slide_num in range(1, 7):
        assert f'data-slide="{slide_num}"' in html, f"Missing slide {slide_num}"

    # 6. Video Demo, Department Pages & Integrated Subsystems
    assert 'id="demo-video"' in html, "Missing Demo Video section"
    assert 'id="departments"' in html, "Missing Departments section"
    for dept_file in ["finance.html", "hr.html", "legal.html"]:
        dept_path = os.path.join(os.path.dirname(__file__), dept_file)
        assert os.path.exists(dept_path), f"{dept_file} must exist"
        assert f'href="{dept_file}"' in html, f"Missing link to {dept_file}"

    assert "ai-account" in html, "Missing ai-account in index.html"
    assert "ai-chat" in html, "Missing ai-chat in index.html"
    assert os.path.isdir(os.path.join(os.path.dirname(__file__), "ai-account"))
    assert os.path.isdir(os.path.join(os.path.dirname(__file__), "ai-chat"))

    print("✓ All HTML content and section assertions passed.")

def test_http_server():
    server_dir = os.path.dirname(os.path.abspath(__file__))
    handler = functools.partial(http.server.SimpleHTTPRequestHandler, directory=server_dir)

    class ReusableTCPServer(socketserver.TCPServer):
        allow_reuse_address = True

    httpd = ReusableTCPServer(("", 0), handler)
    port = httpd.server_address[1]
    thread = threading.Thread(target=httpd.serve_forever)
    thread.daemon = True
    thread.start()

    try:
        for page in ["index.html", "finance.html", "hr.html", "legal.html", "account.html", "inbox.html", "demo-video/index.html"]:
            url = f"http://localhost:{port}/{page}"
            req = urllib.request.urlopen(url, timeout=3)
            assert req.status == 200, f"Expected status 200 for {page}, got {req.status}"
            body = req.read().decode("utf-8")
            assert "AItoB" in body or "html" in body
            print(f"✓ HTTP 200 passed for {page}.")
    finally:
        httpd.shutdown()
        httpd.server_close()

if __name__ == "__main__":
    test_html_structure()
    test_http_server()
    print("ALL CHECKS PASSED.")
