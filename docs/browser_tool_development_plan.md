# Web Browser Tool 开发计划

> 将现有 `web_browser` 工具升级为 `agent-browser` 的完整能力封装，保持工具名不变，并覆盖 `agent-browser` skill 中列出的全部命令能力。

## 1. 背景与目标

### 1.1 当前问题

当前 [web_browser.py](/Users/kc/Desktop/个人资料/个人项目/KittyChain/kittychain/tools/web_browser.py) 只封装了一个很小的固定流程：

```text
open -> wait --load -> get page text -> summarize -> close
```

它本质上是“带浏览器渲染的网页抓取工具”，还不是一个浏览器自动化工具。

### 1.2 目标

将 `web_browser` 升级为统一浏览器工具，使 AI agent 可以直接完成 `agent-browser` skill 中的完整浏览器能力，包括：

- 导航和关闭浏览器
- snapshot 与 `@ref` 引用定位
- 点击、输入、滚动、拖拽、上传等交互
- 获取页面和元素信息
- 等待页面、元素、文本、URL、下载完成
- 下载、网络检查、HAR、路由
- viewport 与 device emulation
- screenshot 和 PDF
- stream、clipboard、dialog
- state、auth、connect
- diff 和 batch

### 1.3 非目标

这次升级不保留旧 `web_browser` 的旧职责语义，不再将它限定为“公共网页抓取 + 总结”工具。

这次升级也不让 `intent` 参与底层浏览器动作选择。`intent` 只在“已经拿到关键网页内容之后”用于 LLM 总结，使用方式应与当前 `_summarize_with_llm()` 一致。

这次升级同时要求将 `web_browser` 从单文件实现迁移到 `tools` 下的独立目录中，但工具导出名仍保持 `web_browser`。

---

## 2. 核心设计原则

| 原则 | 说明 |
| --- | --- |
| 工具名不变 | 保持工具名为 `web_browser`，避免新增平行工具 |
| 能力全覆盖 | 以 `agent-browser` skill 为基准做能力映射，不做“部分支持” |
| 动作确定性 | 底层 action 只负责执行浏览器命令，不混入隐式 AI 推理 |
| 统一入口 | 一个 `web_browser` 工具，通过 `action` 参数区分子能力 |
| 结构化响应 | 所有 action 返回统一 JSON 字符串，便于 agent 继续消费 |
| 意图后处理 | `intent` 仅在已取得关键内容后触发 LLM 总结 |
| 最小惊讶 | CLI 行为尽量与 `agent-browser` 原生命令保持一致 |

---

## 3. 总体架构

### 3.1 工具形态

保留单一工具：

```python
class WebBrowserTool(Tool):
    name = "web_browser"
```

工具内部升级为统一 dispatcher，而不是新增 `browser` 工具。

### 3.2 建议文件结构

`web_browser` 必须迁移到目录实现，而不是继续保留为单文件。目录结构保持克制，只拆到足以支撑完整能力覆盖。

```text
kittychain/tools/web_browser/
  __init__.py
  tool.py
  core.py
  parsing.py
  summarize.py
tests/test_web_browser.py
```

说明：

- `__init__.py`：导出 `WebBrowserTool`
- `tool.py`：Tool 定义、参数 schema、action 分发
- `core.py`：命令构建、subprocess、错误映射、会话辅助
- `parsing.py`：snapshot / network / diff 等输出解析
- `summarize.py`：`intent` 触发的 LLM 总结逻辑
- `tests/test_web_browser.py`：按 capability matrix 写测试

不要在第一版就继续细拆成 `_actions/` 十几个文件。先用上面这 4 个文件承接能力，只有在目录内部再次明显膨胀时才做第二轮拆分。

### 3.3 响应格式

所有 action 都返回 JSON 字符串：

```json
{
  "success": true,
  "action": "snapshot",
  "session": "default",
  "data": {
    "url": "https://example.com",
    "title": "Example",
    "elements": [
      {
        "ref": "@e1",
        "text": "Submit",
        "role": "button"
      }
    ]
  }
}
```

错误统一为：

```json
{
  "success": false,
  "action": "click",
  "error": "element_not_found",
  "reason": "Page changed and the ref is no longer valid.",
  "suggestion": "Re-run snapshot to get fresh refs."
}
```

### 3.4 `intent` 规则

`intent` 只允许出现在“已有关键内容”的 action 中作为可选后处理参数，例如：

