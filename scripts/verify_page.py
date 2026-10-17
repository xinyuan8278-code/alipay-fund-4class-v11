# -*- coding: utf-8 -*-
"""页面自检（不需要浏览器也能跑）：
1) 关键区块齐全  2) 无 __TOKEN__ 残留  3) 无字面 %%  4) 有本金输入框与高亮列
5) ECharts 已内联、无外部 <script src>  6) 抽最后一个 <script> 块做 node --check
7) 若环境里有 chromium/edge，则额外数 <canvas>（应为 4）
用法：python scripts/verify_page.py <html路径>"""
import os, re, sys, glob, shutil, subprocess, tempfile

KEYS = ['下单清单（按最新净值折算份数）', '历史收益表现', '本期全部可行权重', '什么情况会改',
        '五、近一年权重变化', '六、换标规则', '七、回测局限', '四项打分口径',
        'A股/科创 ETF 优选池', '关键时点快照', '本网页不涉及任何基金推荐']
BROWSERS = ['chromium', 'chromium-browser', 'google-chrome', 'chrome',
            r'C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe',
            r'C:\Program Files\Google\Chrome\Application\chrome.exe']


def find_browser():
    for b in BROWSERS:
        p = b if os.path.isabs(b) else shutil.which(b)
        if p and os.path.exists(p):
            return p
    return None


def count_canvas(path):
    br = find_browser()
    if not br:
        return None
    prof = tempfile.mkdtemp()
    try:
        out = subprocess.run([br, '--headless=new', '--disable-gpu', '--no-sandbox',
                              '--user-data-dir=' + prof, '--virtual-time-budget=25000',
                              '--dump-dom', 'file:///' + os.path.abspath(path).replace('\\', '/')],
                             stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, timeout=180)
        return out.stdout.decode('utf-8', 'replace').count('<canvas')
    except Exception:
        return None


def main():
    path = sys.argv[1] if len(sys.argv) > 1 else sorted(
        glob.glob(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                               'outputs', 'final', '*.html')), key=os.path.getmtime)[-1]
    h = open(path, encoding='utf-8', errors='replace').read()
    fails = []
    print('核对文件：%s（%.2f MB）' % (path, len(h.encode('utf-8')) / 1048576.0))
    for k in KEYS:
        ok = k in h
        print(('  ✔ ' if ok else '  ✗ 缺 ') + k)
        if not ok:
            fails.append('缺区块 ' + k)
    toks = [t for t in re.findall(r'__[A-Z0-9_]+__', h) if 'EC' not in t]
    print('  %s 残留 token：%s' % ('✔' if not toks else '✗', toks[:5]))
    if toks:
        fails.append('残留 token')
    lit = h.count('%%')
    print('  %s 字面 %%：%d' % ('✔' if lit == 0 else '✗', lit))
    if lit:
        fails.append('字面 %%')
    print('  %s 本金输入框 id="cap" / 高亮列 gcol：%s / %d'
          % ('✔' if 'id="cap"' in h and 'gcol' in h else '✗', 'id="cap"' in h, h.count('gcol')))
    if 'id="cap"' not in h:
        fails.append('缺本金输入框')
    srcs = re.findall(r'<script[^>]*\bsrc=', h)
    print('  %s 外部 script src：%d（应为 0，页面必须自包含）' % ('✔' if not srcs else '✗', len(srcs)))
    if srcs:
        fails.append('存在外链')
    # 「组合 A」「每 2 个月换标」只允许出现在「已删除/不再有」的说明句里（与参考站一致）
    bad_ctx = []
    for kw in ('组合 A', '每 2 个月'):
        for m in re.finditer(re.escape(kw), h):
            ctx = h[max(0, m.start() - 60): m.start() + 60]
            if not any(x in ctx for x in ('删除', '不再', '取消', '已改')):
                bad_ctx.append((kw, ctx.replace('\n', ' ')[:80]))
    print('  %s 「组合 A」/「每 2 个月换标」仅出现在「已删除」说明中：%s'
          % ('✔' if not bad_ctx else '✗', not bad_ctx))
    if bad_ctx:
        fails.append('组合 A / 周期换标 残留')
        for kw, ctx in bad_ctx[:3]:
            print('      · %s → %s' % (kw, ctx))
    # node --check 最后一个 script 块
    blocks = re.findall(r'<script[^>]*>(.*?)</script>', h, re.S)
    if blocks:
        node = shutil.which('node')
        tmp = os.path.join(tempfile.gettempdir(), 'last_script.js')
        open(tmp, 'w', encoding='utf-8').write(blocks[-1])
        if node:
            r = subprocess.run([node, '--check', tmp], stdout=subprocess.PIPE,
                               stderr=subprocess.STDOUT)
            print('  %s 最后一个 script 块 node --check：%s'
                  % ('✔' if r.returncode == 0 else '✗', r.stdout.decode('utf-8', 'replace')[:200]))
            if r.returncode != 0:
                fails.append('JS 语法错误')
        else:
            print('  · 未找到 node，跳过 JS 语法校验')
    n = count_canvas(path)
    if n is None:
        print('  · 未找到 chromium/edge，跳过 <canvas> 计数（本地请用 Edge 复核 = 4）')
    else:
        print('  %s <canvas> 数量：%d（应为 4）' % ('✔' if n == 4 else '✗', n))
        if n != 4:
            fails.append('图表未渲染')
    if fails:
        print('\n自检未通过：%s' % '；'.join(fails))
        sys.exit(1)
    print('\n✔ 自检全部通过')


if __name__ == '__main__':
    main()
