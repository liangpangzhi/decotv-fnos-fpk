# DecoTV for 飞牛 fnOS（fpk 打包工程）

把 [Decohererk/DecoTV](https://github.com/Decohererk/DecoTV)（一个基于 Next.js 的影视聚合播放站）打包成飞牛 fnOS 可安装的 `.fpk`，**安装后在飞牛桌面点击图标直接进入 Web 界面**。

本仓库只包含**打包脚本与实测文档**，不包含 DecoTV 源码，也不内嵌其 Docker 镜像。

| 项目 | 值 |
| --- | --- |
| 应用名 | `decotv` |
| 显示名称 | DecoTV |
| 版本 | 1.5.0 |
| 架构 | x86_64 |
| 包类型 | Docker 型 fpk（`config/resource` 声明 `docker-project`） |
| 默认端口 | 3000（安装时可自定义） |
| 镜像 | `ghcr.io/decohererk/decotv:latest` |
| 实测环境 | 飞牛 fnOS `1.2.0800`，x86_64，Docker 28.5.2 |

## 下载

**[⬇ DecoTV-1.5.0-fnos-x86.fpk](https://github.com/liangpangzhi/decotv-fnos-fpk/releases/download/v1.5.0/DecoTV-1.5.0-fnos-x86.fpk)** · [Release 页面](https://github.com/liangpangzhi/decotv-fnos-fpk/releases/tag/v1.5.0) · [Actions 构建产物](https://github.com/liangpangzhi/decotv-fnos-fpk/actions)

约 265 KB，不含镜像（安装时拉取）。

```text
大小:   271089 字节
SHA256: e6e954752ad7852b1bfbf9326246db0d95cb6cfeb6f1a853c1a28ef50a7be974
```

仓库内同版本副本：[`dist/DecoTV-1.5.0-fnos-x86.fpk`](dist/DecoTV-1.5.0-fnos-x86.fpk)

---

## 1. 安装

### 方式一：应用中心手动安装（推荐）

1. 把 `DecoTV-1.5.0-fnos-x86.fpk` 下载到电脑
2. 飞牛网页端 → **应用中心** → 右上角 **手动安装** → 选择该 fpk
3. 安装向导里填两项：

   | 字段 | 默认值 | 说明 |
   | --- | --- | --- |
   | 访问端口 | `3000` | 对外访问端口，容器内部固定 3000；端口被占用时安装会直接报错 |
   | 管理密码 | `admin123` | DecoTV 登录密码，安装后可用它登录，建议改掉 |

4. 安装完成后，桌面出现 **DecoTV** 图标，点击即打开 `http://<NAS地址>:<端口>/`

### 方式二：命令行安装

在 NAS 上通过 SSH 执行（需要 root 或 sudo）：

```bash
appcenter-cli install-fpk DecoTV-1.5.0-fnos-x86.fpk -v 1
```

需要跳过向导、直接指定参数时，用 `-e` 传入环境变量文件：

```bash
# decotv.env
# wizard_port=3999
# wizard_admin_password=换成你的密码

appcenter-cli install-fpk DecoTV-1.5.0-fnos-x86.fpk -e decotv.env -v 1
```

### 首次登录

用户名 `admin`，密码为安装向导里设置的值（默认 `admin123`）。

### 数据位置

应用数据共享目录：`/vol1/@appshare/decotv/data`（按实际安装卷变化），容器内挂载为 `/data`，用于 FFmpeg 转存下载缓存。卸载应用时该共享目录会保留。

---

## 2. 打包

### 依赖

- Python 3.8+ 与 Pillow（生成图标）
- [fnpack](https://developer.fnnas.com/docs/cli/fnpack/)：飞牛官方打包工具

```bash
pip install pillow
# Windows
curl -L -o fnpack.exe https://static2.fnnas.com/fnpack/fnpack-1.2.3-windows-amd64
# Linux / macOS
curl -L -o fnpack https://static2.fnnas.com/fnpack/fnpack-1.2.3-linux-amd64 && chmod +x fnpack
```

### 一键构建

```bash
./build.sh
```

等价于：

```bash
python3 make_fpk.py                      # 生成 pkg/decotv 工程目录
./fnpack build --directory pkg/decotv    # 打包，产出 decotv.fpk
```

`make_fpk.py` 是**唯一的事实来源**：`pkg/decotv/` 下的 manifest、`cmd/` 脚本、`app/ui/config`、`wizard/install` 全部由它渲染生成。改逻辑请改这个脚本，不要直接改 `pkg/`（会被覆盖）。

想换 DecoTV 版本时，改 `make_fpk.py` 顶部常量：

```python
VERSION = "1.5.0"
IMG_UPSTREAM = "ghcr.io/decohererk/decotv:latest"
IMG_LOCAL = "decotv:" + VERSION      # 安装时把上游镜像重打成这个私有标签
```

### CI

`.github/workflows/build.yml` 会在 push 到 `main` 或手动触发时，用 Linux 版 fnpack 构建，并把 `DecoTV-<version>-fnos-x86.fpk` 作为 artifact 上传（Actions → 对应运行 → Artifacts）。

> 向 GitHub 推送 workflow 文件需要 token 带 `workflow` 权限；只有 `repo` 权限时会报
> `refusing to allow a Personal Access Token to create or update workflow ... without workflow scope`。
> 不方便用 CI 时，本地跑 `./build.sh` 结果完全一致。

---

## 3. 包结构

```
pkg/decotv/
├── manifest                     # 应用元数据（含 service_port / desktop 入口）
├── ICON.PNG                     # 64×64 桌面/列表图标
├── ICON_256.PNG                 # 256×256 图标
├── app/
│   ├── ui/
│   │   ├── config               # 桌面入口定义（type=url + 端口）
│   │   └── images/icon_{0}.png  # 64 / 128 / 256 多尺寸图标
│   └── docker/
│       └── docker-compose.yaml  # 模板；安装时由 install_init 按用户参数重写
├── cmd/                         # 生命周期脚本
│   ├── install_init             # 校验 Docker、端口检查、生成 compose、准备镜像
│   ├── install_callback         # 记录密码/端口，兜底写桌面入口
│   ├── main                     # start / stop / status
│   ├── upgrade_init|callback
│   ├── uninstall_init|callback
│   └── config_init|callback
├── config/
│   ├── privilege                # run-as: root（必须，否则无权访问 docker.sock）
│   └── resource                 # docker-project + data-share
└── wizard/
    └── install                  # 安装向导：访问端口 + 管理密码
```

关键 manifest 片段：

```ini
appname               = decotv
version               = 1.5.0
display_name          = DecoTV
platform              = x86
source                = thirdparty
service_port          = 3000
checkport             = false     # 端口由向导决定，脚本里自行校验
ctl_stop              = true      # 允许在应用中心启动/停止
desktop_uidir         = ui
desktop_applaunchname = decotv.Application
```

关键 `app/ui/config`：

```json
{
  ".url": {
    "decotv.Application": {
      "title": "DecoTV",
      "icon": "images/icon_{0}.png",
      "type": "url",
      "protocol": "http",
      "port": "3000",
      "url": "/",
      "allUsers": true
    }
  }
}
```

> `title` / `port` 是安装时按向导参数重写的，`{0}` 由前端按尺寸（64/128/256）替换，所以图标必须按 `icon_64.png`、`icon_128.png`、`icon_256.png` 命名。

---

## 4. 实现要点（踩坑总结）

飞牛的 fpk 生命周期有几处和直觉不一致，这个包的处理方式如下。完整的实测记录见 [`docs/fnos-fpk-notes.md`](docs/fnos-fpk-notes.md)。

### 4.1 `privilege` 必须是 root

Docker 型应用的脚本要读 `/var/run/docker.sock`。用模板默认的 `run-as: package` 会直接报「Docker 服务未运行」（错误码 10237）。

```json
{ "defaults": { "run-as": "root" } }
```

### 4.2 端口和密码必须在 `install_init` 里写进 compose

实测时序是：

```
install_init → 复制文件到目标目录 → docker compose up（创建容器）
            → install_callback → install_success → 注册桌面入口
```

也就是说容器在 `install_callback` **之前**就已经起来了。因此：

- 不能用 compose 的 `${VAR:-default}` + `.env`（应用中心不会读我们写的 `.env`，实测密码和端口都没生效）；
- 必须由 `install_init` **直接生成** `docker-compose.yaml`，把端口和管理密码写死进去。

`install_init` 执行时 `$TRIM_APPDEST` 还不存在，待安装的副本在 `$TRIM_PKGINST_TEMP_DIR`，改这里才会被复制到目标目录。

### 4.3 桌面入口的端口要另外回写

桌面入口的 URL 由应用中心**在安装早期**就写进数据库（`appcenter` 库的 `app_service.url`），改包里的 `ui/config` 追不上。所以 `cmd/main status` 里做了一次幂等校正：读 `.env` 里的端口，若与上次记录不同就 `update app_service set url`。应用中心会周期性轮询 `status`，安装完成后的第一次轮询就把入口修正到位。

> 这一步失败不影响使用（磁盘上的 `ui/config` 已是正确端口，也可以在应用设置里手动调整）。

### 4.4 镜像源要按国内可达性排序

在这台 NAS 上直连 `ghcr.io` 拉 362 MB 镜像**6 分钟零字节**；南京大学镜像 `ghcr.nju.edu.cn` 秒下。安装脚本的尝试顺序：

1. `ghcr.nju.edu.cn/decohererk/decotv:latest`
2. `ghcr.m.daocloud.io/decohererk/decotv:latest`
3. `ghcr.io/decohererk/decotv:latest`

拉到后统一重打成私有标签 `decotv:<version>`，`docker-compose.yaml` 只引用这个本地标签，这样 compose 启动时不会再去 registry 拉取。

---

## 5. 升级与卸载

- **升级**：用新版 fpk 走正常安装流程；`upgrade_callback` 会沿用 `$TRIM_PKGETC` 里保存的密码与端口，重写 compose 与桌面入口
- **卸载**：`uninstall_init` 先备份密码/端口到应用配置目录；`uninstall_callback` 删除容器与私有镜像；数据共享目录保留
- **改端口/密码**：重新安装并在向导里填新值，或直接改

  ```bash
  # /vol1/@appcenter/decotv/docker/docker-compose.yaml
  ports: ["新端口:3000"]
  environment: PASSWORD: "新密码"
  ```

  然后 `appcenter-cli stop decotv && appcenter-cli start decotv`；端口变更后还需同步桌面入口（重启应用会由 `status` 自动校正）

---

## 6. 验证记录

在 fnOS `1.2.0800`（x86_64，默认安装卷 `/vol1`）上的实测结果：

| 项目 | 结果 |
| --- | --- |
| `appcenter-cli install-fpk` | 成功，镜像已缓存时约 15 秒 |
| 应用状态 | `running`，容器 `decotv` 正常运行 |
| 首页 | `http://<NAS>:3000/` → `307` 跳转 `/login?redirect=%2F` |
| 登录接口 `POST /api/login` | 正确密码 `200 {"ok":true}`；错误密码 `401` |
| 桌面入口 | `http://${host}:3000/`，`no_display=false`，所有用户可见 |
| 图标 | `ui/images/icon_{64,128,256}.png`，权限 `rwxrwxr-x` |
| 自定义端口（实测 3999） | 容器映射 `3999→3000`，桌面入口同步为 `:3999`，密码一并生效 |
| 数据挂载 | `/vol1/@appshare/decotv/data` → `/data` |
| 卸载 | 容器与镜像清理，数据目录保留 |

---

## 7. 已知限制

- 仅打包 `platform = x86`；ARM 机型需要改 manifest 后重新构建（镜像本身是否为多架构取决于上游）
- 首次安装需要拉取约 362 MB 镜像，网络不通时安装失败并提示换源
- 端口写入桌面入口依赖应用中心数据库结构（`app_service` / `app_shortcut`），在 `1.2.0800` 上验证；若后续版本表结构变化，这一步会静默跳过（不影响应用本身运行）
- DecoTV 采用 `NEXT_PUBLIC_STORAGE_TYPE=localstorage`（单机模式，数据在浏览器 localStorage），未接 Redis/Kvrocks；需要多端同步请自行改 compose

---

## 8. 排错

| 现象 | 原因与处理 |
| --- | --- |
| 安装报 `10237` + “Docker 服务未运行” | `config/privilege` 不是 `run-as: root` |
| 安装报 `10266` + `registry-1.docker.io ... deadline exceeded` | 拉取镜像失败：安装脚本已按镜像源回退，若全失败请检查 NAS 出网或 Docker 加速配置 |
| 安装报“端口已被占用” | 换一个访问端口重新安装 |
| 桌面图标打开是空白/连不上 | 端口与容器映射不一致。检查 `docker ps` 的映射端口，改 compose 后重启应用，`status` 会自动校正入口 |
| 密码不对 | 早期 `install_callback` 写 `.env` 的方式对 compose 无效，本包已改为由 `install_init` 直接生成 compose；确认 `docker inspect decotv` 里的 `PASSWORD` 与向导一致 |

---

## 9. 致谢与许可

- **DecoTV**：© [Decohererk](https://github.com/Decohererk/DecoTV)，请遵循其仓库的许可协议。本仓库不分发其源码或镜像，仅在安装时从上游镜像仓库（或其镜像站）拉取。
- 图标取自 DecoTV 仓库的 PWA 图标，仅用于应用入口展示。
- 本仓库的打包脚本与文档可自由使用、修改。

飞牛应用开发文档：<https://developer.fnnas.com/>
