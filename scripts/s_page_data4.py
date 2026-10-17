# -*- coding: utf-8 -*-
"""step 11 · 页面数据组装（按 bt2 腿集重建全部展示口径）→ page_data4.json
用法：QDII_SRC=_ref python s_page_data4.py   # 读 bt2_ref.json / wt_hist_ref.json"""
import os, re, json, math
import common as C

TAG = C.SRC
MAXROWS = 14
CROSSNAME = re.compile(r'\s*\(LOF\)|\s*ETF|\s*联接|\s*发起[式联]*')


def f(x, d=2, sign=False, pct=False):
    if x is None:
        return '—'
    v = x * 100 if pct else x
    return ('%+.*f' if sign else '%.*f') % (d, v) + ('%' if pct else '')


def pct_cell(x):
    if x is None:
        return "<td class='num'>—</td>"
    col = '#7fd1a8' if x >= 0 else '#e08a8a'
    return "<td class='num' style='color:%s'>%+.2f%%</td>" % (col, x * 100)


def crow(v):
    """按中国习惯：正红负绿（涨红跌绿）"""
    return '#e05a5a' if v >= 0 else '#3fae6a'


def num_cell(x, d=2, suffix='', color=None):
    if x is None:
        return "<td class='num'>—</td>"
    st = " style='color:%s'" % color if color else ''
    return ("<td class='num'%s>%%.%df%s</td>" % (st, d, suffix)) % x


def wan(x):
    if x is None:
        return '—'
    if x >= 1e8:
        return '不限额'
    if x >= 1e4:
        return '%.1f 万' % (x / 1e4)
    return '%.0f 元' % x


def quota_text(a):
    if not a:
        return '—'
    sgzt = a.get('sgzt') or '—'
    mx = a.get('maxsg')
    mn = a.get('minsg')
    if sgzt == '场内交易':
        return "场内交易（需券商账户）"
    if sgzt in ('暂停申购', '认购期', '封闭期'):
        return sgzt
    lim = '不限额度' if (mx is None or mx >= 1e10) else '单日上限 %s' % wan(mx)
    return '%s ｜ 起购 %s' % (lim, ('%.0f 元' % mn) if mn else '—')


def short(n, k=26):
    n = CROSSNAME.sub('', n or '')
    return n if len(n) <= k else n[:k] + '…'


def rate_pct(s):
    if not s:
        return None
    m = re.search(r'([\d.]+)', str(s))
    return float(m.group(1)) if m else None


# ------------------------------------------------------------ 尾部业务
def build_hist(bt):
    rows = []
    s = bt['schemes']
    wl = bt['window_labels']
    def line(label, wr, cls=''):
        return {'label': label, 'cls': cls, 'wr': wr}
    rows.append(line('主推（场外可执行 · v5 约束网格）', bt['main_wr'], 'hi'))
    rows.append(line('v4 旧口径权重（禁止 0 权重 · 对照）', s['v4 旧口径（最大化卡玛）']['wr']))
    rows.append(line('货基 · 天弘余额宝货币', bt['cash_wr'], 'bench'))
    rows.append(line('沪深300（510300）', bt['bench_wr'], 'bench'))
    return rows


def build_wtbl(bt, wt):
    """主推权重：上期 → 本周（＝下周）"""
    weeks = wt['weeks']
    n = len(weeks)
    cur = weeks[-1]
    last = weeks[-2] if n >= 2 else None
    prev_ok = None
    for i in range(n - 2, -1, -1):
        if weeks[i]['feas']:
            prev_ok = weeks[i]
            break
    legs = bt['order']
    curw = cur['w'] or {k: 0 for k in legs}
    lw = (last['w'] or {k: 0 for k in legs}) if last else {k: 0 for k in legs}
    pw = (prev_ok['w'] or {k: 0 for k in legs}) if prev_ok else {k: 0 for k in legs}
    rows = []
    for k in legs:
        chg = curw.get(k, 0) - pw.get(k, 0)
        if abs(chg) < 1e-9:
            act = '维持'
        elif chg > 0:
            act = '加仓 +%dpp' % chg
        else:
            act = '减仓 %dpp' % (-chg)
        rows.append({'cat': k, 'code': bt['legs'][k]['code'], 'name': bt['legs'][k]['name'],
                     'prev': pw.get(k, 0), 'last': lw.get(k, 0), 'cur': curw.get(k, 0),
                     'chg': chg, 'act': act})
    # 货基行
    cashw = 100 - sum(curw.get(k, 0) for k in legs)
    cash_last = 100 - sum(lw.get(k, 0) for k in legs)
    rows.append({'cat': '货基', 'code': bt['cash'], 'name': '天弘余额宝货币',
                 'prev': 100 - sum(pw.get(k, 0) for k in legs), 'last': cash_last,
                 'cur': cashw, 'chg': cashw - (100 - sum(pw.get(k, 0) for k in legs)),
                 'act': '不持有（备用的「无解周」去处）' if cashw == 0 else '持有 %d%%' % cashw,
                 'bench': True})
    return {'rows': rows, 'cur_date': cur['date'], 'last_date': last['date'] if last else '—',
            'prev_date': prev_ok['date'] if prev_ok else '—',
            'last_feas': bool(last and last['feas']), 'prev_feas': bool(prev_ok),
            'cash_week': bool(cur['w'] is None)}


