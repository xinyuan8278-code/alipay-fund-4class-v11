# -*- coding: utf-8 -*-
"""step 07 · 周度回测 + 5% 整数倍权重网格 + 五窗口跑赢货基 + 无可行解退化 → bt2.json"""
import os, json, math, time
import common as C

# 腿集（场外可执行 · 支付宝可买）；在持标的由 swap_state.json 钉住
LEG_ORDER = ['能源', '债券', '黄金', '科创']
FALLBACK_LEGS = {'能源': ('013275', '富国中证煤炭指数(LOF)C'),
                 '债券': ('018266', '富国中债7-10年政策性金融债ETF发起式联接A'),
                 '黄金': ('009504', '富国上海金ETF联接A'),
                 '科创': ('017470', '嘉实上证科创板芯片ETF发起联接C')}
BENCH = '510300'
CASH = '000198'
LOOKBACK_DAYS = 1095          # 回测窗口 = 最近 3 年
CAP_LO, CAP_HI = 10, 40       # 等权外的方案单腿上限（%）
FORCE_NOFEAS = os.environ.get('QDII_FORCE_NOFEAS') == '1'


# ------------------------------------------------------------------ 数据
def leg_codes():
    p = C.wfile('swap_state.json')
    if os.path.exists(p):
        st = json.load(open(p, encoding='utf-8'))
        hold = st.get('hold') or {}
        if all(k in hold for k in LEG_ORDER):
            return {k: (hold[k]['code'], hold[k]['name']) for k in LEG_ORDER}
    return dict(FALLBACK_LEGS)


def series(code):
    d = C.jload('funds_raw.json')[code]
    nav = d.get('nav') or []
    out = {}
    for x in nav:
        dt, _y, er = x[0], x[1], x[2]
        out[dt] = (1.0 + (float(er) / 100.0 if er is not None else 0.0))
    return out


def cash_series(code=CASH):
    """货基曲线：当日收益 = 万份收益/10000，份额净值恒 1 元、无回撤"""
    d = C.jload('funds_raw.json')[code]
    pts = d.get('minc') or []
    out, cum = {}, 1.0
    for dt, inc in pts:
        cum *= (1.0 + float(inc) / 10000.0)
        out[dt] = cum
    return out


def cum_from(raw):
    """把 {date: (1+日收益)} 累乘成净值曲线字典"""
    out, cum = {}, 1.0
    for d in sorted(raw):
        cum *= raw[d]
        out[d] = cum
    return out


def load_all(until=None):
    codes = leg_codes()
    rets_raw = {k: series(codes[k][0]) for k in LEG_ORDER}
    cash_raw = cash_series()
    # 公共交易日：四条腿的交集，再截最近 3 年
    common = None
    for k in LEG_ORDER:
        s = set(rets_raw[k])
        common = s if common is None else (common & s)
    common = sorted(common)
    if until:
        common = [d for d in common if d <= until]
    latest = common[-1]
    cut = C.shift(latest, -LOOKBACK_DAYS)
    dates = [d for d in common if d >= cut]

    def on_dates(raw):
        """把任意日期序列对齐到 dates（缺失用前值）"""
        out, last = [], None
        ks = sorted(raw)
        j = 0
        for d in dates:
            while j < len(ks) and ks[j] <= d:
                last = ks[j]
                j += 1
            out.append(raw[last] if last is not None else None)
        return out

    bench_raw = cum_from(series(BENCH))
    bser = on_dates(bench_raw)
    bench = [v / bser[0] for v in bser] if bser[0] else [1.0] * len(dates)

    cashser = on_dates(cash_raw)
    cash = [v / cashser[0] for v in cashser] if cashser[0] else [1.0] * len(dates)

    rets = {}
    for k in LEG_ORDER:
        r = []
        prev = None
        for d in dates:
            v = rets_raw[k].get(d)
            r.append(0.0 if prev is None or v is None else v - 1.0)
            if v is not None:
                prev = v
        rets[k] = r
    return codes, dates, rets, cash, bench


def rebal_idx(dates, freq):
    """每周/每月/双月的最后一个交易日下标（用自然周序号，避免时区漂移）"""
    keyfn = {'W': C.week_key, 'M': C.month_key, '2': C.bimonth_key}[freq]
    keys = [keyfn(d) for d in dates]
    out = []
    for i in range(len(dates) - 1):
        if keys[i] != keys[i + 1]:
            out.append(i)
    return out