- `snapshot`
- `get`
- `network_requests`
- `network_request`
- `diff_snapshot`
- `diff_screenshot`
- `diff_url`

执行规则：

1. 先执行原始 `agent-browser` 命令
2. 先返回结构化原始数据
3. 如果提供了 `intent`，并且当前 action 的结果中包含适合总结的关键内容，再调用 `_summarize_with_llm()`
4. 总结结果写入额外字段，如 `summary`

`intent` 不参与：

- 元素筛选
- 命令选择
- 自动点击
- 自动等待
- 自动格式归一化

这些动作仍由 agent 明确调用对应 action 完成。

---

## 4. Capability Matrix

以下矩阵以 `agent-browser` skill 为准。`web_browser` 必须全部覆盖。

| Skill 能力 | `web_browser.action` | 说明 |
| --- | --- | --- |
| `open <url>` | `open` | 打开页面 |
| `close` | `close` | 关闭当前浏览器 / session |
| `snapshot -i` | `snapshot` | 获取可交互元素树和 refs |
| `snapshot -s` | `snapshot` | 支持 `scope` |
| `click @e1` | `click` | 点击 |
| `click @e1 --new-tab` | `click` | 支持 `new_tab` |
| `dblclick @e1` | `dblclick` | 双击 |
| `fill @e1 "text"` | `fill` | 清空后输入 |
| `type @e1 "text"` | `type` | 追加输入 |
| `press Enter` | `press` | 按键 |
| `keyboard type "text"` | `keyboard_type` | 对当前焦点输入 |
| `keyboard inserttext "text"` | `keyboard_inserttext` | 插入文本 |
| `hover @e1` | `hover` | 悬停 |
| `check @e1` | `check` | 勾选 |
| `uncheck @e1` | `uncheck` | 取消勾选 |
| `select @e1 "option"` | `select` | 选择选项 |
| `scroll down 500` | `scroll` | 页面滚动 |
| `scroll ... --selector` | `scroll` | 容器滚动 |
| `scrollinto @e1` | `scrollinto` | 滚到元素可见 |
| `drag @e1 @e2` | `drag` | 拖拽 |
| `upload @e1 file.pdf` | `upload` | 上传文件 |
| `get text @e1` | `get` | 获取文本 |
| `get url` | `get` | 获取当前 URL |
| `get title` | `get` | 获取标题 |
| `get cdp-url` | `get` | 获取 CDP URL |
| `wait @e1` | `wait` | 等待元素 |
| `wait --load networkidle` | `wait` | 等待 load |
| `wait --url "**/page"` | `wait` | 等待 URL |
| `wait 2000` | `wait` | 等待毫秒 |
| `wait --text "Welcome"` | `wait` | 等待文本 |
| `wait --fn "..."` | `wait` | 等待 JS 条件 |
| `wait "#spinner" --state hidden` | `wait` | 等待 selector 状态 |
| `download @e1 ./file.pdf` | `download` | 下载 |
| `wait --download ./output.zip` | `wait_download` | 等待下载完成 |
| `--download-path ./downloads open ...` | `open` | 支持下载目录 |
| `network requests` | `network_requests` | 网络请求列表 |
| `network request <id>` | `network_request` | 单请求详情 |
| `network route "**/api/*" --abort` | `network_route` | 路由和拦截 |
| `network har start` | `network_har_start` | HAR 开始 |
| `network har stop ./capture.har` | `network_har_stop` | HAR 结束 |
| `set viewport 1920 1080` | `set_viewport` | 视口大小 |
| `set device "iPhone 14"` | `set_device` | 设备模拟 |
| `screenshot` | `screenshot` | 截图 |
| `screenshot --full` | `screenshot` | 全页截图 |
| `screenshot --annotate` | `screenshot` | 标注截图 |
| `pdf output.pdf` | `pdf` | 导出 PDF |
| `stream enable` | `stream_enable` | 启用流 |
| `stream status` | `stream_status` | 查询流状态 |
| `stream disable` | `stream_disable` | 关闭流 |
| `clipboard read` | `clipboard_read` | 读剪贴板 |
| `clipboard write "..."` | `clipboard_write` | 写剪贴板 |
| `clipboard copy` | `clipboard_copy` | 复制 |
| `clipboard paste` | `clipboard_paste` | 粘贴 |
| `dialog accept` | `dialog_accept` | 接受对话框 |
| `dialog accept "input"` | `dialog_accept` | prompt 输入 |
| `dialog dismiss` | `dialog_dismiss` | 取消对话框 |
| `dialog status` | `dialog_status` | 查看对话框状态 |
| `state save ./auth.json` | `state_save` | 保存状态 |
| `state load ./auth.json` | `state_load` | 加载状态 |
| `auth save ...` | `auth_save` | 保存凭据 |
| `auth login ...` | `auth_login` | 自动登录 |
| `auth list` | `auth_list` | 列出凭据 |
| `auth show` | `auth_show` | 展示凭据元数据 |
| `auth delete` | `auth_delete` | 删除凭据 |
| `--auto-connect state save ...` | `auto_connect` | 自动连接现有浏览器 |
| `connect <host>:<port>` | `connect` | 连接调试端口 |
| `diff snapshot` | `diff_snapshot` | snapshot diff |
| `diff screenshot` | `diff_screenshot` | 截图 diff |
| `diff url <url1> <url2>` | `diff_url` | 页面 diff |
| `batch --json` | `batch` | 批处理命令 |

