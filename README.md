# Course Study Plugin

面向中国大学生的通用课程学习 Plugin。它把 Codex 的文件处理和内容生成能力组织成一套可复用的课程工作流，并提供完全离线的本地 RAG 检索工具。

- 当前基础版本：`0.2.1`
- Skill 调用名：`$course-study-agent`
- 支持环境：Codex App、Codex CLI，以及经过适配的其他 Agent 平台
- 主要语言：中文讲解，保留必要的 English terminology、公式、代码和引用

## 1. 主要功能

### 课程材料处理

- 处理 PPT/PPTX、PDF、Word/DOCX、Markdown 和 TXT；
- 根据材料所在位置识别课件、教程、作业、学习笔记或历年试卷；
- 重组内容为适合学习的结构，而不是逐页翻译；
- 对模糊扫描、手写内容、公式、图表和来源冲突明确标记不确定性；
- 默认把原始材料视为只读文件。

### 学习笔记

- 按周次或章节生成中文学习笔记；
- 保留重要英文术语、符号、公式和代码；
- 提炼学习目标、核心概念、应用、常见误区和总结；
- 优先复用已有笔记，避免不必要地重复读取全部原始材料。

### 作业支持

- 分析任务要求、交付物、限制条件和评分信号；
- 连接相关课程知识并制定完成计划；
- 提供概念解释、伪代码、调试和草稿支持；
- 不虚构实验结果、数据、引用、个人反思或完成状态。

### 复习与模拟考试

- 制作阶段总结、期中复习和期末复习资料；
- 合并重复概念并整理跨章节关系；
- 根据历年试卷的题型和难度生成新的模拟题；
- 不把模拟题描述为真实考试预测。

### 新材料和状态管理

- 发现新上传或被替换的课程文件；
- 使用大小、修改时间和 SHA-256 指纹识别更新；
- 检查周次、章节和主题，减少重复笔记；
- 根据项目规则维护 `new`、`updated`、`processed`、`ignored` 等状态。

### 离线 RAG v0.2.1

- 使用 SQLite FTS5/BM25，不调用云端 Embedding API；
- 对课程、标题和正文设置不同检索权重；
- 支持英文单词和中文二字词、三字词检索；
- 使用真实 BM25 强度、短语匹配和查询词覆盖率排序；
- 支持项目停用词和中英文同义词；
- 支持课程、资料类型和周次过滤；
- 支持增量索引、过期检测、近重复去除、来源多样性和相邻段落补充；
- 提供 Top-k、Top-1、Hit@3、MRR 和 nDCG 检索评测。

## 2. Plugin 与项目规则的关系

Plugin 只提供通用能力和保守默认值。每个课程项目的 `AGENTS.md` 决定该项目的专属规则，例如：

- 课程和文件夹结构；
- 文件命名方式和输出位置；
- 笔记章节与讲解详细程度；
- 练习题类型、数量和语言；
- 作业支持边界；
- RAG 索引范围；
- manifest、index 和 log 的格式；
- 是否允许跨课程工作；
- 隐私、人工复核和安全更新顺序。

规则优先级：

1. 用户当前任务的明确要求；
2. 当前项目的 `AGENTS.md`；
3. Plugin 的通用默认值。

因此，同一个 Plugin 可以用于计算机、商科、理工科、医学、人文和社会科学，但不同项目可以产生不同的文件结构和输出格式。

## 3. 安装

### 已配置 Personal Marketplace

如果本机的 Personal Marketplace 已经包含 `course-study-plugin`，运行：

```bash
codex plugin add course-study-plugin@personal
codex plugin list
```

`codex plugin list` 中应显示 Plugin 为 `installed, enabled`。

### 分享到另一台 Codex 设备

把完整的 `course-study-plugin` 文件夹放入对方的本地 Marketplace：

```text
<marketplace-root>/
├── .agents/plugins/marketplace.json
└── plugins/
    └── course-study-plugin/
```

`marketplace.json` 至少包含：

```json
{
  "name": "course-study-local",
  "interface": {
    "displayName": "Course Study Local"
  },
  "plugins": [
    {
      "name": "course-study-plugin",
      "source": {
        "source": "local",
        "path": "./plugins/course-study-plugin"
      },
      "policy": {
        "installation": "AVAILABLE",
        "authentication": "ON_INSTALL"
      },
      "category": "Productivity"
    }
  ]
}
```

如果使用的是自建、非默认 Marketplace，先添加 Marketplace 根目录，再安装其中的 Plugin：

```bash
codex plugin marketplace add <marketplace-root>
codex plugin add course-study-plugin@course-study-local
```

安装或更新后，新建一个 Codex 任务，使新的 Skill 内容被完整加载。

## 4. 在 Codex App 中使用

打开课程项目，新建任务并输入：

```text
$course-study-agent 处理这门课新上传的课件并生成中文学习笔记。
```

其他示例：

```text
$course-study-agent 检查 ECON101 是否有尚未处理的新课件。

$course-study-agent 分析 Assignment 2 的要求并制定完成计划，不直接替我完成作业。

$course-study-agent 根据 Week 01 到 Week 06 的笔记制作期中复习资料。

$course-study-agent 参考历年试卷的题型，生成一份新模拟试卷，并把答案与题目分开。

$course-study-agent 使用本地 RAG 查找 congestion control 相关笔记并注明来源。
```

## 5. 在 Codex CLI 中使用

交互式使用：

```bash
cd <course-project>
codex
```

然后输入：

