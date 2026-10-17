# 部署到 Netlify（v11 单文件静态站）

目标形态：

```
GitHub 仓库 xinyuan8278-code/alipay-fund-4class-v11
   │  push（本地跑完 run_v11.py → deploy_github_v11.py 推送新 index.html）
   ▼
Netlify ← 收到 push 自动发布 → https://<站点名>.netlify.app/
```

**Netlify 这边不跑构建、不抓数据**，只把仓库根目录的 `index.html` 发出去。
重活全在本机（`run_v11.py`）或 GitHub 上干——Netlify 构建机在境外，直连东财容易被限流。

仓库里已带 `netlify.toml`（`publish = "."`），导入时**不用手填任何配置**。

---

## 路线 A（推荐）：连接 GitHub 仓库，之后自动更新

1. 打开 <https://app.netlify.com> → 右上 **Add new site** → **Import an existing project**
2. 选 **GitHub** → 授权 Netlify 访问（可选 All repositories 或只选这一个）
3. 在列表里点 **alipay-fund-4class-v11**
4. 站点设置页会自动读到仓库里的 `netlify.toml`，确认三项：
   - **Branch to deploy**：`main`
   - **Build command**：留空（本项目无构建）
   - **Publish directory**：`.`（= 仓库根，`netlify.toml` 已写好；如果被识别成别的，手动填 `.`）
5. 点 **Deploy site**，约 20 秒后可访问 `https://<随机名>.netlify.app/`
6. 改个短名：**Site configuration → Site details → Change site name**（例如 `alipay-fund-4class-v11`）

之后每次更新只要两步（本机）：

```bash
python run_v11.py                    # 重跑回测 + 重新渲染
export GITHUB_TOKEN=$(grep ^GITHUB_TOKEN ~/.workbuddy/skills/alipay-fund-4class-site/config.env | cut -d= -f2)
python deploy_github_v11.py          # 推到 GitHub → Netlify 自动重建
```

---

## 路线 B（最快看到效果，不用授权 GitHub）

打开 <https://app.netlify.com/drop>，把本项目下 **`deploy_netlify` 整个文件夹**拖进去
（或拖 `outputs/final/alipay_fund_4class_v11_netlify_drop.zip` 解压后的目录），几秒后得到临时网址。

> 这条路是「一次性上传」，不连仓库，**不会自动更新**；适合先给领导/客户看一眼效果。

---

## 路线 C（要全自动 / 绑域名 / 加密码）：给我一个 Netlify token

我没有你的 Netlify 凭证，所以上面两步只能在你的浏览器里点。
如果希望我全自动建站 + 绑定自定义域名，需要：

1. Netlify → 右上头像 → **User settings → Applications → Personal access tokens → New access token**
2. 把 token 发我，我就能调 Netlify API 直接：
   - `POST /api/v1/sites` 建站点
   - `POST /api/v1/sites/{site_id}/deploys` 上传 zip 发布
   - 绑定自定义域名、设置密码保护

（token 只会写进本机技能配置，不外传。）

---

## 常用后续操作

- **立刻重新发布**：Netlify → **Deploys → Trigger deploy → Deploy site**
- **自定义域名**：**Site configuration → Domain management → Add a domain**
- **内部使用加密码**：**Site configuration → Access control → Password protection**（Pro 功能）
- **关掉自动发布**：**Build & deploy → Continuous deployment → 停止 / 只保留手动 Trigger deploy**

---

## 常见问题

**Q：部署后图表空白？**
本站是单文件自包含（ECharts 已内联，无任何外链），正常情况不会白屏。
先本地双击 `deploy_netlify/index.html` 确认能出图；若本地正常而线上空白，Ctrl+F5 强刷
（`netlify.toml` 已给 HTML 关掉长缓存）。

**Q：`publish = "."` 会不会把源码也发布出去？**
会——`scripts/`、`data/`、`README.md` 都能被直接访问。这些文件在 GitHub 公开仓库里本来就公开，
所以不构成新增暴露。若不想暴露，把 `netlify.toml` 改成 `publish = "deploy_netlify"` 即可
（该目录只有 `index.html` + `netlify.toml`），但要记得每次重新生成拖拽包。

**Q：和 GitHub Pages 冲突吗？**
不冲突。两者可以同时在线：Pages 是 `https://xinyuan8278-code.github.io/alipay-fund-4class-v11/`，
Netlify 是 `https://<站点名>.netlify.app/`，同一份文件、互不影响。选一个作为对外地址即可。

**Q：为什么不用 Netlify 构建时跑 Python 出页面？**
不推荐。Netlify 构建机在境外，抓 `fund.eastmoney.com` 可能被限流，失败就发不出页面。
本项目的做法是「本机跑数 + 推静态文件」，最稳。
