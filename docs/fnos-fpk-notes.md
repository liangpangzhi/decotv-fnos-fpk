# 飞牛 fnOS fpk 打包实测笔记

记录把 DecoTV 打成 Docker 型 fpk 过程中，对飞牛 fnOS 应用框架的实测结论。官方文档没写清楚或与直觉相反的地方，都标了**实测**依据。

环境：飞牛 fnOS `1.2.0800`（Debian 12，内核 6.18.18），x86_64，Docker `28.5.2`，`appcenter-cli 1.0.2`，`fnpack 1.2.3`。

---

## 1. 生命周期时序（实测）

官方文档说「`install_init` 在安装文件前执行，`install_callback` 在安装文件后执行」。实测的完整顺序比这更细：

```
22:29:33  install app（install_start，此时会扫描包内容）
22:29:33  创建 docker 默认网络 trim-default
22:29:39  install_init                                   ← 目标目录还不存在
22:29:39  复制文件 → /vol1/@appcenter/decotv
22:29:39  docker compose up（容器在此刻就被创建）
22:29:39  install_callback
22:29:39  install_success
22:29:44  start app（main 由 compose 接管，cmd/main start 不会被调用）
```

由此得到的三个硬性约束：

| 约束 | 后果 |
| --- | --- |
| 容器在 `install_callback` 之前创建 | 端口、密码、镜像标签必须在 `install_init` 里就绪 |
| `install_init` 执行时 `$TRIM_APPDEST` 不存在 | 要改文件得改 `$TRIM_PKGINST_TEMP_DIR`（待安装副本） |
| 桌面入口在更早的阶段就已写入数据库 | 改包里的 `ui/config` 对已注册的入口无效 |

### 1.1 待安装副本的位置

`install_init` 里探针输出（节选）：

```text
TRIM_APPDEST=/vol1/@appcenter/decotv          # 此时 ls 报 No such file or directory
TRIM_PKGINST_TEMP_DIR=/vol1/appcenter-downloads/decotv-1.5.0-app
TRIM_TEMP_TPKFILE=/vol1/appcenter-downloads/decotv-1.5.0-tpk
TRIM_SERVICE_PORT=3000
TRIM_RUN_USERNAME=root
```

`TRIM_PKGINST_TEMP_DIR` 下已经是解压好的 `config/ docker/ ui/`，改这里的内容会被复制到目标目录。

---

## 2. 环境变量实测清单

安装阶段 `install_init` 里实际能拿到的（`env | grep ^TRIM_`）：

```text
TRIM_APPDEST=/vol1/@appcenter/decotv
TRIM_APPDEST_VOL=/vol1
TRIM_APPNAME=decotv
TRIM_APPVER=1.5.0
TRIM_APP_STATUS=INSTALL
TRIM_DATA_SHARE_PATHS=/vol1/@appshare/decotv:/vol1/@appshare/decotv/data
TRIM_PKGINST_TEMP_DIR=/vol1/appcenter-downloads/decotv-1.5.0-app
TRIM_PKGETC=/vol1/@appconf/decotv
TRIM_PKGVAR=/vol1/@appdata/decotv
TRIM_PKGTMP=/vol1/@apptemp/decotv
TRIM_PKGHOME=/vol1/@apphome/decotv
TRIM_PKGMETA=/vol1/@appmeta/decotv
TRIM_RUN_UID=0 / TRIM_RUN_USERNAME=root
TRIM_SERVICE_PORT=3000
TRIM_SYS_VERSION=1.2.0800 / TRIM_SYS_ARCH=x86
TRIM_TEMP_LOGFILE=/tmp/decotv.log.32971478
TRIM_TEMP_TPKFILE=/vol1/appcenter-downloads/decotv-1.5.0-tpk
TRIM_UID=976 / TRIM_GID=971 / TRIM_USERNAME=decotv / TRIM_GROUPNAME=decotv
```

要点：

- 向导字段直接变成同名环境变量（`wizard_port`、`wizard_admin_password`），`-e envfile` 传入时也一样
- 写用户可见错误：`echo "..." > "$TRIM_TEMP_LOGFILE"`，然后 `exit 1`；应用中心会把这段文本回显（错误码 `10237`/`10266` 后面跟的就是它）
- `TRIM_SERVICE_PORT` 只等于 manifest 里**静态**的 `service_port`，不会跟随向导变化，所以自定义端口时 `checkport` 要设 `false`，端口校验自己在脚本里做

