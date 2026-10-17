# -*- coding: utf-8 -*-
"""公共库：HTTP（东财接口）、缓存、日期、指标。
只用标准库，Windows / Linux(GitHub Actions) 均可跑。"""
import os, sys, json, re, time, math, ssl, gzip, io, zlib, datetime
import urllib.request, urllib.parse, urllib.error
from concurrent.futures import ThreadPoolExecutor

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
WORK = os.path.join(ROOT, 'work', 'qdii2026')
CACHE = os.path.join(WORK, 'cache')
LOGS = os.path.join(WORK, 'logs')
FINAL = os.path.join(ROOT, 'outputs', 'final')
ASSETS = os.path.join(ROOT, 'assets')
for d in (WORK, CACHE, LOGS, FINAL, ASSETS):
    os.makedirs(d, exist_ok=True)

UA = 'Mozilla/5.0'          # 只能这么短，长 UA 会被东财 WAF 拦
CTX = ssl.create_default_context()
CTX.check_hostname = False
CTX.verify_mode = ssl.CERT_NONE

# 数据截断点（对齐历史口径用；留空 = 用最新净值日）
UNTIL = os.environ.get('QDII_UNTIL') or None
TAG = os.environ.get('QDII_TAG') or ''
SRC = os.environ.get('QDII_SRC') or ''      # '_ref' 读对齐版数据（bt2_ref.json / wt_hist_ref.json）

RF = 0.015                  # 无风险利率
TRADING_DAYS = 252

_used_hosts = ['fund.eastmoney.com', 'fundmobapi.eastmoney.com', 'fundf10.eastmoney.com',
               'qt.gtimg.cn', 'hq.sinajs.cn']


def wfile(name):
    return os.path.join(WORK, name)


def log(msg):
    print(msg, flush=True)


# ---------------------------------------------------------------- HTTP
def _req(url, referer=None, timeout=25, encoding=None):
    hdr = {'User-Agent': UA, 'Accept': '*/*', 'Connection': 'close'}
    if referer:
        hdr['Referer'] = referer
    r = urllib.request.Request(url, headers=hdr)
    with urllib.request.urlopen(r, timeout=timeout, context=CTX) as resp:
        raw = resp.read()
        if resp.headers.get('Content-Encoding') == 'gzip':
            raw = gzip.decompress(raw)
        if encoding:
            return raw.decode(encoding, 'replace')
        for enc in ('utf-8', 'gbk', 'gb18030'):
            try:
                return raw.decode(enc)
            except UnicodeDecodeError:
                continue
        return raw.decode('utf-8', 'replace')


def get(url, referer=None, timeout=25, retries=4, encoding=None, sleep=0.6):
    """带退避的 GET。https 失败自动降级到 http（东财 443 时通时不通）。"""
    urls = [url]
    if url.startswith('https://'):
        urls.append('http://' + url[8:])
    last = None
    for attempt in range(retries):
        for u in urls:
            try:
                t = _req(u, referer, timeout, encoding)
                if t:
                    return t
            except Exception as e:      # noqa
                last = e
        time.sleep(sleep * (attempt + 1))
    raise RuntimeError('GET failed %s -> %r' % (url, last))


def get_json(url, retries=4, **kw):
    for i in range(retries):
        t = get(url, retries=1, **kw)
        try:
            j = json.loads(t)
        except Exception:
            time.sleep(0.8 * (i + 1))
            continue
        if isinstance(j, dict) and j.get('ErrCode') not in (None, 0, '0'):
            time.sleep(0.8 * (i + 1))
            continue
        return j
    raise RuntimeError('bad json %s' % url)


def pmap(fn, items, workers=8, label=''):
    out = []
    n = len(items)
    done = [0]

    def wrap(x):
        try:
            r = fn(x)
        except Exception as e:  # noqa
            r = ('ERR', x, repr(e))
        done[0] += 1
        if label and done[0] % 25 == 0:
            log('  %s %d/%d' % (label, done[0], n))
        return r

    with ThreadPoolExecutor(max_workers=workers) as ex:
        for r in ex.map(wrap, items):
            out.append(r)
    return out


# ---------------------------------------------------------------- json io
def jdump(name, obj):
    p = name if os.path.isabs(name) else wfile(name)
    with open(p, 'w', encoding='utf-8') as f:
        json.dump(obj, f, ensure_ascii=False)
    return p


def jload(name, default=None):
    p = name if os.path.isabs(name) else wfile(name)
    if not os.path.exists(p):
        if default is not None:
            return default
        raise SystemExit('missing %s' % p)
    with open(p, encoding='utf-8') as f:
        return json.load(f)


def cpath(code):
    return os.path.join(CACHE, '%s.json' % code)


