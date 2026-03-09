#!/usr/bin/env bash
# =============================================================================
# 名称: emscripten-wasm-build-template.sh
# 来源: https://simonwillison.net/guides/agentic-engineering-patterns/gif-optimization/
# 用途: 将 C/C++ CLI 工具编译到 WebAssembly 的标准化构建脚本模板
#       - 核心模式：不把源码放 repo，只放 patch + build script + 编译产物
#       - 用法：复制本文件到 lib/{tool-name}/build.sh，填写 TODO 变量
# 依赖: emcc (Emscripten, 通过 emsdk 安装) | bash 4.0+
# 适用场景:
#   - 把任何 C/C++ CLI 工具编译成可在浏览器运行的 WASM 模块
#   - 适合"文件输入 → 处理 → 文件输出"型 CLI 工具（gifsicle, pngquant, optipng 等）
#   - 配合 html-tools/ 下的 drag-drop Web UI 使用
# 日期: 2026-03-13
# =============================================================================

set -euo pipefail

# ==== TODO: 填写以下变量 ====
TOOL_NAME="gifsicle"                                           # 工具名（用于目录和输出文件名）
TOOL_REPO="https://github.com/kohler/gifsicle"                 # 上游 Git 仓库
TOOL_COMMIT="a2b4e2f7c3d1..."                                  # 锁定到已知可构建的 commit hash
SOURCE_FILES="src/gifsicle.c src/gifread.c src/gifwrite.c ..."  # 需要编译的 C/C++ 源文件
EXPORT_NAME="createGifsicleModule"                             # JS 模块构造函数名（建议：create${ToolName}Module）
# ==== END TODO ====

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BUILD_DIR="/tmp/${TOOL_NAME}-wasm-build"
OUTPUT_DIR="${SCRIPT_DIR}/../wasm"
PATCH_FILE="${SCRIPT_DIR}/${TOOL_NAME}.patch"

echo "==> Building ${TOOL_NAME} to WebAssembly"

# ---- Step 1: 安装/激活 Emscripten ----
if ! command -v emcc &>/dev/null; then
    echo "==> Installing Emscripten SDK..."
    EMSDK_DIR="/tmp/emsdk"
    if [ ! -d "$EMSDK_DIR" ]; then
        git clone https://github.com/emscripten-core/emsdk.git "$EMSDK_DIR"
    fi
    "$EMSDK_DIR/emsdk" install latest
    "$EMSDK_DIR/emsdk" activate latest
    # shellcheck source=/dev/null
    source "$EMSDK_DIR/emsdk_env.sh"
else
    echo "==> Emscripten already available: $(emcc --version | head -1)"
fi

# ---- Step 2: 克隆源码到 /tmp（不污染 repo） ----
echo "==> Cloning ${TOOL_REPO} to ${BUILD_DIR}..."
rm -rf "$BUILD_DIR"
git clone "$TOOL_REPO" "$BUILD_DIR"
cd "$BUILD_DIR"
git checkout "$TOOL_COMMIT"
echo "==> At commit: $(git log --oneline -1)"

# ---- Step 3: 应用兼容性 patch（如有） ----
if [ -f "$PATCH_FILE" ]; then
    echo "==> Applying patch: ${PATCH_FILE}"
    git apply "$PATCH_FILE"
else
    echo "==> No patch file found, building unmodified source"
fi

# ---- Step 4: 可选的预编译步骤（如 autoconf / cmake） ----
# 取消注释并按需修改：
# ./bootstrap  # 如果源码有 autoconf
# ./configure --disable-shared --enable-static  # 如有 configure
# cmake -DCMAKE_TOOLCHAIN_FILE="$EMSDK/cmake/Modules/Platform/Emscripten.cmake" .

# ---- Step 5: Emscripten 编译 ----
mkdir -p "$OUTPUT_DIR"

echo "==> Compiling to WASM..."

