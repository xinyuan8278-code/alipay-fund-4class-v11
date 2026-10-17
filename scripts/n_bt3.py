# -*- coding: utf-8 -*-
"""step 09(v11) · 周度回测 + 5% 整数倍权重网格 + 「夏普门槛内最大化收益」双目标 → bt3.json

与 n_bt2.py（v9 口径）的唯一区别是**选权规则**：
  v9 ：五窗口全部跑赢货基 → 取夏普最高；无可行解则当期整仓货基。
  v11：先在 375 组里按夏普取前 10%（夏普门槛随数据每次重算），
       在这批「夏普已经足够高」的解里取**年化收益最高**的一组。
       不设「必须跑赢货基」的硬约束（但把是否跑赢标注出来）。
另额外输出：夏普优先解 / 收益优先解 / 卡玛优先解 / 375 组全样本散点。
"""
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

    # ---------------- 网格（v11 双目标：夏普门槛内最大化年化收益）
    grids = enumerate_grid(0, 8)
    C.log('网格 %d 组' % len(grids))
    t0 = time.time()
    allrun = {}
    for steps in grids:
        w = wdict(LEG_ORDER, steps)
        r = simulate(dates, rets, w, 'W', costs)
        s = stats(r['curve'], dates)
        wr = C.window_returns(r['curve'], dates)
        allrun[steps] = (r, s, wr)
    C.log('网格回测完成 %.1fs' % (time.time() - t0))
    cash_wr = C.window_returns(cash, dates)

    # 目标一：夏普比率进入网格前 GATE_Q（默认 10%）—— 这是一道质量门槛，
    # 保证选出来的组合不是「靠高波动堆出来的高收益」；
    # 目标二：在过门槛的解里，年化收益最高者胜出。
    GATE_Q = 0.10
    ranked_sh = sorted(allrun.items(), key=lambda kv: (-kv[1][1]['sharpe'], -kv[1][1]['ann']))
    n_gate = max(1, int(round(len(grids) * GATE_Q)))
    gate_thr = ranked_sh[n_gate - 1][1][1]['sharpe']
    gate = [(s, v) for s, v in ranked_sh if v[1]['sharpe'] >= gate_thr - 1e-9]
    gate.sort(key=lambda x: (-x[1][1]['ann'], -x[1][1]['sharpe']))
    feas = [(s, v[1], v[2], v[0]) for s, v in gate]      # (steps, stats, wr, run)
    steps0, (r0, s0, wr0) = gate[0]
    main_w = wdict(LEG_ORDER, steps0)
    main_curve = r0['curve']
    main_turn, main_cost = r0['turnover'], r0['cost']
    fallback = False
    ref_combo = None
    over_cash = sum(1 for i in range(5) if wr0[i] > cash_wr[i])
    C.log('夏普门槛（前 %d%%）= %.3f，过门槛 %d 组；主推 %s' % (
        int(GATE_Q * 100), gate_thr, len(gate), {k: int(main_w[k] * 100) for k in LEG_ORDER}))
    C.log('主推五窗口跑赢货基 %d / 5' % over_cash)

    # ---------------- 对照解（同一网格、不同目标函数）
    def alt(steps_stats, label):
        s_, v_ = steps_stats
        r_ = v_[0]
        return {'label': label, 'steps': list(s_), 'w': wdict(LEG_ORDER, s_),
                'stats': v_[1], 'wr': v_[2], 'turnover': r_['turnover'], 'cost': r_['cost'],
                'curve': r_['curve'],
                'over_cash': sum(1 for i in range(5) if v_[2][i] > cash_wr[i])}
    alts = [alt(ranked_sh[0], '夏普优先解（网格夏普最高）'),
            alt(max(allrun.items(), key=lambda kv: kv[1][1]['ann']), '收益优先解（网格年化最高）'),
            alt(max(allrun.items(), key=lambda kv: kv[1][1]['calmar']), '卡玛优先解（网格卡玛最高）')]

    # 375 组全样本散点（风险—收益平面）
    grid_pts = []
    for steps, (r_, s_, wr_) in allrun.items():
        grid_pts.append({'w': [int(x * 5) for x in steps],
                         'ann': s_['ann'], 'vol': s_['vol'], 'mdd': s_['mdd'],
                         'sharpe': s_['sharpe'], 'calmar': s_['calmar']})

    # ---------------- 对照方案
    def sigma(k):
        return C.std(rets[k][1:]) or 1e-9
    eq_w = {k: 0.25 for k in LEG_ORDER}
    inv_w = cap_alloc({k: 1.0 / sigma(k) for k in LEG_ORDER})
    rp_w = cap_alloc({k: 1.0 / sigma(k) ** 2 for k in LEG_ORDER})
    inv_w = {k: v / 20.0 for k, v in round5_pct(inv_w).items()}   # 20 步 = 100%
    rp_w = {k: v / 20.0 for k, v in round5_pct(rp_w).items()}
    # 对照方案（同一网格、算法给出的固定权重）
    schemes = {}
    for nm, w in (('等权 25%×4', eq_w), ('波动率倒数（1/σ）', inv_w), ('风险平价（1/σ²）', rp_w),
                  ('主推（v11 双目标）', main_w)):
        r = simulate(dates, rets, w, 'W', costs)
        s = stats(r['curve'], dates)
        schemes[nm] = {'w': w, 'stats': s, 'turnover': r['turnover'], 'cost': r['cost'],
                       'curve': r['curve'], 'wr': C.window_returns(r['curve'], dates)}
    # 频率对比（按主推权重）
    freqs = {}
    for tag, lab in (('W', '周度调仓'), ('M', '月度调仓'), ('2', '双月调仓')):
        r = simulate(dates, rets, main_w, tag, costs)
        freqs[lab] = {'stats': stats(r['curve'], dates), 'turnover': r['turnover'], 'cost': r['cost']}

    # ---------------- 曲线与相关性
    curves = {'主推（v11 · 周度 · 5%整数权重）': main_curve,
              '夏普优先解': alts[0]['curve'],
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
           'grid_n': len(grids), 'feas_n': len(gate), 'fallback': False,
           'gate_q': GATE_Q, 'gate_n': len(gate), 'gate_thr': gate_thr,
           'rule': '375 组 5%% 整数倍权重里，夏普处于网格前 10%%（门槛 %.3f）的解中取年化收益最高者'
                   % gate_thr,
           'main_w': main_w, 'main_curve': main_curve,
           'main_stats': stats(main_curve, dates),
           'main_wr': C.window_returns(main_curve, dates),
           'main_over_cash': over_cash,
           'main_turnover': main_turn, 'main_cost': main_cost,
           'window_labels': [w[1] for w in C.WINDOWS],
           'window_bases': C.window_dates(dates),
           'feas_all': [{'steps': list(s), 'w': {k: s[i] for i, k in enumerate(LEG_ORDER)},
                         'stats': st, 'wr': wr,
                         'over_cash': sum(1 for i in range(5) if wr[i] > cash_wr[i])}
                        for s, st, wr, _r in feas],
           'alts': alts, 'grid_pts': grid_pts, 'ref_combo': ref_combo,
           'schemes': {k: {'w': v['w'], 'stats': v['stats'], 'turnover': v['turnover'],
                           'cost': v['cost'], 'wr': v['wr']} for k, v in schemes.items()},
           'curves': curves, 'corr': corr, 'assets': assets, 'freqs': freqs,
           'costs': {k: list(costs[k]) for k in LEG_ORDER},
           'legs_scale': {a['cat']: a['scale'] for a in assets}}
    C.jdump('bt3.json', out)
    C.log('主推指标 年化 %.2f%% 波动 %.2f%% 回撤 %.2f%% 夏普 %.2f 卡玛 %.2f' % (
        out['main_stats']['ann'] * 100, out['main_stats']['vol'] * 100,
        out['main_stats']['mdd'] * 100, out['main_stats']['sharpe'], out['main_stats']['calmar']))
    C.log('五窗口 组合 %s' % ' / '.join('%+.2f%%' % (x * 100) for x in out['main_wr']))
    C.log('五窗口 货基 %s' % ' / '.join('%+.2f%%' % (x * 100) for x in cash_wr))
    C.log('五窗口 沪深300 %s' % ' / '.join('%+.2f%%' % (x * 100) for x in out['bench_wr']))
    for a in alts:
        C.log('对照解 %s %s 年化 %.2f%% 夏普 %.2f 卡玛 %.2f'
              % (a['label'], {k: int(a['w'][k] * 100) for k in LEG_ORDER},
                 a['stats']['ann'] * 100, a['stats']['sharpe'], a['stats']['calmar']))


if __name__ == '__main__':
    main()
