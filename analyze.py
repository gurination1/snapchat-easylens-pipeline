import re

with open("/root/snapchat-lens/js/chunk-GQT534DT.js", "r") as fp:
    c = fp.read()

matches = re.findall(r"\$\{H\}/[a-zA-Z0-9_\-\/\?=&%]+", c)
print("H endpoints:")
for m in sorted(set(matches)):
    print(" ", m)

matches2 = re.findall(r"\$\{lg\}/[a-zA-Z0-9_\-\/\?=&%]+", c)
print("lg endpoints:")
for m in sorted(set(matches2)):
    print(" ", m)

matches3 = re.findall(r"\$\{Jt\}/[a-zA-Z0-9_\-\/\?=&%]+", c)
print("Jt endpoints:")
for m in sorted(set(matches3)):
    print(" ", m)

matches4 = re.findall(r"\$\{Ka\}/[a-zA-Z0-9_\-\/\?=&%]+", c)
print("Ka endpoints:")
for m in sorted(set(matches4)):
    print(" ", m)
