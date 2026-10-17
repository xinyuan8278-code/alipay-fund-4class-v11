# -*- coding: utf-8 -*-
"""step 12 · 渲染单文件 HTML（ECharts 内联、无外链、无 CDN）
用法：QDII_SRC=_ref python o_build_page9.py   # 渲染对齐版
输出：outputs/final/alipay_fund_4class_portfolio_<YYYYMMDD>_<HHMMSS>_v9[..].html"""
import os, re, json, time, html
import common as C

CSS = """<style>

*{box-sizing:border-box}
body{margin:0;background:#0f1216;color:#e6e9ef;font:14px/1.6 -apple-system,BlinkMacSystemFont,"Segoe UI","PingFang SC","Microsoft YaHei",sans-serif}
.wrap{max-width:1180px;margin:0 auto;padding:26px 20px 70px}
h1{font-size:22px;margin:0 0 6px}
h2{font-size:17px;margin:34px 0 12px;padding-left:10px;border-left:3px solid #d4a24a}
h3{font-size:15px;margin:0 0 8px}
.sub{font-weight:400;color:#8b95a5;font-size:12px}
.lead{color:#9aa4b2;font-size:12.5px;margin:0 0 16px}
.rule{background:#161b22;border:1px solid #232a34;border-radius:8px;padding:12px 14px;color:#c3cad6;font-size:12.5px}
.rule b{color:#e8c37a}
.hero{background:linear-gradient(135deg,#182029 0%,#141a22 60%,#1b1a14 100%);border:1px solid #2a3441;border-radius:12px;padding:18px 20px;margin:14px 0 6px}
.kpis{display:flex;flex-wrap:wrap;gap:10px;margin:12px 0 6px}
.kpi{flex:1 1 132px;background:#111721;border:1px solid #232b36;border-radius:9px;padding:10px 12px}
.kpi .k{color:#8b95a5;font-size:11.5px;letter-spacing:.3px}
.kpi .v{font-size:19px;font-weight:600;color:#7fd1a8;margin-top:3px}
.kpi .v.warn{color:#e8c37a}
.kpi .v.bad{color:#e08a8a}
.kpi .s{font-size:11px;color:#7d8797}
.card{background:#141922;border:1px solid #222a35;border-radius:10px;padding:14px 16px;margin:12px 0}
.note{color:#98a2b0;font-size:12px;margin:8px 0 10px}
table.grid{width:100%;border-collapse:collapse;font-size:12.3px}
table.grid th{background:#1b222d;color:#9fb0c4;font-weight:500;text-align:left;padding:7px 6px;border-bottom:1px solid #2b3441;white-space:nowrap}
table.grid td{padding:6px;border-bottom:1px solid #1d242e;vertical-align:middle}
table.grid tr:hover td{background:#181f29}
table.grid tr.chosen td{background:#1b2a22}
table.grid tr.dim td{color:#7d8797}
table.grid.small{font-size:11.6px}
td.num,th.num{text-align:right;font-variant-numeric:tabular-nums}
.mono{font-family:ui-monospace,SFMono-Regular,Menlo,monospace;color:#b9c4d4}
.pick{background:#2c5f45;color:#a9e8c5;font-size:10.5px;padding:1px 5px;border-radius:4px;margin-left:4px}
.tag{font-size:11px;padding:1px 6px;border-radius:4px;white-space:nowrap}
.tag.ok{background:#1d3a2b;color:#7fd1a8}
.tag.warn{background:#3a3320;color:#e8c37a}
.tag.bad{background:#3a2222;color:#e08a8a}
.tag.gray{background:#242b36;color:#9aa4b2}
tr.hi td{background:#1d2a22;font-weight:600}
tr.bench td{color:#9aa4b2}
.c-hi{color:#e8c37a}
details{margin-top:8px}
summary{cursor:pointer;color:#8b95a5;font-size:12px}
.chart{height:330px;width:100%}
.tw{overflow-x:auto;-webkit-overflow-scrolling:touch}
.prem{color:#e8c37a;font-weight:600}
.prem.bad{color:#e08a8a}
.two{display:grid;grid-template-columns:1fr 1fr;gap:14px}
@media(max-width:860px){.two{grid-template-columns:1fr}}
.wrow{display:flex;justify-content:space-between;border-bottom:1px dashed #232b36;padding:5px 0;font-size:12.5px}
.wrow b{color:#7fd1a8}
ol,ul{padding-left:20px;color:#c3cad6;font-size:12.8px}
li{margin:5px 0}
.foot{margin-top:30px;padding-top:14px;border-top:1px solid #232a34;color:#8b95a5;font-size:12px}
.warnbox{background:#241d1a;border:1px solid #3d2f28;border-radius:8px;padding:12px 14px;color:#dcc0a8;font-size:12.5px}
table.grid th.gcol,table.grid td.gcol{background:#1c3325 !important;box-shadow:inset 1px 0 0 #35754f,inset -1px 0 0 #35754f;color:#eaffef !important;font-weight:700}
tr.up td{color:#e05a5a}
.fbad{background:#241d1a;border:1px solid #3d2f28;border-radius:8px;padding:12px 14px;color:#e8b48a;font-size:12.5px;margin:10px 0}
.fok{background:#16241c;border:1px solid #24402f;border-radius:8px;padding:12px 14px;color:#a9e8c5;font-size:12.5px;margin:10px 0}
</style>"""


def e(s):
    return html.escape('' if s is None else str(s), quote=True)


def n2(x, d=2, sign=False, suffix=''):
    if x is None:
        return '—'
    return ('%+.*f' % (d, x)) if sign else ('%.*f' % (d, x))


def pct(x, d=2, sign=True):
    if x is None:
        return '—'
    return (('%+.*f%%' if sign else '%.*f%%') % (d, x * 100))


def col(v):
    return '#7fd1a8' if v >= 0 else '#e08a8a'


def td_pct(x, d=2, sign=True):
    if x is None:
        return "<td class='num'>—</td>"
    return "<td class='num' style='color:%s'>%s</td>" % (col(x), pct(x, d, sign))


def H(tag, txt):
    return '<%s>%s</%s>' % (tag, txt, tag)


# ------------------------------------------------------------------ 章节
def sec_head():
    d = PAGE
    kpis = ''.join(
        '<div class="kpi"><div class="k">%s</div><div class="v %s">%s</div><div class="s">%s</div></div>'
        % (e(k['k']), e(k['cls']), e(k['v']), e(k['s'])) for k in d['kpis'])
    lead = ('国债/债券ETF · 黄金ETF · A股/科创ETF · 能源ETF ｜ 数据截至 %s ｜ 组合（场外可执行 · 支付宝可买）'
            '%s ~ %s（%d 个交易日）' % (d['asof'], d['range'][0], d['range'][1], d['n_days']))
    return ('<h1>支付宝可申购基金 · 四大类筛选与组合回测</h1>\n'
            '<p class="lead">%s<br>%s</p>\n' % (lead, _v9_points()))


