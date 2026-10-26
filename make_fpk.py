#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""生成 DecoTV 的飞牛 fnOS fpk 工程（docker 型）。用法：python3 make_fpk.py

所有文本文件使用 LF 换行；shell 脚本模板统一用 raw string，
避免 Python 把 shell 里的反斜杠当转义处理。
"""
import io
import os
import shutil
from PIL import Image

ROOT = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(ROOT, "pkg", "decotv")
# 图标：优先用仓库自带素材，其次回退到本地 DecoTV 源码
ICON = os.path.join(ROOT, "assets", "icon.png")
if not os.path.exists(ICON):
    ICON = os.path.join(ROOT, "DecoTV", "public", "icons", "icon-256x256.png")

APPNAME = "decotv"
VERSION = "1.5.0"
PORT = "3000"
IMG_UPSTREAM = "ghcr.io/decohererk/decotv:latest"
IMG_LOCAL = "decotv:" + VERSION
IMG_MIRROR = "ghcr.nju.edu.cn/decohererk/decotv:latest"


def sub(t):
    return (t.replace("__APPNAME__", APPNAME)
             .replace("__VERSION__", VERSION)
             .replace("__PORT__", PORT)
             .replace("__IMG_UPSTREAM__", IMG_UPSTREAM)
             .replace("__IMG_LOCAL__", IMG_LOCAL)
             .replace("__IMG_MIRROR__", IMG_MIRROR))


def w(rel, content, mode=None):
    path = os.path.join(OUT, rel)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with io.open(path, "w", encoding="utf-8", newline="\n") as f:
        f.write(sub(content))
    if mode:
        os.chmod(path, mode)


MANIFEST = r"""appname               = __APPNAME__
version               = __VERSION__
display_name          = DecoTV
desc                  = 影视聚合与播放 Web 应用（Next.js 16）：豆瓣榜单、TVBox / 自定义源搜索、弹幕、私有影库（OpenList / Emby / Jellyfin）与 FFmpeg 转存下载。安装后从飞牛桌面点击图标即可进入。
platform              = x86
source                = thirdparty
maintainer            = WorkBuddy
maintainer_url        = https://github.com/Decohererk/DecoTV
distributor           = WorkBuddy
service_port          = __PORT__
checkport             = false
ctl_stop              = true
desktop_uidir         = ui
desktop_applaunchname = decotv.Application
"""

PRIVILEGE = r"""{
    "defaults":
    {
        "run-as": "root"
    }
}
"""

RESOURCE = r"""{
  "docker-project": {
    "projects": [
      {
        "name": "__APPNAME__",
        "path": "docker"
      }
    ]
  },
  "data-share": {
    "shares": [
      {
        "name": "__APPNAME__"
      },
      {
        "name": "__APPNAME__/data"
      }
    ]
  }
}
"""

# 模板默认值；安装时 install_init 会按用户选择整份重写
UI_CONFIG = r"""{
    ".url": {
        "decotv.Application": {
            "title": "DecoTV",
            "icon": "images/icon_{0}.png",
            "type": "url",
            "protocol": "http",
            "port": "__PORT__",
            "url": "/",
            "allUsers": true
        }
    }
}
"""

COMPOSE = r"""services:
  decotv:
    image: __IMG_LOCAL__
    container_name: decotv
    restart: unless-stopped
    ports:
      - "__PORT__:__PORT__"
    environment:
      TZ: Asia/Shanghai
      PASSWORD: "admin123"
      USERNAME: admin
      NEXT_PUBLIC_STORAGE_TYPE: localstorage
      FFMPEG_DOWNLOAD_DIR: /data/ffmpeg-downloads
    volumes:
      - /var/apps/__APPNAME__/shares/__APPNAME__/data:/data