```text
$course-study-agent 检查当前项目有哪些尚未处理的课程材料。
```

直接带任务启动：

```bash
codex -C <course-project> \
  '$course-study-agent 根据已有笔记制作本周复习提纲。'
```

非交互执行：

```bash
codex exec -C <course-project> \
  '$course-study-agent 使用本地 RAG 查找与数据库事务有关的课程笔记。'
```

在 shell 中使用单引号包住提示词，避免 `$course-study-agent` 被当成环境变量展开。

## 6. 本地 RAG 快速开始

下面的 `<skill-dir>` 指：

```text
<plugin-root>/skills/course-study-agent
```

建立或增量更新索引：

```bash
python3 <skill-dir>/scripts/rag/index_vault.py --vault <course-project>
```

检查索引状态：

```bash
python3 <skill-dir>/scripts/rag/index_vault.py --vault <course-project> --status
```

搜索笔记：

```bash
python3 <skill-dir>/scripts/rag/query_vault.py \
  --vault <course-project> \
  "问题或关键词" \
  --course <course-code>
```

为复习任务准备上下文：

```bash
python3 <skill-dir>/scripts/rag/retrieve_context.py \
  --vault <course-project> \
  --task final-review \
  --course <course-code> \
  --scope "考试范围"
```

索引默认保存到：

```text
<course-project>/.course-study/rag_index.sqlite
```

它是可以重新生成的本地缓存，不建议分享或提交到 Git。

## 7. RAG 配置

生成项目配置：

```bash
python3 <skill-dir>/scripts/rag/init_config.py --vault <course-project>
```

配置保存在项目根目录的 `course-study.json`。示例：

```json
{
  "rag": {
    "include_dirs": [],
    "exclude_globs": [],
    "include_extracted": false,
    "minimum_should_match": 0.18,
    "dedupe_threshold": 0.92,
    "stopwords": [],
    "synonyms": {
      "人工智能": ["artificial intelligence", "AI"]
    }
  }
}
```

修改配置后，旧索引会被标记为过期；再次运行索引命令即可重建。

## 8. 离线抽取原始材料文字

结构化 Markdown 笔记是首选检索来源。需要临时检索原始材料时，可以在本地抽取文字：

```bash
python3 <skill-dir>/scripts/rag/extract_source.py \
  <project-relative-source> \
  --vault <course-project>
```

支持：

- PPTX：内置 ZIP/XML 解析；
- DOCX：内置 ZIP/XML 解析；
- PDF：使用电脑中已有的 `pdftotext` 或 `pypdf`；
- Markdown/TXT：直接读取。

抽取结果保存在 `.course-study/extracted/`。需要在 `course-study.json` 中启用 `rag.include_extracted` 后重新建立索引。

老式 `.ppt`、扫描件、手写内容、图片、复杂图表和公式需要额外的本地转换、OCR 或视觉检查。抽取文字不能替代对原文件布局的核对。

## 9. 检索质量评测

准备 JSONL 文件，每行包含一个问题和预期来源：

```json
{"query":"需求曲线为什么向下倾斜","expected_sources":["Week 01 Supply and Demand.md"]}
```

运行：

```bash
python3 <skill-dir>/scripts/rag/evaluate_rag.py \
  evaluation.jsonl \
  --vault <course-project> \
  --top-k 5
```

输出包括 Top-k 命中率、Top-1 accuracy、Hit@3、MRR、nDCG@k 和实际返回来源。

## 10. 离线与联网边界

可以完全离线完成：

- RAG 建索引、搜索和状态检查；
- 增量更新和文件哈希；
- PPTX、DOCX、Markdown 和 TXT 文字抽取；
- 使用已经安装的本地工具抽取 PDF；
- 检索质量评测。

通常需要模型的任务：

- 生成中文讲解和学习笔记；
- 分析作业内容；
- 制作复习资料和模拟题；
- 根据检索结果组织自然语言回答。

Plugin 不会自行调用额外的大模型 API。模型由当前 Codex 或其他 Agent 提供。Codex 使用在线模型时需要联网；配置本地模型时可以使用本地推理能力。

## 11. 目录结构

```text
course-study-plugin/
├── .codex-plugin/
│   └── plugin.json
├── README.md
├── USAGE_GUIDE.md
├── skills/
│   └── course-study-agent/
│       ├── SKILL.md
│       ├── agents/
│       ├── assets/
│       ├── references/
│       └── scripts/rag/
└── tests/
```

## 12. 重要限制

- Plugin 不是一个独立的大语言模型；
- RAG 默认检索 Markdown，原始课件文字需要先抽取或生成笔记；
- 图片、扫描件、复杂公式和图表可能无法仅靠文字抽取理解；
- AI 生成的课程笔记和作业草稿应由学生复核；
- 历年试卷只用于学习题型和难度，不代表真实考试预测；
- 分享 Plugin 时不要附带课程材料、作业、个人笔记或 `.course-study` 索引。

## 13. 更多说明

- 专属规则清单与最小 `AGENTS.md` 模板：[USAGE_GUIDE.md](USAGE_GUIDE.md)
- Skill 工作流：[skills/course-study-agent/SKILL.md](skills/course-study-agent/SKILL.md)
- RAG 详细说明：[skills/course-study-agent/references/local-rag.md](skills/course-study-agent/references/local-rag.md)
- RAG 配置示例：[skills/course-study-agent/assets/course-study.example.json](skills/course-study-agent/assets/course-study.example.json)
