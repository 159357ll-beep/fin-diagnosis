# 云端部署说明（智能财务诊断与估值系统）

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

前提：代码在一个 GitHub 仓库里。

**本机已完成的准备**（无需重做）：

- Git 已装好：`C:\Users\fcr20\.local\PortableGit\cmd\git.exe`，已加入用户 PATH（新开终端可直接用 `git`）
- 仓库已初始化并提交到 `main` 分支（19 个文件，约 50 KB）
- SSH 密钥已生成：私钥 `~/.ssh/id_ed25519`，公钥 `~/.ssh/id_ed25519.pub`；`github.com` 已写入 `known_hosts`

**还需要你做的：**

1. 注册 GitHub（需邮箱验证）：<https://github.com/signup>
2. 建一个**空**仓库：New repository → 名称如 `fin-diagnosis` → 不要勾选 README / .gitignore / license → Create。
3. 把公钥加到账号：右上头像 → Settings → SSH and GPG keys → New SSH key → 粘贴 `C:\Users\fcr20\.ssh\id_ed25519.pub` 的全部内容。
4. 在项目目录推送（把 `<用户名>` 换成你的 GitHub 用户名）：
   ```powershell
   git remote add origin git@github.com:<用户名>/fin-diagnosis.git
   git push -u origin main
   ```
   首次连接若提示 `Are you sure you want to continue connecting?`，输入 `yes`。
5. 打开 <https://share.streamlit.io> → GitHub 授权登录 → New app → 选仓库、分支 `main`、主文件 `app.py` → Deploy。
6. 得到形如 `https://<app名>.streamlit.app` 的公网地址，电脑关机也能访问。

> 免费档的限制：无人访问一段时间后会自动休眠，下次访问需要等十几秒冷启动；已保存的 `st.session_state` 会丢失（本应用是纯计算，无影响）。

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
