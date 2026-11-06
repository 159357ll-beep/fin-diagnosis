# 云端部署说明（智能财务诊断与估值系统）

## 已上线（2026-11-06）

| 项目 | 值 |
| --- | --- |
| 公网访问地址 | <https://fin-diagnosis.streamlit.app> |
| 代码仓库 | <https://github.com/159357ll-beep/fin-diagnosis>（公开，`main` 分支） |
| 部署平台 | Streamlit Community Cloud（免费档） |
| 主文件 | `app.py`（仓库根目录） |
| 管理后台 | <https://share.streamlit.io> → Your apps → `fin-diagnosis` |

日常更新只需提交并推送，平台会自动重新部署（想手动触发就到管理后台点 **Reboot / Rerun**，构建日志也在那一页）：

```powershell
git add -A
git commit -m "feat: 修改说明"
git push
```

若网页提示需要唤醒，免费档冷启动约十几秒属正常；应用不落盘，休眠不会丢数据。

---

本应用是单文件 Streamlit 程序（`app.py`），运行期只需要 `streamlit` + `pandas`，不读写本地文件、不需要数据库，因此可以部署到任何支持 Python/容器的平台。

已为你准备好的文件：

| 文件 | 作用 |
| --- | --- |
| `requirements.txt` | 依赖清单（云平台据此安装） |
| `.streamlit/config.toml` | 主题、关闭使用统计、公网不暴露堆栈 |
| `Dockerfile` | 通用镜像，监听 `$PORT`，自带健康检查 |
| `docker-compose.yml` | 在自有服务器上一键起服务 |
| `render.yaml` | Render 平台的蓝图配置 |
| `.dockerignore` / `.gitignore` | 避免把本地运行时、日志、安装包上传 |

健康检查地址统一为 `/_stcore/health`（正常返回 `ok`）。

---

## 方案一：Streamlit Community Cloud（免费、最快，推荐先试）

本应用已用该方案部署完成，以下为实际执行记录（首次部署时走过一次即可，之后无需重做）：

1. 仓库初始化并提交到 `main`（19 个文件）。
2. 生成 SSH 密钥 `~/.ssh/id_ed25519`，公钥（标题 `fcr20-local-deploy`）添加到 GitHub 账号。
3. 建**空**仓库 `fin-diagnosis`，然后：

   ```powershell
   git remote add origin git@github.com:159357ll-beep/fin-diagnosis.git
   git push -u origin main
   ```

4. <https://share.streamlit.io> 用 GitHub 登录 → 授权 Streamlit OAuth App → Deploy an app：
   - Repository：`159357ll-beep/fin-diagnosis`
   - Branch：`main`
   - Main file path：`app.py`
   - App URL：`fin-diagnosis`
5. 构建完成后公网地址为 <https://fin-diagnosis.streamlit.app>，电脑关机也能访问。

> 免费档的限制：无人访问一段时间后会自动休眠，下次访问需要等十几秒冷启动；已保存的 `st.session_state` 会丢失（本应用是纯计算，无影响）。
>
> 注意：GitHub 的 OAuth 授权页有时把「Authorize streamlit」按钮显示为灰色不可点（通常是页面脚本或网络抖动导致），刷新页面重试即可。

---

## 方案二：Render（免费档，Docker 部署）

1. 同上把代码推到 GitHub。
2. <https://dashboard.render.com> → New → Blueprint → 选择该仓库，`render.yaml` 会被自动识别。
3. 部署完成后访问 `https://fin-diagnosis-xxxx.onrender.com`。

免费档同样有休眠策略；Render 会自动注入 `PORT`，Dockerfile 已适配，无需改动。

---

## 方案三：自己的云服务器（阿里云 / 腾讯云 / 轻量应用服务器）

前提：一台装了 Docker 的 Linux 服务器，安全组放行 8501（或 80/443）。

```bash
# 上传代码（在项目目录执行）
scp -r . root@<服务器IP>:/opt/fin-diag

# 服务器上
cd /opt/fin-diag
docker compose up -d --build
docker compose ps          # STATUS 应为 healthy
curl http://127.0.0.1:8501/_stcore/health
```

浏览器访问 `http://<服务器IP>:8501`。

### 换成域名 + HTTPS（可选）

Nginx 反向代理需要放行 WebSocket，否则页面会一直转圈：

```nginx
server {
    listen 80;
    server_name finance.example.com;

    location / {
        proxy_pass http://127.0.0.1:8501;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header Host $host;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_read_timeout 3600s;
    }
}
```

然后用 `certbot --nginx -d finance.example.com` 申请证书。

如果不走反向代理、直接暴露 8501 端口，Streamlit 的 CORS/XSRF 校验可能拦截访问，可在 `docker-compose.yml` 的 `environment` 中追加：

```yaml
STREAMLIT_SERVER_ENABLE_CORS: "false"
STREAMLIT_SERVER_ENABLE_XSRF_PROTECTION: "false"
```

（走 Nginx 时保持默认开启更安全。）

---

## 本地验证（部署前先确认镜像逻辑没问题）

```powershell
# 以容器内的方式启动（等价于 Dockerfile 的 CMD）
.tools\python\python.exe -m streamlit run app.py --server.address=0.0.0.0 --server.port=8899 --server.headless=true

# 另开一个终端
curl http://127.0.0.1:8899/_stcore/health   # 期望输出 ok
```

---

## 常见问题

- **打开页面一直 "Please wait..." / 转圈**：反向代理没放行 WebSocket，见上面的 Nginx 配置。
- **构建失败提示找不到 `requirements.txt`**：确认构建上下文是项目根目录（`dockerContext: .`）。
- **中文乱码/方框**：容器内没有中文字体。本应用页面文字由浏览器渲染，不受影响；若以后导出 PDF 再考虑装 `fonts-noto-cjk`。
- **数据会不会丢**：应用不落盘，所有输入都在浏览器会话里，刷新即清空；如需留存请自行加导出功能。
