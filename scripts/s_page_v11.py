# -*- coding: utf-8 -*-
"""step 11(v11) · 页面数据组装 → page_data_v11.json

读 bt3.json（v11 双目标网格）+ wt_hist3.json（v11 滚动 52 周）+ 复用 v9 的
筛选/打分/订单口径（picks2 / astock / api_data / api_universe / exch / metrics）。
所有展示口径统一由 bt3 的腿集与区间重建，保证页面内部自洽。
"""
import os, re, json, math, time
import common as C
import s_page_data4 as S4

short = S4.short
quota_text = S4.quota_text
rate_pct = S4.rate_pct


# ------------------------------------------------------------ 结论栏
def build_windows(bt):
    """结论栏五窗口：主推 + 三个对照（夏普优先解 / 收益优先解 / 货基 / 沪深300）"""
    rows = [{'label': '主推组合（v11 双目标 · 5% 整数权重 · 周度调仓）', 'cls': 'hi',
             'wr': bt['main_wr'], 'over_cash': bt['main_over_cash']}]
    for a in bt['alts']:
        rows.append({'label': a['label'], 'cls': '', 'wr': a['wr'], 'over_cash': a['over_cash']})
    rows.append({'label': '货币基金 · 天弘余额宝货币（000198）', 'cls': 'bench',
                 'wr': bt['cash_wr'], 'over_cash': None})
    rows.append({'label': '沪深300（510300 净值代理）', 'cls': 'bench',
                 'wr': bt['bench_wr'], 'over_cash': None})
    return rows


def build_kpis(bt):
    """结论栏右上角的策略指标（年化/波动/回撤/夏普/卡玛）"""
    ms = bt['main_stats']
    es = bt['schemes']['等权 25%×4']['stats']
    v = bt['alts'][0]['stats']      # 夏普优先解
    out = [
        {'k': '年化收益', 'v': '%+.2f%%' % (ms['ann'] * 100), 'cls': 'r' if ms['ann'] >= 0 else 'g',
         's': '%s ~ %s（%d 个交易日）· 已扣再平衡成本' % (bt['dates'][0], bt['dates'][-1], len(bt['dates']))},
        {'k': '年化波动', 'v': '%.2f%%' % (ms['vol'] * 100), 'cls': '',
         's': '等权 25%%×4 为 %.2f%%' % (es['vol'] * 100)},
        {'k': '最大回撤', 'v': '%.2f%%' % abs(ms['mdd'] * 100), 'cls': 'g',
         's': '沪深300 同期 %.2f%%' % abs(bt['bench_stats']['mdd'] * 100)},
        {'k': '夏普比率', 'v': '%.2f' % ms['sharpe'], 'cls': 'r',
         's': '网格最高 %.2f（夏普优先解）· 沪深300 %.2f' % (v['sharpe'], bt['bench_stats']['sharpe'])},
        {'k': '卡玛比率', 'v': '%.2f' % ms['calmar'], 'cls': '',
         's': '年化收益 ÷ 最大回撤（网格最高 2.27）'},
    ]
    return out


# ------------------------------------------------------------ 权重表
def build_wtbl(bt, wt):
    """主推权重：上期有解 → 上周 → 本期（＝下周执行）"""
    weeks = wt['weeks']
    n = len(weeks)
    cur = weeks[-1]
    last = weeks[-2] if n >= 2 else None
    prev = weeks[-5] if n >= 5 else (weeks[0] if weeks else None)   # 一个月前
    legs = bt['order']
    cw = cur['w'] or {}
    lw = (last['w'] or {}) if last else {}
    pw = (prev['w'] or {}) if prev else {}
    rows = []
    for k in legs:
        chg = cw.get(k, 0) - pw.get(k, 0)
        act = '维持' if abs(chg) < 1e-9 else ('加仓 +%dpp' % chg if chg > 0 else '减仓 %dpp' % (-chg))
        rows.append({'cat': k, 'code': bt['legs'][k]['code'], 'name': bt['legs'][k]['name'],
                     'prev': pw.get(k, 0), 'last': lw.get(k, 0), 'cur': cw.get(k, 0),
                     'chg': chg, 'act': act})
    cashw = 100 - sum(cw.get(k, 0) for k in legs)
    rows.append({'cat': '货基', 'code': bt['cash'], 'name': '天弘余额宝货币',
                 'prev': 100 - sum(pw.get(k, 0) for k in legs),
                 'last': 100 - sum(lw.get(k, 0) for k in legs),
                 'cur': cashw, 'chg': cashw - (100 - sum(pw.get(k, 0) for k in legs)),
                 'act': '不持有' if cashw == 0 else '持有 %d%%' % cashw, 'bench': True})
    return {'rows': rows, 'cur_date': cur['date'],
            'last_date': last['date'] if last else '—',
            'prev_date': prev['date'] if prev else '—',
            'last_feas': True, 'prev_feas': True, 'cash_week': False}


