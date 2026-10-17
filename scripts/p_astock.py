# -*- coding: utf-8 -*-
"""step 06 · A股/科创腿优选（满分 120）→ astock.json
排除跨境；成立/数据历史 ≥ 2.5 年（MIN_SPAN_YEARS）；
年化收益率 70（近 2 年年化，类内归一，核心键）+ 规模 15（log 归一）+ 费率 10 + 评价 5
+ 科创/科技加成 20（科创系列）/ 10（其他 芯片·半导体·人工智能·科技）/ 0"""
import math, re, json
import common as C

MIN_SPAN_YEARS = 2.5
CROSS = re.compile(r'中韩|日经|纳指|纳斯达克|标普|美国|恒生|港股|海外|全球|亚太|德国|法国|日本|印度|越南|东南亚|'
                   r'中概|MSCI|东证|亚洲|中国香港|韩国|欧洲|新兴市场|国际|跨境|QDII')
KJ = re.compile(r'科创')


def rate_num(s):
    if not s:
        return None
    m = re.search(r'([\d.]+)', str(s))
    return float(m.group(1)) if m else None


def main():
    u = C.jload('api_universe.json')
    met = C.jload('metrics.json')
    api = C.jload('api_data.json')
    rows = []
    for d in u['astock']:
        c = d['code']
        m, a = met.get(c), api.get(c)
        if not m or not a:
            continue
        if CROSS.search(a.get('name_off') or m['name']):
            continue
        ally = (m.get('all') or {}).get('years', 0)
        if ally < MIN_SPAN_YEARS:
            continue
        a2 = m.get('a2') or m['a3']
        ann2 = a2['ann']
        scale = (a.get('endnav') / 1e8) if a.get('endnav') else (m.get('scale') or 0)
        hold = (rate_num(a.get('mgrexp')) or 0) + (rate_num(a.get('truspexp')) or 0) + \
               (rate_num(a.get('salesexp')) or 0)
        nm = a.get('name_off') or m['name']
        rows.append({
            'code': c, 'name': nm, 'scale': scale, 'form': '场内' if a.get('isexchg') == '1' else '场外',
            'ann2': ann2, 'ann_all': (m.get('all') or {}).get('ann', 0), 'years': ally,
            'vol': (m.get('a2') or m['a3'])['vol'], 'mdd': (m.get('a2') or m['a3'])['mdd'],
            'sharpe': a.get('sharpe1') or 0, 'hold': hold, 'sgzt': a.get('sgzt'),
            'maxsg': a.get('maxsg'), 'indexname': a.get('indexname') or '',
            'indexcode': a.get('indexcode') or '', 'estab': a.get('estabdate'),
            'bonus': 20.0 if KJ.search(nm) else (10.0 if re.search(r'芯片|半导体|人工智能|科技', nm) else 0.0),
        })
    if not rows:
        raise SystemExit('A股/科创池为空')
    anns = [r['ann2'] for r in rows]
    lo, hi = min(anns), max(anns)
    ls = [math.log(max(r['scale'], 1e-6)) for r in rows]
    slo, shi = min(ls), max(ls)
    ss = sorted(rows, key=lambda r: r['sharpe'])
    for i, r in enumerate(ss):
        r['sharp_rank'] = (i + 1) / len(ss) if len(ss) > 1 else 1.0
    for r, l in zip(rows, ls):
        r['s_ann'] = 70.0 * (r['ann2'] - lo) / (hi - lo) if hi - lo > 1e-12 else 35.0
        r['s_scale'] = 15.0 * (l - slo) / (shi - slo) if shi - slo > 1e-9 else 7.5
        r['s_fee'] = 10.0 * max(0.0, min(1.0, (1.0 - r['hold']) / 0.85))
        r['s_eval'] = 5.0 * r['sharp_rank']
        r['total'] = r['s_ann'] + r['s_scale'] + r['s_fee'] + r['s_eval'] + r['bonus']
    rows.sort(key=lambda r: -r['total'])
    inst = [r for r in rows if r['form'] == '场内']
    off = [r for r in rows if r['form'] == '场外']
    best = inst[0] if inst else rows[0]
    # 对应场外联接：优先跟踪指数代码相同，其次指数名相同，最后按基金公司+关键词
    offp = None
    for cand in off:
        if best['indexcode'] and cand['indexcode'] == best['indexcode']:
            offp = cand
            break
    if not offp and best['indexname']:
        for cand in off:
            if cand['indexname'] == best['indexname']:
                offp = cand
                break
    if not offp:
        issuer = best['name'][-2:]
        for cand in off:
            if issuer in cand['name'] and (KJ.search(cand['name']) == KJ.search(best['name'])):
                offp = cand
                break
    if not offp and off:
        offp = off[0]
    out = {'n_all': len(rows), 'rows': rows, 'picked_inst': best['code'],
           'picked_off': offp['code'] if offp else None,
           'inst_row': best, 'off_row': offp}
    C.jdump('astock.json', out)
    C.log('A股/科创优选池 %d 只（≥%.1f 年、非跨境）' % (len(rows), MIN_SPAN_YEARS))
    C.log('场内第一 %s %s（总分 %.1f，近2年年化 %.1f%%）' % (best['code'], best['name'], best['total'], best['ann2'] * 100))
    if offp:
        C.log('对应场外 %s %s' % (offp['code'], offp['name']))
    for r in rows[:6]:
        C.log('   %s %-30s %s 近2年年化 %.1f%% 总分 %.1f' % (r['code'], r['name'][:28], r['form'], r['ann2'] * 100, r['total']))


if __name__ == '__main__':
    main()
