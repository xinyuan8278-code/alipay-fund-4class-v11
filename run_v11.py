# -*- coding: utf-8 -*-
"""一键跑通 v11 站点（在本机离线复用已抓取的基金数据，不重新下载）

    python run_v11.py

依赖顺序：
  01 网格回测（v11 双目标）      scripts/n_bt3.py         → work/qdii2026/bt3.json
  02 近一年权重滚动重构（52 周）  scripts/v_wt3.py         → work/qdii2026/wt_hist3.json
  03 页面数据组装                scripts/s_page_v11.py    → work/qdii2026/page_data_v11.json
  04 渲染单文件 HTML             scripts/o_build_v11.py   → outputs/final/*.html
  05 页面自检                    scripts/verify_v11.py

前置数据（已由主流水线抓取，位于 work/qdii2026/）：
    api_data.json / api_universe.json / funds_raw.json / metrics.json
    picks2.json / astock.json / exch.json
重新抓取请到上一级流水线跑 `python run_weekly.py`（约 2.5 分钟，需东财接口可达）。

bt 引擎交叉验证（第五章）需要 bt_run/out/ 下的产物，若缺失先跑：
    cd bt_run && "$VENV" bt_grid5.py        # 375 组 5% 网格 · 周度 · 约 20 分钟
"""
import os, sys, subprocess, time

ROOT = os.path.dirname(os.path.abspath(__file__))
SCRIPTS = os.path.join(ROOT, 'scripts')
STEPS = [('01 网格回测（v11）', 'n_bt3.py'),
         ('02 滚动 52 周权重重构', 'v_wt3.py'),
         ('03 页面数据组装', 's_page_v11.py'),
         ('04 渲染单文件 HTML', 'o_build_v11.py'),
         ('05 页面自检', 'verify_v11.py')]


def main():
    t0 = time.time()
    env = dict(os.environ)
    env['PYTHONIOENCODING'] = 'utf-8'
    env['PYTHONPATH'] = SCRIPTS + os.pathsep + env.get('PYTHONPATH', '')
    for k in ('HTTP_PROXY', 'HTTPS_PROXY', 'http_proxy', 'https_proxy'):
        env[k] = ''
    print('=== 支付宝可申购基金 · 四大类 ETF 智能组合回测与下周操作建议 · v11 ===')
    for name, script in STEPS:
        p = os.path.join(SCRIPTS, script)
        print('[%s]' % name)
        r = subprocess.run([sys.executable, p], cwd=SCRIPTS, env=env,
                           stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
        out = r.stdout.decode('utf-8', 'replace')
        for line in out.strip().splitlines()[-8:]:
            print('    ' + line)
        if r.returncode != 0:
            print(out)
            raise SystemExit('!! %s 失败（退出码 %d）' % (script, r.returncode))
    print('=== 完成，用时 %.1fs ===' % (time.time() - t0))


if __name__ == '__main__':
    sys.exit(main())
