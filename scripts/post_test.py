import requests, re

URL='http://127.0.0.1:5000/packages/'

s = requests.Session()
r = s.get(URL, timeout=10)
print('GET', r.status_code)
if r.status_code != 200:
    print('GET failed')
    exit(1)

m = re.search(r'name="csrfmiddlewaretoken" value="([^"]+)"', r.text)
if not m:
    print('no csrf token found')
    exit(1)

token = m.group(1)
print('CSRF token found (prefix):', token[:8])

data = {'slug': 'modal-test-req', 'description': 'desc', 'csrfmiddlewaretoken': token}
headers = {'Referer': URL}

r2 = s.post(URL, data=data, headers=headers, allow_redirects=True, timeout=10)
print('POST', r2.status_code, 'final URL', r2.url)
print('Response length', len(r2.text))
print('Slug present in response?', 'modal-test-req' in r2.text)

r3 = s.get(URL)
print('Listing GET', r3.status_code, 'contains slug?', 'modal-test-req' in r3.text)
