# -*- coding: utf-8 -*-
"""step 01 · 候选池
口径：全量基金清单（fundcode_search.js）+ 类型过滤（指数型-* / QDII-*，等价于东财
FundType ∈ {3,4,6,8} 四池并集，且能覆盖 ETF 联接份额）→ 四大类关键词正则命中。
输出 api_universe.json"""
import re, json
import common as C

FC = 'https://fund.eastmoney.com/js/fundcode_search.js'

INC = {
    '债券': r'国债ETF|政金债ETF|政策性金融债ETF|金融债ETF|信用债ETF|公司债ETF|城投债ETF|短融ETF|债券ETF|国开|地方债ETF|债ETF联接|利率债',
    '黄金': r'黄金ETF|上海金ETF|黄金交易型|黄金ETF联接|黄金主题|黄金及贵金属|金ETF|黄金',
    '能源': r'能源ETF|中证能源|石油|油气|原油|煤炭|天然气|能源指数|油ETF|能源',
}
EXC = (r'新能源|光伏|电池|储能|氢能|风电|医疗|生物|创新药|半导体(?!.*美国)|芯片|军工|白酒|银行|券商|地产|农业|'
       r'食品|有色|钢铁|化工|建材|传媒|游戏|影视|旅游|消费(?!.*标普)|教育')
EXC_CROSS = (r'中韩|日经|纳指|纳斯达克|标普|美国|恒生|港股|海外|全球|亚太|德国|法国|日本|印度|越南|东南亚|中概|'
             r'MSCI|东证|亚洲|中国香港|韩国|欧洲|新兴市场|国际|跨境|QDII')
INC_A = r'科创|芯片|半导体|人工智能|科技'


def load_all_funds():
    h = C.get(FC)
    arr = json.loads(h[h.index('['):h.rindex(']') + 1])
    out = {}
    for a in arr:
        code, _, name, typ = a[0], a[1], a[2], a[3]
        out[code] = {'code': code, 'name': name, 'type': typ}
    return out


def is_index_like(t):
    """东财 FundType ∈ {3,4,6,8} 四池并集 ≈ 指数型-* / QDII-* 类型"""
    t = t or ''
    return t.startswith('指数型') or t.startswith('QDII')


def in_etf_family(name):
    """只保留 ETF / ETF 联接 / LOF 指数族（场内 ETF 及其场外联接份额）。
    场内 ETF 支付宝买不到，必须能对应到场外可申购的联接份额。"""
    return 'ETF' in name or 'LOF' in name


def main():
    allf = load_all_funds()
    C.log('全量基金 %d 只' % len(allf))
    base = {c: d for c, d in allf.items() if is_index_like(d['type']) and in_etf_family(d['name'])}
    C.log('ETF/联接 指数池 %d 只（≈ 东财 FundType 3/4/6/8 并集中的 ETF 族）' % len(base))

    cats = {k: [] for k in ('债券', '黄金', '能源')}
    a_pool = []
    inc = {k: re.compile(v) for k, v in INC.items()}
    exc, excx, inca = re.compile(EXC), re.compile(EXC_CROSS), re.compile(INC_A)
    for c, d in sorted(base.items()):
        nm = d['name']
        hit = False
        if not exc.search(nm):      # 排除词只作用于债券/黄金/能源三大类
            for k, rgx in inc.items():
                if rgx.search(nm):
                    cats[k].append(dict(d, cat=k))
                    hit = True
                    break
        if not hit and inca.search(nm) and not excx.search(nm):
            a_pool.append(dict(d, cat='A股科创'))

    C.jdump('api_universe.json', {'all': allf, 'base_size': len(base),
                                  'cats': cats, 'astock': a_pool})
    for k, v in cats.items():
        C.log('%s 候选 %d' % (k, len(v)))
    C.log('A股/科创候选 %d' % len(a_pool))
    codes = [d['code'] for v in cats.values() for d in v] + [d['code'] for d in a_pool]
    C.log('去重后待抓 %d 只' % len(set(codes)))


if __name__ == '__main__':
    main()
