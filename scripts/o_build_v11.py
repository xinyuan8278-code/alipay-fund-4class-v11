# -*- coding: utf-8 -*-
"""渲染单文件 HTML（v11 · 浅色主题 · 红涨绿跌 · ECharts 内联、无外链）

用法：python o_build_v11.py
输入：work/qdii2026/page_data_v11.json + bt_run/out/*.json/csv
输出：outputs/final/alipay_fund_4class_v11_<YYYYMMDD>_<HHMMSS>.html
"""
import os, re, csv, json, time, html
import common as C

BT_RUN = os.path.join(C.ROOT, 'bt_run', 'out')


# ------------------------------------------------------------------ 小工具
def e(s):
    return html.escape('' if s is None else str(s), quote=True)


def pctf(x, d=2, sign=True):
    if x is None:
        return '—'
    return (('%+.*f%%' if sign else '%.*f%%') % (d, x * 100))


def numf(x, d=2, sign=False):
    if x is None:
        return '—'
    return ('%+.*f' if sign else '%.*f') % (d, x)


def tone(v):
    """中国习惯：正 = 红，负 = 绿"""
    return 'up' if (v is not None and v >= 0) else 'down'


def tdp(x, d=2, sign=True, bold=False):
    if x is None:
        return '<td class="n">—</td>'
    b = '<b>' if bold else ''
    be = '</b>' if bold else ''
    return '<td class="n %s">%s%s%s</td>' % (tone(x), b, pctf(x, d, sign), be)


def tdp_raw(x, d=2):
    """x 已经是「百分数」单位（如 -5.50 表示 -5.50%），不再乘 100"""
    if x is None:
        return '<td class="n">—</td>'
    return '<td class="n %s">%+.*f%%</td>' % (tone(x), d, x)


def short(n, k=26):
    n = re.sub(r'\s*\(LOF\)', '(LOF)', n or '')
    return n if len(n) <= k else n[:k] + '…'


def legstr(w, order):
    return ' / '.join('%s %d%%' % (k, round(w.get(k, 0) * 100)) for k in order)


def legstr5(w, order):
    return '·'.join('%s%d' % (k[0], round(w.get(k, 0) * 100)) for k in order)


def legstr_list(wv, cols):
    return ' / '.join('%s %d%%' % (cols[i], wv[i]) for i in range(min(len(wv), len(cols))))


# ------------------------------------------------------------------ CSS
CSS = """<style>
*{box-sizing:border-box}
:root{
  --red:#c8102e; --red2:#d8443c; --green:#0f9d58; --ink:#1b1f24; --ink2:#4a5560; --ink3:#7b8794;
  --line:#e3e7ec; --bg:#f4f6f8; --card:#ffffff; --gold:#b8860b;
}
body{margin:0;background:var(--bg);color:var(--ink);
  font:14px/1.65 -apple-system,BlinkMacSystemFont,"Segoe UI","PingFang SC","Microsoft YaHei",sans-serif;
  -webkit-font-smoothing:antialiased}
.wrap{max-width:1200px;margin:0 auto;padding:22px 18px 64px}
h1{font-size:23px;margin:0 0 4px;letter-spacing:.2px}
h2{font-size:17.5px;margin:36px 0 12px;padding-left:11px;border-left:4px solid var(--red);line-height:1.25}
h3{font-size:14.5px;margin:0 0 8px}
h4{font-size:13px;margin:14px 0 6px;color:var(--ink2)}
.lead{color:var(--ink3);font-size:12.5px;margin:0 0 4px}
.disc{background:#fdf3f3;border:1px solid #f3d8d8;border-radius:8px;padding:9px 13px;color:#8a3a3a;font-size:12.3px;margin:12px 0 0}
.card{background:var(--card);border:1px solid var(--line);border-radius:11px;padding:16px 18px;margin:12px 0;
  box-shadow:0 1px 2px rgba(20,30,45,.04)}
.hero{background:linear-gradient(150deg,#fff 0%,#fff 58%,#fff7f7 100%);border:1px solid #f0dfe1;
  border-top:4px solid var(--red);border-radius:12px;padding:18px 20px 16px;margin:14px 0 4px;
  box-shadow:0 2px 10px rgba(200,16,46,.05)}
.hero h2{margin:0 0 4px;border:0;padding:0;font-size:18px}
.hero .concl{font-size:15.5px;color:var(--ink);margin:6px 0 2px}
.hero .pick{font-size:13px;color:var(--ink2);margin:2px 0 12px}
.wgrid{display:grid;grid-template-columns:repeat(5,1fr);gap:9px;margin:10px 0 4px}
.wcell{background:#fbfcfd;border:1px solid var(--line);border-radius:9px;padding:10px 12px;text-align:center}
.wcell .k{font-size:11.5px;color:var(--ink3);letter-spacing:.3px}
.wcell .v{font-size:21px;font-weight:700;margin-top:2px;font-variant-numeric:tabular-nums}
.wcell .s{font-size:10.5px;color:var(--ink3);margin-top:1px}
.kpis{display:grid;grid-template-columns:repeat(5,1fr);gap:9px;margin:12px 0 2px}
.kpi{background:#fbfcfd;border:1px solid var(--line);border-radius:9px;padding:9px 12px}
.kpi .k{font-size:11.5px;color:var(--ink3)}
.kpi .v{font-size:17px;font-weight:700;margin-top:2px;font-variant-numeric:tabular-nums}
.kpi .s{font-size:10.5px;color:var(--ink3);margin-top:1px;line-height:1.4}
.up{color:var(--red2)} .down{color:var(--green)} .neutral{color:var(--ink)}
.big{font-size:15px}
table.grid{width:100%;border-collapse:collapse;font-size:12.4px}
table.grid th{background:#f7f9fb;color:var(--ink2);font-weight:600;text-align:left;padding:8px 7px;
  border-bottom:1.5px solid #e8ecf0;white-space:nowrap}
table.grid td{padding:7px;border-bottom:1px solid #eef1f4;vertical-align:middle}
table.grid tr:hover td{background:#fafbfc}
table.grid tr.hi td{background:#fff6f6;font-weight:600}
table.grid tr.chosen td{background:#f2fbf5}
table.grid tr.dim td{color:#9aa5b1}
table.grid tr.bench td{color:var(--ink2);background:#fafbfc}
td.n,th.n{text-align:right;font-variant-numeric:tabular-nums}
.mono{font-family:ui-monospace,SFMono-Regular,Menlo,Consolas,monospace;color:#3d4a56;font-size:11.8px}
.wrapx{overflow-x:auto;-webkit-overflow-scrolling:touch}
.tag{display:inline-block;font-size:10.5px;padding:1px 7px;border-radius:10px;white-space:nowrap;margin-left:4px}
.t-ok{background:#e8f7ee;color:#0f7a44} .t-warn{background:#fdf4e3;color:#9a6b0a}
.t-bad{background:#fdecec;color:#a52a2a} .t-gray{background:#eef1f4;color:#5a6672}
.note{color:var(--ink3);font-size:12.2px;margin:8px 0 10px;line-height:1.65}
.note b{color:var(--ink2)}
.chart{height:340px;width:100%}
.two{display:grid;grid-template-columns:1fr 1fr;gap:14px}
.three{display:grid;grid-template-columns:repeat(3,1fr);gap:12px}
@media(max-width:900px){.wgrid,.kpis{grid-template-columns:repeat(2,1fr)}.two,.three{grid-template-columns:1fr}}
ol,ul{padding-left:20px;color:#2b333b;font-size:12.8px;margin:6px 0}
li{margin:6px 0}
.foot{margin-top:34px;padding-top:14px;border-top:1px solid var(--line);color:var(--ink3);font-size:12px;line-height:1.7}
.box{border-radius:9px;padding:12px 14px;font-size:12.8px;margin:10px 0}
.box.warn{background:#fffaf0;border:1px solid #f2e2c4;color:#7d5b12}
.box.info{background:#f5f9ff;border:1px solid #dbe7f7;color:#2a4d75}
.box.good{background:#f3fbf6;border:1px solid #d8eee0;color:#186b40}
.box.bad{background:#fdf5f5;border:1px solid #f2dcdc;color:#8a3a3a}
.ask{font-size:15px;font-weight:600;color:var(--red);line-height:1.5;margin:2px 0 10px}
.inline{background:#f7f9fb;border:1px solid var(--line);border-radius:6px;padding:1px 7px;font-family:ui-monospace,Menlo,monospace;font-size:12px}
input#cap{background:#fff;color:var(--ink);border:1px solid #ccd4dc;border-radius:5px;padding:3px 7px;width:74px;font-variant-numeric:tabular-nums}
.legendline{font-size:11.5px;color:var(--ink3);margin-top:6px}
details{margin-top:8px}
summary{cursor:pointer;color:var(--ink2);font-size:12.3px}
</style>"""


# ------------------------------------------------------------------ 各章节
def sec_head(d):
    lead1 = ('数据源：东方财富公开接口（fundmobapi / pingzhongdata / f10 / 腾讯行情）｜'
             '筛选范围：<b>支付宝可申购口径的场外基金</b>，四大类 ETF（国债·黄金·A股科技·能源）')
    lead2 = ('组合区间：%s ~ %s（%d 个交易日）｜权重：5%% 整数倍、单腿 0~40%%、周度调仓｜数据截至 %s ｜生成 %s'
             % (d['range'][0], d['range'][1], d['n_days'], d['asof'], d['gen']))
    return ('<h1>支付宝可申购基金 · 四大类 ETF 智能组合回测与下周操作建议</h1>'
            '<p class="lead">%s</p><p class="lead">%s</p>' % (lead1, lead2))


def sec_disc():
    return ('<div class="disc">本网页为研究用途，不构成任何基金推荐、申购或赎回建议；'
            '回测基于历史净值，不代表未来收益。基金有风险，投资须谨慎。'
            '华泰期货 国际业务部 袁鑫　yuanxin@htfc.com　021-60679262</div>')


