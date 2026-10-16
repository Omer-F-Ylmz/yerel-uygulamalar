# OBB icindeki sifreli Lua betiklerini cozer (her bayt XOR 0xFF).
# Kullanim: python lua_coz.py <assets/Lua klasoru> <cikis klasoru>
import sys, os
src, dst = sys.argv[1], sys.argv[2]
n = 0
for root, _, files in os.walk(src):
    for f in files:
        p = os.path.join(root, f)
        out = os.path.join(dst, os.path.relpath(p, src))
        os.makedirs(os.path.dirname(out), exist_ok=True)
        data = open(p, 'rb').read()
        if f.endswith('.lua'):
            data = bytes(b ^ 0xFF for b in data)
            n += 1
        open(out, 'wb').write(data)
print(n, "lua cozuldu")