def build_ops(bt, wt, wtbl, assets):
    """「下周怎么操作」：一条叙事（中文字 200±30），不堆数据"""
    legs = bt['order']
    cur = wtbl['rows']
    amap = {a['cat']: a for a in assets}
    w = {k: bt['main_w'][k] for k in legs}
    wr = {k: amap[k]['wr'] for k in legs}

    def lab(x):
        return '正' if x >= 0 else '负'

    def cp(v):
        return ('%+.2f' % (v * 100))

    off = anchor = back = watch = None
    if bt.get('fallback'):
        txt = ('本期规则给不出解：四条腿在「上周／近一月／近三月／今年以来／近2年」五个窗口里，'
               '没有任何一组权重能同时跑赢货币基金，所以按规则本周不持任何风险腿、整仓退到货基。'
               '主要卡点在近一月——煤炭%s%%、黄金%s%%、科创%s%%三条腿同时为负，'
               '唯一为正的债券近一月只有%s%%，单腿权重上限百分之四十，凑不出跑赢货基的短窗口。'
               '这属于规则设计内的正常结果（过去五十二周里有%d周如此），不是数据出错。'
               '下周只要煤炭或科创短窗口转正、或债券近一月超额回到零点三个百分点以上，'
               '网格里就会重新出现可行解，届时按新权重建仓。' % (
                   cp(wr['能源'][1]), cp(wr['黄金'][1]), cp(wr['科创'][1]), cp(wr['债券'][1]),
                   wt['nocash']))
    else:
        # 进攻腿 = 权重最高且多窗口为正；压舱石 = 唯一五窗口全正的低波腿；回吐腿/观望腿 = 短窗口最差的两条
        order = sorted(legs, key=lambda k: -w[k])
        n5 = {k: sum(1 for j in range(5) if wr[k][j] > 0) for k in legs}
        off = order[0]
        anchor = next((k for k in legs if k != off and n5[k] == 5), None) or \
                 min(legs, key=lambda k: amap[k]['stats']['vol'])
        # 回吐腿 = 近三月仍为正、只是短窗口转弱；观望腿 = 近三月深度回撤（高位回调）
        worst = sorted([k for k in legs if k not in (off, anchor)], key=lambda k: -wr[k][2])
        back = worst[0] if worst else None
        rest = [k for k in legs if k not in (off, anchor, back)]
        watch = rest[0] if rest else None
        pw = {r['cat']: r['prev'] for r in wtbl['rows']}
        parts = []
        parts.append('本周期的安排是跟着已经发生的行情走（趋势跟随式再平衡），不是预测点位：')
        parts.append('%s是四条腿里动能最强的品种（近三月 %s%%、今年以来 %s%%），%s，给到 %d%% 当进攻腿；'
                     % (off, cp(wr[off][2]), cp(wr[off][3]),
                        '近一月也在涨、短窗口同步转好' if wr[off][1] > 0 else '近三月与今年以来的动能最完整',
                        int(w[off] * 100)))
        parts.append('%s五个窗口全部为正（近一月 %s%%）、年化波动只有 %.1f%%，是组合里唯一不靠单边行情吃饭的腿，继续 %d%% 作压舱石；'
                     % (anchor, cp(wr[anchor][1]), amap[anchor]['stats']['vol'] * 100, int(w[anchor] * 100)))
        if back:
            parts.append('%s近一月 %s%%、今年以来 %s%%，短窗口转弱、属高位回吐，从 %d%% 压到 %d%%；'
                         % (back, cp(wr[back][1]), cp(wr[back][3]), int(pw.get(back, 0)), int(w[back] * 100)))
        if watch:
            if w[watch] > 0:
                parts.append('%s近三月 %s%%、上周 %s%%，处在回调与拥挤度消化阶段，只留 %d%% 观察仓；'
                             % (watch, cp(wr[watch][2]), cp(wr[watch][0]), int(w[watch] * 100)))
            else:
                parts.append('%s近三月 %s%%、上周 %s%%，动能尚未修复，本期整腿剔除（权重 0%%）；'
                             % (watch, cp(wr[watch][2]), cp(wr[watch][0])))
        parts.append('一句话：进攻交给%s、防守交给%s，%s等动能修复再回补。'
                     % (off, anchor, '与'.join([x for x in (back, watch) if x])))
        txt = ''.join(parts)
    zh = len(re.findall(r'[\u4e00-\u9fff]', txt))
    # 方向
    dirs = []
    for r in wtbl['rows']:
        if r['cat'] == '货基':
            continue
        if abs(r['chg']) < 1e-9:
            dirs.append('%s 维持 %d%%' % (r['cat'], r['cur']))
        else:
            dirs.append('%s %s%dpp（→ %d%%）' % (r['cat'], '加仓 +' if r['chg'] > 0 else '减仓 ', abs(r['chg']), r['cur']))
    direction = '；'.join(dirs) + '。具体金额与份额见上面的「下周下单清单」。'
    falsify = ('只要%s近一月转负、%s止跌转正、或%s短窗口回正，规则就会在当周自动把权重换向；'
               '若出现「五个窗口全部跑赢货基」无解，则整仓退到货基。所以这是一套可证伪的安排'
               '——下一周的行情会直接说明它对不对。'
               % (off, watch or anchor, back or anchor))
    if bt.get('fallback'):
        falsify = ('只要任一条腿的短窗口转正、使五窗口约束重新可满足，规则会在当周自动给出权重并提示建仓；'
                   '在此之前按规则应当整仓持货基。这是一套可证伪的安排——下一周的行情会直接说明它对不对。')
    return {'narrative': txt, 'zh': zh, 'direction': direction, 'falsify': falsify,
            'open': off if not bt.get('fallback') else None,
            'anchor': anchor if not bt.get('fallback') else None}