def sec_hero(d):
    o = d['feas_order']           # ['能源','债券','黄金','科创']
    lab = d['window_labels']
    ws = d['windows']
    main = ws[0]
    o2 = ['<div class="hero">']
    o2.append('<h2>结论</h2>')
    o2.append('<div class="concl">最优组合：<b style="color:#c8102e">%s</b>'
              '（在 375 组 5%% 整数倍权重里，夏普进入前 10%% 的 %d 组中取年化最高）</div>'
              % (e(legstr({r['cat']: r['cur'] / 100.0 for r in d['wtbl']['rows']}, o)), d['feas_n']))
    ms = d['main_stats']
    o2.append('<div class="pick">区间年化 <b class="%s">%s</b> ｜ 年化波动 %s ｜ 最大回撤 %s ｜ 夏普 <b>%.2f</b> ｜ 卡玛 %.2f '
              '｜ 五窗口中跑赢货基 %d / 5</div>'
              % (tone(ms['ann']), pctf(ms['ann']), pctf(ms['vol'], 2, False), pctf(ms['mdd'], 2, False),
                 ms['sharpe'], ms['calmar'], d['main_over_cash']))
    # 五窗口大格
    o2.append('<div class="wgrid">')
    for i, x in enumerate(main['wr']):
        o2.append('<div class="wcell"><div class="k">%s</div><div class="v %s">%s</div>'
                  '<div class="s">基准日 %s</div></div>'
                  % (e(lab[i]), tone(x), pctf(x), e(d['window_bases'][i])))
    o2.append('</div>')
    o2.append('<div class="legendline">上表＝主推组合在五个窗口的区间收益（已扣再平衡成本）。'
              '跑赢货基的窗口标在下方对照表里。</div>')
    # 对照表
    o2.append('<table class="grid" style="margin-top:10px"><tr><th>组合 / 基准</th>'
              + ''.join('<th class="n">%s</th>' % e(x) for x in lab)
              + '<th class="n">跑赢货基</th></tr>')
    for r in ws:
        cells = ''.join(tdp(x, 2, True) for x in r['wr'])
        oc = r['over_cash']
        octxt = '—' if oc is None else ('%d / 5' % oc)
        occ = 't-ok' if (oc is not None and oc >= 3) else ('t-bad' if (oc is not None and oc <= 2) else 't-gray')
        o2.append('<tr class="%s"><td>%s</td>%s<td class="n"><span class="tag %s">%s</span></td></tr>'
                  % ('hi' if r['cls'] == 'hi' else ('bench' if r['cls'] == 'bench' else ''),
                     e(r['label']), cells, occ, octxt))
    o2.append('</table>')
    # 策略指标
    o2.append('<div class="kpis">')
    for k in d['kpis']:
        o2.append('<div class="kpi"><div class="k">%s</div><div class="v %s">%s</div>'
                  '<div class="s">%s</div></div>' % (e(k['k']), e(k['cls']), e(k['v']), e(k['s'])))
    o2.append('</div>')
    o2.append('<p class="note">规则：%s。'
              '「夏普优先解」＝网格里夏普最高的一组；「收益优先解」＝网格里年化最高的一组。'
              '三个解都在同一份历史、同一成本口径下算出，差别只在目标函数——'
              '本页主推取「先保证夏普进前 10%%、再最大化收益」，是在风险与收益之间取了偏收益的一档。</p>'
              % e(d['rule']))
    o2.append('</div>')
    return '\n'.join(o2)


def sec_next(d):
    o = d['feas_order']
    w = {r['cat']: r['cur'] for r in d['wtbl']['rows']}
    m = d['market']
    ops = d['ops']
    o2 = ['<h2>下周操作建议</h2><section class="card">']
    o2.append('<div class="box bad" style="font-size:13.2px"><b>我的判断（自主观点，不来自回测）：</b><br>'
              + e(m['headline']).replace('**', ''))
    o2.append('</div>')
    # 方向表
    o2.append('<h3>操作方向</h3>')
    o2.append('<div class="wrapx"><table class="grid"><tr><th>腿</th><th>标的</th>'
              '<th class="n">规则权重<br><span class="tag t-gray">回测给出</span></th>'
              '<th>我的执行建议<br><span class="tag t-gray">自主判断</span></th></tr>')
    sugg = {'债券': '一次配到位（减震器，不择时）',
            '能源': '5% → 实际配 10%~15%，分批、逢回调加',
            '黄金': '先配到 25%，余下等 10/28 FOMC 后决定',
            '科创': '先配 10%~15%，余下等三季报与美债方向明朗'}
    for r in d['wtbl']['rows']:
        if r['cat'] == '货基':
            continue
        o2.append('<tr><td><b>%s</b></td><td>%s <span class="mono">%s</span></td>'
                  '<td class="n"><b>%d%%</b></td><td>%s</td></tr>'
                  % (e(r['cat']), e(short(r['name'])), e(r['code']), r['cur'],
                     e(sugg.get(r['cat'], '—'))))
    o2.append('<tr class="bench"><td><b>整仓节奏</b></td><td>—</td><td class="n">—</td>'
              '<td>分 2~3 批、跨度 2~3 周建仓，不要一天买完</td></tr>')
    o2.append('</table></div>')
    # 为什么
    o2.append('<h3 style="margin-top:16px">为什么下周要这样操作</h3>')
    for p in m['why']:
        o2.append('<p class="note" style="font-size:12.8px;color:#2b333b">%s</p>' % e(p))
    # 判断理由来源
    o2.append('<h3 style="margin-top:16px">判断理由来自哪里</h3>')
    o2.append('<ul>' + ''.join('<li>%s</li>' % e(x) for x in m['sources']) + '</ul>')
    o2.append('<div class="box info"><b>规则面的方向（可复现）</b><br>%s</div>' % e(ops['direction']))
    o2.append('<div class="box info" style="margin-top:-2px"><b>规则的自我说明</b><br>%s</div>' % e(ops['narrative']))
    # 何时推翻
    o2.append('<h3 style="margin-top:16px">什么情况会推翻上面的判断</h3>')
    o2.append('<div class="box warn"><ul style="margin:0">'
              + ''.join('<li>%s</li>' % e(x) for x in m['falsify_market']) + '</ul>'
              + '<p class="note" style="margin:8px 0 0">规则层面：%s</p>' % e(ops['falsify']) + '</div>')
    # 日历
    o2.append('<h3 style="margin-top:16px">下周关键日程（北京时间）</h3>')
    o2.append('<table class="grid"><tr><th>时间</th><th>事件</th></tr>'
              + ''.join('<tr><td class="mono">%s</td><td>%s</td></tr>' % (e(a), e(b))
                        for a, b in m['calendar']) + '</table>')
    o2.append('</section>')
    return '\n'.join(o2)


def sec_one(d):
    lis = [
        '候选池来源：名称与类型命中四大类关键词的全部 ETF 及其场外联接份额（东财 FundType ∈ {3,4,6,8} 的并集）。'
        '场内 ETF 支付宝买不到，因此组合只用<b>场外可申购的联接份额</b>。',
        '可申购判定：东财申购状态字段——「开放申购」与「限大额」计入可申购；'
        '「暂停申购 / 封闭期 / 认购期」与「场内交易」不计入（场内 ETF 单独折叠列表备查）。',
        '收益口径：使用逐日净值增长率累乘为总收益指数，已含分红再投资；基金净值本身已扣除管理费与托管费，'
        '故回测只再扣「优惠申购费 + 持有满 7 天赎回费」。',
        '货币基金没有净值序列，用官方「每万份收益」累乘重建曲线（份额净值恒 1 元、无回撤）。',
        '官方字段口径：SYL_1N/3N/5N 为区间累计（非年化，本页 3 年列已年化）；MAXSG ≥ 1e10 视为不限额度；'
        '净值日期为官方最新披露日。',
        '口径交叉校验：自算近 1 年收益与官方 SYL_1N 交叉核对，偏差中位数 %s、90 分位 %s。' % (CROSS[0], CROSS[1]),
        '数据来源：东财 fundmobapi（申购状态 / 单日限额 / 起购 / 优惠费率 / 管理+托管+销服费 / 跟踪指数 / 阶段收益）'
        '+ 天天基金 f10 费率页 + 天天基金逐日净值序列 + 腾讯行情（场内现价、折溢价）。',
        '评价维度：官方星级评级页由 JS 动态加载、数据源端无可用接口（已实测），'
        '故改用「官方夏普 + 跟踪误差 + 成立年限」合成，规则公开可复核。',
    ]
    o = ['<h2>一、数据源与筛选范围</h2><section class="card">']
    o.append('<h3>这一版的候选池有多大（本次抓取口径）</h3>')
    o.append('<div class="wrapx"><table class="grid"><tr><th>层级</th><th class="n">数量</th><th>说明</th></tr>'
             + ''.join('<tr><td>%s</td><td class="n">%s</td><td>%s</td></tr>' % (e(a), e(b), c)
                       for a, b, c in POOL) + '</table></div>')
    o.append('<p class="note">抓取当日（%s）官方申购状态分布：%s。'
             '组合只从「开放申购 / 限大额」的场外份额里选。</p>'
             % (e(d['asof']), '；'.join('%s %d 只' % (k, v) for k, v in POOL_STAT)))
    o.append('<h3 style="margin-top:14px">口径说明</h3><ul>'
             + ''.join('<li>%s</li>' % x for x in lis) + '</ul></section>')
    return '\n'.join(o)