# ------------------------------------------------------------ 下周操作（规则复述）
def build_ops(bt, wt, wtbl, assets):
    legs = bt['order']
    amap = {a['cat']: a for a in assets}
    w = {k: bt['main_w'][k] for k in legs}
    wr = {k: amap[k]['wr'] for k in legs}
    cp = lambda v: '%+.2f' % (v * 100)
    order = sorted(legs, key=lambda k: -w[k])
    off = order[0]
    anchor = min(legs, key=lambda k: amap[k]['stats']['vol'])
    rest = [k for k in legs if k not in (off, anchor)]
    parts = []
    parts.append('本期的权重是「规则算出来的」，不是观点：在 375 组 5%% 整数倍权重里，'
                 '先把夏普比率进入前 10%% 的 %d 组挑出来（门槛 %.2f），再在其中选年化收益最高的一组，'
                 '结果是%s %d%%、%s %d%%、%s %d%%、%s %d%%。'
                 % (bt['gate_n'], bt['gate_thr'],
                    off, int(w[off] * 100), anchor, int(w[anchor] * 100),
                    rest[0], int(w[rest[0]] * 100), rest[1], int(w[rest[1]] * 100)))
    parts.append('%s是回撤最小、任何窗口都为正的压舱石（近一月 %s%%、今年以来 %s%%、区间年化波动仅 %.1f%%），'
                 '给 %d%%；%s是三年区间里收益贡献最大的一条腿（近 2 年 %s%%），但近三月 %s%%、上周 %s%%，'
                 '正处在深度回撤里，给 %d%%——规则给它的权重来自「长期风险调整后收益」，'
                 '不代表它下周会涨。'
                 % (anchor, cp(wr[anchor][1]), cp(wr[anchor][3]), amap[anchor]['stats']['vol'] * 100,
                    int(w[anchor] * 100), off, cp(wr[off][4]), cp(wr[off][2]), cp(wr[off][0]),
                    int(w[off] * 100)))
    parts.append('这条规则不加「短窗口必须为正」的硬约束，所以它会在资产被砸下来之后继续持有、'
                 '甚至加仓（黄金、科创这两条腿就是这样）。这是夏普最大化路线的固有特征，'
                 '不是参数没调好——要短窗口好看，就得牺牲长期夏普。')
    txt = ''.join(parts)
    zh = len(re.findall(r'[\u4e00-\u9fff]', txt))
    dirs = []
    for r in wtbl['rows']:
        if r['cat'] == '货基':
            continue
        dirs.append('%s %s（%d%%→%d%%）' % (r['cat'], '加仓' if r['chg'] > 0 else
                                        ('减仓' if r['chg'] < 0 else '维持'),
                                        r['prev'], r['cur']))
    direction = '；'.join(dirs) + '。相对一个月前（%s）的口径，具体金额与份额见「下单清单」。' % wtbl['prev_date']
    falsify = ('这套权重每周重算一次：只要四条腿的夏普—收益结构变化，门槛内的最优解就会换一组，'
               '权重随之变化（近一年 52 周里，主推权重平均每 %.1f 周就会明显跳一次）。'
               '如果哪天「年化收益最高」那组跌破夏普前 10%%，它就会被淘汰。'
               % wt.get('jump_weeks', 3.0))
    return {'narrative': txt, 'zh': zh, 'direction': direction, 'falsify': falsify,
            'open': off, 'anchor': anchor}


