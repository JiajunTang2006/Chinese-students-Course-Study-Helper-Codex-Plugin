# Course Study Plugin 使用手册

## 1. 这个 Plugin 做什么

`course-study-plugin` 为大学课程项目提供通用学习能力：

- 处理 PPT/PPTX、PDF、Word/DOCX 和 Markdown 课程材料；
- 以中文讲解课程内容；
- 按章节或周次生成学习笔记；
- 分析作业要求、交付物和完成步骤；
- 生成期中、期末复习资料；
- 根据历年试卷的题型和难度生成新模拟题；
- 使用本地离线 RAG 检索 Markdown 课程笔记；
- 发现新材料、检测重复内容并管理处理状态；
- 适配计算机、商科、理工科、医学、文科等不同专业。

Plugin 提供“能力和通用默认值”，课程项目中的 `AGENTS.md` 提供“当前项目的专属规则”。

规则优先级：

1. 用户本次明确要求；
2. 当前项目的 `AGENTS.md`；
3. Plugin 的通用默认规则。

## 2. 在 Codex 中使用

安装 Plugin 后，新建一个 Codex 任务，在课程项目中调用：

```text
$course-study-agent 处理这门课新上传的课件并生成中文学习笔记。
```

常见调用示例：

```text
$course-study-agent 检查 ECON101 是否有尚未处理的新课件。

$course-study-agent 分析 Assignment 2 的要求并制定完成计划，不要直接替我完成作业。

$course-study-agent 根据 Week 01 到 Week 06 的笔记制作期中复习资料。

$course-study-agent 参考历年试卷的题型，生成一份新的模拟试卷并分开给出答案。
```

Plugin 可以在没有 `AGENTS.md` 的项目中工作，但只会使用保守的通用默认值。长期使用时，建议为每个课程项目建立自己的 `AGENTS.md`。

## 3. 项目专属规则应该包含什么

不需要把下面所有项目都写得很长，但至少应明确会改变输出结果或文件位置的规则。

### 3.1 项目和课程范围

- 项目的用途和学生阶段；
- 当前有哪些课程，如何识别课程代码和课程名称；
- 是否允许跨课程检索、比较或整合；
- 新增课程时需要创建什么结构。

### 3.2 文件夹和原始材料

- 原始课件、普通笔记、复习资料、作业和历年试卷分别放在哪里；
- 原始文件是否只读；
- PPT、PDF、DOCX、Markdown、图片、扫描件和压缩包的处理规则；
- 未知格式或多个候选材料出现时如何处理。

### 3.3 文件命名和输出位置

- 周笔记、章节笔记、作业指导、期中复习、期末复习和模拟题的命名格式；
- 每类结果写入哪个文件夹；
- 同一内容存在旧文件时更新还是新建；
- 哪些重要输出需要加入课程索引。

### 3.4 笔记语言和结构

- 中文、英文或双语；
- 是否保留 English terminology、公式、代码和引用；
- 每篇笔记必须包含哪些章节；
- 讲解详细程度、示例数量和是否需要常见误区；
- 是否保留学生自己的理解、待确认问题或教师重点。

### 3.5 作业支持边界

- 只提供要求分析、规划、概念讲解和调试，还是允许生成草稿；
- 草稿是否必须明确标注；
- 禁止虚构的数据、实验结果、引用、个人反思和完成状态；
- 学校或课程的 Academic Integrity 要求。

### 3.6 练习题和模拟考试

- 是否默认出题；
- 题型、数量、语言、难度和选项数量；
- 题目与答案是否分开；
- 解析使用什么语言；
- 历年试卷只用于题型参考，还是允许提取原题；
- 模拟题存放位置。

### 3.7 RAG 和读取范围

- 哪些 Markdown 文件允许进入本地索引；
- 是否排除原始材料、日志、作业答案或私人笔记；
- 普通问答、复习和模拟题分别优先读取哪些资料；
- 什么时候重新建立索引；
- 检索不足时是否允许读取原始 PPT/PDF。

### 3.8 新材料、重复文件和处理状态

- 如何登记新课件；
- 使用文件大小、修改时间或 SHA-256 指纹检测更新；
- 状态名称，例如 `new`、`updated`、`processed`、`ignored`；
- 什么时候才可以标记为已处理；
- 同周、同章节或同主题笔记的重复检测方法。