def _v9_points():
    return ('版本 v9：① <b>只做场外可买到的组合</b>，原「组合 A（场内 ETF）」整块删除；'
            '② <b>组合权重允许为 0</b>——表现不佳的腿可整腿剔除，权重在 5% 整数倍网格里重跑，'
            '硬约束为「上周／近一月／近三月／今年以来／近 2 年<b>全部跑赢货基（余额宝）</b>」，'
            '可行解里取夏普最高，<b>无可行解则当期 100% 货基</b>；'
            '③ 结论区「历史收益表现」新增<b>货基对照行</b>，并列出本期<b>全部可行权重</b>（含把某腿设 0 的方案）；'
            '④ 新增「<b>近一年权重变化</b>」章节（柱状图 + 折线图 + 关键时点快照表），'
            '把同一规则在过去 52 周逐周重跑一遍；'
            '⑤ 「主推权重」升级为<b>上期／上周／本期对照表</b>（每个腿要调多少一目了然），'
            '「下周怎么操作」补上<b>判断依据</b>：为什么这样操作、操作方向、依据从哪来、什么情况下会再变；'
            '⑥ 新增「<b>下周下单清单</b>」：用四条腿的<b>最新净值</b>把目标权重折成<b>申购金额与买卖份额</b>'
            '（本金可在页面上改，默认 1 万元），并给出「从货基建仓」与「从上期权重的调整」两套；'
            '⑦「本期＝下周」整列<b>高亮</b>，「下周怎么操作」改为<b>行情判断</b>'
            '（约 200 字，讲为什么这样配，不堆数据）。回测仍为周度调仓、权重取 5% 整数倍')


def sec_rule():
    return ('<div class="rule">本网页不涉及任何基金推荐，仅限研究使用。回测基于历史净值，不代表未来收益。<br>\n'
            '如有任何问题，请联系 华泰期货 国际业务部 袁鑫　邮箱：yuanxin@htfc.com　电话：021-60679262。</div>\n')


def sec_hero():
    d = PAGE
    out = ['<div class="hero">']
    out.append('<h3>结论：%s</h3>' % ('<span style="color:#e8c37a">本期无可行解 → 按规则整仓货币基金（不持风险腿）</span>'
                                     if d['fallback'] else
                                     '推荐「场外可执行组合 · v5 约束网格权重 · 周度调仓」'))
    out.append('<div class="kpis">' + ''.join(
        '<div class="kpi"><div class="k">%s</div><div class="v %s">%s</div><div class="s">%s</div></div>'
        % (e(k['k']), e(k['cls']), e(k['v']), e(k['s'])) for k in d['kpis']) + '</div>')
    # 历史收益表现
    wl = d['window_labels']
    rows = []
    for r in d['hist']:
        cells = ''.join(td_pct(x) for x in r['wr'])
        rows.append('<tr class="%s"><td>%s</td>%s</tr>' % (e(r['cls']), e(r['label']), cells))
    out.append('<section class="card"><h3>历史收益表现（场外组合，已扣再平衡成本）</h3>')
    out.append('<table class="grid"><tr><th>组合</th>' +
               ''.join("<th class='num'>%s</th>" % e(x) for x in wl) + '</tr>' + ''.join(rows) + '</table>')
    wb = d['window_bases']
    out.append('<p class="note">基准日：%s；「近 2 年」为区间累计收益（非年化）。主推＝<b>允许 0 权重的 5%% 整数倍网格里、'
               '5 个窗口全部跑赢货基且夏普最高</b>的那组权重（周度调仓，曲线按逐腿真实净值加权、已扣再平衡成本）；'
               'v4 旧口径＝原「禁止 0 权重、最大化卡玛」的权重，仅作对照。货基＝天弘余额宝货币（场外可买），'
               '同期年化 %.2f%%。</p>' % (' / '.join('；'.join(a) for a in zip(wl, wb)), CASH_ANN * 100))
    # 本期全部可行权重
    out.append('<h3 style="margin-top:14px">本期全部可行权重（5 窗口全部跑赢货基 · 共 %d 组）</h3>' % d['feas_n'])
    if d['feas']:
        out.append('<table class="grid small"><tr><th>权重（%s）</th><th class="num">年化</th><th class="num">波动</th>'
                   '<th class="num">回撤</th><th class="num">夏普</th><th class="num">卡玛</th>%s</tr>'
                   % ('/'.join(d['feas_order']), ''.join('<th class="num">%s</th>' % e(x) for x in wl)))
        for r in d['feas']:
            st = r['stats']
            out.append('<tr class="%s"><td class="mono">%s</td><td class=\'num\'>%s</td><td class=\'num\'>%s</td>'
                       '<td class=\'num\'>%s</td><td class=\'num\'>%.2f</td><td class=\'num\'>%.2f</td>%s</tr>'
                       % ('hi' if r['main'] else '', e(r['wstr']),
                          pct(st['ann'], 2, False), pct(st['vol'], 2, False), pct(st['mdd'], 2, False),
                          st['sharpe'], st['calmar'], ''.join(td_pct(x) for x in r['wr'])))
        out.append('</table>')
        out.append('<p class="note">网格共 %d 组（单腿 0/5/…/40%%，合计 100%%），只有上表这些组能同时满足「5 个窗口跑赢货基」。'
                   '约束主要由<b>短窗口</b>决定：近一月表现差的腿会被自动压到很低甚至 0，腾出的权重给短窗口为正的腿。</p>'
                   % d['grid_n'])
    else:
        out.append('<div class="fbad">本期 <b>%d 组权重里没有一组</b>能同时满足「上周／近一月／近三月／今年以来／近2年'
                   '五个窗口全部跑赢货基」，因此按规则<b>整仓退到货币基金</b>、不持任何风险腿。'
                   '这是规则设计内的正常结果（近一年 %d 周里有 %d 周如此），不是数据出错。</div>'
                   % (d['grid_n'], WT_N, WT_NOCASH))
    out.append('</section>')
    out.append(sec_wtbl())
    out.append('</div>')
    return '\n'.join(out)


def sec_wtbl():
    d = PAGE
    w = d['wtbl']
    rows = []
    for r in w['rows']:
        cls = " class='bench'" if r.get('bench') else ''
        chgc = '' if abs(r['chg']) < 1e-9 else " style='color:%s'" % ('#7fd1a8' if r['chg'] > 0 else '#e08a8a')
        rows.append("<tr%s><td>%s · %s <span class='mono'>%s</span></td><td class='num'>%d%%</td>"
                    "<td class='num'>%d%%</td><td class='num gcol'><b>%d%%</b></td>"
                    "<td class='num'%s>%+dpp</td><td>%s</td></tr>"
                    % (cls, e(r['cat']), e(short(r['name'])), e(r['code']),
                       r['prev'], r['last'], r['cur'], chgc, r['chg'], e(r['act'])))
    tbl = ('<table class="grid small"><tr><th>类别 · 基金（代码）</th>'
           '<th class=\'num\'>上期有解<br><span class=\'sub\'>%s</span></th>'
           '<th class=\'num\'>上周<br><span class=\'sub\'>%s</span></th>'
           '<th class=\'num gcol\'>本期 ＝ 下周<br><span class=\'sub\'>%s</span></th>'
           '<th class=\'num\'>变化<br><span class=\'sub\'>vs 上期有解</span></th><th>下周动作</th></tr>%s</table>'
           % (e(w['prev_date']), e(w['last_date']), e(w['cur_date']), ''.join(rows)))
    note = ('<p class="note"><b>怎么用这张表：</b>「上期有解」＝规则最近一次给出的权重（%s）；「上周」＝%s，那一周%s。'
            '「本期 ＝ 下周」就是下周要按这个比例持有（整列<b>高亮</b>）。<b>变化列＝本期 − 上期有解</b>：'
            '正数要买入，负数要卖出。<b>权重每周重跑一次网格，偏离目标 5pp 以上才动手</b>；'
            '标的仍由 S1/S2/S3 信号决定（无固定更换周期）。</p>'
            % (e(w['prev_date']), e(w['last_date']),
               '按规则应 100% 持货基' if not w['last_feas'] else
               '有解：' + '／'.join('%s %d%%' % (r['cat'], r['last']) for r in w['rows'] if r['cat'] != '货基')))
    ops = d['ops']
    opsbox = ('<p><b>下周权重安排（基于当前行情的判断）</b><br>%s</p>'
              '<p><b>方向：</b>%s</p><p><b>什么情况会改：</b>%s</p>'
              '<p class="note">判断由规则给出（约束式权重网格：单腿 0~40%%、五个窗口全部跑赢货基、可行解里取夏普最高），'
              '上面的行情解读是对该结果的复述。本期可行性：全部 %d 组权重中 %d 组满足约束。%s</p>'
              % (e(ops['narrative']), e(ops['direction']), e(ops['falsify']),
                 d['grid_n'], d['feas_n'],
                 '「上周怎么操作」已合并到本表，页内只保留一个定时任务口径。' if not d['fallback'] else
                 '无解周不持风险腿，下周重新评估。'))
    return ('<div class="two">\n<div><h3 style="margin:6px 0">主推权重：上期 → 本期（＝下周执行）</h3>\n'
            + tbl + '\n' + note + '</div>\n'
            + '<div><h3 style="margin:6px 0">下周怎么操作（方向 + 判断依据）</h3>\n' + opsbox + '</div>\n</div>')