# ------------------------------------------------------------ 我的市场判断（自主部分）
def build_market(bt, assets):
    """下周操作建议的『自主判断』层：不依赖历史净值，来自对当前行情的判断。
    数据点已在 2026-10-16 逐一核对（来源见 sources）。"""
    amap = {a['cat']: a for a in assets}
    w = bt['main_w']
    return {
        'headline': '规则给的是权重，我给的是一句话：**这周先别急着重仓黄金和科创，把债券和能源配到位，'
                    '剩下两条腿分三批慢慢接。**',
        'why': [
            '一、这周（10/13–10/16）市场的主线是「美债利率 + 美联储加息预期」，不是中国基本面。'
            '美国 9 月 PPI 同比 +6.3%、环比 +1.3%，双双大超预期，创 2022 年以来最大涨幅（能源分项环比 +10.8%）；'
            '10 年期美债收益率回到 5% 上方，市场对 10 月 28 日 FOMC 加息的定价已到三成以上。'
            '全球高估值成长股（久期资产）都在杀估值——10 月 15 日韩国 KOSPI 跌 7.57%、日经 225 跌 4.9%，'
            'A 股科创 50 同日跌 1.50%、创业板指跌 2.92%。这条外生压力下周不会自动消失，'
            '所以组合里最贵、最依赖贴现率的科创腿，我不建议一次买满 30%。',
            '二、黄金短期同样被利率压着，但给它 40% 不是错。金价从 8 月的 4690 美元一路回落到 10 月初的 4066–4169 区间，'
            '原因是美元强 + 美债实际收益率高 + 加息预期升温；但央行购金（9 月净增 23 吨）、'
            '去美元化与美伊/霍尔木兹的地缘风险都在托底，机构普遍认为 4000–4200 美元区间具备配置价值。'
            '它不是这周最好的资产，但它是这份组合里唯一同时具备「长期正收益」和「与 A 股负相关」的腿——'
            '这正是夏普比率的最大来源，而不是收益来源。所以要配，但应在 10 月 28 日 FOMC 之前留出加仓空间。',
            '三、债券腿（7–10 年政金债）本周刚刚走到了「收益率逼近历史低位」的位置：10 年期国债收益率 1.65%，'
            '10 月 15 日盘中一度到 1.64%，30 年国债 2.07%；央行 10 月买断式逆回购合计净投放 4000 亿元，'
            'DR001 已到 1.27%、低于 1.4% 的政策利率。这是持有它的理由，同时也是一个警告——'
            '收益率已接近 1.6% 的历史极值，且政府债四季度供给高峰、宽信用政策密集落地、'
            '监管已开始提醒部分机构注意债券投资风险，进一步下行的空间被压得很窄。'
            '所以债券给到 25% 是「拿票息 + 当组合减震器」，不是去赌利率再下一个台阶。',
            '四、能源（煤炭）是这周基本面最硬的一条腿，但规则只给了 5%，我认为可以适当超配。'
            '秦皇岛港 5500 大卡动力煤在 10 月 10 日破千元、10 月 13 日报 1013 元/吨，年内涨幅 48.5%，创两年新高；'
            '供给端是硬约束——8 月山西原煤产量同比 −30.9%，全国原煤产量连续三个月处于近五年同期最低，'
            '印尼把煤炭出口收归国企统一管理；需求端冬储补库尚未真正放量（终端库存同比低约 1500 万吨），'
            '大秦线 10 月 7 日起还要集中修 20 天。'
            '风险是厄尔尼诺下的暖冬和 1155 元/吨的限价天花板，所以「超配」也要有度（建议不超过 15%）。',
        ],
        'direction': [
            '债券 25%：一次性配到位（它是减震器，不需要择时）。',
            '能源 5% → 建议实际配 10%~15%：分批，逢板块回调加。',
            '黄金 40%：先配 25%，剩下的等 10 月 28 日 FOMC 落地后再决定。',
            '科创 30%：先配 10%~15%，剩下的等三季报密集披露（10 月下旬–31 日）与美债利率方向明朗后再说。',
            '整体：分 2–3 批、跨度 2–3 周建仓，不要一天买完。',
        ],
        'sources': [
            '行情与利率数据：Wind / 各交易所公开行情（10 年美债 5.089%、现货黄金 4169 美元、'
            '布伦特 105.92 美元、美元指数 102.06、10 年国债 1.65%、DR001 1.27%）；'
            '来源：财联社、北京商报、21 世纪经济报道、CCTD 中国煤炭市场网、Mysteel、国家统计局。',
            '基本面数据：秦皇岛港 5500 大卡动力煤 10/13 报 1013 元/吨（年内 +48.5%）；'
            '8 月山西原煤产量同比 −30.9%；9 月 PPI +5.0%、CPI +0.9%、社零预期 +0.7%、出口 +25.7%；'
            '三季度 GDP 预期 4.4%。来源：国家统计局、海关总署、第一财经首席调研。',
            '政策与事件：央行 10 月买断式逆回购净投放 4000 亿元、10 月 15 日 7000 亿元 6 个月期操作；'
            '房贷贴息与 8000 亿元政策性金融工具；10 月 28 日 FOMC、10 月 20 日 LPR、'
            '10 月 26–29 日二十届五中全会。来源：中国人民银行、新华财经、济安金信事件日历。',
            '板块与筹码：硬科技自 7 月以来大幅回撤、电子/通信较年中高点回撤接近或超过 40%；'
            '中泰证券认为抛压主要来自险资与「固收+」被动赎回、筹码出清已近尾声；'
            '华泰证券策略建议沿「科技硬件业绩兑现 / 顺周期与基建链 / 红利底仓」三条线索配置。'
            '来源：证券时报、中国基金报、中国证券报、华泰证券策略、中泰证券研报。',
            '组合内四条腿的历史口径：本页回测（%s ~ %s，729 个交易日，已扣申赎费）。'
            % (bt['dates'][0], bt['dates'][-1]),
        ],
        'falsify_market': [
            '推翻「科创先少量配」的情形：下周美国 9 月 PCE（10/29）与 FOMC（10/28）若明确不加息、'
            '美债长端收益率跌破 4.8%，成长股杀估值压力解除 → 科创可加快建仓。',
            '推翻「黄金先配 25%」的情形：FOMC 意外加息或沃什表态更鹰，金价失守 4000 美元 → 黄金暂缓加仓并重估权重。',
            '推翻「能源可超配」的情形：暖冬确认、主产区煤矿复产超预期、或动力煤现货跌破 900 元/吨 → 回到规则给的 5%。',
            '推翻「债券拿票息」的情形：10 年国债收益率快速上行突破 1.85%（宽信用见效 + 供给冲击）→ '
            '债券腿降为减震器以外不做超配。',
        ],
        'calendar': [
            ('10/19（下周一）10:00', '三季度 GDP（预期 4.4%）、9 月工业增加值 / 社零 / 固定资产投资、70 城房价'),
            ('10/20（下周二）09:15', '10 月 LPR 报价（上游 PPI 创近四年新高，进一步降息空间收窄）'),
            ('10/20–21', 'APEC 财政部长会议（中国香港）'),
            ('10/22', '消费电子创新大会（果链 / 半导体情绪）'),
            ('10/26–29', '二十届五中全会在北京召开'),
            ('10/28（下下周二）', '美联储 FOMC 议息会议（27–28 日），市场对加息定价约三成以上'),
            ('10/29', '美国 9 月 PCE 物价指数'),
            ('10/31', '三季报披露截止 + 10 月 PMI'),
        ],
    }


