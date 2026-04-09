#!/bin/bash
# OPC Team 通用安装脚本
# 支持 Claude Code / OpenClaw / Cursor / Windsurf / 通用 CLI

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CALLER_DIR="$(pwd)"

# 颜色输出
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

echo_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

echo_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

echo_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

run_repo_tool() {
    local tool="$1"
    shift
    (
        cd "$SCRIPT_DIR"
        python3 "tools/${tool}.py" "$@"
    )
}

write_adapted_skill() {
    local output_file="$1"
    local config_path="$2"
    local tool_prefix="$3"

    python3 - "$SCRIPT_DIR/SKILL.md" "$output_file" "$config_path" "$tool_prefix" <<'PY'
from pathlib import Path
import sys

src, dst, config_path, tool_prefix = sys.argv[1:5]
text = Path(src).read_text(encoding="utf-8")
text = text.replace("python3 tools/", f"OPC_CONFIG={config_path} python3 {tool_prefix}/")
Path(dst).write_text(text, encoding="utf-8")
PY
}

sync_project_bundle() {
    local bundle_dir="$1"
    local bundle_platform="$2"

    mkdir -p "$bundle_dir/tools"
    cp "$SCRIPT_DIR"/tools/*.py "$bundle_dir/tools/"
    cp "$SCRIPT_DIR/config.json" "$bundle_dir/"
    cp "$SCRIPT_DIR/README.md" "$bundle_dir/"
    cp "$SCRIPT_DIR/install.sh" "$bundle_dir/"
    cp "$SCRIPT_DIR/DEPLOYMENT.md" "$bundle_dir/"
    (
        cd "$bundle_dir"
        python3 tools/config.py init --platform "$bundle_platform" >/dev/null
        python3 tools/memory_sync.py init >/dev/null
    )
}

init_bundle_config() {
    local bundle_dir="$1"
    local bundle_platform="$2"

    (
        cd "$bundle_dir"
        python3 tools/config.py init --platform "$bundle_platform" >/dev/null
        python3 tools/memory_sync.py init >/dev/null
    )
}

# 检测操作系统
detect_os() {
    if [[ "$OSTYPE" == "linux-gnu"* ]]; then
        echo "linux"
    elif [[ "$OSTYPE" == "darwin"* ]]; then
        echo "macos"
    elif [[ "$OSTYPE" == "msys" ]] || [[ "$OSTYPE" == "cygwin" ]]; then
        echo "windows"
    else
        echo "unknown"
    fi
}

# 检测 Python 版本
check_python() {
    if command -v python3 &> /dev/null; then
        PYTHON_VERSION=$(python3 --version | awk '{print $2}')
        PYTHON_MAJOR=$(echo $PYTHON_VERSION | cut -d. -f1)
        PYTHON_MINOR=$(echo $PYTHON_VERSION | cut -d. -f2)

        if [ "$PYTHON_MAJOR" -ge 3 ] && [ "$PYTHON_MINOR" -ge 7 ]; then
            echo_success "Python $PYTHON_VERSION 已安装"
            return 0
        else
            echo_error "需要 Python 3.7+，当前版本: $PYTHON_VERSION"
            return 1
        fi
    else
        echo_error "未找到 Python 3，请先安装 Python 3.7+"
        return 1
    fi
}

# 检测 AI 平台
detect_platform() {
    if [ -d "$HOME/.claude" ]; then
        echo "claude_code"
    elif [ -d "$HOME/.openclaw" ]; then
        echo "openclaw"
    elif [ -f "$CALLER_DIR/.cursorrules" ]; then
        echo "cursor"
    elif [ -f "$CALLER_DIR/.windsurfrules" ]; then
        echo "windsurf"
    else
        echo "generic"
    fi
}

# 安装依赖
install_dependencies() {
    echo_info "检查依赖..."

    # 检查是否需要安装 filelock（Windows 或没有 fcntl 的系统）
    OS=$(detect_os)
    if [ "$OS" == "windows" ]; then
        echo_info "Windows 系统，安装 filelock..."
        python3 -m pip install filelock --quiet
    fi

    echo_success "依赖检查完成"
}

# 初始化配置
init_config() {
    echo_info "初始化配置..."

    if [ -n "$PLATFORM" ] && [ "$PLATFORM" != "auto" ]; then
        TARGET_PLATFORM="$PLATFORM"
    else
        TARGET_PLATFORM=$(detect_platform)
    fi

    if [ "$CALLER_DIR" = "$SCRIPT_DIR" ]; then
        run_repo_tool config init --platform "$TARGET_PLATFORM"
        echo_success "已按平台初始化配置: $TARGET_PLATFORM"
    elif [ ! -f "$SCRIPT_DIR/config.json" ]; then
        run_repo_tool config init --platform generic
        echo_success "已创建默认配置"
    else
        echo_info "使用仓库内默认配置: $SCRIPT_DIR/config.json"
    fi

    echo_success "配置初始化完成"
}

# 创建数据目录
init_data_dirs() {
    echo_info "创建数据目录..."

    mkdir -p \
        "$SCRIPT_DIR/data/tasks" \
        "$SCRIPT_DIR/data/decisions" \
        "$SCRIPT_DIR/data/risks" \
        "$SCRIPT_DIR/data/memory" \
        "$SCRIPT_DIR/data/logs"

    echo_success "数据目录创建完成"
}

# 初始化记忆文件
init_memory() {
    echo_info "初始化记忆系统..."

    run_repo_tool memory_sync init

    echo_success "记忆系统初始化完成"
}

# 设置环境变量
setup_env() {
    echo_info "设置环境变量..."

    OPC_HOME="$SCRIPT_DIR"

    # 检测 shell 类型
    if [ -n "$BASH_VERSION" ]; then
        SHELL_RC="$HOME/.bashrc"
    elif [ -n "$ZSH_VERSION" ]; then
        SHELL_RC="$HOME/.zshrc"
    else
        SHELL_RC="$HOME/.profile"
    fi

    # 检查是否已经设置
    if grep -q "OPC_HOME" "$SHELL_RC" 2>/dev/null; then
        echo_warning "OPC_HOME 已在 $SHELL_RC 中设置"
    else
        echo "" >> "$SHELL_RC"
        echo "# OPC Team" >> "$SHELL_RC"
        echo "export OPC_HOME=\"$OPC_HOME\"" >> "$SHELL_RC"
        echo "export PATH=\"\$OPC_HOME/tools:\$PATH\"" >> "$SHELL_RC"
        echo_success "已添加 OPC_HOME 到 $SHELL_RC"
        echo_warning "请运行 'source $SHELL_RC' 或重启终端"
    fi
}

# 平台特定安装
install_for_platform() {
    PLATFORM=$1

    case $PLATFORM in
        claude_code)
            echo_info "为 Claude Code 安装..."
            SKILL_DIR="$HOME/.claude/skills/opc-team"
            mkdir -p "$SKILL_DIR"
            mkdir -p "$SKILL_DIR/tools"
            cp "$SCRIPT_DIR"/tools/*.py "$SKILL_DIR/tools/"
            cp "$SCRIPT_DIR/config.json" "$SKILL_DIR/"
            init_bundle_config "$SKILL_DIR" "claude_code"
            write_adapted_skill \
                "$SKILL_DIR/SKILL.md" \
                "$(printf '%q' "$SKILL_DIR/config.json")" \
                "$(printf '%q' "$SKILL_DIR/tools")"
            echo_success "已安装到 $SKILL_DIR"
            echo_info "重启 Claude Code 后即可使用"
            ;;

        openclaw)
            echo_info "为 OpenClaw 安装..."
            # 支持 --agent-id 参数或交互式输入
            if [ -z "$AGENT_ID" ]; then
                if [ -t 0 ]; then
                    echo_info "请输入 agent ID (例如: default)"
                    read -p "输入 agent ID: " AGENT_ID
                else
                    echo_warning "未提供 agent ID，非交互环境下默认使用 default"
                fi
            fi
            if [ -z "$AGENT_ID" ]; then
                AGENT_ID="default"
            fi
            SKILL_DIR="$HOME/.openclaw/workspace-$AGENT_ID/skills/opc-team"
            mkdir -p "$SKILL_DIR"
            mkdir -p "$SKILL_DIR/tools"
            cp "$SCRIPT_DIR"/tools/*.py "$SKILL_DIR/tools/"
            cp "$SCRIPT_DIR/config.json" "$SKILL_DIR/"
            init_bundle_config "$SKILL_DIR" "openclaw"
            write_adapted_skill \
                "$SKILL_DIR/SKILL.md" \
                "$(printf '%q' "$SKILL_DIR/config.json")" \
                "$(printf '%q' "$SKILL_DIR/tools")"
            echo_success "已安装到 $SKILL_DIR"
            echo_info "Agent ID: $AGENT_ID"
            ;;

        api)
            echo_info "为 API 模式安装..."
            echo_info "API 模式需要通过环境变量配置"
            echo_info "设置 OPC_API_KEY 和 OPC_API_URL 后即可使用"
            echo_success "API 模式安装完成"
            ;;

        cursor)
            echo_info "为 Cursor 安装..."
            sync_project_bundle "$CALLER_DIR/opc-team" "cursor"
            if [ -f "$CALLER_DIR/.cursorrules" ]; then
                echo_warning ".cursorrules 已存在，将追加内容"
                echo "" >> "$CALLER_DIR/.cursorrules"
            fi
            TEMP_SKILL="$(mktemp)"
            write_adapted_skill "$TEMP_SKILL" "opc-team/config.json" "opc-team/tools"
            cat "$TEMP_SKILL" >> "$CALLER_DIR/.cursorrules"
            rm -f "$TEMP_SKILL"
            echo_success "已同步工具到 $CALLER_DIR/opc-team 并追加到 .cursorrules"
            echo_info "Cursor 会自动加载规则"
            ;;

        windsurf)
            echo_info "为 Windsurf 安装..."
            sync_project_bundle "$CALLER_DIR/opc-team" "windsurf"
            if [ -f "$CALLER_DIR/.windsurfrules" ]; then
                echo_warning ".windsurfrules 已存在，将追加内容"
                echo "" >> "$CALLER_DIR/.windsurfrules"
            fi
            TEMP_SKILL="$(mktemp)"
            write_adapted_skill "$TEMP_SKILL" "opc-team/config.json" "opc-team/tools"
            cat "$TEMP_SKILL" >> "$CALLER_DIR/.windsurfrules"
            rm -f "$TEMP_SKILL"
            echo_success "已同步工具到 $CALLER_DIR/opc-team 并追加到 .windsurfrules"
            ;;

        generic)
            echo_info "通用安装模式"
            echo_success "工具已就绪，可直接使用 CLI 命令"
            echo_info "示例: python3 \"$SCRIPT_DIR/tools/task_flow.py\" create --title '测试任务' --ceo-input '测试'"
            ;;
    esac
}

# 运行测试
run_test() {
    echo_info "运行测试..."

    # 创建测试任务
    TEST_OUTPUT=$(run_repo_tool task_flow create --title "安装测试" --ceo-input "测试安装是否成功" 2>&1)

    if echo "$TEST_OUTPUT" | grep -q "success.*true"; then
        TASK_ID=$(echo "$TEST_OUTPUT" | grep -o 'T[0-9]\{3\}')
        echo_success "测试通过！任务 $TASK_ID 创建成功"

        # 清理测试数据
        rm -f "$SCRIPT_DIR/data/tasks/$TASK_ID.json"
        return 0
    else
        echo_error "测试失败"
        echo "$TEST_OUTPUT"
        return 1
    fi
}

# 显示帮助
show_help() {
    cat << EOF
OPC Team 安装脚本

用法:
    ./install.sh [选项]

选项:
    -h, --help              显示帮助信息
    -p, --platform PLATFORM 指定平台 (claude_code/openclaw/api/cursor/windsurf/generic)
    -a, --agent-id ID       OpenClaw agent ID（默认: default）
    -t, --test              安装后运行测试
    --skip-env              跳过环境变量设置
    --skip-deps             跳过依赖安装

示例:
    ./install.sh                         # 自动检测平台并安装
    ./install.sh -p claude_code          # 为 Claude Code 安装
    ./install.sh -p openclaw -a default   # 为 OpenClaw 安装（指定 agent）
    ./install.sh -p api                   # 为 API 模式安装
    ./install.sh -t                      # 安装并测试

EOF
}

# 主函数
main() {
    echo "========================================="
    echo "  OPC Team v4.2.2 安装程序"
    echo "========================================="
    echo ""

    # 解析参数
    PLATFORM=""
    AGENT_ID=""
    RUN_TEST=false
    SKIP_ENV=false
    SKIP_DEPS=false

    while [[ $# -gt 0 ]]; do
        case $1 in
            -h|--help)
                show_help
                exit 0
                ;;
            -p|--platform)
                PLATFORM="$2"
                shift 2
                ;;
            -a|--agent-id)
                AGENT_ID="$2"
                shift 2
                ;;
            -t|--test)
                RUN_TEST=true
                shift
                ;;
            --skip-env)
                SKIP_ENV=true
                shift
                ;;
            --skip-deps)
                SKIP_DEPS=true
                shift
                ;;
            *)
                echo_error "未知选项: $1"
                show_help
                exit 1
                ;;
        esac
    done

    # 检查 Python
    if ! check_python; then
        exit 1
    fi

    # 安装依赖
    if [ "$SKIP_DEPS" = false ]; then
        install_dependencies
    fi

    # 自动检测平台（如果用户指定了 -p 则使用用户指定的）
    if [ -z "$PLATFORM" ]; then
        PLATFORM=$(detect_platform)
    fi

    # 初始化
    init_data_dirs
    init_config
    init_memory

    # 设置环境变量
    if [ "$SKIP_ENV" = false ]; then
        setup_env
    fi

    # 平台特定安装
    install_for_platform "$PLATFORM"

    # 运行测试
    if [ "$RUN_TEST" = true ]; then
        run_test
    fi

    echo ""
    echo "========================================="
    echo_success "安装完成！"
    echo "========================================="
    echo ""
    echo "下一步:"
    echo "  1. 运行 'source ~/.bashrc' (或 ~/.zshrc) 加载环境变量"
    echo "  2. 测试: python3 \"$SCRIPT_DIR/tools/task_flow.py\" create --title '测试' --ceo-input '测试'"
    echo "  3. 查看文档: cat \"$SCRIPT_DIR/README.md\""
    echo ""
}

# 运行主函数
main "$@"
