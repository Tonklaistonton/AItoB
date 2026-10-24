# -*- coding: utf-8 -*-
import asyncio, urllib.request, json
from open_webui.models.users import Users
from open_webui.utils.mfa import get_auth
from open_webui.utils.auth import create_token

async def test_reply():
    user = await Users.get_user_by_id('0626e561-2dae-46fb-b5a6-58b35710c228')
    auth = await get_auth(user.id)
    token = create_token({
        'id': user.id,
        'typ': 'session',
        'auth_method': 'password',
        'session_stamp': auth.session_stamp,
        'mfa_verified': True
    })
    
    chat_id = 'line-Uc17ea54a77a4bacc38249dd89d01d6ec-1792743152'
    
    # 1. Admin sends 'ส่งเลย'
    payload = {
        'model': 'aitob_assistant.assistant',
        'chat_id': chat_id,
        'messages': [
            {'role': 'user', 'content': 'สนใจเริ่มติดตั้งระบบ AI สัปดาห์หน้าเลยครับ'},
            {'role': 'assistant', 'content': 'สวัสดีครับคุณ Tonton ยินดีมากๆ ครับ สำหรับการติดตั้งสัปดาห์หน้า แอดมินขออนุญาตส่ง Checklist สรุปให้ตรวจเช็คได้เลยครับ\n\n---\n*(💡 พิมพ์คำตอบใหม่แล้วกด Send...)*'},
            {'role': 'user', 'content': 'ส่งเลย'}
        ],
        'stream': False
    }
    
    req = urllib.request.Request(
        'http://localhost:8080/api/chat/completions',
        data=json.dumps(payload, ensure_ascii=False).encode('utf-8'),
        headers={'Authorization': f'Bearer {token}', 'Content-Type': 'application/json'}
    )
    with urllib.request.urlopen(req, timeout=15) as resp:
        res = json.load(resp)
        print("Reply to 'ส่งเลย':")
        print(res.get('choices', [{}])[0].get('message', {}).get('content', ''))

    # 2. Admin sends 'ปิดเคส'
    payload_close = {
        'model': 'aitob_assistant.assistant',
        'chat_id': chat_id,
        'messages': [
            {'role': 'user', 'content': 'ปิดเคส'}
        ],
        'stream': False
    }
    req2 = urllib.request.Request(
        'http://localhost:8080/api/chat/completions',
        data=json.dumps(payload_close, ensure_ascii=False).encode('utf-8'),
        headers={'Authorization': f'Bearer {token}', 'Content-Type': 'application/json'}
    )
    with urllib.request.urlopen(req2, timeout=15) as resp:
        res2 = json.load(resp)
        print("\nReply to 'ปิดเคส':")
        print(res2.get('choices', [{}])[0].get('message', {}).get('content', ''))

asyncio.run(test_reply())