def build_orders(bt, wtbl, api, met, cap=10000.0):
    legs = bt['order']
    curw = {r['cat']: r['cur'] for r in wtbl['rows']}
    prevw = {r['cat']: r['prev'] for r in wtbl['rows']}
    asof = bt['dates'][-1]
    RAW = C.jload('funds_raw.json')

    def nav_at(code):
        raw = RAW.get(code) or {}
        pts = [x for x in (raw.get('nav') or []) if x[0] <= asof]
        if pts:
            return pts[-1][1], pts[-1][0]
        a = api.get(code) or {}
        return a.get('dwjz'), a.get('fsrq') or asof

    A, tot_m, tot_f, tot_u = [], 0.0, 0.0, 0.0
    for k in legs:
        code = bt['legs'][k]['code']
        a = api.get(code) or {}
        nav, navdate = nav_at(code)
        wr_ = curw.get(k, 0) / 100.0
        money = cap * wr_
        buy_rate = (rate_pct(a.get('rate')) or 0) / 100.0
        fee = money - money / (1 + buy_rate)
        net = money - fee
        units = net / nav if nav else 0.0
        tot_m += money
        tot_f += fee
        tot_u += units
        A.append({'cat': k, 'code': code, 'name': bt['legs'][k]['name'], 'nav': nav, 'navdate': navdate,
                  'w': curw.get(k, 0), 'money': money, 'fee': fee, 'units': units})
    cashw = curw.get('货基', 100 - sum(curw.get(k, 0) for k in legs))
    cash_money = cap * cashw / 100.0
    A.append({'cat': '货基', 'code': bt['cash'], 'name': '天弘余额宝货币', 'nav': 1.0,
              'navdate': '份额净值恒 1 元', 'w': cashw, 'money': cash_money, 'fee': None,
              'units': cash_money, 'bench': True})
    tot_m += cash_money
    tot_u += cash_money
    B = []
    for k in legs:
        code = bt['legs'][k]['code']
        a = api.get(code) or {}
        nav, _nd = nav_at(code)
        d = (curw.get(k, 0) - prevw.get(k, 0)) / 100.0
        money = cap * d
        act = '不动' if abs(d) < 1e-9 else ('买入' if d > 0 else '卖出')
        units = abs(money) / nav if nav else 0.0
        B.append({'cat': k, 'code': code, 'name': bt['legs'][k]['name'], 'prev': prevw.get(k, 0),
                  'cur': curw.get(k, 0), 'act': act, 'money': money, 'units': units, 'nav': nav})
    tot_buy = sum(x['money'] for x in B if x['money'] > 0)
    tot_sell = sum(-x['money'] for x in B if x['money'] < 0)
    return {'A': A, 'B': B, 'total_money': tot_m, 'total_fee': tot_f,
            'buy_value': tot_m - tot_f, 'total_units': tot_u, 'cap': cap,
            'total_buy': tot_buy, 'total_sell': tot_sell, 'net_cash': tot_sell - tot_buy,
            'fallback': bool(bt.get('fallback')), 'cashw': cashw}


