# -*- coding: utf-8 -*-
"""step 09 · 场内折溢价（腾讯行情）→ exch.json
折溢价 = 现价 / 最新披露单位净值 − 1（不是 IOPV），表格必须带净值日期"""
import re, json
import common as C

QT = 'http://qt.gtimg.cn/q=%s'
SINA = 'http://hq.sinajs.cn/list=%s'


def prefix(code):
    """5xxxxx = 沪市，1xxxxx = 深市"""
    return ('sh' if code[0] == '5' else 'sz') + code


def main():
    met = C.jload('metrics.json')
    api = C.jload('api_data.json')
    codes = [c for c, a in api.items() if a.get('isexchg') == '1']
    out = {}
    if codes:
        q = ','.join(prefix(c) for c in codes)
        try:
            txt = C.get(QT % q, encoding='gbk', retries=3)
        except Exception:
            txt = ''
        for line in txt.split(';'):
            m = re.match(r'v_([a-z]{2}\d{6})="(.*)"', line.strip())
            if not m:
                continue
            f = m.group(2).split('~')
            if len(f) < 5 or not f[3]:
                continue
            code = m.group(1)[2:]
            try:
                price = float(f[3])
            except Exception:
                continue
            if price <= 0:
                continue
            out[code] = {'price': price, 'pname': f[1]}
    # 折溢价
    for code, d in out.items():
        m = met.get(code) or {}
        a = api.get(code) or {}
        nav = a.get('dwjz')
        navdate = a.get('fsrq')
        if not nav and m.get('nav'):
            pass
        raw = C.jload('funds_raw.json').get(code) or {}
        navs = raw.get('nav') or []
        if navs:
            if not navdate:
                navdate = navs[-1][0]
            if not nav:
                nav = navs[-1][1]
        if nav:
            d['nav'] = nav
            d['navdate'] = navdate
            d['prem'] = d['price'] / nav - 1.0
    C.jdump('exch.json', out)
    got = sum(1 for v in out.values() if v.get('prem') is not None)
    C.log('场内报价 %d 只，其中可算折溢价 %d 只' % (len(out), got))
    for c, v in list(out.items())[:5]:
        C.log('  %s %s 现价%.3f 净值%s(%s) 溢价%s' % (
            c, v.get('pname', ''), v['price'], v.get('nav'), v.get('navdate'),
            '—' if v.get('prem') is None else '%.2f%%' % (v['prem'] * 100)))


if __name__ == '__main__':
    main()