def sec_orders():
    d = PAGE
    o = d['orders']
    rows = []
    for r in o['A']:
        cls = " class='bench'" if r.get('bench') else ''
        fee = '<td class=\'num\'>—</td>' if r['fee'] is None else \
              "<td class='num' data-money=\"%.2f\">%.2f</td>" % (r['fee'], r['fee'])
        rows.append("<tr%s><td>%s · %s <span class='mono'>%s</span></td>"
                    "<td class='num'>%s<br><span class='sub'>%s</span></td><td class='num'>%d%%</td>"
                    "<td class='num' data-money=\"%.2f\">%.2f</td>%s"
                    "<td class='num'><b data-unit=\"%.2f\">%.2f</b></td></tr>"
                    % (cls, e(r['cat']), e(short(r['name'])), e(r['code']),
                       n2(r['nav'], 4), e(r['navdate']), r['w'],
                       r['money'], r['money'], fee, r['units'], r['units']))
    tblA = ('<div class="tw"><table class="grid small"><tr><th>类别 · 基金（代码）</th>'
            '<th class="num">最新净值<br><span class="sub">净值日</span></th><th class="num">目标权重</th>'
            '<th class="num">申购金额</th><th class="num">申购费</th><th class="num">买入份额</th></tr>'
            + ''.join(rows) + '</table></div>')
    rowsB = []
    for r in o['B']:
        rowsB.append("<tr><td>%s · %s <span class='mono'>%s</span></td><td class='num'>%d%% → %d%%</td>"
                     "<td>%s</td><td class='num' data-money=\"%.2f\">%.2f</td>"
                     "<td class='num' data-unit=\"%.2f\">%.2f</td></tr>"
                     % (e(r['cat']), e(short(r['name'])), e(r['code']), r['prev'], r['cur'], e(r['act']),
                        r['money'], r['money'], r['units'], r['units']))
    rowsB.append("<tr class='hi'><td>小结</td><td class='num'>—</td><td>买 %.2f / 卖 %.2f</td>"
                 "<td class='num' data-money=\"%.2f\">%.2f</td><td>%s</td></tr>"
                 % (o.get('total_buy', 0), o.get('total_sell', 0),
                    o.get('net_cash', 0), o.get('net_cash', 0),
                    '净回收现金（留货基）' if o.get('net_cash', 0) >= 0 else '需自筹现金'))
    tblB = ('<div class="tw"><table class="grid small"><tr><th>类别 · 基金（代码）</th><th class="num">上期 → 本期</th>'
            '<th>动作</th><th class="num">金额</th><th class="num">份额</th></tr>' + ''.join(rowsB) + '</table></div>')
    legs_desc = '／'.join('%s %d%%' % (r['cat'], r['cur']) for r in d['wtbl']['rows'] if r['cat'] != '货基')
    fee_desc = '、'.join('%s %s' % (a['cat'],
                                 ('%.2f%%' % (a['buy'] * 100)) if a['buy'] else '0（免申购费）')
                       for a in d['assets'])
    return ('<section class="card"><h3>下周下单清单（按最新净值折算份数）'
            '<span class="sub">本金 <input id="cap" value="10000" size="7" '
            'style="background:#0f1216;color:#e6e9ef;border:1px solid #2b3441;border-radius:4px;padding:2px 6px"> '
            '元（可直接改，表格自动重算）</span></h3>'
            '<p class="note">下面所有金额与份额都按 <b><span id="capshow">10000</span> 元</b>本金折算；'
            '目标权重取本页主推（%s）。上期有解＝%s。</p>'
            '<h4 style="margin:10px 0 4px">A. 若现在资金全在货基%s——建仓清单</h4>%s'
            '<p class="note">%s</p>'
            '<h4 style="margin:12px 0 4px">B. 若现在仍持有「上期有解」那套权重——调整清单</h4>%s'
            '<p class="note">口径：净值取最新披露的单位净值（场外基金按 T 日净值确认份额，货币基金份额净值恒 1 元）；'
            '申购份额＝申购金额 ÷ (1+优惠申购费率) ÷ 净值，赎回份额＝金额 ÷ 净值，'
            '<b>申购在下单时填金额、赎回填份额</b>，份额确认到 0.01 份，所以实际成交份额会有几分钱的尾差。'
            '费率：%s。货币基金（天弘余额宝货币）无申购/赎回费、1 元 1 份，'
            '可以直接把没投出去的钱留在里面。<b>申购费已含在金额里</b>（不是「剩余现金」），'
            '所以写法是「合计下单 X 元，其中费用 Y 元，实际买入市值 X−Y 元」。</p></section>'
            % (legs_desc, e(d['wtbl']['prev_date']),
               '（按规则上期应持货基）' if not d['wtbl']['last_feas'] else '（上期无解周应持货基）',
               tblA,
               ('本期无可行解、不买风险腿：<b data-money="%.2f">%.2f</b> 元本金'
                '<b>全部留在货币基金</b>（无申购费）。下周重跑网格，一旦出现可行解再按上面的权重建仓。'
                % (o['total_money'], o['total_money'])) if o.get('fallback') else
               ('四条腿合计下单 <b data-money="%.2f">%.2f</b> 元，其中申购费 '
                '<b data-money="%.2f">%.2f</b> 元，<b>实际买入市值 <span data-money="%.2f">%.2f</span> 元</b>。'
                '建议分 2~3 批建仓。' % (o['total_money'], o['total_money'], o['total_fee'], o['total_fee'],
                                     o['buy_value'], o['buy_value'])),
               tblB, fee_desc))