def build_cats(u, picks, api, met, exch, bt):
    """四大类筛选明细：场外可申购按规模降序前 14 + 场内折叠表"""
    out = {}
    asof = bt['dates'][-1]
    RAW = C.jload('funds_raw.json')

    def nav_at(code):
        pts = [x for x in ((RAW.get(code) or {}).get('nav') or []) if x[0] <= asof]
        if pts:
            return pts[-1][0]
        return (api.get(code) or {}).get('fsrq') or asof
    for cat, v in picks['cats'].items():
        off = [r for r in v['rows'] if (r['sgzt'] in ('开放申购', '限大额') and r['isexchg'] != '1')]
        if not off:
            off = v['off_rows'] or v['rows']
        rows = sorted(off, key=lambda r: -(r['scale'] or 0))[:MAXROWS]
        tbl = []
        for r in rows:
            a = api.get(r['code']) or {}
            m = met.get(r['code']) or {}
            a3 = m.get('a3') or {}
            s3 = a.get('syl_3n')
            ann3off = ((1 + s3 / 100.0) ** (1 / 3.0) - 1) * 100 if s3 is not None else None
            tbl.append({
                'code': r['code'], 'name': short(r['name'], 26), 'scale': r['scale'],
                'quota': quota_text(a), 'buy': r['buy_raw'] or '—', 'red': r['red'],
                'syl1': a.get('syl_1n'), 'syl3a': ann3off, 'sylall': a.get('syl_ln'),
                'ann3': a3.get('ann'), 'mdd': a3.get('mdd'), 'vol': a3.get('vol'),
                'sharpe': a3.get('sharpe'), 'te': r['te'],
                'holdfee': (r['mgr'] or 0) + (r['tru'] or 0) + (r['sal'] or 0),
                'navdate': nav_at(r['code']), 'isexchg': a.get('isexchg') == '1',
                'sgzt': a.get('sgzt'), 'hold': r['code'] == bt['legs'].get(cat, {}).get('code'),
            })
        inst = []
        for r in sorted([x for x in v['rows'] if (api.get(x['code']) or {}).get('isexchg') == '1'],
                        key=lambda r: -(r['scale'] or 0))[:6]:
            a = api.get(r['code']) or {}
            e = exch.get(r['code']) or {}
            s3 = a.get('syl_3n')
            inst.append({'code': r['code'], 'name': short(r['name'], 22), 'scale': r['scale'],
                         'price': e.get('price'), 'nav': e.get('nav'), 'navdate': nav_at(r['code']),
                         'prem': e.get('prem'), 'syl1': a.get('syl_1n'),
                         'syl3a': ((1 + s3 / 100.0) ** (1 / 3.0) - 1) * 100 if s3 is not None else None})
        out[cat] = {'n_all': v['n_all'], 'n_off': v['n_off'],
                    'hold': bt['legs'].get(cat, {}).get('code'),
                    'holdname': bt['legs'].get(cat, {}).get('name'),
                    'rows': tbl, 'inst': inst,
                    'top_off': v['top_off']}
    return out