def simulate(dates, rets, w, freq, costs):
    """周/月/双月最后一个交易日按目标权重调回；扣逐腿真实申赎费。
    w: {leg: 权重(0-1)}；costs: {leg: (申购费率, 赎回费率)} 均为小数"""
    n = len(dates)
    legs = list(LEG_ORDER)
    reb = set(rebal_idx(dates, freq))
    target = {k: w.get(k, 0.0) for k in legs}
    cur = dict(target)
    curve = [1.0]
    turnover = 0.0
    costsum = 0.0
    for i in range(1, n):
        vals = {k: cur[k] * (1.0 + rets[k][i]) for k in legs}
        tot = sum(vals.values())
        if tot <= 0:
            tot = 1.0
            vals = {k: cur[k] for k in legs}
        curve.append(curve[-1] * tot)
        cur = {k: vals[k] / tot for k in legs}
        if i in reb and i < n:
            delta = {k: target[k] - cur[k] for k in legs}
            c = 0.0
            for k in legs:
                d = delta[k]
                cb, cr = costs.get(k, (0.0, 0.0))
                c += (d * cb if d > 0 else (-d) * cr)
            turnover += 0.5 * sum(abs(delta[k]) for k in legs)
            costsum += c
            curve[-1] *= (1.0 - c)
            cur = dict(target)
    years = max(1e-9, (C.d2ord(dates[-1]) - C.d2ord(dates[0])) / 365.0)
    return {'curve': curve, 'turnover': turnover / years, 'cost': costsum / years}


def stats(curve, dates):
    n = len(curve) - 1
    days = C.d2ord(dates[-1]) - C.d2ord(dates[0])
    a = C.ann_return(curve, days)
    v = C.ann_vol(curve)
    m = C.max_drawdown(curve)
    return {'ann': a, 'vol': v, 'mdd': m, 'sharpe': (a - C.RF) / v if v > 1e-12 else 0.0,
            'calmar': a / abs(m) if abs(m) > 1e-12 else 0.0, 'cum': curve[-1] / curve[0] - 1.0}


# ------------------------------------------------------------------ 网格
def enumerate_grid(lo_step=0, hi_step=8, total=20):
    out = []
    for a in range(lo_step, hi_step + 1):
        for b in range(lo_step, hi_step + 1):
            for c in range(lo_step, hi_step + 1):
                d = total - a - b - c
                if d < lo_step or d > hi_step:
                    continue
                out.append((a, b, c, d))
    return out


def wdict(order, steps):
    return {k: steps[i] / 20.0 for i, k in enumerate(order)}


def cap_alloc(raw, lo=CAP_LO, hi=CAP_HI):
    """水填充夹逼（逐个夹逼、每轮重算比例）：把 raw 归一后裁剪到 [lo,hi] 且合计 100。
    纯 ERC 在「债券日波动 0.1% vs 商品 2%」上会把债券推到 80%+，必须配这层约束。"""
    keys = list(raw)
    remain = 100.0
    out = {}
    free = list(keys)
    guard = 0
    while free and guard < 200:
        guard += 1
        s = sum(raw[k] for k in free)
        if s <= 0:
            for k in free:
                out[k] = remain / len(free)
            break
        if remain <= lo * len(free) + 1e-9:
            for k in free:
                out[k] = remain / len(free)
            break
        hit = None
        for k in free:
            v = raw[k] * remain / s
            if v < lo - 1e-9:
                hit = (k, lo)
                break
            if v > hi + 1e-9:
                hit = (k, hi)
                break
        if hit is None:
            for k in free:
                out[k] = raw[k] * remain / s
            break
        k, v = hit
        out[k] = v
        remain -= v
        free.remove(k)
    tot = sum(out.values())
    if tot > 0:
        out = {k: v * 100.0 / tot for k, v in out.items()}
    return out


def round5_pct(w):
    """四舍五入到 5% 并配平到 100（步数）"""
    steps = {k: int(round(v / 5.0)) for k, v in w.items()}
    diff = 20 - sum(steps.values())
    if diff:
        k = max(steps, key=lambda x: steps[x])
        steps[k] += diff
    return steps


