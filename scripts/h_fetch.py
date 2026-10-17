# -*- coding: utf-8 -*-
"""step 03 · 官方字段（fundmobapi Basic + Detail）+ 天天基金 f10 赎回费分档
→ api_data.json（单只一条，落盘缓存 basic_cache.json）
硬约束：fundmobapi 走纯 http://80、UA 只写 Mozilla/5.0、校验 ErrCode/Datas。"""
import re, os, json, time
import common as C
from b_fetch import load_codes

BASE = ('http://fundmobapi.eastmoney.com/FundMNewApi/FundMN%s'
        '?FCODE=%s&deviceid=Wap&plat=Wap&product=EFund&version=2.0.0')
JJFL = 'https://fundf10.eastmoney.com/jjfl_%s.html'
CACHEF = C.wfile('basic_cache.json')


def num(v):
    try:
        f = float(v)
        return f
    except Exception:
        return None


def parse_redeem(html):
    """解析赎回费率分档 → [(lo_days, hi_days, rate_pct)]"""
    m = re.search(r'赎回费率.*?<tbody>(.*?)</tbody>', html, re.S)
    if not m:
        return []
    rows = re.findall(r'<tr>\s*<td>(.*?)</td>\s*<td>(.*?)</td>\s*</tr>', m.group(1), re.S)
    out = []
    for lab, val in rows:
        lab = re.sub(r'<[^>]+>', '', lab)
        val = re.sub(r'<[^>]+>', '', val)
        r = re.search(r'([\d.]+)\s*%', val)
        if not r:
            continue
        rate = float(r.group(1))
        lo, hi = 0, 10 ** 9
        t = re.search(r'大于等于\s*(\d+)\s*(天|个月|月|年)', lab)
        if t:
            lo = int(t.group(1)) * {'天': 1, '个月': 30, '月': 30, '年': 365}[t.group(2)]
        t2 = re.search(r'小于\s*(\d+)\s*(天|个月|月|年)', lab)
        if t2:
            hi = int(t2.group(1)) * {'天': 1, '个月': 30, '月': 30, '年': 365}[t2.group(2)]
        out.append((lo, hi, rate))
    return out


def redeem_at7(tiers):
    """持有满 7 天所适用的赎回费率（%）"""
    for lo, hi, rate in tiers:
        if lo <= 7 < hi:
            return rate
    return 0.0


def fetch_one(code):
    rec = {}
    try:
        jb = C.get_json(BASE % ('BasicInformation', code))
        b = jb.get('Datas') or {}
    except Exception:
        b = {}
    try:
        jd = C.get_json(BASE % ('DetailInformation', code))
        d = jd.get('Datas') or {}
    except Exception:
        d = {}
    if not b and not d:
        return None
    rec['code'] = code
    rec['name_off'] = b.get('SHORTNAME') or d.get('SHORTNAME') or ''
    rec['fullname'] = d.get('FULLNAME') or ''
    rec['ftype'] = b.get('FTYPE') or d.get('FTYPE') or ''
    rec['isexchg'] = b.get('ISEXCHG')
    rec['sgzt'] = b.get('SGZT')
    rec['sgztmark'] = b.get('SGZTMARK')
    rec['shzt'] = b.get('SHZT')
    rec['minsg'] = num(b.get('MINSG'))
    rec['maxsg'] = num(b.get('MAXSG'))
    rec['minrg'] = num(b.get('MINRG'))
    rec['source_rate'] = b.get('SOURCERATE')
    rec['rate'] = b.get('RATE')
    rec['isfsales'] = b.get('ISSALES')
    rec['endnav'] = num(b.get('ENDNAV')) or num(d.get('ENDNAV'))
    rec['estabdate'] = (d.get('ESTABDATE') or b.get('ISSBDATE') or '')[:10]
    rec['indexname'] = b.get('INDEXNAME') or d.get('INDEXNAME') or ''
    rec['indexcode'] = b.get('INDEXCODE') or d.get('INDEXCODE') or ''
    rec['bench'] = d.get('BENCH') or ''
    rec['mgrexp'] = d.get('MGREXP')
    rec['truspexp'] = d.get('TRUSTEXP')
    rec['salesexp'] = d.get('SALESEXP')
    rec['sharpe1'] = num(b.get('SHARP1'))
    rec['maxretra1'] = num(b.get('MAXRETRA1'))
    rec['stddev1'] = num(b.get('STDDEV1'))
    rec['risklevel'] = b.get('RISKLEVEL')
    rec['jjgs'] = b.get('JJGS') or d.get('JJGS')
    rec['syl_1n'] = num(b.get('SYL_1N'))
    rec['syl_3n'] = num(b.get('SYL_3N'))
    rec['syl_jn'] = num(b.get('SYL_JN'))
    rec['fsrq'] = b.get('FSRQ')
    rec['dwjz'] = num(b.get('DWJZ'))
    # 赎回费
    try:
        html = C.get(JJFL % code, retries=2)
        tiers = parse_redeem(html)
        rec['redeem_tiers'] = tiers
        rec['redeem7'] = redeem_at7(tiers)
    except Exception:
        rec['redeem_tiers'] = []
        rec['redeem7'] = None
    return rec


def main():
    codes = load_codes()
    cache = {}
    if os.path.exists(CACHEF):
        cache = json.load(open(CACHEF, encoding='utf-8'))
    todo = [c for c in codes if c not in cache]
    C.log('官方字段：待抓 %d（缓存命中 %d）' % (len(todo), len(cache)))
    t0 = time.time()
    if todo:
        res = C.pmap(fetch_one, todo, workers=8, label='官方')
        for r in res:
            if isinstance(r, tuple):
                continue
            if r:
                cache[r['code']] = r
        json.dump(cache, open(CACHEF, 'w', encoding='utf-8'), ensure_ascii=False)
    C.log('共 %d 条（%.1fs）' % (len(cache), time.time() - t0))
    C.jdump('api_data.json', cache)
    miss = [c for c in codes if c not in cache]
    C.log('未取到：%d %s' % (len(miss), miss[:8]))


if __name__ == '__main__':
    main()