---

## 3. `config/privilege` 必须是 root

Docker 型应用要访问 `/var/run/docker.sock`。模板默认：

```json
{ "defaults": { "run-as": "package" } }
```

实测直接失败：

```text
level=error msg="install error" appName=decotv error="10237:" text="Docker 服务未运行。请先启动 Docker 后重试安装。"
```

原因不是 Docker 没起来，而是脚本以包用户身份运行，`docker info` 报 `permission denied ... /var/run/docker.sock`。

改成：

```json
{ "defaults": { "run-as": "root" } }
```

参考系统里其他第三方 Docker 应用（`moo`、`gately`）也都是 `run-as: root`。

---

## 4. compose 的 `.env` 不被读取

模板和很多教程会写：

```yaml
ports:
  - "${HOST_PORT}:3000"
environment:
  - PASSWORD=${PASSWORD:-admin123}
```

实测在应用中心的执行环境下，同目录的 `.env` **不生效**：往 `$TRIM_APPDEST/docker/.env` 写 `DECOTV_PORT=3999`、`DECOTV_ADMIN_PASSWORD=xxx`，容器起来仍是 `3000` 和 `admin123`。

结论：**别依赖插值**，在 `install_init` 里直接渲染完整的 compose：

```bash
cat > "$COMPOSE" <<EOF
services:
  decotv:
    image: $IMG_LOCAL
    container_name: decotv
    restart: unless-stopped
    ports:
      - "$HOST_PORT:3000"
    environment:
      TZ: Asia/Shanghai
      PASSWORD: "$PWD_VALUE"
      ...
EOF
```

密码放进 YAML 双引号标量时，`"`、`\`、`$` 会破坏解析或被 compose 再次插值，向导/脚本里直接拒绝这三类字符最省事。

---

## 5. 桌面入口是怎么注册的

应用中心把入口存在 `appcenter` 库（PostgreSQL）里。相关表：

| 表 | 作用 | 关键列 |
| --- | --- | --- |
| `app` | 应用主记录 | `app_name`、`version`、`status`、`service_url` |
| `app_service` | 入口/服务定义 | `title`、`type`、`url`、`icon`、`full_url`、`no_display`、`control` |
| `app_shortcut` | 应用到入口的映射 | `app_id`、`service_id` |
| `app_env` | 向导提交值 | `field`、`value` |

和我们这个包相关的记录（实测）：

```text
app_service: title=DecoTV | type=url | url=http://${host}:3000/ | icon=ui/images/icon_{0}.png
             no_display=false
             control={"show":0,...,"portPerm":"editable","pathPerm":"editable","fullUrlPerm":"editable"}
```

几个细节：

- `${host}` 是**运行时**占位符，数据库里存的就是模板字符串，前端渲染时替换成访问域名
- `icon` 里的 `{0}` 同理，前端按尺寸替换成 `icon_64.png` / `icon_128.png` / `icon_256.png`
- `no_display=false` + `allUsers: true` 才会出现在所有用户的桌面
- 入口的 `url` 在**安装早期**写入，之后改包里的 `ui/config` 或重启应用都不会刷新（实测：改磁盘 `ui/config` 到 3999 后 `stop/start`，库里的 `url` 仍是 3000）

### 5.1 自定义端口怎么落到桌面图标上

`app_service.url` 不能靠改文件更新，只能改库。包里在 `cmd/main status` 里做**幂等校正**（应用中心会周期性轮询 `status`）：

```bash
sync_shortcut_port() {
    [ -f "$ENV_FILE" ] || return 0
    PORT=$(sed -n 's/^DECOTV_PORT=//p' "$ENV_FILE")
    case "$PORT" in ''|*[!0-9]*) return 0 ;; esac
    command -v psql >/dev/null 2>&1 || return 0

    STAMP="${TRIM_PKGVAR:-/tmp}/.shortcut_port"
    [ -f "$STAMP" ] && [ "$(cat "$STAMP")" = "$PORT" ] && return 0   # 只在端口变化时执行

    SQLFILE="${TRIM_PKGTMP:-/tmp}/fix_shortcut.sql"
    cat > "$SQLFILE" <<SQL
