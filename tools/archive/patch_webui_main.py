with open('/app/backend/open_webui/main.py', 'r', encoding='utf-8') as f:
    content = f.read()

target = 'applications.get_swagger_ui_html = swagger_ui_html\n'
new_code = '''
# --- AItoB LINE Smart Inbox Embedded Route (Port 3000) ---
from fastapi.responses import HTMLResponse
import httpx

@app.get('/inbox', response_class=HTMLResponse)
@app.get('/line', response_class=HTMLResponse)
async def line_inbox_page():
    async with httpx.AsyncClient(timeout=10, trust_env=False) as client:
        try:
            r = await client.get('http://line-bot:8003/')
            html_content = r.text.replace('fetch("/api/', 'fetch("/line-proxy/api/')
            return HTMLResponse(content=html_content)
        except Exception as e:
            return HTMLResponse(content=f'<h1>ไม่สามารถเชื่อมต่อ LINE Bot Service ได้</h1><p>{e}</p>', status_code=502)

@app.api_route('/line-proxy/api/{path:path}', methods=['GET', 'POST', 'PUT', 'DELETE'])
async def line_proxy(path: str, request: Request):
    async with httpx.AsyncClient(timeout=30, trust_env=False) as client:
        req_content = await request.body()
        resp = await client.request(
            method=request.method,
            url=f'http://line-bot:8003/api/{path}',
            content=req_content,
            headers={k: v for k, v in request.headers.items() if k.lower() not in ('host', 'content-length')}
        )
        return Response(content=resp.content, status_code=resp.status_code, media_type=resp.headers.get('content-type'))
# --- End AItoB LINE Route ---
'''

if 'line_inbox_page' not in content:
    if target in content:
        content = content.replace(target, target + new_code)
        with open('/app/backend/open_webui/main.py', 'w', encoding='utf-8') as f:
            f.write(content)
        print('Route patched successfully')
    else:
        print('Target not found')
else:
    print('Already patched')