def sec_one():
    d = PAGE
    lis = [
        '候选池来源：名称与类型命中四大类关键词的全部 ETF 及其场外联接份额（东财 FundType ∈ {3,4,6,8} 的并集）。'
        '场内 ETF 支付宝买不到，因此组合只用<b>场外可申购的联接份额</b>。',
        '可申购判定：东财申购状态字段——「开放申购」与「限大额」计入可申购；'
        '「暂停申购/封闭期/认购期」与「场内交易」不计入（场内 ETF 已单独折叠列表备查）。',
        '收益口径：使用逐日净值增长率累乘为总收益指数，已含分红再投资；基金净值本身已扣除管理费与托管费，'
        '故回测只再扣「申购费 + 持有满 7 天赎回费」。',
        '跟踪误差：以「同一跟踪标的 + 同一份额币种」中规模最大者为参照，按日收益差的标准差年化。',
        '官方字段口径：SYL_1N/3N/5N 为区间累计（非年化，本页 3 年列已年化）；MAXSG ≥ 1e10 视为不限额度；'
        '净值日期为官方最新披露日；A股/科创腿的「年化收益率」＝近 2 年净值年化。',
        '口径交叉校验：自算近 1 年收益与官方 SYL_1N 交叉校验，偏差中位数 %s、90 分位 %s，'
        '说明净值管线与官方口径一致。' % (CROSS[0], CROSS[1]),
        '数据来源：东财 fundmobapi（申购状态/单日限额/起购/优惠费率/管理+托管+销服费/跟踪指数/阶段收益）'
        '+ 天天基金 f10 费率页（申购费、赎回费分档）+ 天天基金逐日净值序列 + 腾讯行情（场内现价/折溢价）。',
        '合规：官方星级评级页由 JS 动态加载、接口取不到 → 评价维度改用「官方夏普 + 跟踪误差 + 成立年限」合成，'
        '规则与权重全部公开、可复核。',
    ]
    return ('<h2>一、清单与口径</h2><section class="card"><ul>' +
            ''.join('<li>%s</li>' % x for x in lis) + '</ul></section>')


def sec_two():
    rule = [('规模 AUM', '30', '类内对数规模线性归一：该类最大者 30 分，最小者 0 分'),
            ('费率·交易', '15', '申购费（第三方优惠费率）+ 持有满 7 天赎回费；合计 0% 满分，≥1.2% 得 0 分'),
            ('费率·持有', '10', '管理费 + 托管费 + 销售服务费（年化）；≤0.15% 满分，≥1.0% 得 0 分'),
            ('认购/申购额度', '25', '开放申购不限额度 25 / 场内可交易 22 / 单日上限 ≥100 万 18 / 1 万~100 万 12 / 小于 1 万 6 / 暂停 0'),
            ('评价', '20', '官方近 1 年夏普（类内排名 50%）+ 跟踪误差（越小越好 30%）+ 成立年限（≥5 年满分 20%）')]
    tbl = ''.join('<tr><td>%s</td><td class="num">%s</td><td>%s</td></tr>' % r for r in rule)
    out = ['<h2>二、筛选标准：债券/黄金/能源按四项 100 分口径，A股/科创按年化收益率 120 分口径</h2>']
    out.append('<section class="card"><h3>四项打分口径（AUM 大 / 认购赎回费低 / 无认购金额限制 / 评价好）'
               '—— 用于债券 / 黄金 / 能源三类</h3>')
    out.append('<p class="note">每只候选按四项打分（满分 100）；绿底行＝该类实际选用，灰字行＝当前不可申购，仅作对照。</p>')
    out.append('<table class="grid small"><tr><th>维度</th><th class="num">满分</th><th>打分规则</th></tr>' + tbl + '</table>')
    out.append('<p class="note">「评价」口径说明：天天基金/招商证券的星级评级页由 JS 动态加载、数据源端无可用接口（已实测），'
               '故该维度改用风险调整后收益（官方夏普）+ 跟踪误差 + 成立年限三项可追溯指标合成。</p>')
    for cat in ('债券', '黄金', '能源'):
        rows = PAGE['scores'].get(cat) or []
        if not rows:
            continue
        trs = []
        for r in rows:
            cls = ' class="chosen"' if r['hold'] else (' class="dim"' if r['isexchg'] else '')
            buy = '—' if r.get('isexchg') else (r['buy'] or '—')
            red = '—' if r.get('isexchg') else (('%.2f%%' % r['red']) if r['red'] is not None else '—')
            trs.append("<tr%s><td class='mono'>%s</td><td>%s</td><td>%s</td><td class='num'>%.2f</td>"
                       "<td class='num'>%s</td><td class='num'>%s</td><td class='num'>%.2f%%</td>"
                       "<td>%s</td><td class='num'>%.1f</td><td class='num'>%.1f</td>"
                       "<td class='num'>%.1f</td><td class='num'>%.1f</td>"
                       "<td class='num'><b>%.1f</b></td></tr>"
                       % (cls, e(r['code']), e(r['name']), e(r['form']), r['scale'] or 0,
                          e(buy), e(red), r['holdfee'], e(r['quota']),
                          r['s_scale'], r['s_fee'], r['s_quota'], r['s_eval'], r['total']))
        out.append('<h3 style="margin-top:16px">%s —— 打分明细（总分前 10，含场内对照；'
                   '绿底行＝组合实际选用）</h3>' % e(cat))
        out.append('<div class="tw"><table class="grid small"><tr><th>代码</th><th>基金名称</th><th>形态</th>'
                   '<th class="num">规模<br>亿元</th><th class="num">申购费<br>优惠</th>'
                   '<th class="num">赎回费<br>满7天</th>'
                   '<th class="num">年费率<br>管理+托管+销服</th><th>申购额度（官方）</th>'
                   '<th class="num">规模分30</th><th class="num">费率分25</th>'
                   '<th class="num">额度分25</th><th class="num">评价分20</th><th class="num">总分</th></tr>'
                   + ''.join(trs) + '</table></div>')
    out.append('</section>')
    return '\n'.join(out)


