# -*- coding: utf-8 -*-
"""把 v11 站点一键发布到 GitHub（全程 REST API，不依赖 git 协议 —— 公司网把 git 协议拦死了）

用法：
    export GITHUB_TOKEN=$(grep ^GITHUB_TOKEN ~/.workbuddy/skills/alipay-fund-4class-site/config.env | cut -d= -f2)
    python deploy_github_v11.py --dry-run      # 只校验 token / 文件清单，不写远端
    python deploy_github_v11.py                # 建仓 + 推送 + 开 GitHub Pages
    python deploy_github_v11.py --repo 别的名   # 换仓库名

做六件事：
  ① 把最新一版 HTML 复制成根目录 index.html（Pages 直接吃根目录）
  ② 校验 token（GET /user）
  ③ 建仓库（已存在则跳过；空仓库先造 .gitkeep 激活，否则 blobs 会 409）
  ④ Git Data API 一次性提交（blobs → tree → commit → ref）
  ⑤ 打开 GitHub Pages（source = main:/，纯静态不需要 Actions）
  ⑥ 轮询 Pages 构建状态，最后打印可访问地址
"""
import os, sys, json, time, base64, shutil, glob, urllib.request, urllib.error

ROOT = os.path.dirname(os.path.abspath(__file__))
API = 'https://api.github.com'
OWNER = 'xinyuan8278-code'
REPO = 'alipay-fund-4class-v11'
BRANCH = 'main'
TIMEOUT = 90
DESC = '支付宝可申购基金 · 四大类 ETF 智能组合回测与下周操作建议（单页站，数据截至 2026-10-15）'


# ---------------------------------------------------------------- 清单
def pick_html():
    """取最新一版 v11 交付页"""
    fs = [f for f in glob.glob(os.path.join(ROOT, 'outputs', 'final', 'alipay_fund_4class_v11_*.html'))]
    if not fs:
        raise SystemExit('!! outputs/final 下没有 v11 交付页，先跑 python run_v11.py')
    return sorted(fs, key=os.path.getmtime)[-1]


def collect():
    """返回 [(repo_path, local_path)]"""
    out = []
    latest = pick_html()
    idx = os.path.join(ROOT, 'index.html')
    shutil.copyfile(latest, idx)
    out.append(('index.html', idx))
    out.append(('.nojekyll', os.path.join(ROOT, '.nojekyll')))
    for rel in ('README.md', 'run_v11.py', 'netlify.toml', 'DEPLOY_NETLIFY.md', 'deploy_github_v11.py'):
        p = os.path.join(ROOT, rel)
        if os.path.exists(p):
            out.append((rel, p))
    for d in ('scripts',):
        for dp, dn, fn in os.walk(os.path.join(ROOT, d)):
            dn[:] = [x for x in dn if x != '__pycache__']
            for f in sorted(fn):
                if f.endswith('.py'):
                    p = os.path.join(dp, f)
                    out.append((os.path.relpath(p, ROOT).replace(os.sep, '/'), p))
    p = os.path.join(ROOT, 'bt_run', 'bt_grid5.py')
    if os.path.exists(p):
        out.append(('bt_run/bt_grid5.py', p))
    # 可复核的数据快照（页面就是由这三个 JSON 渲染出来的）
    for name in ('bt3.json', 'wt_hist3.json', 'page_data_v11.json'):
        p = os.path.join(ROOT, 'work', 'qdii2026', name)
        if os.path.exists(p):
            out.append(('data/' + name, p))
    return out, latest


# ---------------------------------------------------------------- HTTP
def api(method, path, token, body=None):
    url = path if path.startswith('http') else API + path
    data = json.dumps(body).encode('utf-8') if body is not None else None
    hdr = {'User-Agent': 'alipay-v11-deployer',
           'Accept': 'application/vnd.github+json',
           'Authorization': 'token ' + token}
    if data:
        hdr['Content-Type'] = 'application/json'
    op = urllib.request.build_opener(urllib.request.ProxyHandler(urllib.request.getproxies()))
    req = urllib.request.Request(url, data=data, headers=hdr, method=method)
    try:
        with op.open(req, timeout=TIMEOUT) as r:
            t = r.read().decode('utf-8', 'replace')
            return r.status, (json.loads(t) if t.strip() else {})
    except urllib.error.HTTPError as e:
        t = e.read().decode('utf-8', 'replace')
        try:
            t = json.loads(t)
        except Exception:
            pass
        return e.code, t
    except Exception as e:
        return 0, repr(e)


