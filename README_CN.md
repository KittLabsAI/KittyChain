[English](README.md) | 中文

# KittyChain - 面向链上分析的终端代理

KittyChain 是一个轻量级终端 AI 代理，重点服务于链上分析与调查类工作流。它把交互式 CLI、链上分析工具、本地文件操作、网页检索以及 skill 驱动的任务辅助整合到同一个终端环境里，方便你从一个问题快速进入实际的链上分析过程。

![KittyChain 首页截图](docs/assets/kittychain-home.png)

## 快速开始

1. 安装 KittyChain：

```bash
pip install kittychain
```

2. 通过引导式配置完成初始化：

```bash
kittychain --config
```

3. 启动交互式终端界面：

```bash
kittychain
```

## 功能特点与链上分析能力

- 轻量级终端 agent loop，同时支持交互式 REPL 和单次命令模式。
- 支持 OpenAI 兼容接口与 Anthropic 兼容接口。
- 内置 Shell 执行、文件读取与编辑、网页搜索、网页抓取、TODO 跟踪和 skill 加载等本地工具。
- 支持通过斜杠命令切换模型、保存会话、压缩上下文和查看已加载 skills。
- 支持会话持久化与任务中断，适合持续性的分析流程。

KittyChain 同时内置了常见链上分析能力，可直接用于日常调查任务：

- 地址余额查询
- 地址身份与标签查询
- 地址转账记录分析
- 恶意地址风险筛查
- 代币基础信息查询
- 代币安全检测

这使得 KittyChain 很适合用于钱包初筛、代币尽调、可疑地址检查，以及一般性的区块链研究工作。

## 使用方法

启动交互式终端界面：

```bash
kittychain
```

单次执行一个提示词并退出：

```bash
kittychain -p "检查这个钱包，并总结风险信号"
```

恢复历史会话：

```bash
kittychain -r session_1234567890
```

打开配置向导：

```bash
kittychain --config
```

也可以通过模块方式启动：

```bash
python -m kittychain
```

当 CLI 正在执行时，可以按 `Esc` 在下一处安全检查点中断当前任务。

## 交互命令

在 REPL 中，KittyChain 支持以下命令：

- `/help`
- `/reset`
- `/skills`
- `/<skill name>`
- `/model <name>`
- `/tokens`
- `/compact`
- `/save`
- `/sessions`
- `/quit`

`/skills` 命令会展示启动时已加载的 skills。输入斜杠命令时也支持前缀匹配，便于在终端里快速发现可用命令和 skills。