def main():
    codes, dates, rets, cash, bench = load_all(C.UNTIL)
    met = C.jload('metrics.json')
    api = C.jload('api_data.json')
    costs = {}
    for k in LEG_ORDER:
        a = api.get(codes[k][0]) or {}
        buy = 0.0
        import re as _re
        m = _re.search(r'([\d.]+)', str(a.get('rate') or '0'))
        if m:
            buy = float(m.group(1)) / 100.0
        red = (a.get('redeem7') or 0.0) / 100.0
        costs[k] = (buy, red)
    C.log('腿集：' + '；'.join('%s %s %s' % (k, codes[k][0], codes[k][1][:20]) for k in LEG_ORDER))
    C.log('窗口 %s ~ %s（%d 个交易日）' % (dates[0], dates[-1], len(dates)))
    C.log('费率：' + '；'.join('%s 申购%.2f%% 赎回%.2f%%' % (k, costs[k][0] * 100, costs[k][1] * 100) for k in LEG_ORDER))

    # ---------------- 网格
    grids = enumerate_grid(0, 8)
    C.log('网格 %d 组' % len(grids))
    t0 = time.time()
    best, feas = None, []
    allrun = {}
    for steps in grids:
        w = wdict(LEG_ORDER, steps)
        r = simulate(dates, rets, w, 'W', costs)
        s = stats(r['curve'], dates)
        wr = C.window_returns(r['curve'], dates)
        allrun[steps] = (r, s, wr)
    C.log('网格回测完成 %.1fs' % (time.time() - t0))
    cash_wr = C.window_returns(cash, dates)
    if FORCE_NOFEAS:
        cash_wr = [v + 0.01 for v in cash_wr]
    for steps, (r, s, wr) in allrun.items():
        if all(wr[i] > cash_wr[i] for i in range(5)):
            feas.append((steps, s, wr, r))
    feas.sort(key=lambda x: (-x[1]['sharpe'], -x[1]['ann']))
    fallback = False
    if feas:
        steps0, s0, wr0, r0 = feas[0]
        main_w = wdict(LEG_ORDER, steps0)
        main_curve = r0['curve']
        main_turn, main_cost = r0['turnover'], r0['cost']
        ref_combo = None
    else:
        fallback = True
        main_w = {k: 0.0 for k in LEG_ORDER}
        main_curve = list(cash)
        main_turn, main_cost = 0.0, 0.0
        bestmin = None
        for steps, (r, s, wr) in allrun.items():
            exc = [wr[i] - cash_wr[i] for i in range(5)]
            if bestmin is None or min(exc) > bestmin[0]:
                bestmin = (min(exc), steps, wr)
        ref_combo = {'steps': list(bestmin[1]), 'w': wdict(LEG_ORDER, bestmin[1]),
                     'wr': bestmin[2], 'min_exc': bestmin[0]}
    C.log('可行解 %d / %d，主推 %s' % (len(feas), len(grids),
                                    {k: int(main_w[k] * 100) for k in LEG_ORDER}))
    if fallback:
        C.log('⚠ 本期无可行解 → 退化 100%% 货基')

    # ---------------- 对照方案
    def sigma(k):
        return C.std(rets[k][1:]) or 1e-9
    eq_w = {k: 0.25 for k in LEG_ORDER}
    inv_w = cap_alloc({k: 1.0 / sigma(k) for k in LEG_ORDER})
    rp_w = cap_alloc({k: 1.0 / sigma(k) ** 2 for k in LEG_ORDER})
    inv_w = {k: v / 20.0 for k, v in round5_pct(inv_w).items()}   # 20 步 = 100%
    rp_w = {k: v / 20.0 for k, v in round5_pct(rp_w).items()}
    # v4 旧口径：禁止 0 权重、单腿 10%~40%、最大化卡玛
    v4, v4s = None, None
    for steps in enumerate_grid(2, 8):
        w = wdict(LEG_ORDER, steps)
        r = simulate(dates, rets, w, 'W', costs)
        s = stats(r['curve'], dates)
        if v4s is None or s['calmar'] > v4s['calmar']:
            v4, v4s = w, s
    schemes = {}
    for nm, w in (('等权 25%×4', eq_w), ('波动率倒数（1/σ）', inv_w), ('风险平价（1/σ²）', rp_w),
                  ('主推（5% 网格）', main_w), ('v4 旧口径（最大化卡玛）', v4)):
        r = simulate(dates, rets, w, 'W', costs)
        s = stats(r['curve'], dates)
        schemes[nm] = {'w': w, 'stats': s, 'turnover': r['turnover'], 'cost': r['cost'],
                       'curve': r['curve'], 'wr': C.window_returns(r['curve'], dates)}
    if fallback:      # 无解周：主推方案就是货基，别让它显示成 0% 的零收益组合
        cs = stats(cash, dates)
        schemes['主推（5% 网格）'] = {'w': {k: 0.0 for k in LEG_ORDER}, 'stats': cs,
                                   'turnover': 0.0, 'cost': 0.0, 'curve': list(cash),
                                   'wr': C.window_returns(cash, dates)}
        schemes['v4 旧口径（最大化卡玛）'] = schemes.get('v4 旧口径（最大化卡玛）', schemes['等权 25%×4'])
    # 频率对比（按主推权重）
    freqs = {}
    for tag, lab in (('W', '周度调仓'), ('M', '月度调仓'), ('2', '双月调仓')):
        r = simulate(dates, rets, main_w, tag, costs)
        freqs[lab] = {'stats': stats(r['curve'], dates), 'turnover': r['turnover'], 'cost': r['cost']}

    # ---------------- 曲线与相关性
    curves = {'网格最优（周度·5%整数权重）': main_curve,
              '网格最优（v4 旧口径·禁止0权重）': schemes['v4 旧口径（最大化卡玛）']['curve'],
              '等权（周度）': schemes['等权 25%×4']['curve'],
              '货基（余额宝000198）': cash,
              '沪深300（510300）': bench}
    rr = {k: rets[k][1:] for k in LEG_ORDER}
    corr = [[C.corr(rr[a], rr[b]) for b in LEG_ORDER] for a in LEG_ORDER]

    # ---------------- 资产统计
    assets = []
    for i, k in enumerate(LEG_ORDER):
        code, name = codes[k]
        m = met.get(code) or {}
        a3 = m.get('a3') or {}
        sub = [rets[k][j] for j in range(1, len(dates))]
        cur = []
        v = 1.0
        for r in sub:
            v *= (1.0 + r)
            cur.append(v)
        st = stats([1.0] + cur, dates)
        assets.append({'cat': k, 'code': code, 'name': name, 'indexname': (api.get(code) or {}).get('indexname', ''),
                       'scale': (api.get(code) or {}).get('endnav', 0) / 1e8 if (api.get(code) or {}).get('endnav') else m.get('scale'),
                       'buy': costs[k][0], 'red': costs[k][1], 'stats': st,
                       'sharpe1': (api.get(code) or {}).get('sharpe1'),
                       'curve': [1.0] + cur, 'wr': C.window_returns([1.0] + cur, dates)})

    out = {'legs': {k: {'code': codes[k][0], 'name': codes[k][1]} for k in LEG_ORDER},
           'order': LEG_ORDER, 'dates': dates, 'bench': BENCH, 'cash': CASH,
           'cash_curve': cash, 'bench_curve': bench, 'cash_wr': cash_wr,
           'cash_ann': stats(cash, dates)['ann'], 'cash_stats': stats(cash, dates),
           'bench_stats': stats(bench, dates), 'bench_wr': C.window_returns(bench, dates),
           'grid_n': len(grids), 'feas_n': len(feas), 'fallback': fallback,
           'rule': '五窗口全部跑赢货基 000198，其中取夏普最高；无可行解则当期 100% 货基',
           'main_w': main_w, 'main_curve': main_curve,
           'main_stats': stats(main_curve, dates),
           'main_wr': C.window_returns(main_curve, dates),
           'main_turnover': main_turn, 'main_cost': main_cost,
           'window_labels': [w[1] for w in C.WINDOWS],
           'window_bases': C.window_dates(dates),
           'feas_all': [{'steps': list(s), 'w': {k: s[i] for i, k in enumerate(LEG_ORDER)},
                         'stats': st, 'wr': wr} for s, st, wr, _r in feas],
           'ref_combo': ref_combo,
           'schemes': {k: {'w': v['w'], 'stats': v['stats'], 'turnover': v['turnover'],
                           'cost': v['cost'], 'wr': v['wr']} for k, v in schemes.items()},
           'curves': curves, 'corr': corr, 'assets': assets, 'freqs': freqs,
           'costs': {k: list(costs[k]) for k in LEG_ORDER},
           'legs_scale': {a['cat']: a['scale'] for a in assets}}
    C.jdump('bt2.json', out)
    C.log('主推指标 年化 %.2f%% 波动 %.2f%% 回撤 %.2f%% 夏普 %.2f 卡玛 %.2f' % (
        out['main_stats']['ann'] * 100, out['main_stats']['vol'] * 100,
        out['main_stats']['mdd'] * 100, out['main_stats']['sharpe'], out['main_stats']['calmar']))
    C.log('五窗口 组合 %s' % ' / '.join('%+.2f%%' % (x * 100) for x in out['main_wr']))
    C.log('五窗口 货基 %s' % ' / '.join('%+.2f%%' % (x * 100) for x in cash_wr))
    C.log('五窗口 沪深300 %s' % ' / '.join('%+.2f%%' % (x * 100) for x in out['bench_wr']))
    C.log('v4 旧口径 %s 年化 %.2f%% 近2年 %+.2f%%' % ({k: int(v4[k] * 100) for k in LEG_ORDER},
                                                v4s['ann'] * 100, schemes['v4 旧口径（最大化卡玛）']['wr'][4] * 100))


if __name__ == '__main__':
    main()
