# -*- coding: utf-8 -*-
"""step 10(v11) · 近一年权重逐周滚动重构（52 周）→ wt_hist3.json

与 v_wt_hist.py（v9 口径）的区别：每周的选权规则换成 v11 双目标
——「夏普处于该周网格前 10% 的解里，年化收益最高者胜出」。
因为门槛是**逐周相对**的，所以每一周都只用「截至那一周」的数据重算，
不存在未来函数。所有样本周回测起点相同，故每个候选只模拟一次、在曲线上取前缀。
最后一周必须等于当期主推（硬断言）。"""
import os, json, math, time
import common as C
import n_bt3 as N

GATE_Q = 0.10


def week_ends(dates, k=52):
    """每个自然周（周一为界）最后一个交易日；取最后 k 个"""
    keys = [C.week_key(d) for d in dates]
    out = [i for i in range(len(dates)) if i == len(dates) - 1 or keys[i] != keys[i + 1]]
    return out[-k:]


def main():
    bt = C.jload('bt3.json')
    codes, dates, rets, cash, bench = N.load_all(C.UNTIL)
    costs = {k: tuple(v) for k, v in bt['costs'].items()}
    grids = N.enumerate_grid(0, 8)

    # 每个候选组合只算一次完整曲线
    runs = {}
    for steps in grids:
        w = N.wdict(N.LEG_ORDER, steps)
        runs[steps] = N.simulate(dates, rets, w, 'W', costs)['curve']

    # 每个 t 的窗口下标（只与日期有关）
    widx_by_t = {}
    for t in week_ends(dates):
        sub = dates[:t + 1]
        widx_by_t[t] = [C.window_index(sub, k, len(sub) - 1) for k, _ in C.WINDOWS]

    stack = {k: [] for k in N.LEG_ORDER}
    labels, weeks = [], []
    last_w = None
    n_gate_cur = 0
    for t in week_ends(dates):
        sub = dates[:t + 1]
        widx = widx_by_t[t]
        days = C.d2ord(sub[-1]) - C.d2ord(sub[0])
        cw = [cash[t] / cash[i] - 1.0 for i in widx]
        metr = []
        for steps in grids:
            cv = runs[steps][:t + 1]
            a = C.ann_return(cv, days)
            v = C.ann_vol(cv)
            sh = (a - C.RF) / v if v > 1e-12 else 0.0
            metr.append((sh, a, steps))
        metr.sort(reverse=True)
        kg = max(1, int(round(len(grids) * GATE_Q)))
        thr = metr[kg - 1][0]
        gate = [x for x in metr if x[0] >= thr - 1e-9]
        best = max(gate, key=lambda x: (x[1], x[0]))[2]
        n_gate_cur = len(gate)

        for i, k in enumerate(N.LEG_ORDER):
            stack[k].append(best[i] * 5)
        last_w = {k: best[i] / 20.0 for i, k in enumerate(N.LEG_ORDER)}
        cvv = runs[best]
        wr = [(cvv[t] / cvv[i] - 1.0) * 100 for i in widx]
        rec = {'date': sub[-1], 'label': sub[-1][2:],
               'w': {k: best[i] * 5 for i, k in enumerate(N.LEG_ORDER)},
               'feas': True, 'feas_n': len(gate), 'gate_thr': thr,
               'ann': C.ann_return(cvv[:t + 1], days),
               'sharpe': (C.ann_return(cvv[:t + 1], days) - C.RF) /
                         (C.ann_vol(cvv[:t + 1]) or 1e-12),
               'wr': wr,
               'over_cash': sum(1 for j in range(5) if wr[j] * 0.01 > cw[j])}
        labels.append(sub[-1][2:])
        weeks.append(rec)
    out = {'labels': labels, 'stack': stack,
           'leglabels': list(N.LEG_ORDER),
           'nocash': 0, 'n': len(labels), 'last_w': last_w,
           'weeks': weeks, 'gate_q': GATE_Q,
           'week_ends': [dates[t] for t in week_ends(dates)]}
    C.jdump('wt_hist3.json', out)
    C.log('52 周滚动重构完成（v11 规则）：每周期权门槛内 %d 组' % n_gate_cur)
    C.log('最后一周权重 %s' % {k: int((last_w or {}).get(k, 0) * 100) for k in N.LEG_ORDER})
    # 一致性断言：滚动最后一周 == 当期页面主推
    cur = {k: bt['main_w'][k] for k in N.LEG_ORDER}
    ok = last_w is not None and all(abs(last_w[k] - cur[k]) < 1e-9 for k in N.LEG_ORDER)
    if not ok:
        raise SystemExit('!! 一致性断言失败：滚动最后一周 %s != 当期主推 %s' % (last_w, cur))
    C.log('OK 一致性断言通过（滚动最后一周 == 当期主推）')


if __name__ == '__main__':
    main()