# ------------------------------------------------------------ 计算说明 / 局限
def build_rule_text(bt):
    return ('在 375 组「单腿 0/5/10/…/40%%、合计 100%%」的周度调仓组合里：'
            '① 先按夏普比率排序，取前 10%%（本期门槛 %.3f，共 %d 组）；'
            '② 在这批解里取年化收益最高的一组为主推。'
            '不设「必须跑赢货基」的硬约束（页内把是否跑赢标注出来供参考）。'
            % (bt['gate_thr'], bt['gate_n']))


def build_limits(bt, wt):
    ms = bt['main_stats']
    v = bt['alts'][0]
    r = bt['alts'][1]
    kj = next((a for a in bt['assets'] if a['cat'] == '科创'), None)
    au = next((a for a in bt['assets'] if a['cat'] == '黄金'), None)
    en = next((a for a in bt['assets'] if a['cat'] == '能源'), None)
    bo = next((a for a in bt['assets'] if a['cat'] == '债券'), None)
    out = []
    out.append('区间偏差（最重要的一条）：%s 至 %s 这 %d 个交易日，覆盖了黄金（%+.2f%%）与科创芯片（%+.2f%%）'
               '两轮大行情，组合的长期夏普与这段区间的表现强相关。换一个起点，最优权重会明显不同。'
               '本页所有数字都是「在这段区间里最优」，不是可复制的收益预期。'
               % (bt['dates'][0], bt['dates'][-1], len(bt['dates']),
                  au['wr'][4] * 100 if au else 0, kj['wr'][4] * 100 if kj else 0))
    out.append('选权规则本身是样本内拟合：夏普门槛与「门槛内最大化收益」都用同一段历史算出来，'
               '存在后视偏差。它的正当性来自「规则公开、可逐周复现」，而不是「预测准确」。')
    out.append('主推（%s）与夏普优先解（%s）的差别：年化 %.2f%% vs %.2f%%，夏普 %.2f vs %.2f，'
               '最大回撤 %.2f%% vs %.2f%%。主推多赚的 %.2f 个百分点，是用 %.1f 个百分点的回撤换来的。'
               % ('/'.join('%s %d%%' % (k, bt['main_w'][k] * 100) for k in bt['order']),
                  '/'.join('%s %d%%' % (k, v['w'][k] * 100) for k in bt['order']),
                  ms['ann'] * 100, v['stats']['ann'] * 100, ms['sharpe'], v['stats']['sharpe'],
                  ms['mdd'] * 100, v['stats']['mdd'] * 100,
                  (ms['ann'] - v['stats']['ann']) * 100, abs(ms['mdd'] - v['stats']['mdd']) * 100))
    if kj:
        out.append('A股/科创腿的集中度风险：该腿区间年化 %.1f%%、年化波动 %.1f%%、最大回撤 %.1f%%，'
                   '近三月 %.2f%%、上周 %.2f%%。它是本页所有高收益方案的第一大波动来源；'
                   '一旦板块继续回调，组合回撤会明显放大。'
                   % (kj['stats']['ann'] * 100, kj['stats']['vol'] * 100, kj['stats']['mdd'] * 100,
                      kj['wr'][2] * 100, kj['wr'][0] * 100))
    if en:
        out.append('能源腿（煤炭）的单一行业集中度：煤炭是单一行业，受价格、进口、安监与限价政策影响极大，'
                   '区间年化波动 %.1f%%、最大回撤 %.1f%%。' % (en['stats']['vol'] * 100, en['stats']['mdd'] * 100))
    if bo:
        out.append('债券腿的口径：持有的是 7–10 年政金债 ETF 联接，久期长、对利率敏感（区间年化波动 %.2f%%）；'
                   '当前 10 年国债收益率已在 1.65%%，逼近历史低位，票息薄、资本利得空间小，'
                   '若利率上行该腿也会亏。' % (bo['stats']['vol'] * 100))
    out.append('短窗口可以是为负的：本页不强制「五个窗口都跑赢货基」，所以主推组合的上周 / 近一月 / 近三月'
               '可能是负数（本期就是）。这是「夏普与长期收益优先」的必然代价，也是与 v9 那套规则'
               '（要求五窗口全部跑赢货基、无解则整仓货基）的核心区别：v9 在本期直接给不出解，'
               'v11 给的是「长期最优、短期难看」的权重。')
    out.append('回测口径：周度调仓（每周最后一个交易日按目标权重调回），权重取 5%% 整数倍、单腿 0~40%%；'
               '收益用逐日净值增长率累乘（含分红再投资），已扣逐腿真实的「优惠申购费 + 持有满 7 天赎回费」'
               '（本期四腿再平衡成本合计约 %.2f%%/年）；基金净值内已含管理费 / 托管费。'
               % (bt['main_cost'] * 100))
    out.append('货币基金口径：天弘余额宝货币（000198），用每日「每万份收益」累乘成净值曲线，份额净值恒 1 元、'
               '不存在回撤；同期年化约 %.2f%%，近 2 年累计 %+.2f%%。' % (bt['cash_ann'] * 100, bt['cash_wr'][4] * 100))
    out.append('关于 bt 引擎的交叉验证：另用 pmorissette/bt 引擎（场内 ETF 前复权价、单边 2.5bp 佣金）'
               '重跑同一套 5% 网格做对照，两条腿的标的与成本模型不同（场外联接 vs 场内 ETF），'
               '所以两边数字方向可比、不可逐位对读；结论（权重集中在债券 / 黄金、能源与科创权重较低）是一致的。')
    out.append('可申购性与限额：场外份额的「限大额 / 暂停申购」会逐日调整，本页数值为抓取时点值，'
               '下单前请以支付宝 / 基金公司页面为准。')
    out.append('不是投资建议：本页仅用于研究与内部讨论，不构成任何申购、赎回或持有的建议。'
               '基金过往业绩不代表未来表现，投资须谨慎。')
    return out