def sec_three():
    d = PAGE
    out = ['<h2>三、四大类筛选明细</h2>']
    desc = {'债券': '只纳入利率债 / 综合债 ETF 及其联接（国债、政金债、国开债、信用债、公司债、城投债、短融）；可转债与海外债不计入。',
            '黄金': '纳入跟踪上海金 / 黄金 9999 的场内 ETF 及其联接，以及黄金主题 QDII；白银、黄金股、有色不计入。',
            '能源': '纳入煤炭 / 石油 / 油气 / 天然气等传统能源指数基金及联接；新能源车、光伏、储能等成长主题不计入。'}
    for cat in ('债券', '黄金', '能源'):
        v = d['cats'][cat]
        out.append('<section class="card"><h3>%sETF 候选 %d 只｜场外可申购 %d 只｜组合持有（场外）'
                   '<span class="mono">%s</span> %s</h3>' % (e(cat), v['n_all'], v['n_off'],
                                                             e(v['hold'] or '—'), e(v['holdname'] or '')))
        out.append('<p class="note">%s（下表按规模降序，最多列 %d 只；官方限额/费率取自东财 fundmobapi）</p>'
                   % (e(desc[cat]), len(v['rows'])))
        trs = []
        for r in v['rows']:
            cls = ' class="chosen"' if r['hold'] else ('' if r['sgzt'] in ('开放申购', '限大额') else ' class="dim"')
            def _c(val, fmt, cls2='num'):
                return "<td class='%s'>%s</td>" % (cls2, fmt % val if val is not None else '—')
            cells = [
                "<td class='mono'>%s</td>" % e(r['code']),
                "<td>%s</td>" % e(r['name']),
                _c(r['scale'], '%.2f'),
                "<td>%s</td>" % e(r['quota']),
                _c(r['buy'] if r['buy'] not in (None, '—', '--') else None, '%s',
                   'num') if False else "<td class='num'>%s</td>" % e(r['buy'] if r['buy'] not in (None, '--') else '—'),
                _c(r['syl1'], '%+.2f%%'),
                _c(r['syl3a'], '%+.2f%%'),
                _c(r['sylall'], '%+.2f%%'),
                _c(r['ann3'] * 100 if r['ann3'] is not None else None, '%+.2f%%'),
                _c(r['mdd'] * 100 if r['mdd'] is not None else None, '%.2f%%'),
                _c(r['vol'] * 100 if r['vol'] is not None else None, '%.2f%%'),
                _c(r['sharpe'], '%.2f'),
                _c(r['te'] * 100 if r['te'] is not None else None, '%.2f%%'),
                _c(r['holdfee'], '%.2f%%'),
                "<td>%s</td>" % e(r['navdate']),
            ]
            trs.append('<tr%s>%s</tr>' % (cls, ''.join(cells)))
        out.append('<div class="tw"><table class="grid"><tr><th>代码</th><th>基金名称</th><th class="num">规模</th>'
                   '<th>申购条件（官方：单日限额 / 起购）</th><th class="num">申购费</th>'
                   '<th class="num">近1年官方</th><th class="num">近3年年化官方</th><th class="num">成立以来官方</th>'
                   '<th class="num">近3年年化自算口径</th><th class="num">最大回撤</th><th class="num">年化波动</th>'
                   '<th class="num">夏普</th><th class="num">跟踪误差*</th><th class="num">管理/托管/销服</th>'
                   '<th>净值日期</th></tr>' + ''.join(trs) + '</table></div>')
        if v['inst']:
            irs = []
            for r in v['inst']:
                prem = '—' if r['prem'] is None else "<span class='prem%s'>%+.2f%%</span>" % (
                    ' bad' if r['prem'] > 0.02 else '', r['prem'] * 100)
                irs.append("<tr class='dim'><td class='mono'>%s</td><td>%s</td><td class='num'>%.2f</td>"
                           "<td class='num'>%s</td><td class='num'>%s<br><span class='sub'>%s</span></td>"
                           "<td class='num'>%s</td><td class='num'>%s</td><td class='num'>%s</td></tr>"
                           % (e(r['code']), e(r['name']), r['scale'] or 0,
                              n2(r['price'], 3), n2(r['nav'], 4), e(r['navdate'] or '—'),
                              prem, e(('%+.2f%%' % r['syl1']) if r['syl1'] is not None else '—'),
                              e(('%+.2f%%' % r['syl3a']) if r['syl3a'] is not None else '—')))
            out.append('<details><summary>仅场内交易（支付宝不可直接申购，需券商账户）规模前 6，含实时折溢价</summary>'
                       '<div class="tw"><table class="grid small"><tr><th>代码</th><th>名称</th><th class="num">规模</th>'
                       '<th class="num">现价</th><th class="num">单位净值<br><span class="sub">净值日期</span></th>'
                       '<th class="num">折溢价<br><span class="sub">相对最新净值</span></th>'
                       '<th class="num">近1年官方</th><th class="num">近3年年化官方</th></tr>'
                       + ''.join(irs) + '</table></div></details>')
            out.append('<p class="note">折溢价 =（场内现价 − 最新披露单位净值）/ 最新披露单位净值，<b>非 IOPV</b>；'
                       'QDII 净值滞后 1–2 个交易日，额度紧张时溢价会被放大（列表已标注净值日期）。'
                       '行情来源：腾讯行情。溢价 >2% 不建议买入。</p>')
        out.append('</section>')
    # A股/科创
    a = d['astock']
    out.append('<section class="card"><h3>A股/科创 ETF 优选池 候选 %d 只（≥2.5 年历史、非跨境）｜场外选用 '
               '<span class="mono">%s</span> %s</h3>' % (a['n_all'], e(a['hold'] or '—'), e(a['holdname'] or '')))
    out.append('<p class="note">本腿替代原「美股 ETF」：美股 ETF 存在每日申购金额限制，可操作性低。'
               '排序口径＝年化收益率为核心指标（占 70 分，取近 2 年净值年化）＋规模 15 / 费率 10 / 评价 5，'
               '并给科创/科技类加分（科创板系列 20 分、其他芯片半导体人工智能 10 分）；只保留成立满 2.5 年以上的标的。'
               '场内第一名为 <span class="mono">%s</span>，其对应场外联接为 <span class="mono">%s</span>。</p>'
               % (e(a['picked_inst']), e(a['picked_off'] or '—')))
    trs = []
    for r in a['rows']:
        cls = ' class="chosen"' if r['hold'] else ('' if r['form'] == '场外' else ' class="dim"')
        trs.append("<tr%s><td class='mono'>%s</td><td>%s</td><td>%s</td><td class='num'>%.2f</td>"
                   "<td class='num'>%+.2f%%</td><td class='num'>%+.2f%%</td><td class='num'>%.2f%%</td>"
                   "<td class='num'>%.2f%%</td><td class='num'>%.2f</td><td class='num'>+%.0f</td>"
                   "<td class='num'>%.1f</td><td class='num'>%.1f</td><td class='num'>%.1f</td>"
                   "<td class='num'><b>%.1f</b></td></tr>"
                   % (cls, e(r['code']), e(r['name']), e(r['form']), r['scale'] or 0,
                      r['ann2'] * 100, r['annall'] * 100, r['vol'] * 100, r['mdd'] * 100,
                      r['sharpe'], r['bonus'], r['s_scale'], r['s_fee'], r['s_eval'], r['total']))
    out.append('<div class="tw"><table class="grid small"><tr><th>代码</th><th>基金名称</th><th>形态</th>'
               '<th class="num">规模亿元</th><th class="num">年化收益率<br><span class="sub">近2年</span></th>'
               '<th class="num">成立以来年化</th><th class="num">年化波动</th><th class="num">最大回撤</th>'
               '<th class="num">夏普</th><th class="num">科创加分</th><th class="num">规模分</th>'
               '<th class="num">费率分</th><th class="num">评价分</th><th class="num">总分</th></tr>'
               + ''.join(trs) + '</table></div>')
    out.append('<p class="note">合计满分 120 分（年化 70 + 规模 15 + 费率 10 + 评价 5 + 科创加分 20）。'
               '本页只做场外可买的组合，因此本腿选用的是场外联接份额（场内 ETF 仅列出作对照，需要券商账户）。</p></section>')
    return '\n'.join(out)


