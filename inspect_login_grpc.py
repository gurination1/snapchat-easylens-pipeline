import urllib.request, re

url = "https://static.snapchat.com/accounts/_next/static/chunks/pages/v2/login-763f1ba620f005eb.js"
js = urllib.request.urlopen(url).read().decode("utf-8")

matches = re.findall(r'["\']([a-zA-Z0-9_.]+\.[a-zA-Z0-9_.]+/\w+)["\']', js)
print("gRPC service paths in login chunk:")
for m in set(matches):
    print(" ", m)