---

## 5. 参数设计

### 5.1 顶层参数

```python
parameters = {
    "type": "object",
    "properties": {
        "action": {"type": "string"},
        "session": {"type": "string"},
        "timeout": {"type": "integer"},
        "intent": {"type": "string"},
        "proxy": {"type": "string"},
        "proxy_bypass": {"type": "string"},
        "download_path": {"type": "string"}
    },
    "required": ["action"]
}
```

### 5.2 通用动作参数

在顶层参数之外，按动作支持以下字段：

- `url`
- `ref`
- `ref_target`
- `value`
- `path`
- `full`
- `annotate`
- `scope`
- `selector`
- `depth`
- `compact`
- `new_tab`
- `width`
- `height`
- `device_scale_factor`
- `device_name`
- `host`
- `port`
- `request_id`
- `route_pattern`
- `route_behavior`
- `state`
- `text`
- `url_pattern`
- `javascript`
- `milliseconds`
- `status_filter`
- `method`
- `resource_types`
- `baseline`
- `url_a`
- `url_b`
- `commands`
- `auth_name`
- `auth_url`
- `username`
- `password`
- `password_stdin`

说明：

- 参数不需要强行一把梭都塞进 `required`
- 每个 action 自己校验最小必填项
- 参数命名优先贴近 `agent-browser` 语义，而不是重新发明概念

---

## 6. 实现设计

### 6.1 `web_browser/tool.py`

职责：

- 定义 `WebBrowserTool`
- 定义参数 schema
- 做 action dispatch
- 为每个 action 调用 core 层
- 在适用场景下触发 `_summarize_with_llm()`

伪代码：

```python
class WebBrowserTool(Tool):
    name = "web_browser"

    def execute(self, action: str, **kwargs) -> str:
        result = dispatch_action(action, kwargs)
        if should_summarize(action, kwargs, result):
            result["summary"] = summarize_result(
                agent=getattr(self, "_parent_agent", None),
                action=action,
                intent=kwargs.get("intent", ""),
                data=result.get("data"),
            )
        return json.dumps(result, ensure_ascii=False)
```

### 6.2 `web_browser/core.py`

职责：

- 构建 `agent-browser` 命令
- 执行 `subprocess.run`
- 统一处理 `FileNotFoundError`
- 统一处理 timeout
- 统一处理 stderr/stdout 错误
- 解析 JSON 或文本输出

建议核心函数：

```python
def run_agent_browser(
    session: str | None,
    timeout: int,
    *args: str,
    proxy: str | None = None,
    proxy_bypass: str | None = None,
) -> str:
    ...


def format_success(action: str, session: str | None, data: dict | list | str | None = None, **extra) -> dict:
    ...


def format_error(action: str, error: str, reason: str, suggestion: str | None = None, **extra) -> dict:
    ...
```

### 6.3 `web_browser/parsing.py`

职责：

- 解析 `snapshot` 的 `@ref` 输出
- 解析 `network requests` / `network request`
- 解析 `diff_*`
- 解析 `stream status`
- 将 CLI 文本输出收敛成统一结构

建议核心函数：

```python
def parse_snapshot_output(output: str) -> list[dict]:
    ...


def parse_network_requests(output: str) -> list[dict]:
    ...


def parse_diff_output(output: str) -> dict:
    ...
```