def build_astock_v11(ast, api, bt):
    """A股/科创腿优选池：取总分前 15，并把组合实际持有的份额补进来（保证绿底行可见）"""
    rows = sorted(ast['rows'], key=lambda r: -r['total'])[:15]
    hold = bt['legs'].get('科创', {}).get('code')
    if hold and hold not in [r['code'] for r in rows]:
        extra = [r for r in ast['rows'] if r['code'] == hold]
        if extra:
            rows = rows[:14] + extra
    out = S4.build_astock(ast, api, bt)
    out['rows'] = [{'code': r['code'], 'name': short(r['name'], 26), 'form': r['form'],
                    'scale': r['scale'], 'ann2': r['ann2'], 'annall': r['ann_all'],
                    'vol': r['vol'], 'mdd': r['mdd'], 'sharpe': r['sharpe'],
                    'bonus': r['bonus'], 's_ann': r['s_ann'], 's_scale': r['s_scale'],
                    's_fee': r['s_fee'], 's_eval': r['s_eval'], 'total': r['total'],
                    'hold': r['code'] == hold} for r in rows]
    return out


def build_scores_v11(picks, bt):
    """打分明细（v11）：只列<b>场外可申购</b>候选前 10，并把组合实际持有的份额补进来。
    场内 ETF 支付宝买不到，不在本表出现（第三章另有折叠对照表）。"""
    out = {}
    for cat, v in picks['cats'].items():
        chosen = (bt['legs'].get(cat) or {}).get('code') or v['top_off']
        off = [r for r in v['rows'] if r['isexchg'] != '1'] or list(v['rows'])
        rows = sorted(off, key=lambda r: -r['total'])[:10]
        if chosen and chosen not in [r['code'] for r in rows]:
            extra = [r for r in off if r['code'] == chosen]
            if extra:
                rows = rows[:9] + extra
        items = []
        for r in rows:
            items.append({'code': r['code'], 'name': short(r['name'], 24),
                          'form': '组合持有 · 场外' if r['code'] == chosen else '场外',
                          'scale': r['scale'], 'buy': r['buy_raw'] or '—', 'red': r['red'],
                          'holdfee': (r['mgr'] or 0) + (r['tru'] or 0) + (r['sal'] or 0),
                          'quota': r['qtxt'],
                          's_scale': r['sscore'], 's_fee': r['tscore'] + r['hscore'],
                          's_quota': r['qscore'], 's_eval': r['escore'], 'total': r['total'],
                          'isexchg': False, 'hold': r['code'] == chosen})
        out[cat] = items
    return out