def build_scores(picks):
    """每类打分明细：总分前 10（含场内，标注「场内（本页不采用）」）+ 组合持有的场外一行"""
    out = {}
    for cat, v in picks['cats'].items():
        chosen = v['top_off']
        rows = sorted(v['rows'], key=lambda r: -r['total'])[:10]
        if chosen and chosen not in [r['code'] for r in rows]:
            extra = [r for r in v['rows'] if r['code'] == chosen]
            rows = rows + extra
        items = []
        for r in rows:
            isex = r['isexchg'] == '1'
            if isex:
                form = '场内（本页不采用）'
            elif r['code'] == chosen:
                form = '组合持有 · 场外'
            else:
                form = '场外'
            items.append({'code': r['code'], 'name': short(r['name'], 24), 'form': form,
                          'scale': r['scale'],
                          'buy': '—' if isex else (r['buy_raw'] or '—'),
                          'red': None if isex else r['red'],
                          'holdfee': (r['mgr'] or 0) + (r['tru'] or 0) + (r['sal'] or 0),
                          'quota': r['qtxt'],
                          's_scale': r['sscore'], 's_fee': r['tscore'] + r['hscore'],
                          's_quota': r['qscore'], 's_eval': r['escore'], 'total': r['total'],
                          'isexchg': isex,
                          'hold': r['code'] == (chosen or '')})
        out[cat] = items
    return out


def build_astock(ast, api, bt):
    rows = sorted(ast['rows'], key=lambda r: -r['total'])[:15]
    hold = bt['legs'].get('科创', {}).get('code')
    return {'n_all': ast['n_all'], 'hold': hold, 'holdname': bt['legs'].get('科创', {}).get('name'),
            'picked_inst': ast['picked_inst'], 'picked_off': ast['picked_off'],
            'rows': [{'code': r['code'], 'name': short(r['name'], 26), 'form': r['form'],
                      'scale': r['scale'], 'ann2': r['ann2'], 'annall': r['ann_all'],
                      'vol': r['vol'], 'mdd': r['mdd'], 'sharpe': r['sharpe'],
                      'bonus': r['bonus'], 's_ann': r['s_ann'], 's_scale': r['s_scale'],
                      's_fee': r['s_fee'], 's_eval': r['s_eval'], 'total': r['total'],
                      'hold': r['code'] == hold} for r in rows]}


def build_wavg(bt):
    legs = bt['order']
    out = []
    for nm, s in bt['schemes'].items():
        out.append({'scheme': nm, 'w': [s['w'].get(k, 0) for k in legs],
                    'cost': s['cost'], 'turnover': s['turnover'], 'stats': s['stats'],
                    'wr': s['wr'], 'main': nm.startswith('主推')})
    return out


def build_pts(bt):
    pts = []
    for a in bt['assets']:
        st = a['stats']
        pts.append({'name': a['cat'] + '·' + short(a['name'], 8),
                    'value': [st['vol'] * 100, st['ann'] * 100, st['mdd'] * 100]})
    for nm, s in bt['schemes'].items():
        st = s['stats']
        pts.append({'name': nm.split('（')[0], 'value': [st['vol'] * 100, st['ann'] * 100, st['mdd'] * 100]})
    for nm, cv, st in (('货基', bt['cash_curve'], bt['cash_stats']),
                       ('沪深300', bt['bench_curve'], bt['bench_stats'])):
        pts.append({'name': nm, 'value': [st['vol'] * 100, st['ann'] * 100, st['mdd'] * 100]})
    return pts


