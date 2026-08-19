import asyncio
import os
import httpx
from vision.config import config


async def check_all():
    results = {}

    # 1. Cartesia TTS - test real synthesis byte generation
    cartesia_keys = config.CARTESIA_API_KEYS
    cart_res = []
    async with httpx.AsyncClient(timeout=6.0) as client:
        for k in cartesia_keys:
            try:
                r = await client.post(
                    'https://api.cartesia.ai/tts/bytes',
                    headers={'X-API-Key': k, 'Cartesia-Version': '2024-06-10', 'Content-Type': 'application/json'},
                    json={'model_id': 'sonic-2', 'transcript': 'Test', 'voice': {'mode': 'id', 'id': '1259b7e3-cb8a-43df-9446-30971a46b8b0'}, 'output_format': {'container': 'wav', 'encoding': 'pcm_s16le', 'sample_rate': 24000}}
                )
                if r.status_code == 200:
                    cart_res.append((k[:12] + '...', True, 'Working (Synthesis OK, Credits Active)'))
                elif r.status_code == 402:
                    cart_res.append((k[:12] + '...', False, 'Out of Credits (HTTP 402 Payment Required)'))
                elif r.status_code == 401:
                    cart_res.append((k[:12] + '...', False, 'Invalid Key (HTTP 401 Unauthorized)'))
                elif r.status_code == 429:
                    cart_res.append((k[:12] + '...', False, 'Rate Limited (HTTP 429)'))
                else:
                    cart_res.append((k[:12] + '...', False, f'HTTP {r.status_code}: {r.text[:60]}'))
            except Exception as e:
                cart_res.append((k[:12] + '...', False, f'Error: {e}'))
    results['Cartesia TTS'] = cart_res

    # 2. Groq
    groq_keys = list(config.GROQ_API_KEYS)
    if config.GROQ_API_KEY and config.GROQ_API_KEY not in groq_keys:
        groq_keys.insert(0, config.GROQ_API_KEY)
    groq_res = []
    async with httpx.AsyncClient(timeout=6.0) as client:
        for k in groq_keys:
            try:
                r = await client.get('https://api.groq.com/openai/v1/models', headers={'Authorization': f'Bearer {k}'})
                if r.status_code == 200:
                    groq_res.append((k[:12] + '...', True, 'Working (200 OK)'))
                elif r.status_code == 401:
                    groq_res.append((k[:12] + '...', False, 'Invalid Key (401)'))
                elif r.status_code == 429:
                    groq_res.append((k[:12] + '...', False, 'Rate Limited (429)'))
                else:
                    groq_res.append((k[:12] + '...', False, f'HTTP {r.status_code}'))
            except Exception as e:
                groq_res.append((k[:12] + '...', False, f'Error: {e}'))
    results['Groq (LLM + STT)'] = groq_res

    # 3. NVIDIA NIM
    nim_keys = list(config.NVIDIA_API_KEYS)
    if config.NVIDIA_API_KEY and config.NVIDIA_API_KEY not in nim_keys:
        nim_keys.insert(0, config.NVIDIA_API_KEY)
    nim_res = []
    async with httpx.AsyncClient(timeout=6.0) as client:
        for k in nim_keys:
            try:
                r = await client.get('https://integrate.api.nvidia.com/v1/models', headers={'Authorization': f'Bearer {k}'})
                if r.status_code == 200:
                    nim_res.append((k[:12] + '...', True, 'Working (200 OK)'))
                elif r.status_code == 401:
                    nim_res.append((k[:12] + '...', False, 'Invalid Key (401)'))
                elif r.status_code == 429:
                    nim_res.append((k[:12] + '...', False, 'Rate Limited (429)'))
                else:
                    nim_res.append((k[:12] + '...', False, f'HTTP {r.status_code}'))
            except Exception as e:
                nim_res.append((k[:12] + '...', False, f'Error: {e}'))
    results['NVIDIA NIM'] = nim_res

    # 4. OpenRouter
    or_keys = list(config.OPENROUTER_API_KEYS)
    or_res = []
    async with httpx.AsyncClient(timeout=6.0) as client:
        for k in or_keys:
            try:
                r = await client.get('https://openrouter.ai/api/v1/auth/key', headers={'Authorization': f'Bearer {k}'})
                if r.status_code == 200:
                    data = r.json().get('data', {})
                    limit = data.get('limit')
                    usage = data.get('usage')
                    or_res.append((k[:16] + '...', True, f'Working (Usage: {usage}, Limit: {limit})'))
                elif r.status_code == 401:
                    or_res.append((k[:16] + '...', False, 'Invalid Key (401)'))
                elif r.status_code == 429:
                    or_res.append((k[:16] + '...', False, 'Rate Limited (429)'))
                else:
                    or_res.append((k[:16] + '...', False, f'HTTP {r.status_code}'))
            except Exception as e:
                or_res.append((k[:16] + '...', False, f'Error: {e}'))
    results['OpenRouter'] = or_res

    # 5. Gemini
    gem_key = config.GEMINI_API_KEY
    gem_res = []
    if gem_key:
        async with httpx.AsyncClient(timeout=6.0) as client:
            try:
                r = await client.get(f'https://generativelanguage.googleapis.com/v1beta/models?key={gem_key}')
                if r.status_code == 200:
                    gem_res.append((gem_key[:12] + '...', True, 'Working (200 OK)'))
                else:
                    gem_res.append((gem_key[:12] + '...', False, f'HTTP {r.status_code}'))
            except Exception as e:
                gem_res.append((gem_key[:12] + '...', False, f'Error: {e}'))
    results['Google Gemini'] = gem_res

    # 6. GitHub
    gh_token = getattr(config, 'GITHUB_TOKEN', None) or os.getenv('GITHUB_TOKEN')
    gh_res = []
    if gh_token:
        async with httpx.AsyncClient(timeout=6.0) as client:
            try:
                r = await client.get('https://api.github.com/user', headers={'Authorization': f'Bearer {gh_token}', 'User-Agent': 'VISION-AI'})
                if r.status_code == 200:
                    user_login = r.json().get('login', 'OK')
                    gh_res.append((gh_token[:12] + '...', True, f'Working (User: {user_login})'))
                else:
                    gh_res.append((gh_token[:12] + '...', False, f'HTTP {r.status_code}'))
            except Exception as e:
                gh_res.append((gh_token[:12] + '...', False, f'Error: {e}'))
    results['GitHub'] = gh_res

    print('\n' + '=' * 70)
    print('VISION LIVE API KEYS AUDIT & STATUS REPORT')
    print('=' * 70)
    total_keys = 0
    working_keys = 0
    for prov, items in results.items():
        w = sum(1 for _, ok, _ in items if ok)
        t = len(items)
        total_keys += t
        working_keys += w
        print(f"\n[{prov}]: {w}/{t} Active & Working")
        for mask, ok, msg in items:
            tag = '[OK]  ' if ok else '[FAIL]'
            print(f'  {tag} {mask} -> {msg}')
    print('\n' + '=' * 70)
    print(f'SUMMARY: {working_keys} out of {total_keys} total API keys are currently working.')
    print('=' * 70)


if __name__ == '__main__':
    asyncio.run(check_all())
