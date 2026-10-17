# -*- coding: utf-8 -*-
"""step 05 · 债券/黄金/能源 三项四项打分（满分 100）→ picks2.json
规模 30（类内 log 归一） + 费率 25（交易费 15 + 持有费 10） + 额度 25 + 评价 20"""
import math, json
import common as C

IN_POOL = 1e10
LATEST = '2026-10-15'


def rate_num(s):
    if not s:
        return None
    import re
    m = re.search(r'([\d.]+)', str(s))
    return float(m.group(1)) if m else None


def quota_score(a):
    if not a:
        return 0.0, '—'
    sgzt = a.get('sgzt') or ''
    if sgzt == '场内交易':
        return 22.0, '场内可交易'
    if sgzt in ('暂停申购', '认购期', '封闭期'):
        return 0.0, sgzt
    mx = a.get('maxsg')
    if mx is None or mx >= IN_POOL:
        return 25.0, '开放申购不限额度'
    if mx >= 1e6:
        return 18.0, '单日上限 %.0f 万' % (mx / 1e4)
    if mx >= 1e4:
        return 12.0, '单日上限 %.1f 万' % (mx / 1e4)
    return 6.0, '单日上限 %.0f 元' % mx


def build_rows(cat, codes, met, api):
    rows = []
    for c in codes:
        m = met.get(c)
        a = api.get(c)
        if not m or not a:
            continue
        scale = a.get('endnav') / 1e8 if a.get('endnav') else (m.get('scale') or 0)
        buy = rate_num(a.get('rate'))
        red = a.get('redeem7')
        mgr = rate_num(a.get('mgrexp'))
        tru = rate_num(a.get('truspexp'))
        sal = rate_num(a.get('salesexp'))
        trade = (buy or 0) + (red or 0)
        hold = (mgr or 0) + (tru or 0) + (sal or 0)
        qs, qtxt = quota_score(a)
        rows.append({
            'code': c, 'name': a.get('name_off') or m['name'],
            'scale': scale, 'buy': buy, 'red': red, 'buy_raw': a.get('rate'),
            'trade': trade, 'hold': hold, 'mgr': mgr, 'tru': tru, 'sal': sal,
            'qscore': qs, 'qtxt': qtxt, 'sgzt': a.get('sgzt'),
            'maxsg': a.get('maxsg'), 'minsg': a.get('minsg'),
            'isexchg': a.get('isexchg'), 'estab': a.get('estabdate'),
            'indexname': a.get('indexname'), 'sharpe1': a.get('sharpe1'),
            'te': m.get('te'), 'm': m, 'aj3': m.get('a3'), 'aj1': m.get('a1'),
        })
    if not rows:
        return rows
    ls = [math.log(max(r['scale'], 1e-6)) for r in rows]
    lo, hi = min(ls), max(ls)
    for r, l in zip(rows, ls):
        r['sscore'] = 30.0 if hi - lo < 1e-9 else 30.0 * (l - lo) / (hi - lo)
        r['tscore'] = 15.0 * max(0.0, min(1.0, (1.2 - r['trade']) / 1.2))
        r['hscore'] = 10.0 * max(0.0, min(1.0, (1.0 - r['hold']) / 0.85))
    # 评价 20 = 官方夏普类内排名 50% + 跟踪误差 30% + 成立年限 20%
    ss = sorted([r for r in rows if r['sharpe1'] is not None], key=lambda r: r['sharpe1'])
    for i, r in enumerate(ss):
        r['sharp_rank'] = (i + 1) / len(ss) if len(ss) > 1 else 1.0
    tes = sorted([r['te'] for r in rows if r['te'] is not None])
    tema = max(tes) if tes else None
    for r in rows:
        p1 = 10.0 * (r.get('sharp_rank') or 0.0)
        if r['te'] is None or not tema:
            p2 = 3.0
        else:
            p2 = 6.0 * max(0.0, 1.0 - r['te'] / tema)
        try:
            yrs = (C.d2ord(LATEST) - C.d2ord(r['estab'])) / 365.0
        except Exception:
            yrs = 0.0
        yrs = max(0.0, yrs)
        p3 = 4.0 * min(1.0, yrs / 5.0)
        r['years'] = yrs
        r['escore'] = p1 + p2 + p3
        r['total'] = r['sscore'] + r['tscore'] + r['hscore'] + r['qscore'] + r['escore']
    rows.sort(key=lambda r: -r['total'])
    for r in rows:
        r.pop('m', None)
    return rows


def main():
    global LATEST
    u = C.jload('api_universe.json')
    met = C.jload('metrics.json')
    api = C.jload('api_data.json')
    LATEST = max((v['a3']['end'] for v in met.values() if v.get('a3')), default=LATEST)
    out = {'cats': {}, 'swap': {'mode': 'signal', 'review': 'weekly',
                                'trigger': 'S1 不可执行 / S2 溢价>3% / S3 榜首选领先≥5 分'}}
    for cat, lst in u['cats'].items():
        codes = [d['code'] for d in lst]
        rows = build_rows(cat, codes, met, api)
        off = [r for r in rows if r['sgzt'] in ('开放申购', '限大额') and r['isexchg'] != '1']
        out['cats'][cat] = {
            'n_all': len(rows),
            'n_off': len(off),
            'rows': rows,
            'top_inst': rows[0]['code'] if rows else None,
            'top_off': off[0]['code'] if off else None,
            'off_rows': off,
        }
        C.log('%s: 候选 %d，场外可申购 %d；场内第一 %s %s；场外第一 %s %s' % (
            cat, len(rows), len(off),
            rows[0]['code'] if rows else '-', (rows[0]['name'][:16] if rows else ''),
            off[0]['code'] if off else '-', (off[0]['name'][:22] if off else '')))
    C.jdump('picks2.json', out)


if __name__ == '__main__':
    main()