def sec_two(d):
    rule = [('规模 AUM', '30', '类内对数规模线性归一：该类最大者 30 分，最小者 0 分'),
            ('费率·交易', '15', '申购费（第三方优惠费率）+ 持有满 7 天赎回费；合计 0% 满分，≥1.2% 得 0 分'),
            ('费率·持有', '10', '管理费 + 托管费 + 销售服务费（年化）；≤0.15% 满分，≥1.0% 得 0 分'),
            ('认购 / 申购额度', '25', '开放申购不限额度 25 / 场内可交易 22 / 单日上限 ≥100 万 18 / '
                                  '1 万~100 万 12 / 小于 1 万 6 / 暂停 0'),
            ('评价', '20', '官方近 1 年夏普（类内排名 50%）+ 跟踪误差（30%）+ 成立年限（≥5 年满分 20%）')]
    tbl = ''.join('<tr><td>%s</td><td class="n">%s</td><td>%s</td></tr>' % r for r in rule)
    o = ['<h2>二、筛选标准</h2><section class="card">']
    o.append('<h3>四项 100 分口径（AUM 大 / 认购赎回费低 / 无认购金额限制 / 评价好）—— 用于债券 / 黄金 / 能源</h3>')
    o.append('<p class="note">每只候选按四项打分（满分 100）。下表只列<b>场外可申购</b>的候选（场内 ETF 支付宝买不到，'
             '不进这张表，第三章有折叠对照表），绿底行＝该类实际选用。</p>')
    o.append('<table class="grid"><tr><th>维度</th><th class="n">满分</th><th>打分规则</th></tr>' + tbl + '</table>')
    o.append('<p class="note">「评价」口径说明：天天基金 / 招商证券的星级评级页由 JS 动态加载、数据源端无可用接口（已实测），'
             '故该维度改用风险调整后收益（官方夏普）+ 跟踪误差 + 成立年限三项可追溯指标合成。</p>')
    for cat in ('债券', '黄金', '能源'):
        rows = d['scores'].get(cat) or []
        if not rows:
            continue
        trs = []
        for r in rows:
            cls = ' class="chosen"' if r['hold'] else (' class="dim"' if r['isexchg'] else '')
            buy = '—' if r.get('isexchg') else (r['buy'] or '—')
            red = '—' if r.get('isexchg') else (('%.2f%%' % r['red']) if r['red'] is not None else '—')
            trs.append('<tr%s><td class="mono">%s</td><td>%s</td><td>%s</td><td class="n">%.2f</td>'
                       '<td class="n">%s</td><td class="n">%s</td><td class="n">%.2f%%</td>'
                       '<td>%s</td><td class="n">%.1f</td><td class="n">%.1f</td>'
                       '<td class="n">%.1f</td><td class="n">%.1f</td><td class="n"><b>%.1f</b></td></tr>'
                       % (cls, e(r['code']), e(r['name']), e(r['form']), r['scale'] or 0,
                          e(buy), e(red), r['holdfee'], e(r['quota']),
                          r['s_scale'], r['s_fee'], r['s_quota'], r['s_eval'], r['total']))
        o.append('<h3 style="margin-top:16px">%s —— 打分明细（场外可申购总分前 10）</h3>' % e(cat))
        o.append('<div class="wrapx"><table class="grid"><tr><th>代码</th><th>基金名称</th><th>形态</th>'
                 '<th class="n">规模<br>亿元</th><th class="n">申购费<br>优惠</th>'
                 '<th class="n">赎回费<br>满7天</th><th class="n">年费率<br>管+托+销</th>'
                 '<th>申购额度（官方）</th><th class="n">规模30</th><th class="n">费率25</th>'
                 '<th class="n">额度25</th><th class="n">评价20</th><th class="n">总分</th></tr>'
                 + ''.join(trs) + '</table></div>')
    a = d['astock']
    o.append('<h3 style="margin-top:18px">A股 / 科创腿：以年化收益率为核心的 120 分口径（候选 %d 只，场外选用 '
             '<span class="mono">%s</span> %s）</h3>'
             % (a['n_all'], e(a['hold'] or '—'), e(a['holdname'] or '')))
    o.append('<p class="note">排序口径＝年化收益率（占 70 分，取近 2 年净值年化）＋规模 15 / 费率 10 / 评价 5，'
             '并给科创 / 科技类加分（科创板系列 20 分、其他芯片半导体人工智能 10 分）；只保留成立满 2.5 年以上的标的。'
             '场内第一名为 <span class="mono">%s</span>，其对应场外联接为 <span class="mono">%s</span>。</p>'
             % (e(a['picked_inst']), e(a['picked_off'] or '—')))
    trs = []
    for r in a['rows']:
        cls = ' class="chosen"' if r['hold'] else ('' if r['form'] == '场外' else ' class="dim"')
        trs.append('<tr%s><td class="mono">%s</td><td>%s</td><td>%s</td><td class="n">%.2f</td>'
                   '<td class="n">%+.2f%%</td><td class="n">%+.2f%%</td><td class="n">%.2f%%</td>'
                   '<td class="n">%.2f%%</td><td class="n">%.2f</td><td class="n">+%.0f</td>'
                   '<td class="n">%.1f</td><td class="n">%.1f</td><td class="n">%.1f</td>'
                   '<td class="n"><b>%.1f</b></td></tr>'
                   % (cls, e(r['code']), e(r['name']), e(r['form']), r['scale'] or 0,
                      r['ann2'] * 100, r['annall'] * 100, r['vol'] * 100, r['mdd'] * 100,
                      r['sharpe'], r['bonus'], r['s_scale'], r['s_fee'], r['s_eval'], r['total']))
    o.append('<div class="wrapx"><table class="grid"><tr><th>代码</th><th>基金名称</th><th>形态</th>'
             '<th class="n">规模亿元</th><th class="n">年化<br>近2年</th><th class="n">成立以来<br>年化</th>'
             '<th class="n">年化波动</th><th class="n">最大回撤</th><th class="n">夏普</th>'
             '<th class="n">科创加分</th><th class="n">规模分</th><th class="n">费率分</th>'
             '<th class="n">评价分</th><th class="n">总分</th></tr>' + ''.join(trs) + '</table></div>')
    o.append('<p class="note">合计满分 120 分。本页只做场外可买的组合，因此本腿选用的是场外联接份额'
             '（场内 ETF 仅作对照，需要券商账户）。</p></section>')
    return '\n'.join(o)


def sec_three(d):
    o = ['<h2>三、四大类筛选明细</h2>']
    desc = {'债券': '只纳入利率债 / 综合债 ETF 及其联接（国债、政金债、国开债、信用债、公司债、城投债、短融）；'
                  '可转债与海外债不计入。',
            '黄金': '纳入跟踪上海金 / 黄金 9999 的场内 ETF 及其联接，以及黄金主题 QDII；'
                  '白银、黄金股、有色不计入。',
            '能源': '纳入煤炭 / 石油 / 油气 / 天然气等传统能源指数基金及联接；'
                  '新能源车、光伏、储能等成长主题不计入。'}
    for cat in ('债券', '黄金', '能源'):
        v = d['cats'][cat]
        o.append('<section class="card"><h3>%sETF 候选 %d 只｜场外可申购 %d 只｜组合持有（场外）'
                 '<span class="mono">%s</span> %s</h3>'
                 % (e(cat), v['n_all'], v['n_off'], e(v['hold'] or '—'), e(v['holdname'] or '')))
        o.append('<p class="note">%s（下表按规模降序，最多列 %d 只）</p>' % (e(desc[cat]), len(v['rows'])))
        trs = []
        for r in v['rows']:
            cls = ' class="chosen"' if r['hold'] else ('' if r['sgzt'] in ('开放申购', '限大额') else ' class="dim"')
            cells = [
                '<td class="mono">%s</td>' % e(r['code']),
                '<td>%s</td>' % e(r['name']),
                '<td class="n">%s</td>' % (numf(r['scale']) if r['scale'] is not None else '—'),
                '<td>%s</td>' % e(r['quota']),
                '<td class="n">%s</td>' % e(r['buy'] if r['buy'] not in (None, '--') else '—'),
                '<td class="n">%s</td>' % (('%+.2f%%' % r['syl1']) if r['syl1'] is not None else '—'),
                '<td class="n">%s</td>' % (('%+.2f%%' % r['syl3a']) if r['syl3a'] is not None else '—'),
                '<td class="n">%s</td>' % (('%+.2f%%' % r['sylall']) if r['sylall'] is not None else '—'),
                '<td class="n">%s</td>' % (('%.2f%%' % (r['vol'] * 100)) if r['vol'] is not None else '—'),
                '<td class="n">%s</td>' % (('%.2f%%' % (r['mdd'] * 100)) if r['mdd'] is not None else '—'),
                '<td class="n">%s</td>' % (numf(r['sharpe']) if r['sharpe'] is not None else '—'),
                '<td class="n">%s</td>' % (('%.2f%%' % (r['holdfee'] * 100)) if r['holdfee'] else '—'),
                '<td class="mono">%s</td>' % e(r['navdate']),
            ]
            trs.append('<tr%s>%s</tr>' % (cls, ''.join(cells)))
        o.append('<div class="wrapx"><table class="grid"><tr><th>代码</th><th>基金名称</th>'
                 '<th class="n">规模</th><th>申购条件（官方：单日限额 / 起购）</th><th class="n">申购费</th>'
                 '<th class="n">近1年<br>官方</th><th class="n">近3年年化<br>官方</th>'
                 '<th class="n">成立以来<br>官方</th><th class="n">年化波动<br>自算</th>'
                 '<th class="n">最大回撤</th><th class="n">夏普</th><th class="n">年费率</th>'
                 '<th>净值日期</th></tr>' + ''.join(trs) + '</table></div>')
        if v['inst']:
            irs = []
            for r in v['inst']:
                prem = '—' if r['prem'] is None else ('<span class="%s">%+.2f%%</span>'
                                                      % ('up' if r['prem'] > 0 else 'down', r['prem'] * 100))
                irs.append('<tr class="dim"><td class="mono">%s</td><td>%s</td><td class="n">%.2f</td>'
                           '<td class="n">%s</td><td class="n">%s</td><td class="n">%s</td>'
                           '<td class="n">%s</td><td class="n">%s</td></tr>'
                           % (e(r['code']), e(r['name']), r['scale'] or 0,
                              numf(r['price'], 3), numf(r['nav'], 4), prem,
                              e(('%+.2f%%' % r['syl1']) if r['syl1'] is not None else '—'),
                              e(('%+.2f%%' % r['syl3a']) if r['syl3a'] is not None else '—')))
            o.append('<details><summary>仅场内交易（支付宝不可直接申购，需券商账户）规模前 6，含实时折溢价</summary>'
                     '<div class="wrapx"><table class="grid"><tr><th>代码</th><th>名称</th><th class="n">规模</th>'
                     '<th class="n">现价</th><th class="n">单位净值</th><th class="n">折溢价</th>'
                     '<th class="n">近1年</th><th class="n">近3年年化</th></tr>'
                     + ''.join(irs) + '</table></div></details>')
            o.append('<p class="note">折溢价 =（场内现价 − 最新披露单位净值）/ 最新披露单位净值，<b>非 IOPV</b>；'
                     'QDII 净值滞后 1–2 个交易日。行情来源：腾讯行情。</p>')
        o.append('</section>')
    return '\n'.join(o)