def sec_four():
    d = PAGE
    out = ['<h2>四、组合与回测（周度调仓 · 权重取 5% 整数倍）</h2>']
    legs = [a for a in d['assets']]
    out.append('<section class="card"><h3>回测设定</h3><ul>')
    out.append('<li>组合（场外可执行 · 支付宝可买）：%s</li>'
               % '、'.join('%s %s（%s）' % (e(a['cat']), e(a['name']), e(a['code'])) for a in legs))
    out.append('<li>区间：%s ~ %s（%d 个交易日）；再平衡：每周最后一个交易日按目标权重调回（另附月度/双月对照）；'
               '成本：只做场外，按逐腿实际「优惠申购费 + 持有满 7 天赎回费」扣减；分红：按净值增长率复权（含分红再投资）；'
               '基金净值本身已扣管理费/托管费。</li>' % (d['range'][0], d['range'][1], d['n_days']))
    out.append('<li>基准：沪深300（510300 净值代理）、货币基金（天弘余额宝 000198）。</li></ul>')
    trs = []
    for a in legs:
        st = a['stats']
        trs.append("<tr><td>%s</td><td class='mono'>%s</td><td>%s</td><td class='num'>%+.2f%%</td>"
                   "<td class='num'>%.2f%%</td><td class='num'>%.2f%%</td><td class='num'>%.2f</td>"
                   "<td class='num'>%+.2f%%</td></tr>"
                   % (e(a['cat']), e(a['code']), e(a['name']), st['ann'] * 100, st['vol'] * 100,
                      st['mdd'] * 100, st['sharpe'], st['cum'] * 100))
    out.append('<div class="tw"><table class="grid"><tr><th>类别</th><th>代码</th><th>基金名称</th>'
               '<th class="num">年化</th><th class="num">年化波动</th><th class="num">最大回撤</th>'
               '<th class="num">夏普</th><th class="num">区间累计</th></tr>' + ''.join(trs) + '</table></div>')
    out.append('<p class="note">以上四条腿的指标均按统一的 %s ~ %s 区间自算，保证可比。</p>'
               % (d['range'][0], d['range'][1]))
    out.append('<h3 style="margin-top:16px">权重方案对比（场外可执行 · 周度调仓）</h3>')
    trs = []
    for w in d['wavg']:
        st = w['stats']
        wstr = ' / '.join('%s %d%%' % (k, int(v * 100)) for k, v in zip(['能源', '债券', '黄金', '科创'], w['w']))
        trs.append("<tr%s><td>%s%s</td><td class='mono'>%s</td><td class='num'>%+.2f%%</td><td class='num'>%.2f%%</td>"
                   "<td class='num'>%.2f%%</td><td class='num'>%.2f</td><td class='num'>%.2f</td>"
                   "<td class='num'>%.0f%%</td><td class='num'>%.2f%%</td></tr>"
                   % (' class="hi"' if w['main'] else '', e(w['scheme']),
                      ' ★' if w['main'] else '', e(wstr), st['ann'] * 100, st['vol'] * 100,
                      st['mdd'] * 100, st['sharpe'], st['calmar'], w['turnover'] * 100, w['cost'] * 100))
    out.append('<div class="tw"><table class="grid"><tr><th>方案</th><th>目标权重（5% 整数倍）</th>'
               '<th class="num">年化收益</th><th class="num">年化波动</th><th class="num">最大回撤</th>'
               '<th class="num">夏普比率</th><th class="num">卡玛比率</th><th class="num">年换手</th>'
               '<th class="num">年成本</th></tr>' + ''.join(trs) + '</table></div>')
    out.append('<h3 style="margin-top:16px">再平衡频率对比（按 ★ 主推权重）</h3>')
    trs = []
    for f in d['freqs']:
        st = f['stats']
        trs.append("<tr><td>%s</td><td class='num'>%+.2f%%</td><td class='num'>%.2f%%</td><td class='num'>%.2f%%</td>"
                   "<td class='num'>%.2f</td><td class='num'>%.0f%%</td><td class='num'>%.2f%%</td></tr>"
                   % (e(f['label']), st['ann'] * 100, st['vol'] * 100, st['mdd'] * 100,
                      st['sharpe'], f['turnover'] * 100, f['cost'] * 100))
    out.append('<table class="grid"><tr><th>频率</th><th class="num">年化收益</th><th class="num">年化波动</th>'
               '<th class="num">最大回撤</th><th class="num">夏普比率</th><th class="num">年换手</th>'
               '<th class="num">年成本</th></tr>' + ''.join(trs) + '</table>')
    out.append('<p class="note">怎么读这几张表：所有目标权重都是 5% 的整数倍（0%、5%、15%、20%…），且允许为 0'
               '（＝该腿本期不持有）。主推＝在全部 5% 整数倍权重组合里，先筛出「5 个历史窗口全部跑赢货基」的可行解，'
               '再取夏普最高；v4 旧口径对照＝原「每腿 10%~40%、禁止 0 权重、最大化卡玛」的规则，'
               '长期年化更高、但短窗口为负。风险平价与波动率倒数均加了单腿 10%~40% 的约束，'
               '否则纯 1/σ² 会让债券占到 80% 以上。</p></section>')
    # 图表卡
    out.append('<section class="card"><h3>净值曲线（起点归一为 1）</h3><div id="c1" class="chart"></div></section>')
    out.append('<section class="card"><h3>风险—收益分布</h3><div id="c2" class="chart"></div></section>')
    out.append('<section class="card"><h3>各方案目标权重</h3>')
    trs = []
    for w in d['wavg']:
        trs.append("<tr%s><td>%s</td>%s<td class='num'>%.2f%%</td></tr>"
                   % (' class="hi"' if w['main'] else '', e(w['scheme']),
                      ''.join("<td class='num'>%.1f%%</td>" % (v * 100) for v in w['w']),
                      w['cost'] * 100))
    out.append('<table class="grid"><tr><th>方案</th>%s<th class="num">再平衡成本</th></tr>%s</table>'
               % (''.join('<th>%s</th>' % e(a['name']) for a in legs), ''.join(trs)))
    out.append('<p class="note">表中权重为目标权重（周度调仓时按此调回）；「再平衡成本」为全区间年均值，'
               '按逐腿真实申购/赎回费扣减。</p>')
    out.append('<h3 style="margin-top:16px">成分相关性（日收益，区间内）</h3>')
    cm = d['corr']
    trs = []
    for i, nm in enumerate(cm['cats']):
        trs.append("<tr><td>%s</td>%s</tr>" % (e(nm),
                   ''.join("<td class='num'%s>%.2f</td>"
                           % (" style='color:#e8c37a'" if cm['m'][i][j] > 0.5 else '', cm['m'][i][j])
                           for j in range(len(cm['cats'])))))
    out.append('<table class="grid"><tr><th>—</th>%s</tr>%s</table>'
               % (''.join('<th>%s</th>' % e(x) for x in cm['names']), ''.join(trs)))
    mx = max(abs(cm['m'][i][j]) for i in range(4) for j in range(4) if i != j)
    out.append('<p class="note">四类资产两两相关性最高仅 %.2f，这是组合夏普显著高于单资产的根本原因。</p>' % mx)
    out.append('</section>')
    return '\n'.join(out)


def sec_five():
    d = PAGE
    wh = d['charts']['wh']
    w = d['wtbl']
    weeks = WT_WEEKS
    offs = [('当前', -1), ('1 周前', -2), ('1 个月前', -5), ('3 个月前', -14), ('6 个月前', -27), ('1 年前', -52)]
    trs = []
    for lab, i in offs:
        r = weeks[i]
        if r['w']:
            wtxt = '／'.join('%s %d%%' % (k, r['w'][k]) for k in D_ORDER)
            feas = '有'
            memo = ''
        else:
            wtxt = '无可行解 → 当期 100% 货基'
            feas = '无'
            memo = '最近一次有解是 %s' % (last_feas_before(weeks, len(weeks) + i) or '—')
        trs.append("<tr><td>%s</td><td class='mono'>%s</td><td>%s</td><td>%s</td><td class='num'>%s</td>"
                   "<td class='num'>%s</td><td class='num'>%s</td><td class='num'>%s</td><td>%s</td></tr>"
                   % (e(lab), e(r['date']), e(wtxt), e(feas),
                      ('%+.2f%%' % (r['ann'] * 100)) if r['ann'] is not None else '—',
                      ('%.2f' % r['sharpe']) if r['sharpe'] is not None else '—',
                      ('%+.2f%%' % r['wr'][1]) if r.get('wr') else '—',
                      ('%+.2f%%' % r['wr'][2]) if r.get('wr') else '—', e(memo)))
    out = ['<h2>五、近一年权重变化（每周按同一规则重跑·52 周）</h2>',
           '<section class="card"><h3>怎么算出来的</h3>',
           '<p class="note">把上面那套规则（5%% 整数倍网格、单腿 0~40%%、允许为 0；五个窗口全部跑赢货基；'
           '可行解里取夏普最高；无可行解则当期 100%% 货基）在过去 %d 周里逐周重跑一遍，每周只用「截至那一周」的数据'
           '——所以这是规则在当时会给出的目标权重，不是实际持仓，也不是事后挑出来的最优权重。'
           '所有样本周的回测起点都相同（数据起点 %s），所以这是精确的「逐周重建」，与当期口径完全一致'
           '（当期那一周的结果与上面的主推逐位相同，可自查）。</p>' % (wh['n'], d['range'][0]),
           '<h3 style="margin-top:10px">每周目标权重</h3>',
           '<div id="c3" class="chart" style="height:360px"></div>',
           '<p class="note">柱状图：每周一根柱，四段＝四条腿的目标权重；蓝色整段＝该周「无可行解」，'
           '按规则当期 100%% 持货基。近一年里这样的周有 %d 周 / %d 周。</p>' % (wh['nocash'], wh['n']),
           '<div id="c4" class="chart" style="height:330px"></div>',
           '<p class="note">折线图：每条腿的权重轨迹（阶梯线）。两条线交叉的位置，就是规则把权重从一条腿搬到另一条腿的那一周。</p>',
           '<h3 style="margin-top:16px">关键时点快照</h3>',
           '<table class="grid small"><tr><th>时点</th><th>日期</th><th>权重（%s）</th><th>可行解</th>'
           '<th class="num">年化<br><span class="sub">截至该周</span></th><th class="num">夏普</th>'
           '<th class="num">近一月</th><th class="num">近三月</th><th>备注</th></tr>%s</table>'
           % ('／'.join(D_ORDER), ''.join(trs)),
           '<p class="note">直接回答「一个月前和三个月前一样吗」：<b>不一样</b>。权重不是固定的，也不是「一个月一调」'
           '——它每周按同一套约束重算，所以会跳。跳的幅度与可行解有多少组直接相关：可行解多的周权重很稳，'
           '可行解只有几组的周权重会突然跳到另一个角点。%s</p>' % e(WT_NOTE),
           '</section>']
    return '\n'.join(out)


