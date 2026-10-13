import os
import re
import urllib.request
import threading
import http.server
import socketserver

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

    print("✓ All HTML content and section assertions passed.")

def test_http_server():
    port = 8765
    handler = http.server.SimpleHTTPRequestHandler
    httpd = socketserver.TCPServer(("", port), handler)
    thread = threading.Thread(target=httpd.serve_forever)
    thread.daemon = True
    thread.start()

    try:
        url = f"http://localhost:{port}/index.html"
        req = urllib.request.urlopen(url, timeout=3)
        assert req.status == 200, f"Expected status 200, got {req.status}"
        body = req.read().decode("utf-8")
        assert "<title>AItoB" in body
        print(f"✓ HTTP server test passed on port {port}.")
    finally:
        httpd.shutdown()
        httpd.server_close()

if __name__ == "__main__":
    test_html_structure()
    test_http_server()
    print("ALL CHECKS PASSED.")