def sec_four(d):
    o = ['<h2>四、组合回测（周度调仓 · 权重取 5% 整数倍）</h2><section class="card">']
    o.append('<h3>回测设定</h3><ul>')
    o.append('<li>组合（场外可执行 · 支付宝可买）：%s</li>'
             % '、'.join('%s %s（%s）' % (e(a['cat']), e(a['name']), e(a['code'])) for a in d['assets']))
    o.append('<li>区间：%s ~ %s（%d 个交易日）；再平衡：<b>每周最后一个交易日</b>按目标权重调回；'
             '成本：按逐腿实际「优惠申购费 + 持有满 7 天赎回费」扣减；分红：按净值增长率复权（含分红再投资）。</li>'
             % (d['range'][0], d['range'][1], d['n_days']))
    o.append('<li>权重：<b>5% 的整数倍（0/5/10/…/40%），合计 100%</b>。基准：沪深300（510300 净值代理）、'
             '货币基金（天弘余额宝 000198）。</li></ul>')
    trs = []
    for a in d['assets']:
        st = a['stats']
        trs.append('<tr><td>%s</td><td class="mono">%s</td><td>%s</td>%s%s%s'
                   '<td class="n">%.2f%%</td><td class="n">%.2f%%</td><td class="n">%.2f</td>%s</tr>'
                   % (e(a['cat']), e(a['code']), e(short(a['name'])),
                      tdp(a['wr'][0]), tdp(a['wr'][1]), tdp(a['wr'][2]),
                      st['vol'] * 100, st['mdd'] * 100, st['sharpe'], tdp(a['wr'][4])))
    o.append('<h4>四条腿的区间表现（同一区间自算，保证可比）</h4>')
    o.append('<div class="wrapx"><table class="grid"><tr><th>类别</th><th>代码</th><th>基金名称</th>'
             '<th class="n">上周</th><th class="n">近一月</th><th class="n">近三月</th>'
             '<th class="n">年化波动</th><th class="n">最大回撤</th><th class="n">夏普</th>'
             '<th class="n">近2年</th></tr>' + ''.join(trs) + '</table></div>')
    o.append('<p class="note">这张表解释了主推权重为什么长这样：债券是唯一「任何窗口都为正、波动只有几个百分点」的腿，'
             '所以它几乎每期都被顶到上限附近；黄金与科创的<b>近 2 年</b>收益最高（%s、%s），所以长期夏普与收益都靠它们；'
             '但它们同时也是近期回撤最深的腿（近三月 %s、%s）。'
             % (pctf(next(a for a in d['assets'] if a['cat'] == '黄金')['wr'][4]),
                pctf(next(a for a in d['assets'] if a['cat'] == '科创')['wr'][4]),
                pctf(next(a for a in d['assets'] if a['cat'] == '科创')['wr'][2]),
                pctf(next(a for a in d['assets'] if a['cat'] == '能源')['wr'][2])) + '</p>')
    # 网格散点
    o.append('<h4>375 组权重网格：风险—收益全样本</h4>')
    o.append('<div id="c2" class="chart" style="height:380px"></div>')
    o.append('<p class="note">每个点＝一组权重（375 组）。横轴＝年化波动，纵轴＝年化收益，颜色＝夏普比率。'
             '<b>★</b> 为主推，▲ 为夏普优先解，◆ 为收益优先解。'
             '所有点里最靠左上的是卡玛最优解，不一定夏普最高——这就是为什么必须先把目标函数说清楚。</p>')
    # 门槛内候选
    o.append('<h4>过门槛的 %d 组解（按年化收益降序，列前 %d 组）</h4>'
             % (d['feas_n'], len(d['feas'])))
    lab = d['window_labels']
    o.append('<div class="wrapx"><table class="grid"><tr><th>权重（能源/债券/黄金/科创）</th>'
             '<th class="n">年化</th><th class="n">年化波动</th><th class="n">最大回撤</th>'
             '<th class="n">夏普</th><th class="n">卡玛</th>'
             + ''.join('<th class="n">%s</th>' % e(x) for x in lab)
             + '<th class="n">跑赢货基</th></tr>')
    for r in d['feas']:
        st = r['stats']
        o.append('<tr class="%s"><td class="mono">%s</td>%s%s%s<td class="n">%.2f</td><td class="n">%.2f</td>%s'
                 '<td class="n">%d/5</td></tr>'
                 % ('hi' if r['main'] else '', e(r['wstr']),
                    tdp(st['ann'], 2, False), tdp(st['vol'], 2, False), tdp(st['mdd'], 2, False),
                    st['sharpe'], st['calmar'],
                    ''.join(tdp(x, 2, True) for x in r['wr']), r['over_cash']))
    o.append('</table></div>')
    o.append('<p class="note">门槛内共 %d 组；主推就是其中年化最高的一组（红底行）。'
             '可以看到它们大多是「债券 25%%–40%% + 黄金 25%%–40%%」的骨架，能源与科创在 0%%–30%% 之间做微调。</p>'
             % d['feas_n'])
    # 方案对比
    o.append('<h4>算法权重方案对比（同一区间、同一成本、周度调仓）</h4>')
    trs = []
    for w in d['wavg']:
        st = w['stats']
        trs.append('<tr%s><td>%s%s</td><td class="mono">%s</td>%s%s%s<td class="n">%.2f</td>'
                   '<td class="n">%.2f</td><td class="n">%.0f%%</td><td class="n">%.2f%%</td></tr>'
                   % (' class="hi"' if w['main'] else '', e(w['scheme']), ' ★' if w['main'] else '',
                      e(legstr({k: v for k, v in zip(['能源', '债券', '黄金', '科创'], w['w'])},
                               ['能源', '债券', '黄金', '科创'])),
                      tdp(st['ann'], 2, False), tdp(st['vol'], 2, False), tdp(st['mdd'], 2, False),
                      st['sharpe'], st['calmar'], w['turnover'] * 100, w['cost'] * 100))
    o.append('<div class="wrapx"><table class="grid"><tr><th>方案</th><th>目标权重</th>'
             '<th class="n">年化收益</th><th class="n">年化波动</th><th class="n">最大回撤</th>'
             '<th class="n">夏普</th><th class="n">卡玛</th><th class="n">年换手</th>'
             '<th class="n">年成本</th></tr>' + ''.join(trs) + '</table></div>')
    # 频率
    trs = []
    for f in d['freqs']:
        st = f['stats']
        trs.append('<tr><td>%s</td>%s%s%s<td class="n">%.2f</td><td class="n">%.0f%%</td>'
                   '<td class="n">%.2f%%</td></tr>'
                   % (e(f['label']), tdp(st['ann'], 2, False), tdp(st['vol'], 2, False),
                      tdp(st['mdd'], 2, False), st['sharpe'], f['turnover'] * 100, f['cost'] * 100))
    o.append('<h4>再平衡频率对比（按 ★ 主推权重）</h4>')
    o.append('<table class="grid"><tr><th>频率</th><th class="n">年化收益</th><th class="n">年化波动</th>'
             '<th class="n">最大回撤</th><th class="n">夏普</th><th class="n">年换手</th>'
             '<th class="n">年成本</th></tr>' + ''.join(trs) + '</table>')
    # 净值曲线
    o.append('<h4>净值曲线（起点归一为 1）</h4>')
    o.append('<div id="c1" class="chart"></div>')
    # 相关性
    cm = d['corr']
    trs = []
    for i, nm in enumerate(cm['cats']):
        trs.append('<tr><td>%s</td>%s</tr>' % (e(nm),
                   ''.join('<td class="n">%.2f</td>' % cm['m'][i][j] for j in range(len(cm['cats'])))))
    o.append('<h4>成分相关性（日收益）</h4>')
    o.append('<table class="grid"><tr><th>—</th>%s</tr>%s</table>'
             % (''.join('<th>%s</th>' % e(x) for x in cm['names']), ''.join(trs)))
    mx = max(abs(cm['m'][i][j]) for i in range(4) for j in range(4) if i != j)
    o.append('<p class="note">四类资产两两相关性最高仅 %.2f（绝对值），这是组合夏普显著高于单资产的根本原因：'
             '债券与 A 股科技负相关（股债跷跷板），黄金与其余三条腿几乎不相关。</p></section>' % mx)
    return '\n'.join(o)