def main():
    args = sys.argv[1:]
    repo = args[args.index('--repo') + 1] if '--repo' in args else REPO
    dry = '--dry-run' in args
    token = os.environ.get('GITHUB_TOKEN') or os.environ.get('GH_TOKEN')
    if not token:
        print('!! 先设置 GITHUB_TOKEN')
        return 2

    files, latest = collect()
    total = sum(os.path.getsize(p) for _, p in files)
    print('最新交付页：%s' % os.path.basename(latest))
    print('待提交 %d 个文件，共 %.2f MB' % (len(files), total / 1048576.0))
    for rp, lp in files:
        print('   %-40s %9.1f KB' % (rp, os.path.getsize(lp) / 1024.0))

    st, me = api('GET', '/user', token)
    if st != 200:
        print('!! token 校验失败（%s）：%s' % (st, me))
        return 3
    print('\n✔ token 有效，身份：%s' % me.get('login'))

    st, r = api('GET', '/repos/%s/%s' % (OWNER, repo), token)
    exists = (st == 200)
    if exists:
        print('仓库已存在：%s' % r.get('html_url'))
    elif st == 404:
        if dry:
            print('（dry-run）将新建公开仓库 %s/%s' % (OWNER, repo))
        else:
            st, r = api('POST', '/user/repos', token,
                        {'name': repo, 'private': False, 'auto_init': False, 'description': DESC})
            if st not in (200, 201):
                print('!! 建仓失败（%s）：%s' % (st, r))
                return 4
            print('✔ 已创建仓库 %s' % r.get('html_url'))
            time.sleep(2)
    else:
        print('!! 查询仓库失败（%s）：%s' % (st, r))
        return 4

    if dry:
        print('\n（dry-run）清单与权限校验通过，未写远端。')
        return 0

    # 空仓库 → blobs 会 409，先造初始提交
    st, _ = api('GET', '/repos/%s/%s/git/ref/heads/%s' % (OWNER, repo, BRANCH), token)
    if st != 200:
        print('仓库为空，先造初始提交…')
        st, init = api('PUT', '/repos/%s/%s/contents/.gitkeep' % (OWNER, repo), token,
                       {'message': 'chore: 初始化仓库', 'branch': BRANCH,
                        'content': base64.b64encode(b'init\n').decode('ascii')})
        if st not in (200, 201):
            print('!! 初始化失败（%s）：%s' % (st, init))
            return 5
        print('✔ 初始提交（%s）' % init.get('commit', {}).get('sha', '')[:7])

    print('\n开始上传…')
    tree_items = []
    for i, (rp, lp) in enumerate(files, 1):
        content = base64.b64encode(open(lp, 'rb').read()).decode('ascii')
        st, b = api('POST', '/repos/%s/%s/git/blobs' % (OWNER, repo), token,
                    {'content': content, 'encoding': 'base64'})
        if st not in (200, 201):
            print('!! 上传 %s 失败（%s）：%s' % (rp, st, b))
            return 5
        tree_items.append({'path': rp, 'mode': '100644', 'type': 'blob', 'sha': b['sha']})
        print('   [%2d/%2d] %-40s ✔' % (i, len(files), rp))
    st, tree = api('POST', '/repos/%s/%s/git/trees' % (OWNER, repo), token, {'tree': tree_items})
    if st not in (200, 201):
        print('!! 建 tree 失败：%s' % (tree,))
        return 5
    st, head = api('GET', '/repos/%s/%s/git/ref/heads/%s' % (OWNER, repo, BRANCH), token)
    parents = [head['object']['sha']] if st == 200 else []
    msg = ('feat: 支付宝可申购基金 · 四大类 ETF 智能组合回测与下周操作建议（v11）\n\n'
           '数据截至 2026-10-15；375 组 5% 整数倍权重、周度调仓；\n'
           '选权规则 = 夏普前 10% 门槛内最大化年化收益；含 bt 引擎独立复算。\n'
           're-publish at ' + time.strftime('%Y-%m-%d %H:%M:%S'))
    st, commit = api('POST', '/repos/%s/%s/git/commits' % (OWNER, repo), token,
                     {'message': msg, 'tree': tree['sha'], 'parents': parents})
    if st not in (200, 201):
        print('!! 建 commit 失败：%s' % (commit,))
        return 5
    if parents:
        st, res = api('PATCH', '/repos/%s/%s/git/refs/heads/%s' % (OWNER, repo, BRANCH), token,
                      {'sha': commit['sha'], 'force': True})
    else:
        st, res = api('POST', '/repos/%s/%s/git/refs' % (OWNER, repo), token,
                      {'ref': 'refs/heads/%s' % BRANCH, 'sha': commit['sha']})
    if st not in (200, 201):
        print('!! 更新分支失败：%s' % (res,))
        return 5
    print('✔ 已推送 %s @ %s' % (BRANCH, commit['sha'][:7]))

    # ---- GitHub Pages（纯静态：source = main:/）
    st, pg = api('GET', '/repos/%s/%s/pages' % (OWNER, repo), token)
    if st == 200:
        st2, r2 = api('PUT', '/repos/%s/%s/pages' % (OWNER, repo), token,
                      {'source': {'branch': BRANCH, 'path': '/'}})
        print('✔ Pages 配置已更新（HTTP %s）%s' % (st2, '' if st2 in (200, 204) else r2))
    else:
        st2, r2 = api('POST', '/repos/%s/%s/pages' % (OWNER, repo), token,
                      {'source': {'branch': BRANCH, 'path': '/'}})
        if st2 in (200, 201, 204):
            print('✔ GitHub Pages 已开启')
        else:
            print('! Pages 开启失败（%s）：%s' % (st2, r2))

    url = 'https://%s.github.io/%s/' % (OWNER.lower(), repo)
    print('\n等待 Pages 构建…')
    for i in range(1, 13):
        time.sleep(10)
        st, bd = api('GET', '/repos/%s/%s/pages/builds/latest' % (OWNER, repo), token)
        status = (bd or {}).get('status') if isinstance(bd, dict) else None
        print('   [%2d] status=%s' % (i, status))
        if status == 'built':
            break
        if status == 'errored':
            print('   ! 构建报错：%s' % bd)
            break

    print('\n=== 完成 ===')
    print('  仓库：https://github.com/%s/%s' % (OWNER, repo))
    print('  站点：%s' % url)
    print('  提交：https://github.com/%s/%s/commit/%s' % (OWNER, repo, commit['sha'][:7]))
    return 0


if __name__ == '__main__':
    sys.exit(main())
