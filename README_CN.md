# AI 驱动的全链路代码审查与安全审计系统

基于多 Agent 协作和长链推理的智能代码审查系统，从**安全、性能、规范、逻辑**四个维度对代码进行全方位审查。

## 架构

```
输入 (文件/目录/差异)
       │
       ▼
┌──────────────┐
│  编排 Agent   │  分析代码结构，制定审查计划
└──────┬───────┘
       │
  ┌────┼────┬────┐
  ▼    ▼    ▼    ▼
┌────┐┌────┐┌────┐┌────┐
│ 🔒  ││ ⚡  ││ 📏  ││ 🧠  │  4 个专业 Agent
│安全││性能││规范││逻辑│  并行执行
└──┬─┘└──┬─┘└──┬─┘└──┬─┘
   │     │     │     │
   └────┼────┼────┘
        ▼
┌──────────────┐
│  汇总 Agent   │  去重、冲突消解、风险评分
└──────┬───────┘
       ▼
  📄 审查报告 (Markdown + HTML)
```

### Agent 职责

| Agent | 审查重点 | 分析方法 |
|-------|---------|---------|
| **编排 Agent** | 任务分解 | 分析代码结构，分配审查文件，检测跨文件依赖 |
| **安全 Agent** | OWASP 漏洞 | 6步思维链：输入识别→数据流追踪→Sink识别→漏洞分类→严重性评估→修复方案 |
| **性能 Agent** | 效率与资源 | 算法复杂度、N+1查询、内存泄漏、I/O效率 |
| **规范 Agent** | 代码质量 | SOLID原则、命名、错误处理、文档、最佳实践 |
| **逻辑 Agent** | Bug 与边界 | 6步思维链：入口分析→路径枚举→边界条件→状态一致性→并发→业务逻辑 |
| **汇总 Agent** | 结果整合 | 三层去重、冲突消解、加权风险评分 |

### 长链推理（核心亮点）

安全和逻辑 Agent 采用 6 步思维链（Chain-of-Thought）方法：

**安全 Agent 推理链**：
1. 输入源识别 → 2. 数据流追踪（跨文件） → 3. 危险汇点识别 → 4. 漏洞分类（OWASP/CWE） → 5. 严重性评级 → 6. 修复方案生成

**逻辑 Agent 推理链**：
1. 入口点分析 → 2. 执行路径枚举 → 3. 边界条件验证 → 4. 状态一致性 → 5. 并发分析 → 6. 业务逻辑校验

## 安装

```bash
# 进入项目目录
cd code-review

# 安装项目
pip install -e .

# 配置 API Key
cp .env.example .env
# 编辑 .env 填入你的 Anthropic API Key
```

## 使用

### 审查单个文件
```bash
code-review file app.py --verbose
```

### 审查整个目录
```bash
code-review dir ./src --max-files 20 --format both
```

### 审查 Git 差异
```bash
git diff main > changes.diff
code-review diff changes.diff
```

### 命令选项
```
--output-dir, -o     报告输出目录（默认: ./output）
--format, -f         报告格式：md, html, both（默认: both）
--max-files, -m      最大审查文件数（dir 命令）
--verbose, -v        显示 Agent 详细执行过程
```

## 报告输出

审查报告包括：
- `review-<id>.md` — Markdown 格式，包含所有发现
- `review-<id>.html` — 交互式 HTML 报告，支持按严重性/类别筛选，代码语法高亮，风险徽章

## 风险评分

加权公式：`(严重×10 + 高危×5 + 中危×2 + 低危×0.5) / 文件数 × 平均置信度`

| 评分区间 | 风险等级 |
|---------|---------|
| 0–25  | 低风险 |
| 26–50 | 中等风险 |
| 51–75 | 高风险 |
| 76–100 | 严重风险 |

## 配置

所有配置通过 `.env` 文件设置：

| 变量 | 默认值 | 说明 |
|----------|---------|-------------|
| `ANTHROPIC_API_KEY` | — | Anthropic API 密钥（必填） |
| `ANTHROPIC_MODEL` | `claude-sonnet-4-6` | 使用的 Claude 模型 |
| `ANTHROPIC_MAX_TOKENS` | `4096` | 最大响应 token 数 |
| `ANTHROPIC_THINKING_BUDGET` | `2048` | 扩展思考 token 预算 |
| `MAX_FILES_PER_REVIEW` | `50` | 单次目录审查最大文件数 |
| `AGENT_TIMEOUT_SECONDS` | `120` | 单个 Agent 调用超时时间 |
| `OUTPUT_DIR` | `./output` | 默认报告输出目录 |
| `DEFAULT_FORMAT` | `both` | 默认报告格式 |

## 测试固件

`tests/fixtures/` 目录包含用于测试的漏洞代码：

- `vulnerable_flask.py` — Python Flask 应用，包含 15+ 个故意设置的漏洞（SQL注入、XSS、命令注入、路径穿越、反序列化、IDOR、竞态条件等）
- `vulnerable_express.js` — Node.js Express 应用，包含 12+ 个漏洞（NoSQL注入、SSRF、原型污染、eval注入、内存泄漏等）
- `sample.diff` — Git diff 格式的变更样本

## 运行测试

```bash
pip install -e ".[dev]"
pytest tests/ -v
```

## 项目结构

```
src/code_review/
├── main.py              # CLI 入口 & 流水线编排
├── config.py             # Pydantic 配置管理
├── models/               # 数据模型
│   ├── findings.py       # Finding, Severity, Category
│   ├── context.py        # ReviewContext, FileInfo, Diff
│   └── report.py         # ReviewReport, Summary
├── parser/
│   └── diff_parser.py    # Git diff & 目录解析
├── agents/
│   ├── base.py           # Agent 基类（API调用、重试、JSON修复、思维链）
│   ├── orchestrator.py   # 编排 Agent
│   ├── security.py       # 安全审计 Agent（6步CoT）
│   ├── performance.py    # 性能分析 Agent
│   ├── standards.py      # 代码规范 Agent
│   ├── logic.py          # 逻辑分析 Agent（6步CoT）
│   └── aggregator.py     # 汇总 Agent（去重 + 风险评分）
├── prompts/              # 专业提示词模板
├── reporters/
│   ├── markdown.py       # Markdown 报告生成器
│   └── html.py           # HTML 报告生成器（Jinja2 + Pygments）
└── templates/
    └── report.html.jinja2  # 交互式 HTML 模板
```

## 项目价值

本项目展示的核心能力：

1. **多 Agent 协作**：编排 → 4 专业并行 → 汇总的完整流水线，每个 Agent 有独立职责和专业领域知识
2. **长链推理**：安全 Agent 追踪数据从输入源到危险汇点的完整路径，逻辑 Agent 追踪执行路径并验证边界条件
3. **并行处理**：4 个专业 Agent 通过 `asyncio.gather` 并发执行，显著缩短审查时间
4. **智能去重**：三层去重策略（精确匹配 → 邻近匹配 → 跨 Agent 关联）
5. **量化评估**：基于 OWASP/CWE 标准的加权风险评分体系

## 许可

MIT
