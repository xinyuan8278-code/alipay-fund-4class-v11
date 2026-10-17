# -*- coding: utf-8 -*-
"""固定权重网格回测（bt 引擎）· 步长 5%、单腿 0~40%、合计 100%、**周度再平衡**。

与主管线 n_bt2.py 的口径对齐（周度调仓 / 5% 整数倍 / 单腿 0~40%），
区别只在「标的与成本模型」：bt 用场内 ETF 前复权价（支付宝买不到，仅作代理）＋单边 2.5bp。

产出 out/bt_grid5.json（375 组）+ out/bt_grid5.csv
"""
import os, sys, json, itertools
from pathlib import Path
import pandas as pd
import bt

SK = Path(os.environ.get('BT_SKILL', r'C:/Users/HTFC/.workbuddy/skills/bt-etf-backtest'))
sys.path.insert(0, str(SK / 'scripts'))
import backtest_etf as BE

A = bt.algos
HERE = Path(__file__).resolve().parent
COMM, CAP, WARMUP = 0.00025, 100000, 252


def main():
    src = os.environ.get('BT_PRICES') or (HERE / 'prices.csv')
    px = BE.load_prices(src)
    px = px.dropna(how='any')
    cols = list(px.columns)
    steps = list(range(0, 41, 5))
    combos = [c for c in itertools.product(steps, repeat=4) if sum(c) == 100]
    print('[网格] %d 组（步长 5%%，单腿 0~40%%，周度再平衡，%s ~ %s）'
          % (len(combos), px.index[0].date(), px.index[-1].date()), flush=True)

    strats, names, wmap = [], [], {}
    for combo in combos:
        w = [x / 100.0 for x in combo]
        nm = 'W' + ''.join('%02d' % x for x in combo)
        fw = BE.fixed_weight_targets(px.index, cols, w, 'W')
        strats.append(bt.Strategy(nm, [
            A.RunWeekly(run_on_first_date=False),
            A.SelectThese(cols),
            A.WeighTarget(fw),
            A.Rebalance(),
        ]))
        names.append(nm)
        wmap[nm] = list(combo)

    bts = [bt.Backtest(s, px, initial_capital=CAP,
                       commissions=lambda q, p: abs(q) * p * COMM) for s in strats]
    res = bt.run(*bts)

    warm_i = min(WARMUP, max(len(px) - 30, 0))
    warm_start = px.index[warm_i]
    tbl, equity = BE.summarize(res, names, CAP, warm_start, px.index[-1])

    grid = []
    for nm in names:
        r = tbl.loc[nm]

        def f(k):
            v = r[k]
            return None if pd.isna(v) else float(v)
        grid.append({'name': nm, 'w': wmap[nm],
                     'tot': f('累计收益'), 'ann': f('年化收益'), 'vol': f('年化波动'),
                     'sharpe': f('夏普'), 'mdd': f('最大回撤'), 'calmar': f('卡玛'),
                     'turnover': f('年化换手')})

    out = {'asof': str(px.index[-1].date()),
           'range': [str(warm_start.date()), str(px.index[-1].date())],
           'cols': cols, 'step': 5, 'n': len(grid), 'freq': '周度再平衡',
           'commission_bp': COMM * 10000, 'grid': grid}
    (HERE / 'out' / 'bt_grid5.json').write_text(
        json.dumps(out, ensure_ascii=False, indent=1), encoding='utf-8')
    tbl.to_csv(HERE / 'out' / 'bt_grid5.csv', encoding='utf-8-sig')
    print('[完成] %d 组 → out/bt_grid5.json' % len(grid), flush=True)

    ok = [g for g in grid if g['sharpe'] is not None]
    for title, key in (('夏普 Top8', lambda x: -x['sharpe']),
                       ('卡玛 Top5', lambda x: -x['calmar']),
                       ('年化 Top5', lambda x: -x['ann'])):
        print('  --- %s ---' % title, flush=True)
        for g in sorted(ok, key=key)[:8 if '夏普' in title else 5]:
            print('    %s  年化%6.2f%% 波动%6.2f%% 夏普%5.2f 回撤%6.2f%% 卡玛%5.2f'
                  % (g['w'], g['ann'] * 100, g['vol'] * 100, g['sharpe'],
                     g['mdd'] * 100, g['calmar']), flush=True)


if __name__ == '__main__':
    main()