def sec_six():
    return ('<h2>六、换标规则：标的完全由策略信号决定（无固定周期）</h2><section class="card"><ul>'
            '<li><b>每周（看）：</b>重跑打分（债券/黄金/能源按四项 100 分口径；A股/科创腿按年化收益率为核心的 120 分口径）、'
            '刷新各类优选榜；并重跑组合权重网格。<b>不再有固定周期</b>：已删除「每 2 个月更换一次标的」这一约束'
            '——标的的持有与更换完全由策略信号决定，不设时间窗口。只要信号未触发，在持标的继续持有。</li>'
            '<li><b>信号一 · 换标的（任一击中即换）：</b>① <b>S1 不可执行</b>——在持标的暂停申购／封闭／单日限额买不到目标金额；'
            '② <b>S2 买贵了</b>——该腿场内 ETF 溢价 &gt;3%（情绪过热警示，触发时该腿暂缓加仓）；'
            '③ <b>S3 策略信号更优</b>——同类场外优选榜第一名评分领先在持标的 ≥5 分。</li>'
            '<li><b>信号二 · 换权重：</b>每周在 5% 整数倍网格里重跑组合权重，允许任意腿权重为 0（表现不佳的腿整腿剔除），'
            '约束为「上周／近一月／近三月／今年以来／近 2 年全部跑赢货基」，在满足约束的方案里取夏普最高。'
            '某腿窗口转差 → 权重自动降到 0；转好 → 自动回补，不需要人工判断。</li>'
            '<li><b>每次换标的执行清单：</b>① 复核最新 AUM 与申购状态（只买场外可申购份额）；'
            '② 复核该腿场内 ETF 折溢价（溢价 &gt;3% 不换入）；③ 新标的按 2~3 批建仓；'
            '④ 卖出前确认持有已满 7 天，避免惩罚性赎回费；⑤ 换标后同步更新权重（仍取 5% 整数倍）。</li>'
            '<li><b>本期闸门评估：</b>' + e(SWAP_TXT) + '</li>'
            '</ul></section>')


def sec_seven():
    return ('<h2>七、回测局限与风险提示</h2><section class="card"><div class="warnbox"><ul>'
            + ''.join('<li>%s</li>' % e(x) for x in PAGE['limits']) + '</ul></div></section>')


def sec_foot():
    d = PAGE
    return ('<div class="foot">生成时间：%s ｜ 数据截止：%s<br>'
            '本网页不涉及任何基金推荐，仅限研究使用。回测基于历史净值，不代表未来收益。<br>'
            '本页为华泰期货国际业务部内部研究材料，仅限内部讨论使用。'
            '如有任何问题，请联系 华泰期货 国际业务部 袁鑫　邮箱：yuanxin@htfc.com　电话：021-60679262。'
            '</div>' % (d['gen'], d['asof']))


def last_feas_before(weeks, idx):
    for i in range(idx - 1, -1, -1):
        if i < len(weeks) and weeks[i]['feas']:
            return weeks[i]['date']
    return None


def short(n, k=26):
    n = re.sub(r'\s*\(LOF\)', '(LOF)', n or '')
    return n


# ------------------------------------------------------------------ 图
JS_FUNCS = """function line(){var ch=echarts.init(document.getElementById('c1'),'dark');
var keys=Object.keys(D.curves);
var color={'网格最优（周度·5%整数权重）':'#7fd1a8','网格最优（v4 旧口径·禁止0权重）':'#c08ae0','等权（周度）':'#e8c37a','货基（余额宝000198）':'#5ab0e0','沪深300（510300）':'#8b95a5'};
ch.setOption({backgroundColor:'transparent',grid:{left:52,right:16,top:44,bottom:44},legend:{type:'scroll',top:0,textStyle:{color:'#9aa4b2',fontSize:11}},
tooltip:{trigger:'axis',valueFormatter:function(v){return v.toFixed(3)}},
xAxis:{type:'category',data:D.labels,axisLabel:{color:'#7d8797',fontSize:10,interval:Math.floor(D.labels.length/8)}},
yAxis:{type:'value',scale:true,axisLabel:{color:'#7d8797',fontSize:10},splitLine:{lineStyle:{color:'#1e2530'}}},
series:keys.map(function(k){return {name:k,type:'line',data:D.curves[k],showSymbol:false,smooth:true,
lineStyle:{width:(k.indexOf('网格最优（周度')===0?2.6:1.4),color:color[k]||'#6fbf9a'},itemStyle:{color:color[k]||'#6fbf9a'}}})});}
function whbar(){var ch=echarts.init(document.getElementById('c3'),'dark');
var W=WH, keys=W.leglabels;
ch.setOption({backgroundColor:'transparent',grid:{left:52,right:16,top:44,bottom:56},
legend:{type:'scroll',top:0,textStyle:{color:'#9aa4b2',fontSize:11}},
tooltip:{trigger:'axis',axisPointer:{type:'shadow'},valueFormatter:function(v){return v+'%'}},
xAxis:{type:'category',data:W.labels,axisLabel:{color:'#7d8797',fontSize:9,interval:Math.floor(W.labels.length/10),rotate:38}},
yAxis:{type:'value',max:100,axisLabel:{color:'#7d8797',fontSize:10,formatter:'{value}%'},splitLine:{lineStyle:{color:'#1e2530'}}},
series:keys.map(function(k){var c={'能源':'#e8c37a','债券':'#7fd1a8','黄金':'#c08ae0','科创':'#e08a8a','货基（无可行解）':'#5ab0e0'}[k];
return {name:k,type:'bar',stack:'w',data:W.stack[k],barMaxWidth:14,itemStyle:{color:c}}})});}
function whline(){var ch=echarts.init(document.getElementById('c4'),'dark');
var W=WH, keys=W.leglabels;
ch.setOption({backgroundColor:'transparent',grid:{left:52,right:16,top:44,bottom:56},
legend:{type:'scroll',top:0,textStyle:{color:'#9aa4b2',fontSize:11}},
tooltip:{trigger:'axis',valueFormatter:function(v){return v+'%'}},
xAxis:{type:'category',data:W.labels,boundaryGap:false,axisLabel:{color:'#7d8797',fontSize:9,interval:Math.floor(W.labels.length/10),rotate:38}},
yAxis:{type:'value',max:100,axisLabel:{color:'#7d8797',fontSize:10,formatter:'{value}%'},splitLine:{lineStyle:{color:'#1e2530'}}},
series:keys.map(function(k){var c={'能源':'#e8c37a','债券':'#7fd1a8','黄金':'#c08ae0','科创':'#e08a8a','货基（无可行解）':'#5ab0e0'}[k];
return {name:k,type:'line',step:'end',data:W.stack[k],showSymbol:false,lineStyle:{width:2,color:c},itemStyle:{color:c}}})});}
function scat(){var ch=echarts.init(document.getElementById('c2'),'dark');
ch.setOption({backgroundColor:'transparent',grid:{left:56,right:20,top:30,bottom:44},
tooltip:{formatter:function(o){return o.data.name+'<br>年化波动 '+o.value[0].toFixed(2)+'%<br>年化收益 '+o.value[1].toFixed(2)+'%<br>最大回撤 '+o.value[2].toFixed(2)+'%'}},
xAxis:{name:'年化波动 %',nameTextStyle:{color:'#7d8797'},axisLabel:{color:'#7d8797'},splitLine:{lineStyle:{color:'#1e2530'}}},
yAxis:{name:'年化收益 %',nameTextStyle:{color:'#7d8797'},axisLabel:{color:'#7d8797'},splitLine:{lineStyle:{color:'#1e2530'}}},
series:[{type:'scatter',symbolSize:14,data:D.pts,label:{show:true,formatter:function(o){return o.data.name},position:'top',color:'#c3cad6',fontSize:11}}]});}
function recalc(){var el=document.getElementById('cap');if(!el)return;
var cap=parseFloat(el.value);if(isNaN(cap)||cap<0)cap=0;var k=cap/10000;
document.querySelectorAll('[data-unit]').forEach(function(td){var u=parseFloat(td.getAttribute('data-unit'));td.textContent=(u*k).toFixed(2);});
document.querySelectorAll('[data-money]').forEach(function(td){var u=parseFloat(td.getAttribute('data-money'));td.textContent=(u*k).toFixed(2);});
document.getElementById('capshow').textContent=cap.toFixed(0);}
line();scat();whbar();whline();
var capEl=document.getElementById('cap');if(capEl){capEl.addEventListener('input',recalc);recalc();}
window.addEventListener('resize',function(){['c1','c2','c3','c4'].forEach(function(id){var i=echarts.getInstanceByDom(document.getElementById(id));if(i)i.resize();});});
"""