def sec_bt(d):
    """用 bt-etf-backtest 技能做的独立引擎复算（第五章）"""
    o = ['<h2>五、独立引擎复算：pmorissette/bt（本技能用在哪）</h2><section class="card">']
    o.append('<div class="box info"><b>这一章由 bt-etf-backtest 技能产出。</b>'
             '主管线（第四、六章）用的是自研的纯 Python 周度回测；这里换成第三方权重型回测引擎 '
             '<span class="inline">pmorissette/bt 1.4.1</span>，'
             '用<b>场内 ETF 前复权价</b>作为四条腿的代理（支付宝买不到场内 ETF，仅作价格代理），'
             '单边佣金 2.5bp，跑两件事：<br>'
             '① <b>六套经典算法横评</b>——买入持有 / 等权 / 固定权重 / 逆波动率 / 风险平价 ERC / 双动量 Top2；<br>'
             '② <b>5% 整数倍权重网格独立复算</b>——与主管线同样的 375 组、单腿 0~40%、周度再平衡，'
             '看换一个引擎、换一套标的会不会改变结论。</div>')
    if not BT_OK:
        o.append('<div class="box warn">本次未取到 bt 引擎产物（脚本未运行完成），本章仅保留说明。</div></section>')
        return '\n'.join(o)
    # 六策略指标
    o.append('<h4>① 六套经典算法（区间 %s ~ %s，单边佣金 %.1f bp）</h4>'
             % (e(BT['metrics_range'][0]), e(BT['metrics_range'][1]), BT['comm_bp']))
    o.append('<div class="wrapx"><table class="grid"><tr><th>策略</th><th class="n">累计收益</th>'
             '<th class="n">年化收益</th><th class="n">年化波动</th><th class="n">夏普</th>'
             '<th class="n">最大回撤</th><th class="n">卡玛</th><th class="n">年化换手</th></tr>'
             + ''.join('<tr><td>%s</td>' % e(r['name']) + tdp(r['tot'], 2, False) + tdp(r['ann'], 2, False)
                       + '<td class="n">%.2f%%</td><td class="n">%.2f</td>'
                       % (r['vol'] * 100, r['sharpe']) + tdp(r['mdd'], 2, False)
                       + '<td class="n">%.2f</td><td class="n">%.0f%%</td></tr>'
                       % (r['calmar'], r['turnover'] * 100) for r in BT['metrics'])
             + '</table></div>')
    o.append('<p class="note">bt 引擎给出的答案很直接：<b>逆波动率的夏普最高（%.2f），但它几乎不赚钱（年化 %.2f%%）；'
             '双动量 Top2 年化最高（%.2f%%），但波动 %.1f%%、换手 %.0f%%/年、回撤 %.1f%%</b>。'
             '这正是本页选择「固定权重网格 + 周度调仓」而不是「自动调权算法」的原因：'
             '前者的权重是<b>人能看懂、能下单、能复现</b>的（四条腿、5%% 整数倍），'
             '后者的权重每周都在算，实际执行成本与偏差都会吃掉回测里的优势。</p>'
             % (next(r['sharpe'] for r in BT['metrics'] if '逆波动' in r['name']),
                next(r['ann'] * 100 for r in BT['metrics'] if '逆波动' in r['name']),
                next(r['ann'] * 100 for r in BT['metrics'] if '双动量' in r['name']),
                next(r['vol'] * 100 for r in BT['metrics'] if '双动量' in r['name']),
                next(r['turnover'] * 100 for r in BT['metrics'] if '双动量' in r['name']),
                next(r['mdd'] * 100 for r in BT['metrics'] if '双动量' in r['name'])))
    o.append('<div id="c5" class="chart"></div>')
    o.append('<p class="note">六套策略的净值曲线（bt 引擎，月度再平衡）。</p>')
    # 5% 网格
    if BT.get('grid5'):
        g = BT['grid5']
        o.append('<h4>② 5%% 整数倍权重网格独立复算（%d 组，周度再平衡，%s ~ %s）</h4>'
                 % (g['n'], e(g['range'][0]), e(g['range'][1])))
        o.append('<div id="c6" class="chart" style="height:380px"></div>')
        rows = []
        for tag, rec in (('夏普最高', g['best_sharpe']), ('年化最高', g['best_ann']),
                         ('卡玛最高', g['best_calmar']), ('门槛内年化最高（与主管线同规则）', g['pick'])):
            rows.append('<tr><td>%s</td><td class="mono">%s</td>%s%s%s<td class="n">%.2f</td>'
                        '<td class="n">%.2f</td></tr>'
                        % (e(tag), e(legstr_list(rec['w'], g['cols'])),
                           tdp(rec['ann'], 2, False), tdp(rec['vol'], 2, False),
                           tdp(rec['mdd'], 2, False), rec['sharpe'], rec['calmar']))
        o.append('<div class="wrapx"><table class="grid"><tr><th>目标</th><th>权重（%s）</th>'
                 '<th class="n">年化</th><th class="n">年化波动</th><th class="n">最大回撤</th>'
                 '<th class="n">夏普</th><th class="n">卡玛</th></tr>%s</table></div>'
                 % (e('/'.join(g['cols'])), ''.join(rows)))
        o.append('<p class="note"><b>对照结论（一字不改地写清一致与不一致）：</b><br>'
                 '① <b>一致的部分</b>：两侧都把大头压在<b>债券 + 黄金</b>两条腿上（合计 60%~80%），'
                 '且都认为「黄金权重接近上限」——换引擎、换标的、换成本模型之后，这一点没变。<br>'
                 '② <b>不一致的部分</b>：剩下那 20%~40% 给了谁，两边相反。主管线（场外口径）给<b>科创 30%</b>、'
                 '能源只给 5%；bt 侧（场内口径）反过来，给 <b>能源 35%</b>、科创只给 5%。'
                 '<b>这不是引擎差异，是标的差异</b>——主管线的能源腿是中证煤炭指数（单一行业、区间年化波动 25.9%），'
                 'bt 侧的能源代理要用同指数的 ETF 才对得上（能源 ETF 的成分股占比不到 50%，含油气与综合能源）；'
                 '主管线的科创腿是科创板芯片（半导体高度集中），bt 侧是科创 50ETF（更宽）。'
                 '同一条腿的底层指数不同，最优权重自然会换位——这正是该技能里写明的注意事项。<br>'
                 '③ 数字不可逐位对读：区间（主管线 2023-10-16 起 / bt 侧 2022-01-17 起）、价格口径'
                 '（场外净值 vs 场内前复权价）、成本模型（申赎费 vs 单边 2.5bp 佣金）都不同。'
                 '这一章的价值不是「验证出同样的数字」，而是<b>验证出同样的骨架、并把分歧归因到标的而不是引擎</b>。</p>')
    # 六套策略权重演变
    if BT.get('weight_names'):
        o.append('<h4>③ 算法权重的演变（bt 引擎自动调权）</h4>')
        o.append('<p class="note">逆波动率、风险平价 ERC、双动量 Top2 三条算法在 2022-01 ~ 2026-10 里给出的权重轨迹：'
                 '逆波动率几乎全程把一半以上压在债券上（所以年化波动只有 %.1f%%）；'
                 '双动量 Top2 则会在四条腿之间大幅切换（年换手 %.0f%%），'
                 '这正是「自动化算法在纸面上赢、在账户里难执行」的典型样子。</p>'
                 % (next(r['vol'] * 100 for r in BT['metrics'] if '逆波动' in r['name']),
                    next(r['turnover'] * 100 for r in BT['metrics'] if '双动量' in r['name'])))
    o.append('</section>')
    return '\n'.join(o)


def sec_six(d):
    wh = d['charts']['wh']
    w = d['wtbl']
    weeks = WT_WEEKS
    offs = [('当前', -1), ('1 周前', -2), ('1 个月前', -5), ('3 个月前', -14), ('6 个月前', -27), ('1 年前', -52)]
    trs = []
    for lab, i in offs:
        r = weeks[i]
        wtxt = '／'.join('%s %d%%' % (k, r['w'][k]) for k in D_ORDER)
        trs.append('<tr><td>%s</td><td class="mono">%s</td><td>%s</td>'
                   '<td class="n">%s</td><td class="n">%.2f</td>%s%s%s<td class="n">%d/5</td></tr>'
                   % (e(lab), e(r['date']), e(wtxt),
                      ('%+.2f%%' % (r['ann'] * 100)) if r['ann'] is not None else '—',
                      r['sharpe'] if r['sharpe'] is not None else 0.0,
                      tdp_raw(r['wr'][0]), tdp_raw(r['wr'][1]), tdp_raw(r['wr'][2]),
                      r.get('over_cash', 0)))
    o = ['<h2>六、近一年权重变化（每周按同一规则重算 · 52 周）</h2><section class="card">']
    o.append('<h3>怎么算出来的</h3>')
    o.append('<p class="note">把上面的规则（5%% 整数倍网格、单腿 0~40%%；<b>每周</b>在该周网格里取「夏普前 10%% 门槛内'
             '年化收益最高」的一组）在过去 %d 周里逐周重跑一遍，每周只用「截至那一周」的数据'
             '——所以这是规则在当时会给出的目标权重，不是实际持仓，也不是事后挑出来的最优权重。'
             '所有样本周的回测起点都相同（数据起点 %s），因此与当期口径完全一致'
             '（当期那一周的结果与主推逐位相同，脚本里有硬断言）。</p>' % (wh['n'], d['range'][0]))
    o.append('<h4>每周目标权重</h4><div id="c3" class="chart" style="height:360px"></div>')
    o.append('<p class="note">柱状图：每周一根柱，四段＝四条腿的目标权重。近一年共 %d 周，'
             '其中权重相对上一周出现 ≥10pp 跳变的周有 <b>%d 周</b>——也就是说，这套规则的权重并不是「一个月调一次」，'
             '而是结构性地在债券与黄金之间来回切。</p>' % (wh['n'], d['wt_jumps']))
    o.append('<div id="c4" class="chart" style="height:330px"></div>')
    o.append('<p class="note">折线图：每条腿的权重轨迹（阶梯线）。两条线交叉的位置，就是规则把权重从一条腿搬到另一条腿的那一周。</p>')
    o.append('<h4>关键时点快照</h4>')
    o.append('<table class="grid"><tr><th>时点</th><th>日期</th><th>权重（%s）</th>'
             '<th class="n">年化<br><span class="tag t-gray">截至该周</span></th><th class="n">夏普</th>'
             '<th class="n">上周</th><th class="n">近一月</th><th class="n">近三月</th>'
             '<th class="n">跑赢货基</th></tr>%s</table>' % ('／'.join(D_ORDER), ''.join(trs)))
    o.append('<p class="note">直接回答「一个月前和三个月前一样吗」：<b>不完全一样，但骨架稳定在债券 + 黄金上</b>。'
             '能源与科创的权重在 0%~30% 之间漂移，它们决定短窗口的胜负；债券与黄金合计常年占 60%~80%，'
             '组合的波动率主要由这两条腿决定。</p>')
    o.append('</section>')
    return '\n'.join(o)


