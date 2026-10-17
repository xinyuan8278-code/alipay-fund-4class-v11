# -*- coding: utf-8 -*-
"""step 13 · 在原站基础上追加「bt 引擎多策略横评与权重网格（交叉验证）」章节，
渲染成一个新的单文件站点（不改动原渲染器 o_build_page9.py 的行为）。

依赖同目录的 o_build_page9（复用 CSS / 各 sec_* / JS），
外加 bt_run/out/ 下由 bt-etf-backtest 技能产出的四个文件：
  bt_metrics.csv / bt_grid.json / bt_charts.json

用法：
    python o_build_bt_page.py            # 最新口径
    QDII_SRC=_ref python o_build_bt_page.py
输出：outputs/final/alipay_fund_4class_bt_<YYYYMMDD>_<HHMMSS>_v10.html
"""
import os, re, csv, json, time
import common as C
import o_build_page9 as B9

BT_DIR = os.path.join(C.ROOT, 'bt_run', 'out')
COLOR = {'债券': '#7fd1a8', '能源': '#e8c37a', '黄金': '#c08ae0', '科创': '#e08a8a', '现金': '#5ab0e0'}
STRAT_COLOR = {'买入持有·不再平衡': '#8b95a5', '等权·月度再平衡': '#e8c37a',
               '固定权重40/40/15/5·月度': '#7fd1a8', '逆波动率·月度': '#5ab0e0',
               '风险平价ERC·月度': '#c08ae0', '双动量Top2·月度': '#e08a8a'}


# --------------------------------------------------------------- 取数
def load_bt():
    ch = json.load(open(os.path.join(BT_DIR, 'bt_charts.json'), encoding='utf-8'))
    gr = json.load(open(os.path.join(BT_DIR, 'bt_grid.json'), encoding='utf-8'))
    met = {}
    with open(os.path.join(BT_DIR, 'bt_metrics.csv'), encoding='utf-8-sig', newline='') as f:
        rows = list(csv.reader(f))
    hdr = rows[0][1:]
    for r in rows[1:]:
        if not r or not r[0].strip():
            continue
        vals = {}
        for k, v in zip(hdr, r[1:]):
            try:
                vals[k] = float(v)
            except (TypeError, ValueError):
                vals[k] = None
        met[r[0].strip()] = vals
    return {'charts': ch, 'grid': gr, 'metrics': met}


def fmt_pct(v, d=2, sign=True):
    if v is None:
        return '—'
    return ('%+.*f%%' % (d, v * 100)) if sign else ('%.*f%%' % (d, v * 100))


def fmt_num(v, d=2):
    return '—' if v is None else ('%.*f' % (d, v))