def main():
    bt = C.jload('bt2' + (TAG or '') + '.json')
    wt = C.jload('wt_hist' + (TAG or '') + '.json')
    picks = C.jload('picks2.json')
    ast = C.jload('astock.json')
    api = C.jload('api_data.json')
    met = C.jload('metrics.json')
    u = C.jload('api_universe.json')
    exch = C.jload('exch.json', default={}) or {}
    asof = bt['dates'][-1]
    legs = bt['order']
    kpis = []
    ms = bt['main_stats']
    es = bt['schemes']['等权 25%×4']['stats']
    kpis.append({'k': '年化收益', 'v': '%.2f%%' % (ms['ann'] * 100), 'cls': 'up' if ms['ann'] >= 0 else 'bad',
                 's': '%s ~ %s（%d 个交易日），已扣再平衡成本' % (bt['dates'][0], asof, len(bt['dates']))})
    kpis.append({'k': '年化波动', 'v': '%.2f%%' % (ms['vol'] * 100), 'cls': 'warn',
                 's': '等权方案 %.2f%%' % (es['vol'] * 100)})
    kpis.append({'k': '最大回撤', 'v': '%.2f%%' % abs(ms['mdd'] * 100), 'cls': 'bad',
                 's': '沪深300 同期 %.2f%%' % abs(bt['bench_stats']['mdd'] * 100)})
    fb = bool(bt.get('fallback'))
    kpis.append({'k': '夏普比率', 'v': '%.2f' % ms['sharpe'], 'cls': '',
                 's': ('货基口径（本期整仓货基，风险腿为空）' if fb else '沪深300 %.2f' % bt['bench_stats']['sharpe'])})
    kpis.append({'k': '卡玛比率', 'v': '%.2f' % ms['calmar'], 'cls': '',
                 's': ('货基无回撤，卡玛不适用' if fb else '收益/回撤（v5 约束方案）')})
    wtbl = build_wtbl(bt, wt)
    ops = build_ops(bt, wt, wtbl, bt['assets'])
    page = {
        'asof': asof, 'gen': today_str(), 'ver': 'v9',
        'range': [bt['dates'][0], asof], 'n_days': len(bt['dates']),
        'fallback': bt['fallback'], 'rule': bt['rule'],
        'kpis': kpis,
        'window_labels': bt['window_labels'], 'window_bases': bt['window_bases'],
        'hist': build_hist(bt),
        'feas_n': bt['feas_n'], 'grid_n': bt['grid_n'],
        'feas': [{'wstr': '/'.join('%d%%' % r['w'][k] for k in ['债券', '黄金', '科创', '能源']),
                  'stats': r['stats'], 'wr': r['wr'], 'main': i == 0}
                 for i, r in enumerate(bt['feas_all'])],
        'feas_order': ['债券', '黄金', '科创', '能源'],
        'wtbl': wtbl, 'ops': ops,
        'orders': build_orders(bt, wtbl, api, met),
        'freqs': [{'label': k, **v} for k, v in bt['freqs'].items()],
        'charts': {'labels': [d[2:] for d in bt['dates']],
                   'curves': bt['curves'], 'pts': build_pts(bt),
                   'wh': {'labels': wt['labels'], 'stack': wt['stack'],
                          'leglabels': wt['leglabels'], 'nocash': wt['nocash'], 'n': wt['n']}},
        'wavg': build_wavg(bt),
        'corr': {'names': [short(a['name'], 12) for a in bt['assets']],
                 'cats': [a['cat'] for a in bt['assets']], 'm': bt['corr']},
        'assets': bt['assets'],
        'cats': build_cats(u, picks, api, met, exch, bt),
        'scores': build_scores(picks),
        'astock': build_astock(ast, api, bt),
        'limits': build_limits(bt, wt, page_nocash=wt['nocash']),
        'wt_range': [wt['weeks'][0]['date'], wt['weeks'][-1]['date']],
    }
    C.jdump('page_data4' + (TAG or '') + '.json', page)
    C.log('page_data4%s.json 已生成（asof %s，fallback=%s，可行解 %d，行情判断 %d 字）'
          % (TAG, asof, bt['fallback'], bt['feas_n'], ops['zh']))


def today_str():
    return time.strftime('%Y-%m-%d %H:%M')


