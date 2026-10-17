# -*- coding: utf-8 -*-
"""step 04 · 自算指标（近 1 年 / 近 3 年 / 成立以来 年化、波动、回撤、夏普、卡玛、跟踪误差）
→ metrics.json。曲线用「日净值增长率」累乘（含分红再投资），不是单位净值。"""
import json, math
import common as C

Y3 = 3 * 365
Y2 = 2 * 365
Y1 = 365


def build(raw):
    """-> (dates, curve) 复权累计净值曲线，起点归 1"""
    nav = raw.get('nav') or []
    dates, curve = [], []
    cum = 1.0
    prev = None
    for d, _y, er in nav:
        if d == prev:
            continue
        prev = d
        r = 0.0 if er is None else float(er) / 100.0
        cum *= (1.0 + r)
        dates.append(d)
        curve.append(cum)
    return dates, curve


def sub(dates, curve, days):
    if not dates:
        return [], []
    tgt = C.shift(dates[-1], -days)
    i = 0
    for k in range(len(dates) - 1, -1, -1):
        if dates[k] <= tgt:
            i = k
            break
    return dates[i:], curve[i:]


def pack(dates, curve):
    if len(curve) < 30:
        return None
    n = len(curve) - 1
    span_days = C.d2ord(dates[-1]) - C.d2ord(dates[0])
    c = curve
    mdd = C.max_drawdown(c)
    vol = C.ann_vol(c)
    a = C.ann_return(c, span_days)
    return {
        'start': dates[0], 'end': dates[-1], 'n': len(c), 'days': span_days,
        'years': span_days / 365.0,
        'ann': a, 'vol': vol, 'mdd': mdd,
        'sharpe': (a - C.RF) / vol if vol > 1e-12 else 0.0,
        'calmar': a / abs(mdd) if abs(mdd) > 1e-12 else 0.0,
        'cum': c[-1] / c[0] - 1.0,
    }


def main():
    raw = C.jload('funds_raw.json')
    out = {}
    for code, r in raw.items():
        dates, curve = build(r)
        if len(curve) < 30:
            continue
        d3, c3 = sub(dates, curve, Y3)
        d2, c2 = sub(dates, curve, Y2)
        d1, c1 = sub(dates, curve, Y1)
        rec = {'code': code, 'name': r.get('name') or '', 'scale': r.get('scale'),
               'minc': r.get('minc') or []}
        for tag, (dd, cc) in (('a3', (d3, c3)), ('a2', (d2, c2)), ('a1', (d1, c1)), ('all', (dates, curve))):
            p = pack(dd, cc)
            if p:
                rec[tag] = p
        if 'a3' not in rec and 'all' in rec:
            rec['a3'] = dict(rec['all'])
        if 'a2' not in rec and 'all' in rec:
            rec['a2'] = dict(rec['all'])
        if 'a1' not in rec and 'all' in rec:
            rec['a1'] = dict(rec['all'])
        if 'a3' not in rec:
            continue
        out[code] = rec

    # 跟踪误差：同一「跟踪标的 + 币种」分组内，相对规模最大者的日超额收益标准差年化
    api = C.jload('api_data.json')
    rmap = {}
    for code, r in raw.items():
        rmap[code] = {x[0]: (x[2] or 0) / 100.0 for x in (r.get('nav') or [])}
    groups = {}
    for code, rec in out.items():
        a = api.get(code) or {}
        cur = 'USD' if '美元' in rec['name'] else ('HKD' if ('港币' in rec['name'] or '港元' in rec['name']) else 'CNY')
        key = (a.get('indexcode') or a.get('indexname') or 'NA', cur)
        groups.setdefault(key, []).append(code)
    for key, codes in groups.items():
        if len(codes) < 2:
            for c in codes:
                out[c]['te'] = None
            continue
        codes.sort(key=lambda c: (out[c].get('scale') or 0), reverse=True)
        ref = codes[0]
        refser = rmap.get(ref, {})
        refdays = sorted(refser)[-756:]
        for c in codes:
            if c == ref:
                out[c]['te'] = 0.0
                continue
            cd = rmap.get(c, {})
            ex = [cd[d] - refser[d] for d in refdays if d in cd]
            out[c]['te'] = C.std(ex) * math.sqrt(252) if len(ex) > 30 else None
    C.jdump('metrics.json', out)
    C.log('指标 %d 只' % len(out))
    for c in ('018266', '009504', '013275', '017470'):
        r = out.get(c)
        if not r:
            C.log('  %s 缺' % c)
            continue
        a3 = r['a3']
        C.log('  %s %-32s 近3年年化 %.2f%% 波动 %.2f%% 回撤 %.2f%% 夏普 %.2f 规模 %s TE %s' % (
            c, r['name'][:30], a3['ann'] * 100, a3['vol'] * 100, a3['mdd'] * 100, a3['sharpe'],
            r.get('scale'), None if r.get('te') is None else round(r['te'] * 100, 2)))


if __name__ == '__main__':
    main()
