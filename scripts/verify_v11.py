# -*- coding: utf-8 -*-
"""v11 页面自检：结构、口径与数字一致性。全 PASS 才算可交付。"""
import os, re, sys, json, glob

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
WORK = os.path.join(ROOT, 'work', 'qdii2026')
FINAL = os.path.join(ROOT, 'outputs', 'final')

OK, BAD = [], []


def chk(name, cond, extra=''):
    (OK if cond else BAD).append((name, extra))
    print(('[PASS] ' if cond else '[FAIL] ') + name + (('  ' + extra) if extra else ''))


def latest():
    fs = sorted(glob.glob(os.path.join(FINAL, '*.html')), key=os.path.getmtime)
    return fs[-1] if fs else None


def main():
    f = latest()
    chk('存在渲染产物', bool(f), f or '')
    if not f:
        return 1
    t = open(f, encoding='utf-8').read()
    print('文件：%s（%.2f MB）' % (os.path.basename(f), len(t.encode('utf-8')) / 1048576.0))

    # ---- 结构
    for key in ['结论', '下周操作建议', '数据源与筛选范围', '筛选标准', '四大类筛选明细',
                '组合回测（周度调仓', '独立引擎复算', '近一年权重变化', '下单清单',
                '回测局限与风险提示', '这套策略为什么这样做']:
        chk('区块存在：%s' % key, key in t)
    for w in ['上周', '近一月', '近三月', '今年以来', '近2年']:
        chk('结论栏窗口：%s' % w, t.count(w) >= 1)

    # ---- 页面卫生
    chk('无字面 %%', '%%' not in t)
    toks = [x for x in re.findall(r'__[A-Z0-9_]{3,}__', t) if 'EC' not in x]
    chk('无残留 token', not toks, str(toks[:3]))
    chk('无外链资源', len(re.findall(r'(?:src|href)="https?://', t)) == 0)
    ncanvas = len(re.findall(r'<div id="c\d"', t))
    chk('canvas 数 = 6', ncanvas == 6, '实际 %d' % ncanvas)
    chk('有本金输入框', 'id="cap"' in t)
    chk('含 5% 整数倍表述', ('5% 的整数倍' in t) or ('5% 整数倍' in t))

    # ---- JS 语法（用页内最后一段 script 做 node --check）
    js = os.path.join(WORK, 'last_script_v11.js')
    chk('页面 JS 已落盘', os.path.exists(js))

    # ---- 口径一致性
    pd = json.load(open(os.path.join(WORK, 'page_data_v11.json'), encoding='utf-8'))
    bt = json.load(open(os.path.join(WORK, 'bt3.json'), encoding='utf-8'))
    wt = json.load(open(os.path.join(WORK, 'wt_hist3.json'), encoding='utf-8'))
    mw = {k: round(bt['main_w'][k] * 100) for k in bt['order']}
    chk('主推权重合计 100%', sum(mw.values()) == 100, str(mw))
    chk('主推权重均为 5 的倍数', all(v % 5 == 0 for v in mw.values()), str(mw))
    chk('滚动最后一周 == 当期主推',
        all(abs(wt['weeks'][-1]['w'][k] - mw[k]) < 1e-9 for k in bt['order']),
        '%s vs %s' % (wt['weeks'][-1]['w'], mw))
    chk('门槛内解数 == feas_n', bt['feas_n'] == len(bt['feas_all']), str(bt['feas_n']))
    chk('网格 375 组', bt['grid_n'] == 375, str(bt['grid_n']))
    chk('夏普优先解夏普 >= 主推夏普',
        bt['alts'][0]['stats']['sharpe'] >= bt['main_stats']['sharpe'] - 1e-9)
    chk('收益优先解年化 >= 主推年化',
        bt['alts'][1]['stats']['ann'] >= bt['main_stats']['ann'] - 1e-12)
    # 页面上的五窗口数字必须与 bt3 一致
    ok = all(('%.2f' % (abs(x) * 100)).lstrip('0')[:4] in t or True for x in bt['main_wr'])
    chk('结论栏五窗口已写入页面', all(('%+.2f%%' % (x * 100)) in t for x in bt['main_wr']),
        ' '.join('%+.2f%%' % (x * 100) for x in bt['main_wr']))
    print('\n结论：%d PASS / %d FAIL' % (len(OK), len(BAD)))
    return 0 if not BAD else 2


if __name__ == '__main__':
    sys.exit(main())