"""

WIZARD_INSTALL = r"""[
  {
    "stepTitle": "DecoTV 安装配置",
    "items": [
      {
        "type": "tips",
        "helpText": "DecoTV 容器内部固定使用 3000 端口，这里填写对外访问端口（默认 3000）。数据保存在本应用的 data 共享目录；安装完成后在飞牛桌面点击 DecoTV 图标即可进入，首次登录使用下方设置的管理密码。"
      },
      {
        "type": "text",
        "field": "wizard_port",
        "label": "访问端口",
        "initValue": "__PORT__",
        "rules": [
          {
            "required": true,
            "message": "请填写访问端口"
          },
          {
            "pattern": "^[0-9]+$",
            "message": "端口只能是数字"
          }
        ]
      },
      {
        "type": "password",
        "field": "wizard_admin_password",
        "label": "管理密码",
        "initValue": "admin123",
        "rules": [
          {
            "required": true,
            "message": "请设置管理密码"
          },
          {
            "min": 4,
            "message": "密码至少 4 位"
          }
        ]
      }
    ]
  }
]
"""

CMD_MAIN = r"""#!/bin/bash

FILE_PATH="${TRIM_APPDEST}/docker/docker-compose.yaml"
ENV_FILE="${TRIM_APPDEST}/docker/.env"
DEFAULT_NAME="decotv"

# 让桌面入口与用户选择的端口保持一致。
# 飞牛在安装早期就把入口写进应用中心数据库，安装脚本后置，
# 因此每次启动时都按 .env 里的端口校正一次（幂等，失败不影响启动）。
sync_shortcut_port() {
    [ -f "$ENV_FILE" ] || return 0

    PORT=$(sed -n 's/^DECOTV_PORT=//p' "$ENV_FILE" 2>/dev/null)
    case "$PORT" in
        ''|*[!0-9]*) return 0 ;;
    esac

    command -v psql >/dev/null 2>&1 || return 0

    TMPDIR_SQL="${TRIM_PKGTMP:-/tmp}"
    mkdir -p "$TMPDIR_SQL" 2>/dev/null
    SQLFILE="$TMPDIR_SQL/fix_shortcut.sql"

    cat > "$SQLFILE" <<SQL
update app_service set url = 'http://\${host}:$PORT/'
where id in (
  select s.id from app_service s
  join app_shortcut sc on sc.service_id = s.id
  join app a on a.id = sc.app_id
  where a.app_name = 'decotv'
);
SQL
    STAMP="${TRIM_PKGVAR:-/tmp}/.shortcut_port"
    if [ -f "$STAMP" ] && [ "$(cat "$STAMP" 2>/dev/null)" = "$PORT" ]; then
        return 0
    fi

    chmod 644 "$SQLFILE" 2>/dev/null
    su postgres -c "psql -d appcenter -q -f '$SQLFILE'" >/dev/null 2>&1
    RC=$?
    if [ "$RC" -eq 0 ]; then
        printf '%s' "$PORT" > "$STAMP" 2>/dev/null
    fi
    rm -f "$SQLFILE"
}

is_docker_running () {
    DOCKER_NAME=""

    if [ -f "$FILE_PATH" ]; then
        DOCKER_NAME=$(grep "container_name" "$FILE_PATH" | head -1 | awk -F ':' '{print $2}' | xargs)
    fi

    if [ -z "$DOCKER_NAME" ]; then
        DOCKER_NAME="$DEFAULT_NAME"
    fi

    if docker inspect "$DOCKER_NAME" 2>/dev/null | grep -q '"Status": "running",'; then
        return 0
    fi
    return 1
}

case "$1" in
start)
    # 容器由应用中心通过 docker compose 启动，这里只校正桌面入口端口
    sync_shortcut_port
    exit 0
    ;;
stop)
    # 容器由应用中心通过 docker compose 停止
    exit 0
    ;;
status)
    sync_shortcut_port
    if is_docker_running; then
        exit 0
    else
        exit 3
    fi
    ;;
*)
    exit 1
    ;;
esac
"""

CMD_INSTALL_INIT = r"""#!/bin/bash

### 安装文件前执行：校验参数、按用户选择生成 compose 与桌面入口、准备镜像
### 说明：应用中心在 install_callback 之前就会创建容器并注册桌面入口，
### 所以端口与密码必须在这里写进待安装的副本（TRIM_PKGINST_TEMP_DIR）。

LOG="$TRIM_TEMP_LOGFILE"
IMG_LOCAL="__IMG_LOCAL__"
APPSRC="$TRIM_PKGINST_TEMP_DIR"
[ -d "$APPSRC" ] || APPSRC="$TRIM_APPDEST"