# --------------------------------------------------------------- 章节
def sec_bt():
    B, e = BT, B9.e
    ch, gr, met = B['charts'], B['grid'], B['metrics']
    rng, cols = gr['range'], gr['cols']
    legs = C.jload('bt2' + C.SRC + '.json')['legs']
    proxy = [('债券', '511010', '国债ETF 国泰'), ('能源', '159930', '能源ETF 汇添富'),
             ('黄金', '518880', '黄金ETF 华安'), ('科创', '588000', '科创50ETF 华夏')]
    out = ['<h2>八、bt 引擎多策略横评与权重网格（交叉验证）</h2>']
    out.append(
        '<div class="rule">换个引擎、换批标的、换套口径把上面的结论再验一遍，'
        '看它是不是「自家方法造成的」。回测引擎用 <b>pmorissette/bt 1.4.1</b>'
        '（社区标准的权重型回测框架）；标的换成四条腿对应的<b>场内 ETF 代理</b>（前复权日线，'
        '指数成分与场外联接一致）；区间 <b>%s ~ %s</b>（前 252 个交易日作 warmup 不参与统计）；'
        '<b>月度再平衡</b>，单边成本 2.5bp。<br>'
        '<b>注意口径差异</b>：本页用的是<b>场内复权价</b>、月度调仓、无申赎费；'
        '正文四~五节用的是<b>场外净值</b>、周度调仓、含申购费与赎回费。'
        '两者结论方向可比，数字不可直接对读。</div>' % (rng[0], rng[1]))

    # 1) 标的映射
    out.append('<section class="card"><h3>1. 标的映射：场外（本页组合）→ 场内 ETF 代理（bt 回测）</h3>')
    trs = []
    for i, (cat, code, nm) in enumerate(proxy):
        L = ch['legs'].get(cat) or {}
        of = legs.get(cat) or {}
        if i == 0:
            pass
        trs.append(
            "<tr><td>%s</td><td class='mono'>%s<br><span class='sub'>%s</span></td>"
            "<td class='mono'>%s<br><span class='sub'>%s</span></td>"
            "<td class='num'>%s</td><td class='num'>%s</td><td class='num'>%s</td></tr>"
            % (e(cat), e(of.get('code', '')), e(of.get('name', '')),
               e(code), e(nm),
               e(fmt_pct(L.get('ann'))), e(fmt_pct(L.get('vol'), 2, False)),
               e(fmt_pct(L.get('mdd'), 2, False))))
    out.append('<div class="tw"><table class="grid small"><tr><th>腿</th><th>场外标的（本页组合持有）</th>'
               '<th>场内 ETF 代理（bt 回测）</th><th class="num">区间年化</th>'
               '<th class="num">年化波动</th><th class="num">最大回撤</th></tr>'
               + ''.join(trs) + '</table></div>')
    out.append('<p class="note">区间统计同下表口径（%s ~ %s）。'
               '同样的区间里，<b>科创腿年化仅 +0.61%%、最大回撤 −51.68%%</b>，'
               '是四条腿里风险收益比最差的一条——这一点直接决定了后面网格里它的权重。</p></section>'
               % (rng[0], rng[1]))

    # 2) 六策略指标表
    out.append('<section class="card"><h3>2. 六套配置策略指标对比（同区间、同成本）</h3>')
    trs, best = [], {'夏普': max(met, key=lambda k: met[k]['夏普'] or -9),
                     '年化收益': max(met, key=lambda k: met[k]['年化收益'] or -9),
                     '卡玛': max(met, key=lambda k: met[k]['卡玛'] or -9)}
    for nm, m in met.items():
        tags = ''.join('<span class="pick">%s最优</span>' % t for t, k in best.items() if k == nm)
        cls = ' class="chosen"' if tags else ''
        trs.append("<tr%s><td>%s%s</td><td class='num'>%s</td><td class='num'>%s</td>"
                   "<td class='num'>%s</td><td class='num'>%s</td><td class='num'>%s</td>"
                   "<td class='num'>%s</td><td class='num'>%s</td><td class='num'>%s</td>"
                   "<td class='num'>%s</td></tr>"
                   % (cls, e(nm), tags,
                      e(fmt_pct(m['累计收益'])), e(fmt_pct(m['年化收益'])),
                      e(fmt_pct(m['年化波动'], 2, False)), e(fmt_num(m['夏普'])),
                      e(fmt_pct(m['最大回撤'], 2, False)), e(fmt_num(m['卡玛'])),
                      e(fmt_pct(m['最佳月'])), e(fmt_pct(m['最差月'])),
                      e(fmt_num(m['年化换手']))))
    out.append('<div class="tw"><table class="grid small"><tr><th>策略</th><th class="num">累计收益</th>'
               '<th class="num">年化收益</th><th class="num">年化波动</th><th class="num">夏普</th>'
               '<th class="num">最大回撤</th><th class="num">卡玛</th><th class="num">最佳月</th>'
               '<th class="num">最差月</th><th class="num">年化换手</th></tr>'
               + ''.join(trs) + '</table></div>')
    out.append('<p class="note">夏普最高的是 <b>逆波动率（2.16）</b>，但它的年化只有 6.11%'
               '——因为该算法把 95.5% 的仓位压给了波动仅 1.5% 的债券腿，实质退化成「债券基金」。'
               '年化最高的是 <b>双动量 Top2（14.81%）</b>，代价是波动 18.65%、回撤 −20.72%、'
               '年化换手 4.61（月度调仓换掉近 5 倍资产，对交易成本极敏感）。'
               '<b>风险平价 ERC 是六套里综合最均衡的</b>：年化 11.76%、波动 7.98%、'
               '夏普 1.49、回撤仅 −6.00%、卡玛 1.96。</p></section>')
    out.append('<section class="card"><h3>净值曲线（区间起点归一为 1）</h3>'
               '<div id="c5" class="chart"></div></section>')

    # 3) 风险—收益散点（网格 + 六策略）
    out.append('<section class="card"><h3>3. 风险—收益分布：68 组固定权重网格 + 六套策略</h3>'
               '<div id="c6" class="chart"></div>'
               '<p class="note">绿点＝夏普 ≥1.2 的网格组合，黄点＝1.0~1.2，灰点＝&lt;1.0；'
               '紫菱＝六套策略的位置。左上方是「同样波动、收益更高」的占优区域，'
               '越靠左上越好。<b>网格整体比六套策略更贴近左上角</b>——'
               '因为网格是在已知区间上挑的（后视偏差），这一点在第 6 节会再强调。</p></section>')

    # 4) 网格 Top 表
    out.append('<section class="card"><h3>4. 固定权重网格 Top 组合（步长 10%，单腿 0~40%）</h3>')
    ok = [g for g in gr['grid'] if g['sharpe'] is not None]
    groups = [('夏普最优', sorted(ok, key=lambda x: -x['sharpe'])[:6]),
              ('卡玛最优', sorted(ok, key=lambda x: -(x['calmar'] or -9))[:5]),
              ('年化最优', sorted(ok, key=lambda x: -x['ann'])[:5])]
    for title, rows in groups:
        trs = []
        for g in rows:
            wtag = '/'.join('%d' % x for x in g['w'])
            trs.append("<tr><td class='mono'>%s</td><td class='num'>%s</td><td class='num'>%s</td>"
                       "<td class='num'><b>%s</b></td><td class='num'>%s</td><td class='num'>%s</td>"
                       "<td class='num'>%s</td></tr>"
                       % (e(wtag), e(fmt_pct(g['ann'])), e(fmt_pct(g['vol'], 2, False)),
                          e(fmt_num(g['sharpe'])), e(fmt_pct(g['mdd'], 2, False)),
                          e(fmt_num(g['calmar'])), e(fmt_num(g['turnover']))))
        h4 = ('<h4 style="margin:12px 0 4px">%s（权重按 债券/能源/黄金/科创 顺序）</h4>'
              % e(title))
        out.append(h4 + '<div class="tw"><table class="grid small"><tr><th>权重</th><th class="num">年化收益</th>'
                   '<th class="num">年化波动</th><th class="num">夏普</th><th class="num">最大回撤</th>'
                   '<th class="num">卡玛</th><th class="num">年化换手</th></tr>'
                   + ''.join(trs) + '</table></div>')
    nz = [g for g in ok if g['w'][3] > 0]
    out.append('<p class="note">三个口径都指向同一件事：<b>债券腿打底、黄金腿进攻、'
               '能源腿控比例、科创腿要么砍掉要么压在 10%% 以内</b>。'
               '68 组里夏普 Top6 中只有 %d 组给了科创&lt;=10%% 的正权重；'
               '全网格里科创权重为 0 的组合，平均夏普反而更高。'
               '与正文第 4~5 节「债券常顶到 35~40%% 上限、能源决定短窗口胜负」的判断一致。</p></section>'
               % len([g for g in sorted(ok, key=lambda x: -x['sharpe'])[:6] if g['w'][3] <= 10]))

    # 5) 权重演变
    out.append('<section class="card"><h3>5. 算法型策略的权重演变（月度，堆叠面积）</h3>'
               '<div id="c7" class="chart" style="height:300px"></div>'
               '<div id="c8" class="chart" style="height:300px"></div>'
               '<div id="c9" class="chart" style="height:300px"></div>'
               '<p class="note">自上而下：逆波动率 / 风险平价 ERC / 双动量 Top2。'
               '逆波动率的债券权重长期贴在 90% 以上（算法被最低波动资产吸走）；'
               'ERC 最均衡，债券 55~60%、黄金与能源各 15~20%、科创 5~8%；'
               '双动量的权重是「整腿进出」，最近一期已切到 债券 51.8% + 科创 48.2%，'
               '能源与黄金双双归零——这是它回撤最深、换手最高的原因。</p></section>')

    # 6) 结论
    out.append('<section class="card"><h3>6. 交叉验证结论</h3><ul>')
    for t in CONCL:
        out.append('<li>%s</li>' % t)
    out.append('</ul></section>')

    # 7) 局限
    out.append('<section class="card"><h3>7. 本节的局限（务必读）</h3>'
               '<div class="warnbox"><ul>'
               '<li><b>后视偏差</b>：68 组网格是在"已知这段历史"的前提下挑出来的最优，'
               '年化与夏普都偏乐观；它适合用来做「权重敏感度」判断，不能当成可复制的收益预期。</li>'
               '<li><b>标的不是同一个东西</b>：场内 ETF 与场外联接基金在跟踪误差、'
               '申赎费、T+1/T+2 确认上都有差异，本节的绝对收益与正文不可直接对读。</li>'
               '<li><b>未建模场外申赎</b>：7 天内 1.5% 惩罚性赎回费、每日限购额、'
               '暂停申购等约束在 bt 里都没有体现——这正是正文改用场外净值的理由。</li>'
               '<li><b>未建模分红税与冲击成本</b>：复权价隐含了分红再投，但没有税费与滑点。</li>'
               '<li><b>warmup 会吃掉前一年</b>：指标区间从 2022-01 起算，'
               '包含了 2022 年的股债双杀，这也是科创腿数据难看的原因之一。</li>'
               '</ul></div></section>')
    return '\n'.join(out)


