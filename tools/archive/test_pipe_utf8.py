import asyncio, urllib.request, json
from open_webui.models.users import Users
from open_webui.utils.mfa import get_auth
from open_webui.utils.auth import create_token

async def test_pipe():
    user = await Users.get_user_by_id('0626e561-2dae-46fb-b5a6-58b35710c228')
    auth = await get_auth(user.id)
    token = create_token({
        'id': user.id,
        'typ': 'session',
        'auth_method': 'password',
        'session_stamp': auth.session_stamp,
        'mfa_verified': True
    })
    
    payload = {
        'model': 'aitob_assistant.assistant',
        'messages': [
            {'role': 'user', 'content': 'เช็คไลน์'}
        ],
        'stream': False
    }
    
    req = urllib.request.Request(
        'http://localhost:8080/api/chat/completions',
        data=json.dumps(payload).encode('utf-8'),
        headers={'Authorization': f'Bearer {token}', 'Content-Type': 'application/json'}
    )
    with urllib.request.urlopen(req, timeout=10) as resp:
        res = json.load(resp)
        print("RESULT:")
        print(res.get('choices', [{}])[0].get('message', {}).get('content', ''))

asyncio.run(test_pipe())