update app_service set url = 'http://\${host}:$PORT/'
where id in (select s.id from app_service s
             join app_shortcut sc on sc.service_id = s.id
             join app a on a.id = sc.app_id
             where a.app_name = 'decotv');
SQL
    su postgres -c "psql -d appcenter -q -f '$SQLFILE'" >/dev/null 2>&1 \
        && printf '%s' "$PORT" > "$STAMP"
}
```

要点：

- `cmd/main start` 对 Docker 型应用**不会被调用**（实测无任何调用记录），所以放在 `status`
- 用标记文件避免每次轮询都打一次数据库
- 放在 `install_callback` 里无效——那时还没到最终注册，写完会被覆盖
- 失败要静默：应用本身照常跑，只是入口端口可能仍是旧的

---

## 6. 镜像拉取的网络现实

同一台 NAS 上：

```text
ghcr.io/v2/ 返回 401（可达）    但 docker pull ghcr.io/decohererk/decotv:latest 6 分钟零字节
ghcr.nju.edu.cn  → 1 分多钟拉完 362 MB
```

安装脚本按 `ghcr.nju.edu.cn` → `ghcr.m.daocloud.io` → `ghcr.io` 顺序尝试，成功后 `docker tag` 成本地私有标签 `decotv:<version>`：

```bash
docker tag ghcr.nju.edu.cn/decohererk/decotv:latest decotv:1.5.0
```

compose 里只写 `image: decotv:1.5.0`，这样启动时不会再去 registry；镜像缺失时 compose 会报 `pull access denied`，所以镜像准备必须放在 `install_init`。

---

## 7. fnpack 的校验项

`fnpack build` 前会检查（缺一个就报错）：

- `manifest` 存在且含必要字段
- `config/privilege`、`config/resource` 是合法 JSON
- `ICON.PNG`、`ICON_256.PNG` 存在（64×64 / 256×256）
- `app/`、`cmd/`、`wizard/` 目录存在
- 声明了 `desktop_uidir` 时 `app/<uidir>/` 必须存在

打包产物就是个 tar：

```text
app.tgz           # app/ 目录的内容（ui/ + docker/）
cmd/...
config/...
wizard/...
manifest
ICON.PNG / ICON_256.PNG
```

`app.tgz` 内的文件权限为 644、脚本 755，安装后会被复制到 `target/`。

---

## 8. 安全扫描的一个小坑

安装日志里有一步 `module=security` 会列出"app package contents"：

```text
msg="app package contents" dirs="[cmd config wizard]" files="[ICON.PNG ICON_256.PNG app.tgz manifest]"
```

如果包里出现可执行文件、`*.sh` 或其它可疑内容，可能被拦。纯脚本 + compose 的包没有问题。

---

## 9. 常用排查命令

```bash
# 已安装应用
appcenter-cli list | grep decotv
appcenter-cli status decotv

# 安装日志（错误码后面跟的就是 TRIM_TEMP_LOGFILE 的内容）
grep -a 'install error' /var/log/trim_app_center/error.log | tail -3
tail -40 /var/log/trim_app_center/info.log

# 容器
docker ps -a --format '{{.Names}} {{.Status}} {{.Ports}}' | grep decotv
docker inspect decotv --format '{{range .Config.Env}}{{println .}}{{end}}'

# 桌面入口
sudo -u postgres psql -d appcenter -Atc \
 "select v.title, v.type, v.url, v.icon, v.no_display
  from app_service v join app_shortcut s on s.service_id=v.id
  join app a on a.id=s.app_id where a.app_name='decotv'"

# 服务是否真的通
curl -s -o /dev/null -w '%{http_code}\n' http://127.0.0.1:3000/
```

---

## 10. 结论速查

| 想做的事 | 正确做法 |
| --- | --- |
| 让脚本能用 docker | `config/privilege` → `run-as: root` |
| 安装时定制端口/密码 | `install_init` 里直接生成 compose（不靠 `.env`） |
| 让桌面图标跟着端口走 | `cmd/main status` 里幂等回写 `app_service.url` |
| 改包内容 | 改 `$TRIM_PKGINST_TEMP_DIR`，别改 `$TRIM_APPDEST` |
| 报错给用户看 | 写 `$TRIM_TEMP_LOGFILE` 后 `exit 1` |
| 国内拉镜像 | 优先 `ghcr.nju.edu.cn`，拉完打本地标签 |