CONCL = [
    '<b>结论 1｜原站的核心判断被独立引擎确认。</b>换引擎（bt）、换标的（场内 ETF）、换调仓频率'
    '（周→月）之后，最优权重依然是「债券打底 + 贵金属进攻 + 能源控比例 + 削减科创」，'
    '说明正文那套 5% 网格不是方法artifact。',
    '<b>结论 2｜科创腿是这三年最大的拖累。</b>区间内科创年化 +0.61%、波动 34.21%、'
    '最大回撤 −51.68%；网格夏普 Top6 里它要么 0%、要么 ≤10%。'
    '正文给它 5% 的权重，已经从「按分数应该给更多」退到了「风险预算允许的下限」——'
    '这一条正好互为印证。',
    '<b>结论 3｜黄金的性价比被低估。</b>夏普最优解是 债券40/能源20/黄金40/科创0'
    '（夏普 1.34、年化 12.53%），比正文主推的 40/40/15/5（bt 口径夏普 1.04）高出一截。'
    '差异全部来自「把能源的 20pp 换成黄金」。若单看这三年，黄金（年化 19.75%、波动 18.25%）'
    '确实比能源（年化 14.97%、波动 25.74%）更划算。',
    '<b>结论 4｜ERC / 逆波动率值得作为「低波版本」的备选。</b>风险平价 ERC 在'
    '年化只少 0.4pp 的情况下把波动从 12.6% 压到 8.0%、回撤从 −9.6% 压到 −6.0%，'
    '卡玛 1.96 是六套里最高的。对回撤敏感的账户，这是一个可以直接采用的权重来源。',
    '<b>结论 5｜双动量不适合这个标的池。</b>年化最高（14.81%）但换手 4.61、'
    '回撤 −20.72%，且它的胜负几乎全押在「能源 vs 黄金」的月度切换上；'
    '考虑到场外 T+1 确认与 7 天内赎回费，这套动量在场外口径下会被成本吃掉一大块。',
    '<b>下一步</b>：若要在正文里动权重，优先考虑的是「能源 40%→20%、黄金 15%→40%」这一步；'
    '但这一步只在 2022-2026 这个区间被验证过，跨区间稳定性还没检验——'
    '建议先跑一遍滚动窗口（每 6 个月重构一次权重）再定。',
]


