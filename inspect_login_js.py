import urllib.request, re

req = urllib.request.Request(
    'https://accounts.snapchat.com/v2/login',
    headers={'User-Agent': 'Mozilla/5.0'}
)
html = urllib.request.urlopen(req).read().decode('utf-8')
chunks = re.findall(r'src="([^"]+login[^"]+\.js)"', html)
print('Login chunks:', chunks)
for chunk in chunks:
    chunk_url = 'https://static.snapchat.com' + chunk if chunk.startswith('/') else chunk
    js = urllib.request.urlopen(chunk_url).read().decode('utf-8')
    print(f'Fetched {chunk_url} len: {len(js)}')
    # search for api endpoints
    endpoints = set(re.findall(r'["\'](/api/[^"\']+|/accounts/[^"\']+|/v[0-9]/[^"\']+)["\']', js))
    for ep in sorted(endpoints):
        print('  EP:', ep)
    # search for identifier submit
    methods = [m.start() for m in re.finditer(r'accountIdentifier', js)]
    for idx in methods:
        print('--- Identifier snippet ---')
        print(js[max(0, idx-100):min(len(js), idx+300)])