def sec_orders(d):
    o = d['orders']
    rows = []
    for r in o['A']:
        cls = ' class="bench"' if r.get('bench') else ''
        fee = '<td class="n">—</td>' if r['fee'] is None else \
              '<td class="n" data-money="%.2f">%.2f</td>' % (r['fee'], r['fee'])
        rows.append('<tr%s><td>%s · %s <span class="mono">%s</span></td>'
                    '<td class="n">%s<br><span class="tag t-gray">%s</span></td><td class="n">%d%%</td>'
                    '<td class="n" data-money="%.2f">%.2f</td>%s'
                    '<td class="n"><b data-unit="%.2f">%.2f</b></td></tr>'
                    % (cls, e(r['cat']), e(short(r['name'])), e(r['code']),
                       numf(r['nav'], 4), e(r['navdate']), r['w'], r['money'], r['money'],
                       fee, r['units'], r['units']))
    tblA = ('<div class="wrapx"><table class="grid"><tr><th>类别 · 基金（代码）</th>'
            '<th class="n">最新净值<br><span class="tag t-gray">净值日</span></th><th class="n">目标权重</th>'
            '<th class="n">申购金额</th><th class="n">申购费</th><th class="n">买入份额</th></tr>'
            + ''.join(rows) + '</table></div>')
    rowsB = []
    for r in o['B']:
        rowsB.append('<tr><td>%s · %s <span class="mono">%s</span></td><td class="n">%d%% → %d%%</td>'
                     '<td>%s</td><td class="n" data-money="%.2f">%.2f</td>'
                     '<td class="n" data-unit="%.2f">%.2f</td></tr>'
                     % (e(r['cat']), e(short(r['name'])), e(r['code']), r['prev'], r['cur'], e(r['act']),
                        r['money'], r['money'], r['units'], r['units']))
    tblB = ('<div class="wrapx"><table class="grid"><tr><th>类别 · 基金（代码）</th><th class="n">一个月前 → 本期</th>'
            '<th>动作</th><th class="n">金额</th><th class="n">份额</th></tr>' + ''.join(rowsB) + '</table></div>')
    legs_desc = legstr({r['cat']: r['cur'] / 100.0 for r in d['wtbl']['rows']}, D_ORDER)
    fee_desc = '、'.join('%s %s' % (a['cat'], ('%.2f%%' % (a['buy'] * 100)) if a['buy'] else '0（免申购费）')
                       for a in d['assets'])
    return ('<section class="card"><h3>下单清单（按最新净值折算份数）'
            '<span class="tag t-gray">本金 <input id="cap" value="10000" size="6"> 元，可直接改，表格自动重算</span></h3>'
            '<p class="note">下方所有金额与份额都按 <b><span id="capshow">10000</span> 元</b>本金折算；'
            '目标权重取本页主推（%s）。</p>'
            '<h4>A. 若现在资金全在货币基金——建仓清单</h4>%s'
            '<p class="note">四条腿合计下单 <b>%.2f</b> 元，其中申购费 <b>%.2f</b> 元，'
            '<b>实际买入市值 %.2f 元</b>。结合上面的自主判断，建议分 2~3 批建仓。</p>'
            '<h4>B. 若已按一个月前的权重持有——调整清单</h4>%s'
            '<p class="note">口径：净值取最新披露的单位净值（场外基金按 T 日净值确认份额；货币基金份额净值恒 1 元）。'
            '申购份额＝申购金额 ÷ (1+优惠申购费率) ÷ 净值；<b>申购填金额、赎回填份额</b>，'
            '份额确认到 0.01 份，实际成交会有几分钱尾差。费率：%s。'
            '申购费<b>已含在金额里</b>（不是「剩余现金」）——写法是「合计下单 X 元，其中费用 Y 元，实际买入市值 X−Y 元」。</p>'
            '</section>'
            % (e(legs_desc), tblA, o['total_money'], o['total_fee'], o['buy_value'], tblB, fee_desc))


def sec_seven(d):
    return ('<h2>七、回测局限与风险提示</h2><section class="card"><div class="box warn"><ul style="margin:0">'
            + ''.join('<li>%s</li>' % e(x) for x in d['limits']) + '</ul></div></section>')


def sec_eight(d):
    """策略说明：为什么这么做 + 哪些部分用了 bt-etf-backtest"""
    o = ['<h2>八、这套策略为什么这样做 · 以及本技能用在哪</h2><section class="card">']
    o.append('<h3>A. 我为什么采用这套策略</h3><ol>')
    o.append('<li><b>先把「能买到」放在「收益高」之前。</b>四条腿全部选支付宝可申购的<b>场外联接份额</b>，'
             '而不是场内 ETF——回测里场内 ETF 数据更干净、折溢价可套，但客户买不到，回测再漂亮也没用。'
             '本页只把场内 ETF 放在折叠表里做对照。</li>')
    o.append('<li><b>只给四条腿、权重取 5% 整数倍。</b>资产类别少、权重粒度粗，是刻意的约束：'
             '一方面四个大类（国债 / 黄金 / A 股科技 / 能源）相关性低，组合夏普天然高于单资产；'
             '另一方面 5% 整数倍的权重可以直接翻译成「下 1000 元还是 2500 元」，不需要复杂的下单算法。'
             '代价是最优点被削平——网格里的最优不是连续最优，但可执行。</li>')
    o.append('<li><b>优化目标写成两步，而不是一个黑箱打分。</b>第一步用夏普比率卡一道门槛（网格前 10%%），'
             '第二步在门槛内最大化年化收益。这样做的理由：单纯最大化收益会选出「黄金 40%%+科创 40%% + 零债券」'
             '这种靠高波动堆出来的组合（年化 %.2f%%、波动 %.1f%%、回撤 %.1f%%），一旦板块反转就没人拿得住；'
             '单纯最大化夏普又会选出「一半债券」的类固收组合（年化只有 %.2f%%）。'
             '先卡夏普、再抢收益，是在「拿得住」和「跑得快」之间取的一档，而且规则可复现、可逐周重算。</li>'
             % (d['alts'][1]['stats']['ann'] * 100, d['alts'][1]['stats']['vol'] * 100,
                d['alts'][1]['stats']['mdd'] * 100, d['alts'][0]['stats']['ann'] * 100))
    o.append('<li><b>不设「短窗口必须为正」的硬约束。</b>这是与同类方案最大的差别。'
             '加上那条约束后（「五个窗口全部跑赢货基，无解则整仓货币基金」），本期会直接给出'
             '「无解 → 整仓货币基金」，看起来安全，但代价是长期年化只剩 1.29%%、近 2 年 +2.18%%'
             '（同期沪深300 近 2 年 +12.88%%）。'
             '本页选择把短窗口的难看程度如实展示出来（上周 %s、近一月 %s、近三月 %s），'
             '而不是用约束把亏损藏掉——约束本身也是收益的主要杀手之一。</li>'
             % (pctf(d['main_wr'][0]), pctf(d['main_wr'][1]), pctf(d['main_wr'][2])))
    o.append('<li><b>规则与判断分开，各自标注来源。</b>「权重」由规则给出（可复现）；'
             '「下周怎么下手」由我做自主行情判断（不可复现、可证伪）。页面把两者分栏标注，'
             '并把「什么情况会推翻我的判断」写清楚，方便你照着打脸。</li>')
    o.append('</ol>')
    o.append('<h3>B. 哪些部分用到了 bt-etf-backtest 技能</h3>')
    o.append('<div class="box info"><ul style="margin:0">')
    o.append('<li><b>第五章「独立引擎复算」整章</b>：用该技能的 <span class="inline">bt</span> '
             '（pmorissette/bt 1.4.1）引擎，以场内 ETF 前复权价作四条腿代理、单边佣金 %.1f bp，'
             '跑出六套经典算法（买入持有 / 等权 / 固定权重 / 逆波动率 / 风险平价 ERC / 双动量 Top2）的指标表与净值曲线'
             '—— 用来说明「为什么选固定权重而不是自动调权算法」。</li>' % 2.5)
    o.append('<li><b>375 组 5% 权重网格的独立复算</b>（第五章 ②）：用该技能的权重网格写法'
             '（一次性把全部组合塞进 bt.run、共享同一份价格矩阵），在 bt 侧独立选出「夏普最高 / 年化最高 / 卡玛最高」'
             '三个解，与主管线的结论做对照——确认结论不是某一个引擎的产物。</li>')
    o.append('<li><b>算法口径与踩坑清单</b>：该技能的 <span class="inline">references/bt-cheatsheet.md</span> 与 '
             '<span class="inline">cn-etf-notes.md</span> 提供了 RunWeekly / WeighTarget / 固定权重目标矩阵的标准写法，'
             '以及「调仓触发日 = 每期首个交易日、信号在前一交易日收盘生成」这条无未来函数的口径约定，'
             '本页周度调仓的实现直接沿用了这套约定。</li>')
    o.append('<li><b>引擎一致性判断</b>：该技能记录了「自研向量化回测 vs bt 引擎，卡玛逐位一致」的对照实验结论，'
             '所以本页用自研管线做主线（场外净值、含申赎费）、用 bt 做交叉验证，而不是二选一。</li>')
    o.append('</ul></div>')
    o.append('<h3>C. 一句话总结</h3>')
    o.append('<div class="box good">规则层面：在 375 组 5%% 整数倍权重里取「夏普前 10%% 门槛内年化最高」，'
             '得到<b>债券 25%% / 黄金 40%% / 科创 30%% / 能源 5%%</b>，区间年化 <b>%+.2f%%</b>、夏普 <b>%.2f</b>、'
             '最大回撤 <b>%.2f%%</b>。判断层面：下周别急着重仓黄金和科创，'
             '先把债券配到位、能源适度超配，剩下两条腿分三批接。</div>'
             % (d['main_stats']['ann'] * 100, d['main_stats']['sharpe'], d['main_stats']['mdd'] * 100))
    o.append('</section>')
    return '\n'.join(o)


