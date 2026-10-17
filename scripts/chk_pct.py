import io, re, sys, tokenize
p = sys.argv[1] if len(sys.argv) > 1 else 'o_build_page9.py'
src = open(p, encoding='utf-8').read()
bad = []
for tok in tokenize.generate_tokens(io.StringIO(src).readline):
    if tok.type != tokenize.STRING:
        continue
    t = tok.string
    m = re.match(r'^[a-zA-Z]{0,2}([\'"]{1,3})', t)
    if not m:
        continue
    q = m.group(1)
    body = t[m.end(): t.rfind(q)]
    i = 0
    while i < len(body):
        if body[i] == '%':
            if i + 1 < len(body) and body[i + 1] == '%':
                i += 2
                continue
            mm = re.match(r'[-#0 +]*\d*(?:\.\d+)?[hlL]?[sdfxXeEgrGac%]', body[i + 1:i + 9])
            if not mm:
                bad.append((tok.start[0], body[max(0, i - 30):i + 16]))
                break
            i += 1 + mm.end()
        else:
            i += 1
for ln, frag in bad:
    print(ln, repr(frag))
print('total', len(bad))
