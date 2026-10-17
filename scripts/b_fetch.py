# -*- coding: utf-8 -*-
"""step 02 · 并行抓逐日净值（天天基金 pingzhongdata）→ funds_raw.json + cache/<code>.json"""
import re, os, json, time
import common as C

PZ = 'https://fund.eastmoney.com/pingzhongdata/%s.js'
BENCH = ['510300', '000198']
KEYS = ['fS_name', 'fS_code', 'Data_netWorthTrend', 'Data_millionCopiesIncome',
        'Data_sevenDaysYearIncome', 'Data_fluctuationScale', 'syl_1n', 'syl_3y', 'syl_6y']


def _grab(txt, key):
    m = re.search(r'var\s+%s\s*=\s*' % re.escape(key), txt)
    if not m:
        return None
    i = m.end()
    if i >= len(txt):
        return None
    ch = txt[i]
    if ch == '"':
        j = txt.index('"', i + 1)
        return txt[i + 1:j]
    depth, instr, k = 0, False, i
    while k < len(txt):
        c = txt[k]
        if instr:
            if c == '\\':
                k += 2
                continue
            if c == '"':
                instr = False
        elif c == '"':
            instr = True
        elif c in '[{':
            depth += 1
        elif c in ']}':
            depth -= 1
            if depth == 0:
                k += 1
                break
        k += 1
    frag = txt[i:k]
    try:
        return json.loads(frag)
    except Exception:
        return None


def _ts2date(x):
    """天天基金时间戳：净值序列用毫秒，货币基金万份收益历史上有秒/毫秒两种，自动判别"""
    x = float(x)
    if x > 1e11:
        return C.ms2date(x)
    return C.sec2date(x)


def parse_pz(txt, code):
    o = {'code': code}
    o['name'] = _grab(txt, 'fS_name') or ''
    nav = _grab(txt, 'Data_netWorthTrend') or []
    o['nav'] = [[_ts2date(p['x']), p.get('y'), p.get('equityReturn')] for p in nav
                if isinstance(p, dict) and p.get('y') is not None]
    inc = _grab(txt, 'Data_millionCopiesIncome') or []
    o['minc'] = [[_ts2date(p[0]), p[1]] for p in inc if isinstance(p, list) and len(p) >= 2]
    sc = _grab(txt, 'Data_fluctuationScale')
    scale = None
    if isinstance(sc, dict):
        try:
            ser = sc.get('series') or []
            if ser:
                scale = float(ser[-1]['y'])
        except Exception:
            scale = None
    o['scale'] = scale
    o['syl_1n'] = _grab(txt, 'syl_1n')
    return o


def fetch_one(code):
    p = C.cpath(code)
    if os.path.exists(p):
        try:
            d = json.load(open(p, encoding='utf-8'))
            if d.get('nav') or d.get('minc'):
                return d
        except Exception:
            pass
    txt = C.get(PZ % code, retries=3)
    d = parse_pz(txt, code)
    if not d['nav'] and not d['minc']:
        raise RuntimeError('empty series')
    with open(p, 'w', encoding='utf-8') as f:
        json.dump(d, f, ensure_ascii=False)
    return d


def load_codes():
    u = C.jload('api_universe.json')
    codes = []
    for v in u['cats'].values():
        codes += [d['code'] for d in v]
    codes += [d['code'] for d in u['astock']]
    codes = sorted(set(codes) | set(BENCH))
    return codes


def main(force=False):
    codes = load_codes()
    if force:
        for c in codes:
            try:
                os.remove(C.cpath(c))
            except OSError:
                pass
    C.log('待抓 %d 只' % len(codes))
    t0 = time.time()
    res = C.pmap(fetch_one, codes, workers=10, label='净值')
    ok, bad = {}, []
    for r in res:
        if isinstance(r, tuple) and r and r[0] == 'ERR':
            bad.append((r[1], r[2]))
        elif isinstance(r, dict):
            ok[r['code']] = r
    C.log('成功 %d / 失败 %d（%.1fs）' % (len(ok), len(bad), time.time() - t0))
    for c, e in bad[:10]:
        C.log('  ✗ %s %s' % (c, e[:110]))
    C.jdump('funds_raw.json', ok)
    return ok


if __name__ == '__main__':
    main(force='--force' in os.sys.argv)