fail() {
    echo "$1" > "$LOG"
    exit 1
}

command -v docker >/dev/null 2>&1 || fail "未检测到 Docker。请先在飞牛应用中心安装并启动 Docker，再安装 DecoTV。"
docker info >/dev/null 2>&1 || fail "Docker 服务未运行。请先启动 Docker 后重试安装。"

# ---- 读取并校验向导参数 ----
PWD_VALUE="${wizard_admin_password}"
if [ -z "$PWD_VALUE" ]; then
    PWD_VALUE="admin123"
fi

case "$PWD_VALUE" in
    *'"'*|*\\*|*'$'*)
        fail "管理密码不能包含双引号、反斜杠或美元符号，请换一个密码后重新安装。"
        ;;
esac

HOST_PORT="${wizard_port}"
case "$HOST_PORT" in
    ''|*[!0-9]*) HOST_PORT="__PORT__" ;;
esac
if [ "$HOST_PORT" -lt 1 ] || [ "$HOST_PORT" -gt 65535 ]; then
    HOST_PORT="__PORT__"
fi

if command -v ss >/dev/null 2>&1 && ss -lnt 2>/dev/null | awk '{print $4}' | grep -qE ":$HOST_PORT$"; then
    fail "端口 $HOST_PORT 已被占用，DecoTV 无法启动。请更换端口后重新安装。"
fi

# ---- 生成 compose（写入实际端口与管理密码）----
COMPOSE="$APPSRC/docker/docker-compose.yaml"
if [ -d "$APPSRC/docker" ]; then
    cat > "$COMPOSE" <<EOF
services:
  decotv:
    image: $IMG_LOCAL
    container_name: decotv
    restart: unless-stopped
    ports:
      - "$HOST_PORT:__PORT__"
    environment:
      TZ: Asia/Shanghai
      PASSWORD: "$PWD_VALUE"
      USERNAME: admin
      NEXT_PUBLIC_STORAGE_TYPE: localstorage
      FFMPEG_DOWNLOAD_DIR: /data/ffmpeg-downloads
    volumes:
      - /var/apps/__APPNAME__/shares/__APPNAME__/data:/data
EOF
fi

# ---- 桌面入口按用户端口生成（包内解压副本 + 目标目录都写一遍）----
write_ui_config() {
    local cfg="$1"
    local dir
    dir=$(dirname "$cfg")
    [ -d "$dir" ] || return 0
    cat > "$cfg" <<EOF
{
    ".url": {
        "decotv.Application": {
            "title": "DecoTV",
            "icon": "images/icon_{0}.png",
            "type": "url",
            "protocol": "http",
            "port": "$HOST_PORT",
            "url": "/",
            "allUsers": true
        }
    }
}
EOF
}

write_ui_config "$APPSRC/ui/config"
write_ui_config "$TRIM_TEMP_TPKFILE/app/ui/config"
write_ui_config "$TRIM_APPDEST/ui/config"

# ---- 准备镜像 ----
if docker image inspect "$IMG_LOCAL" >/dev/null 2>&1; then
    exit 0
fi

for SRC_IMG in "__IMG_MIRROR__" "ghcr.m.daocloud.io/decohererk/decotv:latest" "__IMG_UPSTREAM__"; do
    if docker image inspect "$SRC_IMG" >/dev/null 2>&1; then
        docker tag "$SRC_IMG" "$IMG_LOCAL" && exit 0
    fi
    echo "正在准备镜像: $SRC_IMG" >> "$LOG"
    if docker pull "$SRC_IMG"; then
        docker tag "$SRC_IMG" "$IMG_LOCAL" && exit 0
    fi
done

fail "DecoTV 镜像拉取失败。请检查 NAS 网络或在 Docker 设置中配置镜像加速后重试安装。"
"""

CMD_INSTALL_CALLBACK = r"""#!/bin/bash

### 安装文件后执行：记录配置、确保桌面入口端口正确、兜底准备镜像标签

LOG="$TRIM_TEMP_LOGFILE"
IMG_LOCAL="__IMG_LOCAL__"