### 3.9 安全更新、索引和日志

- 文件创建、验证、索引、manifest 和日志的更新顺序；
- 哪些操作需要先询问用户；
- 是否允许自动删除、移动、提交或上传；
- 项目级日志和课程级日志分别记录什么；
- 如何保护用户已有修改。

### 3.10 隐私和人工复核

- 哪些课程材料、作业和个人笔记禁止外传；
- AI 生成内容是否统一视为草稿；
- 需要通过练习、教师反馈、实验或学生自己的解释完成验证；
- 来源不清、扫描模糊或内容冲突时如何标记。

## 4. 最小 `AGENTS.md` 模板

把下面内容复制到课程项目根目录，再按自己的需要修改：

```markdown
# Course Project Rules

## Project Scope

- 本项目用于：<专业、年级或课程范围>。
- 课程列表以：<课程索引或文件夹> 为准。
- 默认不跨课程读取或整合，除非用户明确要求。

## Folder Rules

- 原始材料：`<raw folder>`，只读，不修改。
- 学习笔记：`<notes folder>`。
- 作业指导：`<assignments folder>`。
- 复习和模拟题：`<review folder>`。

## Study Note Rules

- 讲解语言：中文。
- 保留必要的英文术语、公式、代码和来源。
- 周笔记命名：`<naming rule>`。
- 笔记至少包含：来源、学习目标、核心知识点、示例、常见误区和总结。
- 不能确定的内容放入“待确认问题”，不要猜测。

## Assignment Rules

- 默认提供要求分析、交付物清单、完成计划、概念讲解和调试帮助。
- 未经明确要求，不直接生成可提交的最终答案。
- 不虚构数据、实验结果、引用、个人反思或完成状态。

## Practice and Exam Rules

- 默认题型：<题型>。
- 默认数量：<数量>。
- 题目语言：<语言>；解析语言：<语言>。
- 题目和答案分开。
- 历年试卷只用于理解题型与难度，不声称预测真实考试。

## Retrieval Rules

- 本地 RAG 索引：<允许索引的文件夹>。
- 排除：<raw、logs、private notes 等>。
- 笔记更新后重新建立索引。
- 检索证据不足时，先说明不足，再决定是否读取原始材料。

## File Status and Duplicates

- 新材料状态：`new`、`updated`、`processed`、`ignored`。
- 只有目标笔记或输出存在并通过检查后，才能标记为 `processed`。
- 创建笔记前比较课程、周次/章节和主题，优先更新已有文件。

## Safe Update Order

1. 创建或更新实际笔记；
2. 验证文件存在且符合规则；
3. 更新课程索引；
4. 更新材料状态；
5. 最后更新日志；
6. 检查变更并保护无关用户修改。

## Privacy and Review

- 不把课程资料和个人笔记上传到未授权的外部服务。
- AI 生成内容一律视为待复核草稿。
- 模糊、冲突或无法识别的内容必须明确标记。
```

## 5. 不同专业如何调整

### 计算机和工程

- 保留代码、算法、公式、协议图和实验步骤；
- 练习题可包含编程、计算、设计和调试；
- 明确可运行代码和伪代码的区别。

### 商科和经济

- 保留模型假设、案例背景、指标和图表解释；
- 练习题可包含案例分析、计算和论述；
- 明确事实、案例证据和模型补充内容。

### 理科和医学

- 保留公式、单位、实验条件、图像和术语；
- 对扫描、图表和手写内容进行视觉检查；
- 医学内容应增加来源、时效性和非诊疗声明等项目规则。

### 人文和社会科学

- 保留作者、文本、论点、证据、引用和理论背景；
- 避免把模型解释写成原文观点；
- 作业规则应明确引用格式和原创分析要求。

## 6. 本地 RAG

RAG 程序位于 Skill 的 `scripts/rag/`。建索引和搜索均在本机完成，不调用额外的大模型，也不使用云端 Embedding。

`v0.2.1` 检索采用加权 SQLite FTS5/BM25，并增加中文二字词/三字词检索、课程/标题/正文分字段权重、真实 BM25 强度、精确短语和最低命中比例、项目停用词与中英文同义词、导航页和占位内容降权、近重复结果去除、来源多样性和相邻段落补充。普通更新会增量处理新文件、修改文件和已删除文件，无须每次全量重建。