### 6.4 `web_browser/summarize.py`

职责：

- 实现 `intent` 触发的总结逻辑
- 复用当前 `web_browser` 的 `_summarize_with_llm()` 思路
- 只处理已有关键内容，不负责驱动浏览器动作

建议核心函数：

```python
def summarize_result(agent, action: str, intent: str, data: object) -> str:
    ...
```

### 6.5 会话策略

保留与当前实现相近的 session 习惯：

- 未显式传入 `session` 时，创建临时 session
- 临时 session 在单次 action 结束后自动关闭，除非该 action 明确需要跨调用延续
- 显式传入 `session` 时，完全由调用方控制生命周期

关键点：

- 不做复杂的全局 session cache
- 不承诺自动复用匿名 session
- 避免写出与文档不一致的“隐式 temp session 池”

这更符合当前 repo 偏简单、显式的风格。

### 6.6 输出解析

解析策略分两类：

1. 直接透传型
- `get url`
- `get title`
- `clipboard_read`
- `dialog_status`

2. 结构化转换型
- `snapshot`
- `network_requests`
- `network_request`
- `diff_*`
- `stream_status`

`snapshot` 需要专门解析 `@ref` 输出，提取：

- `ref`
- `role` / `tag`
- `text`
- `name`
- `value`
- 可见状态
- 其它必要属性

只保留 agent 真正会用到的字段，不返回完整 DOM。

---

## 7. Action 设计

### 7.1 导航与关闭

动作：

- `open`
- `close`

行为：

- `open` 对应 `agent-browser open <url>`
- 可附带 `download_path`
- 可在成功后补一个可选 `wait --load networkidle`

返回：

- 当前 URL
- 最终 URL
- 页面标题
- 是否重定向

### 7.2 snapshot

动作：

- `snapshot`

行为：

- 对应 `agent-browser snapshot -i`
- 支持 `scope`
- 支持 `compact`
- 支持 `depth`

返回：

- `url`
- `title`
- `elements`

如果有 `intent`：

- 不改变 snapshot 结果
- 只基于 `elements` 和页面上下文生成 `summary`

### 7.3 交互动作

动作：

- `click`
- `dblclick`
- `fill`
- `type`
- `press`
- `keyboard_type`
- `keyboard_inserttext`
- `hover`
- `check`
- `uncheck`
- `select`
- `scroll`
- `scrollinto`
- `drag`
- `upload`

返回：

- 执行的动作
- 目标 ref 或 selector
- 是否可能引起页面变化
- 建议是否需要重新 `snapshot`

### 7.4 获取动作

动作：

- `get`

支持至少：

- `text`
- `html`
- `value`
- `attr`
- `title`
- `url`
- `count`
- `box`
- `styles`
- `cdp-url`

如果有 `intent`：

- 原始值仍保留在 `data.value`
- 额外生成 `summary`
- 不强制把原始值改造成“解析后数值”

### 7.5 检查与等待

动作：

- `is_visible`
- `is_enabled`
- `is_checked`
- `wait`
- `wait_download`

`wait` 支持：

- 元素等待
- `--load`
- `--url`
- `--text`
- `--fn`
- selector + state
- 毫秒等待

### 7.6 下载与网络

动作：

- `download`
- `network_requests`
- `network_request`
- `network_route`
- `network_har_start`
- `network_har_stop`

关键点：

- `network_requests` 支持 method/type/status 过滤
- `network_request` 返回完整请求详情
- `network_route` 支持 block/abort/fulfill 等可行模式，具体以 CLI 实际能力为准
- `network_har_stop` 要返回保存路径

### 7.7 视口与设备

动作：

- `set_viewport`
- `set_device`

返回：

- 当前配置
- 是否成功应用

### 7.8 页面产物

动作：

- `screenshot`
- `pdf`

支持：

- 全页截图
- 标注截图
- 截图格式
- 截图质量

### 7.9 stream / clipboard / dialog

动作：

- `stream_enable`
- `stream_status`
- `stream_disable`
- `clipboard_read`
- `clipboard_write`
- `clipboard_copy`
- `clipboard_paste`
- `dialog_accept`
- `dialog_dismiss`
- `dialog_status`

### 7.10 state / auth / connect

动作：

- `state_save`
- `state_load`
- `auth_save`
- `auth_login`
- `auth_list`
- `auth_show`
- `auth_delete`
- `connect`
- `auto_connect`