def sec_foot(d):
    return ('<div class="foot">生成时间 %s ｜ 数据截止 %s ｜ 回测区间 %s ~ %s（%d 个交易日）<br>'
            '数据来源：东方财富公开接口（fundmobapi / pingzhongdata / f10）、腾讯行情；'
            'bt 引擎复算：pmorissette/bt 1.4.1（bt-etf-backtest 技能）。<br>'
            '本页为华泰期货国际业务部内部研究材料，仅限内部讨论使用。'
            '不构成任何基金推荐或投资建议。华泰期货 国际业务部 袁鑫　yuanxin@htfc.com　021-60679262</div>'
            % (d['gen'], d['asof'], d['range'][0], d['range'][1], d['n_days']))


# ------------------------------------------------------------------ 图表 JS
JS_FUNCS = r"""
var AX={axisLine:{lineStyle:{color:'#cbd4dd'}},axisLabel:{color:'#5a6672',fontSize:10},
  splitLine:{lineStyle:{color:'#eef1f4'}},nameTextStyle:{color:'#5a6672'}};
var TT={trigger:'axis'};

function line(){var ch=echarts.init(document.getElementById('c1'));
var keys=Object.keys(D.curves);
var color={'主推（v11 · 周度 · 5%整数权重）':'#c8102e','夏普优先解':'#e08a2b','等权（周度）':'#2f7ed8',
  '货基（余额宝000198）':'#7b8794','沪深300（510300）':'#8a9aa8'};
ch.setOption({backgroundColor:'transparent',grid:{left:56,right:18,top:46,bottom:44},
legend:{type:'scroll',top:0,textStyle:{color:'#4a5560',fontSize:11}},tooltip:TT,
xAxis:Object.assign({type:'category',data:D.labels,boundaryGap:false,
  axisLabel:{color:'#5a6672',fontSize:10,interval:Math.floor(D.labels.length/8)}},{}),
yAxis:Object.assign({type:'value',scale:true},AX),
series:keys.map(function(k){return {name:k,type:'line',data:D.curves[k],showSymbol:false,smooth:true,
  lineStyle:{width:(k.indexOf('主推')===0?2.6:1.5),color:color[k]||'#8a9aa8'},
  itemStyle:{color:color[k]||'#8a9aa8'}}})});}

function scat(){var ch=echarts.init(document.getElementById('c2'));
var pts=GRID.map(function(p){return {value:[p.vol*100,p.ann*100,p.sharpe,p.mdd*100,p.w.join('/')]};});
var marks=[{name:'主推',v:[MAIN.vol*100,MAIN.ann*100]},{name:'夏普优先解',v:[A1.vol*100,A1.ann*100]},
  {name:'收益优先解',v:[A2.vol*100,A2.ann*100]}];
ch.setOption({backgroundColor:'transparent',grid:{left:64,right:24,top:40,bottom:52},
tooltip:{formatter:function(o){if(o.seriesIndex===1)return o.data.name;
  var v=o.value;return '权重 '+v[4]+'%<br>年化波动 '+v[0].toFixed(2)+'%<br>年化收益 '+v[1].toFixed(2)
  +'%<br>夏普 '+v[2].toFixed(2)+'<br>最大回撤 '+v[3].toFixed(2)+'%';}},
visualMap:{min:0.6,max:1.5,dimension:2,orient:'horizontal',left:'center',bottom:0,itemHeight:80,
  text:['夏普高','夏普低'],textStyle:{color:'#5a6672',fontSize:10},
  inRange:{color:['#c9d8ea','#7fb0e0','#f0a04b','#c8102e']}},
xAxis:Object.assign({type:'value',name:'年化波动 %'},AX),
yAxis:Object.assign({type:'value',name:'年化收益 %'},AX),
series:[{type:'scatter',symbolSize:7,data:pts,itemStyle:{opacity:.75}},
 {type:'scatter',symbolSize:18,data:marks.map(function(m,i){return {name:m.name,value:m.v,
   symbol:i===0?'diamond':(i===1?'triangle':'roundRect'),itemStyle:{color:'#111'}}}),
  label:{show:true,formatter:function(o){return o.data.name},position:'top',color:'#1b1f24',fontSize:11,fontWeight:'bold'},
  itemStyle:{color:'#1b1f24',borderColor:'#fff',borderWidth:1.5}}]});}

function whbar(){var ch=echarts.init(document.getElementById('c3'));
var W=WH,keys=W.leglabels;
var c={'能源':'#c8102e','债券':'#2f7ed8','黄金':'#e0a72b','科创':'#0f9d58','货基（无可行解）':'#9aa5b1'};
ch.setOption({backgroundColor:'transparent',grid:{left:56,right:18,top:46,bottom:58},
legend:{type:'scroll',top:0,textStyle:{color:'#4a5560',fontSize:11}},
tooltip:{trigger:'axis',axisPointer:{type:'shadow'},valueFormatter:function(v){return v+'%'}},
xAxis:Object.assign({type:'category',data:W.labels,
  axisLabel:{color:'#5a6672',fontSize:9,interval:Math.floor(W.labels.length/10),rotate:38}},{}),
yAxis:Object.assign({type:'value',max:100,axisLabel:{color:'#5a6672',fontSize:10,formatter:'{value}%'}},
  {axisLine:AX.axisLine,splitLine:AX.splitLine}),
series:keys.map(function(k){return {name:k,type:'bar',stack:'w',data:W.stack[k],barMaxWidth:14,
  itemStyle:{color:c[k]||'#9aa5b1'}}})});}

function whline(){var ch=echarts.init(document.getElementById('c4'));
var W=WH,keys=W.leglabels;
var c={'能源':'#c8102e','债券':'#2f7ed8','黄金':'#e0a72b','科创':'#0f9d58','货基（无可行解）':'#9aa5b1'};
ch.setOption({backgroundColor:'transparent',grid:{left:56,right:18,top:46,bottom:58},
legend:{type:'scroll',top:0,textStyle:{color:'#4a5560',fontSize:11}},
tooltip:{trigger:'axis',valueFormatter:function(v){return v+'%'}},
xAxis:Object.assign({type:'category',data:W.labels,boundaryGap:false,
  axisLabel:{color:'#5a6672',fontSize:9,interval:Math.floor(W.labels.length/10),rotate:38}},{}),
yAxis:Object.assign({type:'value',max:100,axisLabel:{color:'#5a6672',fontSize:10,formatter:'{value}%'}},
  {axisLine:AX.axisLine,splitLine:AX.splitLine}),
series:keys.map(function(k){return {name:k,type:'line',step:'end',data:W.stack[k],showSymbol:false,
  lineStyle:{width:2,color:c[k]||'#9aa5b1'},itemStyle:{color:c[k]||'#9aa5b1'}}})});}

function btline(){var el=document.getElementById('c5');if(!el)return;var ch=echarts.init(el);
var B=BT;var color={'买入持有·不再平衡':'#7b8794','等权·月度再平衡':'#2f7ed8','固定权重[0.4, 0.4, 0.15, 0.05]·月度':'#c8102e',
 '逆波动率·月度':'#e0a72b','风险平价ERC·月度':'#0f9d58','双动量Top2·月度':'#8e44ad'};
ch.setOption({backgroundColor:'transparent',grid:{left:56,right:18,top:46,bottom:44},
legend:{type:'scroll',top:0,textStyle:{color:'#4a5560',fontSize:11}},tooltip:{trigger:'axis'},
xAxis:Object.assign({type:'category',data:B.labels,boundaryGap:false,
  axisLabel:{color:'#5a6672',fontSize:10,interval:Math.floor(B.labels.length/8)}},{}),
yAxis:Object.assign({type:'value',scale:true},AX),
series:B.order.map(function(k){return {name:k,type:'line',data:B.series[k],showSymbol:false,
  lineStyle:{width:2,color:color[k]||'#8a9aa8'},itemStyle:{color:color[k]||'#8a9aa8'}}})});}

function btgrid(){var el=document.getElementById('c6');if(!el||!BTG)return;var ch=echarts.init(el);
var pts=BTG.grid.map(function(g){return {value:[g.vol*100,g.ann*100,g.sharpe,g.w.join('/')]};});
var marks=[{name:'夏普最高',g:BTG.best_sharpe},{name:'年化最高',g:BTG.best_ann},
  {name:'门槛内年化最高',g:BTG.pick}].map(function(m){return {name:m.name,
  value:[m.g.vol*100,m.g.ann*100],itemStyle:{color:'#111'}}});
ch.setOption({backgroundColor:'transparent',grid:{left:64,right:24,top:40,bottom:52},
tooltip:{formatter:function(o){if(o.seriesIndex===1)return o.data.name;
  var v=o.value;return '权重 '+v[3]+'%<br>年化波动 '+v[0].toFixed(2)+'%<br>年化收益 '+v[1].toFixed(2)
  +'%<br>夏普 '+v[2].toFixed(2);}},
visualMap:{min:0.5,max:1.6,dimension:2,orient:'horizontal',left:'center',bottom:0,itemHeight:80,
  text:['夏普高','夏普低'],textStyle:{color:'#5a6672',fontSize:10},
  inRange:{color:['#c9d8ea','#7fb0e0','#f0a04b','#c8102e']}},
xAxis:Object.assign({type:'value',name:'年化波动 %'},AX),
yAxis:Object.assign({type:'value',name:'年化收益 %'},AX),
series:[{type:'scatter',symbolSize:6,data:pts,itemStyle:{opacity:.7}},
 {type:'scatter',symbolSize:16,data:marks,label:{show:true,formatter:function(o){return o.data.name},
  position:'top',color:'#1b1f24',fontSize:10,fontWeight:'bold'},
  itemStyle:{color:'#111',borderColor:'#fff',borderWidth:1.5}}]});}

function recalc(){var el=document.getElementById('cap');if(!el)return;
var cap=parseFloat(el.value);if(isNaN(cap)||cap<0)cap=0;var k=cap/10000;
document.querySelectorAll('[data-unit]').forEach(function(td){var u=parseFloat(td.getAttribute('data-unit'));
  td.textContent=(u*k).toFixed(2);});
document.querySelectorAll('[data-money]').forEach(function(td){var u=parseFloat(td.getAttribute('data-money'));
  td.textContent=(u*k).toFixed(2);});
document.getElementById('capshow').textContent=cap.toFixed(0);}

line();scat();whbar();whline();btline();btgrid();
var capEl=document.getElementById('cap');if(capEl){capEl.addEventListener('input',recalc);recalc();}
window.addEventListener('resize',function(){
  ['c1','c2','c3','c4','c5','c6'].forEach(function(id){var el=document.getElementById(id);if(!el)return;
  var i=echarts.getInstanceByDom(el);if(i)i.resize();});});
"""