# --------------------------------------------------------------- JS
BT_JS = """
function btCurve(){var ch=echarts.init(document.getElementById('c5'),'dark');
var C5=BT.curve,keys=C5.order,col=__SC__;
ch.setOption({backgroundColor:'transparent',grid:{left:56,right:16,top:44,bottom:44},
legend:{type:'scroll',top:0,textStyle:{color:'#9aa4b2',fontSize:11}},
tooltip:{trigger:'axis',valueFormatter:function(v){return v==null?'—':v.toFixed(3)}},
xAxis:{type:'category',data:C5.labels,axisLabel:{color:'#7d8797',fontSize:10,interval:Math.floor(C5.labels.length/8)}},
yAxis:{type:'value',scale:true,axisLabel:{color:'#7d8797',fontSize:10},splitLine:{lineStyle:{color:'#1e2530'}}},
series:keys.map(function(k){return {name:k,type:'line',data:C5.series[k],showSymbol:false,smooth:true,
lineStyle:{width:(k.indexOf('风险平价')===0||k.indexOf('双动量')===0?2.4:1.4),color:col[k]||'#6fbf9a'},
itemStyle:{color:col[k]||'#6fbf9a'}}})});}
function btScat(){var ch=echarts.init(document.getElementById('c6'),'dark');
var G=BT.grid.grid.map(function(g){var c=g.sharpe>=1.2?'#7fd1a8':(g.sharpe>=1.0?'#e8c37a':'#8b95a5');
return {name:g.w.join('/'),value:[g.vol*100,g.ann*100,g.sharpe,g.mdd*100],itemStyle:{color:c,opacity:0.9}};});
var S=BT.pts.map(function(p){return {name:p.name,value:[p.vol,p.ann,p.sharpe,p.mdd],symbol:'diamond',
symbolSize:16,itemStyle:{color:p.color},label:{show:true,formatter:function(o){return o.data.name},
position:'top',color:'#c3cad6',fontSize:11}};});
ch.setOption({backgroundColor:'transparent',grid:{left:56,right:20,top:30,bottom:44},
legend:{top:0,textStyle:{color:'#9aa4b2',fontSize:11},data:['固定权重网格','六套策略']},
tooltip:{formatter:function(o){return o.data.name+'<br>年化波动 '+o.value[0].toFixed(2)+'%<br>年化收益 '
+o.value[1].toFixed(2)+'%<br>夏普 '+(o.value[2]==null?'—':o.value[2].toFixed(2))+'<br>最大回撤 '+o.value[3].toFixed(2)+'%'}},
xAxis:{name:'年化波动 %',nameTextStyle:{color:'#7d8797'},axisLabel:{color:'#7d8797'},splitLine:{lineStyle:{color:'#1e2530'}}},
yAxis:{name:'年化收益 %',nameTextStyle:{color:'#7d8797'},axisLabel:{color:'#7d8797'},splitLine:{lineStyle:{color:'#1e2530'}}},
series:[{name:'固定权重网格',type:'scatter',data:G,symbolSize:11},
{name:'六套策略',type:'scatter',data:S,symbolSize:16}]});}
function btW(id,key){var el=document.getElementById(id);if(!el)return;
var ch=echarts.init(el,'dark');var W=BT.weights[key];if(!W)return;var col=__LC__;
ch.setOption({backgroundColor:'transparent',grid:{left:52,right:16,top:34,bottom:40},
title:{text:key,left:0,top:0,textStyle:{color:'#c3cad6',fontSize:12,fontWeight:500}},
legend:{top:0,right:0,textStyle:{color:'#9aa4b2',fontSize:11}},
tooltip:{trigger:'axis',valueFormatter:function(v){return (v*100).toFixed(1)+'%'}},
xAxis:{type:'category',data:W.dates,boundaryGap:false,
axisLabel:{color:'#7d8797',fontSize:9,interval:Math.floor(W.dates.length/8)}},
yAxis:{type:'value',max:1,axisLabel:{color:'#7d8797',fontSize:10,formatter:function(v){return (v*100)+'%'}},
splitLine:{lineStyle:{color:'#1e2530'}}},
series:W.legs.map(function(k){return {name:k,type:'line',stack:'w',areaStyle:{opacity:0.8},
data:W.vals[k],showSymbol:false,lineStyle:{width:0.6,color:col[k]||'#6fbf9a'},itemStyle:{color:col[k]||'#6fbf9a'}}})});}
btCurve();btScat();btW('c7','逆波动率·月度');btW('c8','风险平价ERC·月度');btW('c9','双动量Top2·月度');
window.addEventListener('resize',function(){['c5','c6','c7','c8','c9'].forEach(function(id){
var i=echarts.getInstanceByDom(document.getElementById(id));if(i)i.resize();});});
"""
BT_JS = (BT_JS.replace("__SC__", json.dumps(STRAT_COLOR, ensure_ascii=False))
              .replace("__LC__", json.dumps(COLOR, ensure_ascii=False)))