# ---------------------------------------------------------------- 时间
def ms2date(ms):
    return time.strftime('%Y-%m-%d', time.gmtime(int(ms) / 1000.0 + 8 * 3600))


def sec2date(s):
    return time.strftime('%Y-%m-%d', time.gmtime(int(s) + 8 * 3600))


def d2ord(d):
    """'YYYY-MM-DD' -> 天数序号（proleptic Gregorian，与时区无关）"""
    y, m, dd = d.split('-')
    return datetime.date(int(y), int(m), int(dd)).toordinal()


def shift(d, days):
    return (datetime.date.fromordinal(d2ord(d)) + datetime.timedelta(days=days)).isoformat()


def week_key(d):
    """周一为界的自然周序号（跨时区稳定）"""
    return (d2ord(d) - 1) // 7


def month_key(d):
    return d[:7]


def bimonth_key(d):
    return (int(d[:4]) * 12 + int(d[5:7])) // 2


# ---------------------------------------------------------------- 指标
def pct(v):
    """小数 -> 百分数字符串（不带 %）"""
    return v * 100.0


def ann_return(curve, n_days):
    if curve[0] <= 0:
        return 0.0
    tot = curve[-1] / curve[0]
    if n_days <= 0:
        return 0.0
    if tot <= 0:
        return -1.0
    return tot ** (365.0 / n_days) - 1.0


def daily_returns(curve):
    return [curve[i] / curve[i - 1] - 1.0 for i in range(1, len(curve))]


def std(xs):
    n = len(xs)
    if n < 2:
        return 0.0
    m = sum(xs) / n
    return math.sqrt(sum((x - m) ** 2 for x in xs) / (n - 1))


def ann_vol(curve):
    r = daily_returns(curve)
    return std(r) * math.sqrt(TRADING_DAYS)


def max_drawdown(curve):
    peak = curve[0]
    mdd = 0.0
    for v in curve:
        if v > peak:
            peak = v
        if peak > 0:
            dd = v / peak - 1.0
            if dd < mdd:
                mdd = dd
    return mdd


def sharpe(curve):
    a = ann_return(curve, len(curve) - 1)
    v = ann_vol(curve)
    if v <= 1e-12:
        return 0.0
    return (a - RF) / v


def calmar(curve):
    a = ann_return(curve, len(curve) - 1)
    m = abs(max_drawdown(curve))
    if m <= 1e-12:
        return 0.0
    return a / m


def period_return(curve, i):
    """区间收益：以 curve[i] 为基准到 curve[-1]"""
    if i <= 0:
        return curve[-1] / curve[0] - 1.0
    if curve[i] <= 0:
        return 0.0
    return curve[-1] / curve[i] - 1.0


def window_index(dates, kind, n):
    """n = len(dates)-1（最新点）。返回基准点下标 i，使区间收益 = curve[-1]/curve[i]-1。"""
    last = dates[-1]
    if kind == 'W1':
        return max(0, n - 5)
    if kind == 'M1':
        tgt = shift(last, -30)
    elif kind == 'M3':
        tgt = shift(last, -91)
    elif kind == 'YTD':
        return _ytd_index(dates)
    elif kind == 'Y2':
        tgt = shift(last, -730)
    else:
        raise ValueError(kind)
    for i in range(n, -1, -1):
        if dates[i] <= tgt:
            return i
    return 0


def _ytd_index(dates):
    y = int(dates[-1][:4])
    last_prev = '%d-12-31' % (y - 1)
    for i in range(len(dates) - 1, -1, -1):
        if dates[i] <= last_prev:
            return i
    return 0


WINDOWS = [('W1', '上周'), ('M1', '近一月'), ('M3', '近三月'), ('YTD', '今年以来'), ('Y2', '近2年')]


def window_returns(curve, dates):
    n = len(curve) - 1
    return [period_return(curve, window_index(dates, k, n)) for k, _ in WINDOWS]


def window_dates(dates):
    n = len(dates) - 1
    return [dates[window_index(dates, k, n)] for k, _ in WINDOWS]


# ---------------------------------------------------------------- 统计
def mean(xs):
    return sum(xs) / len(xs) if xs else 0.0


def corr(a, b):
    n = min(len(a), len(b))
    a, b = a[-n:], b[-n:]
    if n < 3:
        return 0.0
    ma, mb = mean(a), mean(b)
    va = sum((x - ma) ** 2 for x in a)
    vb = sum((x - mb) ** 2 for x in b)
    if va <= 0 or vb <= 0:
        return 0.0
    cov = sum((a[i] - ma) * (b[i] - mb) for i in range(n))
    return cov / math.sqrt(va * vb)


def round5(x):
    return int(round(x / 5.0)) * 5
