# -*- coding: utf-8 -*-
"""step 10 · 近一年权重逐周滚动重构（52 周）→ wt_hist.json
要点：所有样本周的回测起点相同（数据起点），所以每个权重组合只模拟一次，
再在曲线上取前缀算窗口收益与统计量 —— 与逐周重跑完全等价。
无解周记 w=None（该周 100% 货基）。最后一周必须等于当期主推（硬断言）。"""
import os, json, math, time
import common as C
import n_bt2 as N


def week_ends(dates, k=52):
    """每个自然周（周一为界）最后一个交易日；取最后 k 个"""
    keys = [C.week_key(d) for d in dates]
    out = [i for i in range(len(dates)) if i == len(dates) - 1 or keys[i] != keys[i + 1]]
    return out[-k:]


def main():
    bt = C.jload('bt2' + C.SRC + '.json')
    codes, dates, rets, cash, bench = N.load_all(C.UNTIL)
    costs = {k: tuple(v) for k, v in bt['costs'].items()}
    grids = N.enumerate_grid(0, 8)
    n = len(dates)

    # 每个候选组合只算一次完整曲线
    runs = {}
    for steps in grids:
        w = N.wdict(N.LEG_ORDER, steps)
        runs[steps] = N.simulate(dates, rets, w, 'W', costs)['curve']

    # 货基前缀统计
    csum = [0.0]
    for v in cash:
        csum.append(csum[-1] + v)

    def wr_at(curve, t, widx):
        return [curve[t] / curve[i] - 1.0 if i >= 0 else curve[t] / curve[0] - 1.0 for i in widx]

    # 每个 t 的窗口下标（只与日期有关）
    widx_by_t = {}
    for t in week_ends(dates):
        sub = dates[:t + 1]
        widx_by_t[t] = [C.window_index(sub, k, len(sub) - 1) for k, _ in C.WINDOWS]

    stack = {k: [] for k in N.LEG_ORDER}
    labels, cashrows, weeks = [], [], []
    last_w = None
    for t in week_ends(dates):
        sub = dates[:t + 1]
        widx = widx_by_t[t]
        cw = [cash[t] / cash[i] - 1.0 for i in widx]
        best, bestkey = None, None
        for steps in grids:
            cv = runs[steps]
            wr = [cv[t] / cv[i] - 1.0 for i in widx]
            if not all(wr[j] > cw[j] for j in range(5)):
                continue
            days = C.d2ord(sub[-1]) - C.d2ord(sub[0])
            a = C.ann_return(cv[:t + 1], days)
            v = C.ann_vol(cv[:t + 1])
            sh = (a - C.RF) / v if v > 1e-12 else 0.0
            key = (sh, a)
            if bestkey is None or key > bestkey:
                bestkey, best = key, steps
        rec = {'date': sub[-1], 'label': sub[-1][2:], 'w': None, 'feas': False,
               'ann': None, 'sharpe': None, 'wr': [v * 100 for v in cw]}
        last_w = None
        days = C.d2ord(sub[-1]) - C.d2ord(sub[0])
        if best is None:
            for k in N.LEG_ORDER:
                stack[k].append(0)
            ca = C.ann_return(cash[:t + 1], days)
            cvv = C.ann_vol(cash[:t + 1])
            rec['ann'] = ca
            rec['sharpe'] = (ca - C.RF) / cvv if cvv > 1e-12 else 0.0
        else:
            for i, k in enumerate(N.LEG_ORDER):
                stack[k].append(best[i] * 5)
            last_w = {k: best[i] / 20.0 for i, k in enumerate(N.LEG_ORDER)}
            rec['w'] = {k: best[i] * 5 for i, k in enumerate(N.LEG_ORDER)}
            rec['feas'] = True
            cvv = runs[best]
            rec['ann'] = C.ann_return(cvv[:t + 1], days)
            vv = C.ann_vol(cvv[:t + 1])
            rec['sharpe'] = (rec['ann'] - C.RF) / vv if vv > 1e-12 else 0.0
            rec['wr'] = [(cvv[t] / cvv[i] - 1.0) * 100 for i in widx]
            rec['feas_n'] = sum(1 for st in grids if all(
                runs[st][t] / runs[st][i] - 1.0 > cw[j] for j, i in enumerate(widx)))
        labels.append(sub[-1][2:])
        weeks.append(rec)
    stack['货基（无可行解）'] = [0 if (stack['能源'][i] or stack['债券'][i] or stack['黄金'][i] or stack['科创'][i])
                                 else 100 for i in range(len(labels))]
    nocash = sum(1 for v in stack['货基（无可行解）'] if v == 100)
    out = {'labels': labels, 'stack': stack,
           'leglabels': N.LEG_ORDER + ['货基（无可行解）'],
           'nocash': nocash, 'n': len(labels), 'last_w': last_w,
           'weeks': weeks,
           'week_ends': [dates[t] for t in week_ends(dates)]}
    C.jdump('wt_hist.json', out)
    C.log('52 周滚动重构完成：无解周 %d / %d' % (nocash, len(labels)))
    C.log('最后一周权重 %s' % {k: int((last_w or {}).get(k, 0) * 100) for k in N.LEG_ORDER})
    # 一致性断言：滚动最后一周 == 当期页面主推
    cur = {k: bt['main_w'][k] for k in N.LEG_ORDER}
    if bt.get('fallback'):
        ok = all(abs(cur[k]) < 1e-9 for k in N.LEG_ORDER) and last_w is None
    else:
        ok = last_w is not None and all(abs(last_w[k] - cur[k]) < 1e-9 for k in N.LEG_ORDER)
    if not ok:
        raise SystemExit('!! 一致性断言失败：滚动最后一周 %s != 当期主推 %s' % (last_w, cur))
    C.log('✔ 一致性断言通过（滚动最后一周 == 当期主推）')


if __name__ == '__main__':
    main()