# --------------------------------------------------------------- 组装
def prepare():
    """复用 o_build_page9 的全局与准备逻辑（只设值，不渲染）。"""
    B9.PAGE = C.jload('page_data4' + C.SRC + '.json')
    bt = C.jload('bt2' + C.SRC + '.json')
    wt = C.jload('wt_hist' + C.SRC + '.json')
    B9.CASH_ANN = bt['cash_ann']
    B9.WT_N, B9.WT_NOCASH, B9.WT_WEEKS = wt['n'], wt['nocash'], wt['weeks']
    B9.D_ORDER = bt['order']
    B9.SRC_JSON = None
    met, api_m = C.jload('metrics.json'), C.jload('api_data.json')
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
    B9.CROSS = ('%.2fpp' % devs[len(devs) // 2], '%.2fpp' % devs[int(len(devs) * 0.9)]) if devs else ('—', '—')
    B9.WT_NOTE = ('债券常年占 35%~40%（它是唯一「几乎任何窗口都为正」的腿，因此几乎每期都被顶到上限附近）；'
                  '黄金在 2025 年底一度占到 40%，之后被逐步压到 15% 附近；科创在 5%~25% 之间漂移；'
                  '能源的波动最大（0%~40%），它决定短窗口的胜负。')
    swap = C.jload('swap_state.json')
    ev = swap.get('evaluated') or []
    B9.SWAP_TXT = ('；'.join('%s %s：S1 %s、S2 %s、S3 %s（榜首选领先 %.1f 分）'
                            % (B9.e(x['cat']), B9.e(x['code']),
                               '命中' if x['s1'] else '未命中', '命中' if x['s2'] else '未命中',
                               '命中' if x['s3'] else '未命中', x['gap']) for x in ev)
                   + '。本期无信号触发 → 在持标的继续持有。') if ev else '本期无信号触发 → 在持标的继续持有。'


def main():
    global BT
    prepare()
    BT = load_bt()

    secs = [B9.sec_head(), B9.sec_rule(), B9.sec_hero(), B9.sec_orders(),
            B9.sec_one(), B9.sec_two(), B9.sec_three(), B9.sec_four(), B9.sec_five(),
            B9.sec_six(), B9.sec_seven(), sec_bt(), B9.sec_foot(), '</div>']
    body = '\n'.join(secs)

    resid = re.findall(r'__[A-Z0-9_]+__', body)
    assert not resid, '残留 token: %s' % resid[:5]
    assert '%%' not in body, '存在字面 %%%%'

    p = B9.PAGE
    dj = {'labels': p['charts']['labels'], 'curves': p['charts']['curves'], 'pts': p['charts']['pts']}
    wh = p['charts']['wh']
    btjs = {'curve': BT['charts']['curve'], 'weights': BT['charts']['weights'],
            'grid': {'cols': BT['grid']['cols'], 'step': BT['grid']['step'],
                     'grid': BT['grid']['grid']},
            'pts': [{'name': k, 'vol': v['年化波动'] * 100, 'ann': v['年化收益'] * 100,
                     'sharpe': v['夏普'], 'mdd': v['最大回撤'] * 100, 'color': STRAT_COLOR.get(k, '#8b95a5')}
                    for k, v in BT['metrics'].items()]}
    pagejs = ('var D=' + json.dumps(dj, ensure_ascii=False) + ';\n'
              'var WH=' + json.dumps({'labels': wh['labels'], 'stack': wh['stack'],
                                      'leglabels': wh['leglabels'], 'nocash': wh['nocash'],
                                      'n': wh['n']}, ensure_ascii=False) + ';\n'
              + B9.JS_FUNCS +
              '\nvar BT=' + json.dumps(btjs, ensure_ascii=False) + ';\n' + BT_JS)
    ech = open(os.path.join(C.ASSETS, 'echarts.min.js'), encoding='utf-8').read()
    title = ('支付宝可申购基金 · 四大类筛选与组合回测 + bt 引擎多策略横评（%s）v10'
             % p['asof'])
    doc = ('<!DOCTYPE html>\n<html lang="zh-CN"><head><meta charset="utf-8">\n'
           '<meta name="viewport" content="width=device-width,initial-scale=1">\n'
           '<title>%s</title>\n%s\n<body><div class="wrap">\n%s\n'
           '<script>%s</script>\n<script>%s</script>\n</body></html>'
           % (title, B9.CSS, body, ech, pagejs))
    ts = time.strftime('%Y%m%d_%H%M%S')
    suffix = '_asof%s' % p['asof'].replace('-', '') if C.SRC else ''
    out = os.path.join(C.FINAL, 'alipay_fund_4class_bt_%s_v10%s.html' % (ts, suffix))
    with open(out, 'w', encoding='utf-8') as f:
        f.write(doc)
    C.log('已渲染 %s（%.2f MB，asof %s）' % (out, len(doc.encode('utf-8')) / 1048576.0, p['asof']))
    with open(os.path.join(C.WORK, 'last_bt_script.js'), 'w', encoding='utf-8') as f:
        f.write(pagejs)
    return out


if __name__ == '__main__':
    main()