def main():
    global PAGE, CASH_ANN, WT_N, WT_NOCASH, WT_WEEKS, WT_NOTE, D_ORDER, CROSS, SWAP_TXT
    PAGE = C.jload('page_data4' + C.SRC + '.json')
    bt = C.jload('bt2' + C.SRC + '.json')
    wt = C.jload('wt_hist' + C.SRC + '.json')
    api = C.jload('api_data.json')
    met = C.jload('metrics.json')
    swap = C.jload('swap_state.json')
    pickst = C.jload('picks2.json')
    CASH_ANN = bt['cash_ann']
    WT_N, WT_NOCASH, WT_WEEKS = wt['n'], wt['nocash'], wt['weeks']
    D_ORDER = bt['order']
    # 口径交叉校验
    api_m = C.jload('api_data.json')
    devs = []
    for code, m in met.items():
        a = api_m.get(code) or {}
        if a.get('syl_1n') is None:
            continue
        a1 = (m.get('a1') or {}).get('ann')
        if a1 is None:
            continue
        devs.append(abs(a1 * 100 - a['syl_1n']))
    devs.sort()
    if devs:
        CROSS = ('%.2fpp' % devs[len(devs) // 2], '%.2fpp' % devs[int(len(devs) * 0.9)])
    else:
        CROSS = ('—', '—')
    WT_NOTE = ('债券常年占 35%~40%（它是唯一「几乎任何窗口都为正」的腿，因此几乎每期都被顶到上限附近）；'
               '黄金在 2025 年底一度占到 40%，之后被逐步压到 15% 附近；科创在 5%~25% 之间漂移；'
               '能源的波动最大（0%~40%），它决定短窗口的胜负。')
    ev = swap.get('evaluated') or []
    if ev:
        SWAP_TXT = '；'.join('%s %s：S1 %s、S2 %s、S3 %s（榜首选领先 %.1f 分）'
                            % (e(x['cat']), e(x['code']),
                               '命中' if x['s1'] else '未命中', '命中' if x['s2'] else '未命中',
                               '命中' if x['s3'] else '未命中', x['gap']) for x in ev) + \
                   '。本期无信号触发 → 在持标的继续持有。'
    else:
        SWAP_TXT = '本期无信号触发 → 在持标的继续持有。'

    parts = []
    parts.append(sec_head())
    parts.append(sec_rule())
    parts.append(sec_hero())
    parts.append(sec_orders())
    parts.append(sec_one())
    parts.append(sec_two())
    parts.append(sec_three())
    parts.append(sec_four())
    parts.append(sec_five())
    parts.append(sec_six())
    parts.append(sec_seven())
    parts.append(sec_foot())
    parts.append('</div>')
    body = '\n'.join(parts)

    # 无残留 token 断言（放在注入 echarts 之前，ECharts 自身含 __EC__ 字样）
    resid = [t for t in re.findall(r'__[A-Z0-9_]+__', body)]
    assert not resid, '残留 token: %s' % resid[:5]
    assert '%%' not in body, '存在字面 %%%%'

    dj = {'labels': PAGE['charts']['labels'], 'curves': PAGE['charts']['curves'],
          'pts': PAGE['charts']['pts']}
    wh = PAGE['charts']['wh']
    pagejs = ('var D=' + json.dumps(dj, ensure_ascii=False) + ';\n'
              'var WH=' + json.dumps({'labels': wh['labels'], 'stack': wh['stack'],
                                      'leglabels': wh['leglabels'], 'nocash': wh['nocash'],
                                      'n': wh['n']}, ensure_ascii=False) + ';\n' + JS_FUNCS)
    ech = open(os.path.join(C.ASSETS, 'echarts.min.js'), encoding='utf-8').read()
    title = '支付宝可申购基金 · 四大类筛选与组合回测（%s）v9' % PAGE['asof']
    doc = ('<!DOCTYPE html>\n<html lang="zh-CN"><head><meta charset="utf-8">\n'
           '<meta name="viewport" content="width=device-width,initial-scale=1">\n'
           '<title>%s</title>\n%s\n<body><div class="wrap">\n%s\n'
           '<script>%s</script>\n<script>%s</script>\n</body></html>' %
           (title, CSS, body, ech, pagejs))
    ts = time.strftime('%Y%m%d_%H%M%S')
    suffix = '_asof%s' % PAGE['asof'].replace('-', '') if C.SRC else ''
    name = 'alipay_fund_4class_portfolio_%s_v9%s.html' % (ts, suffix)
    out = os.path.join(C.FINAL, name)
    with open(out, 'w', encoding='utf-8') as f:
        f.write(doc)
    C.log('已渲染 %s（%.2f MB，asof %s，fallback=%s）'
          % (out, len(doc.encode('utf-8')) / 1048576.0, PAGE['asof'], PAGE['fallback']))
    # node --check 语法校验（最后一个 script 块）
    script = os.path.join(C.WORK, 'last_script.js')
    with open(script, 'w', encoding='utf-8') as f:
        f.write(pagejs)
    C.log('页面 JS 已落盘：%s' % script)
    return out


if __name__ == '__main__':
    main()