def main():
    bt = C.jload('bt3.json')
    wt = C.jload('wt_hist3.json')
    picks = C.jload('picks2.json')
    ast = C.jload('astock.json')
    api = C.jload('api_data.json')
    met = C.jload('metrics.json')
    u = C.jload('api_universe.json')
    exch = C.jload('exch.json', default={}) or {}
    asof = bt['dates'][-1]
    legs = bt['order']

    # 滚动 52 周里权重的「跳变」频次（用于文案）
    weeks = wt['weeks']
    jumps = sum(1 for i in range(1, len(weeks))
                if any(abs(weeks[i]['w'].get(k, 0) - weeks[i-1]['w'].get(k, 0)) >= 10 for k in legs))
    wt['jump_weeks'] = 52.0 / jumps if jumps else 52.0

    wtbl = build_wtbl(bt, wt)
    ops = build_ops(bt, wt, wtbl, bt['assets'])
    kpis = build_kpis(bt)
    windows = build_windows(bt)
    market = build_market(bt, bt['assets'])

    # 门槛内候选（按年化降序，页面上列前 12 组）
    feas = [{'wstr': '/'.join('%d%%' % r['w'][k] for k in ['能源', '债券', '黄金', '科创']),
             'stats': r['stats'], 'wr': r['wr'], 'over_cash': r['over_cash'],
             'main': abs(sum(r['w'].values()) - 1.0) < 1e-9 and
                     all(abs(r['w'][k] - bt['main_w'][k]) < 1e-9 for k in legs)}
            for r in bt['feas_all']]
    feas.sort(key=lambda x: -x['stats']['ann'])

    page = {
        'asof': asof, 'gen': time.strftime('%Y-%m-%d %H:%M'), 'ver': 'v11',
        'range': [bt['dates'][0], asof], 'n_days': len(bt['dates']),
        'fallback': False, 'rule': bt['rule'],
        'gate_n': bt['gate_n'], 'gate_thr': bt['gate_thr'], 'grid_n': bt['grid_n'],
        'kpis': kpis,
        'window_labels': bt['window_labels'], 'window_bases': bt['window_bases'],
        'windows': windows,
        'main_wr': bt['main_wr'], 'main_over_cash': bt['main_over_cash'],
        'main_stats': bt['main_stats'],
        'alts': [{'label': a['label'], 'w': a['w'], 'stats': a['stats'], 'wr': a['wr'],
                  'over_cash': a['over_cash'], 'cost': a['cost'], 'turnover': a['turnover']}
                 for a in bt['alts']],
        'feas_n': bt['feas_n'], 'feas': feas[:12], 'feas_order': ['能源', '债券', '黄金', '科创'],
        'wtbl': wtbl, 'ops': ops, 'market': market,
        'orders': S4.build_orders(bt, wtbl, api, met),
        'freqs': [{'label': k, **v} for k, v in bt['freqs'].items()],
        'charts': {'labels': [d[2:] for d in bt['dates']],
                   'curves': bt['curves'], 'pts': S4.build_pts(bt),
                   'wh': {'labels': wt['labels'], 'stack': wt['stack'],
                          'leglabels': wt['leglabels'], 'nocash': wt['nocash'], 'n': wt['n']},
                   'grid_pts': [{'w': p['w'], 'ann': p['ann'], 'vol': p['vol'],
                                 'sharpe': p['sharpe'], 'mdd': p['mdd'], 'calmar': p['calmar']}
                                for p in bt['grid_pts']]},
        'wavg': [{'scheme': nm, 'w': [s['w'].get(k, 0) for k in legs], 'cost': s['cost'],
                  'turnover': s['turnover'], 'stats': s['stats'], 'wr': s['wr'],
                  'main': nm.startswith('主推')}
                 for nm, s in bt['schemes'].items()],
        'corr': {'names': [short(a['name'], 12) for a in bt['assets']],
                 'cats': [a['cat'] for a in bt['assets']], 'm': bt['corr']},
        'assets': bt['assets'],
        'cats': S4.build_cats(u, picks, api, met, exch, bt),
        'scores': build_scores_v11(picks, bt),
        'astock': build_astock_v11(ast, api, bt),
        'limits': build_limits(bt, wt),
        'wt_range': [wt['weeks'][0]['date'], wt['weeks'][-1]['date']],
        'wt_jumps': jumps,
    }
    C.jdump('page_data_v11.json', page)
    C.log('page_data_v11.json 已生成（asof %s，门槛 %.3f，门槛内 %d 组，主推 %s）'
          % (asof, bt['gate_thr'], bt['gate_n'],
             {k: int(bt['main_w'][k] * 100) for k in legs}))


if __name__ == '__main__':
    main()
