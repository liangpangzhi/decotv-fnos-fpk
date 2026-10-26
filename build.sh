#!/usr/bin/env bash
# 一键构建 DecoTV 的飞牛 fnOS 安装包（fpk）
# 依赖：python3 + Pillow；fnpack 会自动下载
set -euo pipefail
cd "$(dirname "$0")"

command -v python3 >/dev/null 2>&1 || { echo "缺少 python3"; exit 1; }
python3 -c 'import PIL' 2>/dev/null || { echo "缺少 Pillow，请先执行: pip install pillow"; exit 1; }

echo "==> 1/4 生成打包工程"
python3 make_fpk.py

echo "==> 2/4 准备 fnpack"
if [ ! -x ./.fnpack ]; then
    case "$(uname -s)" in
        Linux)  URL="https://static2.fnnas.com/fnpack/fnpack-1.2.3-linux-amd64" ;;
        Darwin) URL="https://static2.fnnas.com/fnpack/fnpack-1.2.3-darwin-arm64" ;;
        *)
            echo "当前系统请手动下载 fnpack 并放到 ./.fnpack，或直接运行: fnpack build --directory pkg/decotv"
            exit 1
            ;;
    esac
    echo "    下载 $URL"
    curl -fsSL -o .fnpack "$URL"
    chmod +x .fnpack
fi

echo "==> 3/4 打包"
./.fnpack build --directory pkg/decotv

echo "==> 4/4 归档"
VER=$(sed -n 's/^VERSION = "\(.*\)"/\1/p' make_fpk.py)
mkdir -p dist
mv -f decotv.fpk "dist/DecoTV-${VER}-fnos-x86.fpk"
echo "完成: dist/DecoTV-${VER}-fnos-x86.fpk"