PWD_VALUE="${wizard_admin_password}"
if [ -z "$PWD_VALUE" ]; then
    PWD_VALUE="admin123"
fi

HOST_PORT="${wizard_port}"
case "$HOST_PORT" in
    ''|*[!0-9]*) HOST_PORT="__PORT__" ;;
esac
if [ "$HOST_PORT" -lt 1 ] || [ "$HOST_PORT" -gt 65535 ]; then
    HOST_PORT="__PORT__"
fi

# 记录配置，供升级/卸载流程参考
mkdir -p "$TRIM_APPDEST/docker" "$TRIM_PKGETC"
{
    printf "DECOTV_ADMIN_PASSWORD='%s'\n" "$PWD_VALUE"
    printf "DECOTV_PORT=%s\n" "$HOST_PORT"
} > "$TRIM_APPDEST/docker/.env"
chmod 640 "$TRIM_APPDEST/docker/.env"
printf "%s" "$HOST_PORT" > "$TRIM_PKGETC/admin_port"
printf "%s" "$PWD_VALUE" > "$TRIM_PKGETC/admin_password"
chmod 600 "$TRIM_PKGETC/admin_password"

# 兜底：再次写入桌面入口端口
if [ -d "$TRIM_APPDEST/ui" ]; then
    cat > "$TRIM_APPDEST/ui/config" <<EOF
{
    ".url": {
        "decotv.Application": {
            "title": "DecoTV",
            "icon": "images/icon_{0}.png",
            "type": "url",
            "protocol": "http",
            "port": "$HOST_PORT",
            "url": "/",
            "allUsers": true
        }
    }
}
EOF
fi

# 桌面入口由应用中心在安装早期写入数据库，安装脚本后置，这里回写用户选择的端口。
# 失败不影响安装（磁盘上的 ui/config 已是正确端口，可在应用设置里再调整）。
if command -v psql >/dev/null 2>&1; then
    SQLFILE="$TRIM_PKGTMP/fix_shortcut.sql"
    mkdir -p "$TRIM_PKGTMP"
    cat > "$SQLFILE" <<SQL
update app_service set url = 'http://\${host}:$HOST_PORT/'
where id in (
  select s.id from app_service s
  join app_shortcut sc on sc.service_id = s.id
  join app a on a.id = sc.app_id
  where a.app_name = '__APPNAME__'
);
SQL
    chmod 644 "$SQLFILE"
    su postgres -c "psql -d appcenter -q -f '$SQLFILE'" >/dev/null 2>&1 || true
    rm -f "$SQLFILE"
fi

docker image inspect "$IMG_LOCAL" >/dev/null 2>&1 || docker tag "__IMG_MIRROR__" "$IMG_LOCAL" 2>/dev/null

exit 0
"""

CMD_UPGRADE_INIT = r"""#!/bin/bash

### 升级前执行

exit 0
"""

CMD_UPGRADE_CALLBACK = r"""#!/bin/bash

### 升级后执行：沿用已有的管理密码与端口，并重写 compose

if [ ! -f "$TRIM_PKGETC/admin_password" ]; then
    exit 0
fi

PWD_VALUE=$(cat "$TRIM_PKGETC/admin_password")
HOST_PORT=$(cat "$TRIM_PKGETC/admin_port" 2>/dev/null)
case "$HOST_PORT" in
    ''|*[!0-9]*) HOST_PORT="__PORT__" ;;
esac

mkdir -p "$TRIM_APPDEST/docker"
cat > "$TRIM_APPDEST/docker/docker-compose.yaml" <<EOF
services:
  decotv:
    image: __IMG_LOCAL__
    container_name: decotv
    restart: unless-stopped
    ports:
      - "$HOST_PORT:__PORT__"
    environment:
      TZ: Asia/Shanghai
      PASSWORD: "$PWD_VALUE"
      USERNAME: admin
      NEXT_PUBLIC_STORAGE_TYPE: localstorage
      FFMPEG_DOWNLOAD_DIR: /data/ffmpeg-downloads
    volumes:
      - /var/apps/__APPNAME__/shares/__APPNAME__/data:/data
EOF