```bash
# 建立或增量更新索引
python3 <skill-dir>/scripts/rag/index_vault.py --vault <course-project>

# 检查课件更新后索引是否过期
python3 <skill-dir>/scripts/rag/index_vault.py --vault <course-project> --status

# 搜索和为任务准备上下文
python3 <skill-dir>/scripts/rag/query_vault.py --vault <course-project> "问题或关键词"
python3 <skill-dir>/scripts/rag/retrieve_context.py --vault <course-project> --task final-review --scope "考试范围"
```

默认索引存放在课程项目的 `.course-study/rag_index.sqlite`，属于可重新生成的本地缓存，不建议分享，也不应提交到 Git。

### 6.1 项目配置

需要自定义检索范围时，可以生成根目录配置：

```bash
python3 <skill-dir>/scripts/rag/init_config.py --vault <course-project>
```

生成的 `course-study.json` 可以设置索引文件夹、排除规则、分块大小、每个来源的结果上限、相邻段落数量、最低命中比例、近重复阈值、项目停用词、中英文同义词，以及是否索引本地抽取的课件文本。配置改变后，状态检查会提示重新建索引。完整示例位于 `assets/course-study.example.json`。

### 6.2 离线抽取原始课件文字

结构化 Markdown 笔记仍然是首选。若希望在笔记尚未完成时检索原始文字，可离线抽取 PPTX、PDF、DOCX、Markdown 或 TXT：

```bash
python3 <skill-dir>/scripts/rag/extract_source.py <项目内的课件路径> --vault <course-project>
python3 <skill-dir>/scripts/rag/init_config.py --vault <course-project> --include-extracted
python3 <skill-dir>/scripts/rag/index_vault.py --vault <course-project>
```

PPTX 和 DOCX 使用系统自带的 ZIP/XML 能力；PDF 使用电脑中已经存在的 `pdftotext` 或 `pypdf`，不会自动联网下载。老式 `.ppt`、扫描件、图片、复杂图表和公式仍需合适的本地转换/OCR，并应对照原文件检查。

### 6.3 离线检索质量评测

可以用自己的问题和预期来源制作 JSONL 测试集，再运行：

```bash
python3 <skill-dir>/scripts/rag/evaluate_rag.py evaluation.jsonl --vault <course-project> --top-k 5
```

报告会给出 Top-k 命中率、第一名正确率、Hit@3、平均倒数排名（MRR）、nDCG@k 和实际返回来源，方便不同专业根据真实问题调整检索范围。

## 7. 分享给其他 Agent 用户

把完整的 `course-study-plugin` 文件夹发给对方即可。不要附带自己的课程材料、作业、个人笔记或 RAG 数据库。

- Codex 用户：安装 Plugin，然后在自己的项目中创建 `AGENTS.md`。
- 其他 Agent 用户：保留 `references/`、`assets/` 和 `scripts/rag/`，把 `SKILL.md` 转换成目标平台的规则、Skill 或 System Prompt；`.codex-plugin/plugin.json` 和 `agents/openai.yaml` 需要按目标平台替换。

建议对方先用一份无隐私的示例课件测试，再处理正式课程资料。

## 8. 常见问题

### 为什么同一个 Plugin 在不同项目中输出不同？

因为当前项目的 `AGENTS.md` 会覆盖 Plugin 默认值。这正是通用能力与个人规则分离的设计目标。

### Plugin 会自动调用额外的大模型 API 吗？

不会。RAG 是本地检索；最终生成内容由当前正在使用的 Agent 或模型完成。

### 为什么上传 PPT 后 RAG 搜不到？

默认仍只索引结构化 Markdown 笔记。可以先生成学习笔记；也可以使用离线抽取工具把 PPTX/PDF/DOCX 文字放入 `.course-study/extracted/`，在配置中启用 `include_extracted` 后重新建索引。图表、公式和排版信息仍需查看原文件。

### 可以直接把自己的 `AGENTS.md` 发给别人吗？

可以作为示例，但应先删除个人路径、课程名称、题量偏好、日志规则和隐私信息。通常更推荐让对方使用本手册中的最小模板创建自己的规则。