# 场景 A：文件 I/O 型（最常见）——工具通过文件路径传参，读写 /tmp/ 下的文件
# 适用：gifsicle, pngquant, optipng, convert (ImageMagick), ...
emcc $SOURCE_FILES -o "${OUTPUT_DIR}/${TOOL_NAME}.js" \
    -s WASM=1 \
    -s "EXPORTED_RUNTIME_METHODS=[\"callMain\",\"FS\"]" \
    -s ALLOW_MEMORY_GROWTH=1 \
    -s FORCE_FILESYSTEM=1 \
    -s MODULARIZE=1 \
    -s "EXPORT_NAME=${EXPORT_NAME}" \
    -O2

# 场景 B：stdin/stdout 管道型——工具从 stdin 读、向 stdout 写（取消注释替换场景 A）
# 适用：gzip, bzip2, wc, 无文件参数的纯管道工具
# emcc $SOURCE_FILES -o "${OUTPUT_DIR}/${TOOL_NAME}.js" \
#     -s WASM=1 \
#     -s "EXPORTED_RUNTIME_METHODS=[\"callMain\",\"FS\"]" \
#     -s ALLOW_MEMORY_GROWTH=1 \
#     -s MODULARIZE=1 \
#     -s "EXPORT_NAME=${EXPORT_NAME}" \
#     -O2

# 场景 C：库封装型——不通过 main()，而是暴露特定函数（取消注释替换场景 A）
# 适用：libvips, libpng 等有明确 API 的库
# emcc $SOURCE_FILES -o "${OUTPUT_DIR}/${TOOL_NAME}.js" \
#     -s WASM=1 \
#     -s "EXPORTED_FUNCTIONS=[\"_my_function\",\"_malloc\",\"_free\"]" \
#     -s "EXPORTED_RUNTIME_METHODS=[\"ccall\",\"cwrap\",\"FS\"]" \
#     -s ALLOW_MEMORY_GROWTH=1 \
#     -s MODULARIZE=1 \
#     -s "EXPORT_NAME=${EXPORT_NAME}" \
#     -O2

echo "==> Build complete!"
echo "    ${OUTPUT_DIR}/${TOOL_NAME}.js  ($(du -h "${OUTPUT_DIR}/${TOOL_NAME}.js" | cut -f1))"
echo "    ${OUTPUT_DIR}/${TOOL_NAME}.wasm  ($(du -h "${OUTPUT_DIR}/${TOOL_NAME}.wasm" | cut -f1))"

# ---- 清理（可选）----
# cd /
# rm -rf "$BUILD_DIR"

# ==============================================================================
# 在 HTML 中调用 WASM 模块的标准模式（复制到 .html 文件）
# ==============================================================================
# 
# <script src="lib/wasm/gifsicle.js"></script>
# <script>
# let module;
# 
# async function loadModule() {
#     module = await createGifsicleModule();
#     console.log('WASM module loaded');
# }
# 
# async function processFile(arrayBuffer, cliArgs) {
#     // 写输入文件到 WASM 虚拟文件系统
#     const inputData = new Uint8Array(arrayBuffer);
#     module.FS.writeFile('/input.gif', inputData);
#
#     // 调用 main() ≈ 在命令行执行 gifsicle [args] /input.gif -o /output.gif
#     module.callMain([...cliArgs, '/input.gif', '-o', '/output.gif']);
#
#     // 读取输出
#     const outputData = module.FS.readFile('/output.gif');
#
#     // 创建可下载的 Blob
#     const blob = new Blob([outputData], { type: 'image/gif' });
#     return URL.createObjectURL(blob);
# }
#
# // 清理文件（处理多文件时避免虚拟 FS 积累）
# function cleanupFiles() {
#     try { module.FS.unlink('/input.gif'); } catch(e) {}
#     try { module.FS.unlink('/output.gif'); } catch(e) {}
# }
#
# loadModule();
# </script>
# ==============================================================================