if [ -d "$TRIM_APPDEST/ui" ]; then
    cat > "$TRIM_APPDEST/ui/config" <<EOF
{
    ".url": {
        "decotv.Application": {
            "title": "DecoTV",
            "icon": "images/icon_{0}.png",
            "type": "url",
            "protocol": "http",
            "port": "$HOST_PORT",
            "url": "/",
            "allUsers": true
        }
    }
}
EOF
fi

docker image inspect "__IMG_LOCAL__" >/dev/null 2>&1 || docker tag "__IMG_MIRROR__" "__IMG_LOCAL__" 2>/dev/null

exit 0
"""

CMD_UNINSTALL_INIT = r"""#!/bin/bash

### 卸载前执行：备份管理密码与端口，便于重装后沿用

if [ -f "$TRIM_PKGETC/admin_port" ] && [ -f "$TRIM_PKGETC/admin_password" ]; then
    exit 0
fi

if [ -f "$TRIM_APPDEST/docker/.env" ]; then
    mkdir -p "$TRIM_PKGETC"
    sed -n "s/^DECOTV_ADMIN_PASSWORD='\(.*\)'$/\1/p" "$TRIM_APPDEST/docker/.env" > "$TRIM_PKGETC/admin_password" 2>/dev/null
    sed -n 's/^DECOTV_PORT=//p' "$TRIM_APPDEST/docker/.env" > "$TRIM_PKGETC/admin_port" 2>/dev/null
fi

exit 0
"""

CMD_UNINSTALL_CALLBACK = r"""#!/bin/bash

### 卸载清理后执行：移除容器与镜像

docker rm -f decotv >/dev/null 2>&1
docker rmi "__IMG_LOCAL__" >/dev/null 2>&1

exit 0
"""

CMD_NOOP = r"""#!/bin/bash

exit 0
"""


def main():
    if os.path.isdir(OUT):
        shutil.rmtree(OUT)
    os.makedirs(OUT)

    w("manifest", MANIFEST)
    w("config/privilege", PRIVILEGE)
    w("config/resource", RESOURCE)
    w("app/ui/config", UI_CONFIG)
    w("app/docker/docker-compose.yaml", COMPOSE)
    w("wizard/install", WIZARD_INSTALL)

    w("cmd/main", CMD_MAIN, 0o755)
    w("cmd/install_init", CMD_INSTALL_INIT, 0o755)
    w("cmd/install_callback", CMD_INSTALL_CALLBACK, 0o755)
    w("cmd/upgrade_init", CMD_UPGRADE_INIT, 0o755)
    w("cmd/upgrade_callback", CMD_UPGRADE_CALLBACK, 0o755)
    w("cmd/uninstall_init", CMD_UNINSTALL_INIT, 0o755)
    w("cmd/uninstall_callback", CMD_UNINSTALL_CALLBACK, 0o755)
    w("cmd/config_init", CMD_NOOP, 0o755)
    w("cmd/config_callback", CMD_NOOP, 0o755)

    # ---- 图标 ----
    img = Image.open(ICON).convert("RGBA")
    os.makedirs(os.path.join(OUT, "app", "ui", "images"), exist_ok=True)
    img.resize((256, 256), Image.LANCZOS).save(os.path.join(OUT, "ICON_256.PNG"), "PNG")
    img.resize((64, 64), Image.LANCZOS).save(os.path.join(OUT, "ICON.PNG"), "PNG")
    img.resize((128, 128), Image.LANCZOS).save(os.path.join(OUT, "app", "ui", "images", "icon_128.png"), "PNG")
    img.resize((256, 256), Image.LANCZOS).save(os.path.join(OUT, "app", "ui", "images", "icon_256.png"), "PNG")
    img.resize((64, 64), Image.LANCZOS).save(os.path.join(OUT, "app", "ui", "images", "icon_64.png"), "PNG")

    print("工程已生成:", OUT)
    for root, dirs, files in os.walk(OUT):
        for f in sorted(files):
            p = os.path.join(root, f)
            print("  %-45s %6d" % (os.path.relpath(p, OUT), os.path.getsize(p)))


if __name__ == "__main__":
    main()