# ------------------------------------------------------------------ bt 产物读取
def load_bt():
    out = {'ok': False}
    mp = os.path.join(BT_RUN, 'bt_metrics.csv')
    if not os.path.exists(mp):
        return out
    rows, rng = [], []
    with open(mp, encoding='utf-8-sig') as f:
        r = csv.DictReader(f)
        for row in r:
            nm = (row.get('') or row.get('Unnamed: 0') or '').strip()
            if not nm:
                continue
            def fv(k):
                try:
                    return float(row[k])
                except Exception:
                    return 0.0
            rows.append({'name': nm, 'tot': fv('累计收益'), 'ann': fv('年化收益'), 'vol': fv('年化波动'),
                         'sharpe': fv('夏普'), 'mdd': fv('最大回撤'), 'calmar': fv('卡玛'),
                         'turnover': fv('年化换手')})
    out['ok'] = bool(rows)
    out['metrics'] = rows
    out['comm_bp'] = 2.5
    # 六策略净值曲线
    cp = os.path.join(BT_RUN, 'bt_charts.json')
    if os.path.exists(cp):
        ch = json.load(open(cp, encoding='utf-8'))
        out['labels'] = ch['curve']['labels']
        out['series'] = ch['curve']['series']
        out['order'] = ch['curve']['order']
        out['legs'] = ch.get('legs') or {}
    # 5% 网格
    gp = os.path.join(BT_RUN, 'bt_grid5.json')
    if os.path.exists(gp):
        g = json.load(open(gp, encoding='utf-8'))
        grid = [x for x in g['grid'] if x['sharpe'] is not None]
        bs = max(grid, key=lambda x: x['sharpe'])
        ba = max(grid, key=lambda x: x['ann'])
        bc = max(grid, key=lambda x: x['calmar'])
        ranked = sorted(grid, key=lambda x: (-x['sharpe'], -x['ann']))
        k = max(1, int(round(len(grid) * 0.10)))
        thr = ranked[k - 1]['sharpe']
        gate = [x for x in ranked if x['sharpe'] >= thr - 1e-9]
        pick = max(gate, key=lambda x: x['ann'])
        out['grid5'] = {'n': g['n'], 'cols': g['cols'], 'range': g['range'],
                        'grid': [{'w': x['w'], 'ann': x['ann'], 'vol': x['vol'], 'sharpe': x['sharpe'],
                                  'mdd': x['mdd'], 'calmar': x['calmar']} for x in grid],
                        'best_sharpe': bs, 'best_ann': ba, 'best_calmar': bc,
                        'pick': pick, 'gate_thr': thr, 'gate_n': len(gate)}
    # 需要「月度」六策略区间
    if out.get('labels'):
        out['metrics_range'] = [out['labels'][0], out['labels'][-1]]
    else:
        out['metrics_range'] = ['—', '—']
    return out


# ------------------------------------------------------------------ main
def main():
    global PAGE, CROSS, WT_WEEKS, D_ORDER, BT_OK, BT, POOL, POOL_STAT
    PAGE = C.jload('page_data_v11.json')
    wt = C.jload('wt_hist3.json')
    api = C.jload('api_data.json')
    met = C.jload('metrics.json')
    WT_WEEKS = wt['weeks']
    D_ORDER = ['能源', '债券', '黄金', '科创']
    BT = load_bt()
    BT_OK = bool(BT.get('ok'))

    # 候选池规模（数据源口径）
    import collections
    uni = C.jload('api_universe.json')
    pk = C.jload('picks2.json')
    ast = C.jload('astock.json')
    n_all = len(uni.get('all') or {})
    n_base = uni.get('base_size') or 0
    seg = []
    for cat in ('债券', '黄金', '能源'):
        v = pk['cats'][cat]
        seg.append('%s %d（场外可申购 %d）' % (cat, v['n_all'], v['n_off']))
    seg.append('A股/科创 %d' % ast['n_all'])
    POOL = [('全市场基金（东财 FundMNRank 全量）', '%d 只' % n_all, '抓取当日支付宝/天天基金可见的全部公募基金'),
            ('初筛基础池（FundType ∈ {3,4,6,8}）', '%d 只' % n_base, '股票型 / 混合型 / 债券型 / QDII 的并集，排除货币与理财'),
            ('四大类命中（名称 + 类型关键词）', '%d 只' % sum(pk['cats'][c]['n_all'] for c in ('债券', '黄金', '能源')),
             '＋'.join(seg)),
            ('逐日净值 + 费率 + 限额详查', '%d 只' % len(api), '抓取净值序列、官方限额、优惠费率、管理+托管+销服费'),
            ('最终进入网格回测', '4 只', '每类 1 只场外可申购份额（见第三章）')]
    st = collections.Counter((v or {}).get('sgzt') for v in api.values())
    POOL_STAT = [(k, st[k]) for k in ('开放申购', '限大额', '场内交易', '暂停申购', '认购期') if st.get(k)]

    # 口径交叉校验（自算 vs 官方近 1 年）
    devs = []
    for code, m in met.items():
        a = api.get(code) or {}
        if a.get('syl_1n') is None:
            continue
        a1 = (m.get('a1') or {}).get('ann')
        if a1 is None:
            continue
        devs.append(abs(a1 * 100 - a['syl_1n']))
    devs.sort()
    CROSS = ('%.2fpp' % devs[len(devs) // 2], '%.2fpp' % devs[int(len(devs) * 0.9)]) if devs else ('—', '—')

    parts = [sec_head(PAGE), sec_disc(), sec_hero(PAGE), sec_next(PAGE), sec_one(PAGE),
             sec_two(PAGE), sec_three(PAGE), sec_four(PAGE), sec_bt(PAGE), sec_six(PAGE),
             sec_orders(PAGE), sec_seven(PAGE), sec_eight(PAGE), sec_foot(PAGE)]
    body = '\n'.join(parts)

    resid = re.findall(r'__[A-Z0-9_]+__', body)
    assert not resid, '残留 token: %s' % resid[:5]

    wh = PAGE['charts']['wh']
    dj = {'labels': PAGE['charts']['labels'], 'curves': PAGE['charts']['curves']}
    btc = {}
    btg = None
    if BT_OK:
        btc = {'labels': BT.get('labels', []), 'series': BT.get('series', {}), 'order': BT.get('order', [])}
        if BT.get('grid5'):
            g = BT['grid5']
            btg = {'grid': g['grid'], 'cols': g['cols'], 'best_sharpe': {k: g['best_sharpe'][k] for k in ('w', 'ann', 'vol', 'mdd', 'sharpe', 'calmar')},
                   'best_ann': {k: g['best_ann'][k] for k in ('w', 'ann', 'vol', 'mdd', 'sharpe', 'calmar')},
                   'best_calmar': {k: g['best_calmar'][k] for k in ('w', 'ann', 'vol', 'mdd', 'sharpe', 'calmar')},
                   'pick': {k: g['pick'][k] for k in ('w', 'ann', 'vol', 'mdd', 'sharpe', 'calmar')}}
    ms = PAGE['main_stats']
    a1 = PAGE['alts'][0]['stats']
    a2 = PAGE['alts'][1]['stats']
    pagejs = ('var D=' + json.dumps({'labels': dj['labels'], 'curves': dj['curves']}, ensure_ascii=False) + ';\n'
              'var GRID=' + json.dumps(PAGE['charts']['grid_pts'], ensure_ascii=False) + ';\n'
              'var MAIN=' + json.dumps({'ann': ms['ann'], 'vol': ms['vol']}, ensure_ascii=False) + ';\n'
              'var A1=' + json.dumps({'ann': a1['ann'], 'vol': a1['vol']}, ensure_ascii=False) + ';\n'
              'var A2=' + json.dumps({'ann': a2['ann'], 'vol': a2['vol']}, ensure_ascii=False) + ';\n'
              'var WH=' + json.dumps({'labels': wh['labels'], 'stack': wh['stack'],
                                      'leglabels': wh['leglabels']}, ensure_ascii=False) + ';\n'
              'var BT=' + json.dumps(btc, ensure_ascii=False) + ';\n'
              'var BTG=' + json.dumps(btg, ensure_ascii=False) + ';\n' + JS_FUNCS)
    ech = open(os.path.join(C.ASSETS, 'echarts.min.js'), encoding='utf-8').read()
    title = '支付宝可申购基金 · 四大类 ETF 智能组合回测与下周操作建议（%s）v11' % PAGE['asof']
    doc = ('<!DOCTYPE html>\n<html lang="zh-CN"><head><meta charset="utf-8">\n'
           '<meta name="viewport" content="width=device-width,initial-scale=1">\n'
           '<title>%s</title>\n%s\n</head><body><div class="wrap">\n%s\n'
           '<script>%s</script>\n<script>%s</script>\n</div></body></html>'
           % (title, CSS, body, ech, pagejs))
    ts = time.strftime('%Y%m%d_%H%M%S')
    out = os.path.join(C.FINAL, 'alipay_fund_4class_v11_%s.html' % ts)
    with open(out, 'w', encoding='utf-8') as f:
        f.write(doc)
    C.log('已渲染 %s（%.2f MB）' % (out, len(doc.encode('utf-8')) / 1048576.0))
    script = os.path.join(C.WORK, 'last_script_v11.js')
    with open(script, 'w', encoding='utf-8') as f:
        f.write(pagejs)
    C.log('页面 JS 已落盘：%s' % script)
    return out


if __name__ == '__main__':
    main()