安全要求：

- 所有状态文件相关响应要附带安全提醒
- `auth_save` 需要避免把密码写进日志或错误输出

### 7.11 diff / batch

动作：

- `diff_snapshot`
- `diff_screenshot`
- `diff_url`
- `batch`

`batch` 规则：

- 接收结构化命令数组
- 顺序执行
- 返回每步结果
- 支持 `bail` 模式

---

## 8. 错误处理

统一错误码建议：

| 错误码 | 含义 |
| --- | --- |
| `install_required` | `agent-browser` 未安装 |
| `timeout` | 命令超时 |
| `invalid_action` | 不支持的 action |
| `invalid_arguments` | 参数缺失或冲突 |
| `invalid_ref` | `@ref` 格式错误 |
| `element_not_found` | 元素不存在 |
| `page_changed` | 页面变化导致 ref 失效 |
| `session_error` | session 或状态问题 |
| `command_failed` | CLI 执行失败 |
| `parse_error` | 输出解析失败 |

每个错误都尽量提供 `reason` 和 `suggestion`。

---

## 9. 实现优先级

### Phase 1：执行内核 + 高频核心能力

- `open`
- `close`
- `snapshot`
- `click`
- `fill`
- `type`
- `press`
- `get`
- `is_visible`
- `is_enabled`
- `is_checked`
- `wait`
- `wait_download`
- `screenshot`
- `pdf`

### Phase 2：完整交互与网页操作能力

- `dblclick`
- `keyboard_type`
- `keyboard_inserttext`
- `hover`
- `check`
- `uncheck`
- `select`
- `scroll`
- `scrollinto`
- `drag`
- `upload`
- `download`
- `set_viewport`
- `set_device`

### Phase 3：高级会话与观测能力

- `network_requests`
- `network_request`
- `network_route`
- `network_har_start`
- `network_har_stop`
- `stream_enable`
- `stream_status`
- `stream_disable`
- `clipboard_*`
- `dialog_*`
- `state_*`
- `auth_*`
- `connect`
- `auto_connect`
- `diff_*`
- `batch`

说明：

虽然最终目标是全覆盖，但可以按 phase 实现。每个 phase 结束时，文档都必须更新“已完成能力矩阵”。

---

## 10. 测试计划

### 10.1 单元测试

覆盖：

- action 到 CLI 参数映射
- 错误映射
- snapshot 输出解析
- `intent` summary 触发条件
- session 生命周期

### 10.2 集成测试

覆盖典型流程：

- `open -> snapshot -> click -> wait -> snapshot`
- 表单填写
- 截图和 PDF
- 下载和等待下载
- 网络请求检查
- 状态保存 / 加载
- dialog / clipboard / stream

### 10.3 兼容性测试

对照 `agent-browser` skill 中列出的命令样例，逐条验证：

- 参数是否能表达
- 输出是否可被 agent 消费
- 出错时是否有可恢复提示

---

## 11. 关键设计决策

| 决策 | 选择 | 理由 |
| --- | --- | --- |
| 工具名 | 保留 `web_browser` | 与你的目标一致，避免新增平行工具 |
| 能力范围 | 覆盖 skill 全部命令 | 避免“半自动化工具”继续存在 |
| 工具入口 | 单一 `action` 参数 | 简化 prompt 和工具选择 |
| `intent` 作用域 | 仅内容后处理 | 保持动作确定性，避免隐式智能逻辑 |
| 架构拆分 | 先少拆文件 | 防止过度设计 |
| 匿名 session | 显式短生命周期 | 行为简单、易理解、易测试 |

---

## 12. 交付标准

以下条件全部满足，才算这次升级完成：

1. `web_browser` 名字保持不变
2. `agent-browser` skill 中列出的能力全部有对应 action
3. 所有 action 都有结构化 JSON 响应
4. `intent` 只在内容获取后触发 `_summarize_with_llm()` 风格的总结
5. 实现位于 `kittychain/tools/web_browser/` 目录下，而不是单文件
6. 不再保留旧 `web_browser` 的旧职责约束
7. `python -m pytest -q` 全量通过

---

## 13. 参考

- `agent-browser` skill：`/Users/kc/.kittychain/skills/agent-browser/SKILL.md`
- 当前实现：[kittychain/tools/web_browser.py](/Users/kc/Desktop/个人资料/个人项目/KittyChain/kittychain/tools/web_browser.py)