def build_limits(bt, wt, page_nocash=0):
    ms = bt['main_stats']
    v4 = bt['schemes']['v4 旧口径（最大化卡玛）']['stats']
    legsk = bt['order']
    kj = next((a for a in bt['assets'] if a['cat'] == '科创'), None)
    en = next((a for a in bt['assets'] if a['cat'] == '能源'), None)
    out = []
    out.append('区间偏差：%s 至 %s 覆盖黄金大牛市与半导体/科创芯片的强势行情，回测成绩被这两类资产显著抬高；'
               '该区间不代表一个完整周期。注意：本区间同样包含 2026 年三季度以来科创芯片大幅回调、黄金小幅回落的阶段，'
               'v5 权重正是被这一段决定的。' % (bt['dates'][0], bt['dates'][-1]))
    if kj:
        out.append('A股/科创腿的集中度风险：科创芯片/半导体属于高波动、高相关板块（本页该腿区间年化 %.1f%%、'
                   '年化波动 %.1f%%、最大回撤 %.1f%%），近三月 %.2f%%、上周 %.2f%%——这正是 v4 那套高权重短期转负的主因。'
                   'v5 对它按约束自动降权（本期 %d%%，可行解里也可以设 0），但该腿一旦反转，组合收益也会明显少一块。'
                   % (kj['wr'][4] * 100 * 0 + kj['stats']['ann'] * 100, kj['stats']['vol'] * 100,
                      kj['stats']['mdd'] * 100, kj['wr'][2] * 100, kj['wr'][0] * 100,
                      int(round(bt['main_w'].get('科创', 0) * 100))))
    if en:
        out.append('能源腿（煤炭/油气）的单一行业集中度：主推把能源顶到了权重上限附近（本期 %d%%）。'
                   '煤炭是单一行业，受价格、进口与政策影响大，上限是约束而非固定值，下周重跑网格会变。'
                   % int(round(bt['main_w'].get('能源', 0) * 100)))
    out.append('「窗口约束」是样本内拟合：用「过去 1 周／1 月／3 月／今年以来／近 2 年」五个窗口是否跑赢货基来筛权重，'
               '本质是按近期表现调权重。本期可行解 %d 组（共 %d 组）%s。这不是「稳赚」，只是「历史回测里短窗口不为负」。'
               % (bt['feas_n'], bt['grid_n'],
                  '，贴边界——某条腿一周的涨跌就可能让可行集翻转、权重下周就变' if bt['feas_n'] and bt['feas_n'] <= 6 else ''))
    out.append('与旧口径的取舍：放弃「禁止 0 权重」的 v4 口径（年化 %.2f%%、近 2 年 %+.2f%%）换来的，是短窗口不再为负'
               '（年化 %.2f%%、近 2 年 %+.2f%%）。这是约束的必然代价，不是参数没调好；若更看重长期年化，'
               '可直接用 v4 口径那套权重（页内已列出对照行）。'
               % (v4['ann'] * 100, bt['schemes']['v4 旧口径（最大化卡玛）']['wr'][4] * 100,
                  ms['ann'] * 100, bt['main_wr'][4] * 100))
    out.append('规则有时给不出解：约束不是「总能满足」——近一年 %d 周里有 %d 周五种窗口组合无解，此时按规则应当期 100%% 货基、'
               '不持风险腿。换句话说，「为什么不只买货基」在那些周就是唯一正解；本页把这几周在权重图里单独标成蓝色段，没有藏起来。'
               % (wt['n'], page_nocash))
    out.append('货基对照口径：货基取天弘余额宝货币（%s）——支付宝可以买到的货币基金，用其每日「每万份收益」累乘成净值曲线；'
               '货币基金份额净值恒 1 元，不存在回撤。同期货基年化约 %.2f%%，近 2 年累计 %+.2f%%。'
               % (bt['cash'], bt['cash_ann'] * 100, bt['cash_wr'][4] * 100))
    out.append('可申购性会变：场外份额的「限大额/暂停申购」会随基金公司逐日调整；本报告已优先选择额度宽松、赎回费低的份额，'
               '但下单前需再确认。')
    out.append('净值口径：ETF 联接的净值按交易日 T 日估值，场内 ETF 另受折溢价影响；A股/科创腿的「年化收益率」取近 2 年净值年化，'
               '样本区间恰逢板块高景气，长期均值可能低得多。')
    out.append('费率与成本：回测已按逐腿真实的「优惠申购费 + 持有满 7 天赎回费」扣减（本期四腿的再平衡成本合计约 %.2f%%/年），'
               '基金净值内已含管理费/托管费；未计支付宝端的销售服务费差异（C 类）与可能存在的短期惩罚性赎回费。'
               % (bt['main_cost'] * 100))
    out.append('场内折溢价：本页折溢价是相对「最新披露净值」而非 IOPV。本版不买场内 ETF，折溢价只作为情绪过热的警示（信号 S2）：'
               '溢价被放大时提示该腿暂缓加仓。')
    out.append('官方限额会随时变化：单日限额与申购状态由基金公司逐日调整，本页数值为抓取时点值，下单前请以支付宝/基金公司页面为准。')
    out.append('不是投资建议：本页仅用于研究与内部讨论，不构成任何申购、赎回或持有的建议。基金过往业绩不代表未来表现，投资须谨慎。')
    return out


import time
if __name__ == '__main__':
    main()
