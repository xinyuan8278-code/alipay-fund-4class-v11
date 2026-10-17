# -*- coding: utf-8 -*-
"""step 08 · 换标闸门（信号驱动，无固定周期）→ swap_state.json
S1 不可执行：在持标的暂停申购/封闭
S2 买贵了：在持场内标的溢价 > 3%（该腿暂缓加仓）
S3 榜首位显著更优：同类场外优选榜第一名评分 − 在持标的评分 ≥ 5 分
输出只有 hold / last_change / history（**没有 next**，勿写周期字段）"""
import os, json
import common as C

TH_S3 = 5.0
TH_PREM = 3.0


def seed_hold():
    from n_bt2 import FALLBACK_LEGS
    return {k: {'code': v[0], 'name': v[1]} for k, v in FALLBACK_LEGS.items()}


def main():
    picks = C.jload('picks2.json')
    ast = C.jload('astock.json')
    api = C.jload('api_data.json')
    met = C.jload('metrics.json')
    exch = C.jload('exch.json', default={}) or {}
    p = C.wfile('swap_state.json')
    st = json.load(open(p, encoding='utf-8')) if os.path.exists(p) else {
        'hold': seed_hold(), 'last_change': None, 'history': []}
    hold = st['hold']
    # 场外优选榜
    boards = {}
    for cat, v in picks['cats'].items():
        boards[cat] = v['off_rows']
    aoff = [r for r in ast['rows'] if r['form'] == '场外']
    aoff.sort(key=lambda r: -r['total'])
    boards['科创'] = aoff
    ev = []
    for cat in ('能源', '债券', '黄金', '科创'):
        cur = hold.get(cat)
        if not cur:
            continue
        code = cur['code']
        a = api.get(code) or {}
        bd = boards.get(cat) or []
        me = next((r for r in bd if r['code'] == code), None)
        top = bd[0] if bd else None
        s1 = (a.get('sgzt') in ('暂停申购', '封闭期', '认购期'))
        prem = (exch.get(code) or {}).get('prem')
        s2 = prem is not None and prem > TH_PREM
        gap = (top['total'] - me['total']) if (top and me) else 0.0
        s3 = bool(top and me and top['code'] != code and gap >= TH_S3)
        why = []
        if s1:
            why.append('S1 暂停申购')
        if s2:
            why.append('S2 溢价 %.1f%%>%.0f%%' % (prem, TH_PREM))
        if s3:
            why.append('S3 榜首 %s 领先 %.1f 分' % (top['code'], gap))
        ev.append({'cat': cat, 'code': code, 'name': cur['name'], 's1': s1, 's2': s2, 's3': s3,
                   'prem': prem, 'gap': gap, 'why': why,
                   'top': (top['code'] if top else None)})
        if (s1 or s3) and top and top['code'] != code:
            hold[cat] = {'code': top['code'], 'name': top['name']}
            st['last_change'] = C.jload('bt2.json', default={}).get('dates', ['-'])[-1] if os.path.exists(C.wfile('bt2.json')) else '-'
            st['history'].append({'cat': cat, 'from': code, 'to': top['code'], 'why': why})
            C.log('换标 %s：%s → %s（%s）' % (cat, code, top['code'], '；'.join(why)))
    st['hold'] = hold
    st['review'] = 'weekly'
    st['signals'] = {'S1': '不可执行（暂停申购/封闭）', 'S2': '溢价 >3% 暂缓加仓',
                     'S3': '同类场外优选榜第一名评分领先 ≥5 分'}
    st['evaluated'] = ev
    if 'next' in st:
        st.pop('next')
    json.dump(st, open(p, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    C.log('在持：' + '；'.join('%s %s' % (k, hold[k]['code']) for k in ('能源', '债券', '黄金', '科创') if k in hold))
    for e in ev:
        C.log('  %s %s  S1=%s S2=%s S3=%s gap=%.1f' % (e['cat'], e['code'], e['s1'], e['s2'], e['s3'], e['gap']))


if __name__ == '__main__':
    main()
