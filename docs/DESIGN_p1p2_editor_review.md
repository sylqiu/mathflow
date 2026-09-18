# DESIGN P1+P2 — Lesson 结构化编辑 + Review 锚定真实内容

日期:2026-09-09 · 状态:draft 待 ZD 审阅 · 范围:P1(lesson 结构化编辑)+ P2(review 锚定真实 lesson 内容)
后续:P3(决策闭环 apply/resolved)、P4(草稿/发布/版本 diff)另行设计,本文只留扩展点。

---

## 0. 目标

1. **P1**:lesson 编辑页里 defs / theorems / checkpoints / exercises 四个 section 不再手写 JSON,
   改为**卡片式结构化表单**:字段级输入、逐条校验、选项行编辑、增删排序、实时数学预览。
   保留 raw JSON 模式作为高级出口,不锁死用户。
2. **P2**:review 文档能**锚定真实课程内容**——从 lesson 一键生成 review,block 自动抓取
   def/thm/checkpoint/exercise 与 body 小节,审的是原件快照;review ↔ lesson 双向可见。
   现有"空白 review 手动贴文本"流程完全保留(plan/course-draft 继续用)。

## 1. 现状(已核对的代码事实)

- `course_server.py`(port 8788):`/api/admin/*` 需 token / loopback;lesson GET/PUT、manifest、
  course validate(`/api/admin/courses/<id>/validate` → validate_courses.py)、media、reviews CRUD
  (`/api/admin/reviews*`,blocks decision/comments)均已存在。**实时读盘,内容改动无需重启。**
- `templates/admin.html`(~63KB hash-routed SPA):lesson 编辑页(renderLesson)现有——
  meta(module/kind/title)+ body(markdown textarea + 实时预览,mdToHtml + renderMath)
  + 4 个 section **raw JSON textarea**(jsonSectionHtml: Format / Add blank entry 按钮)。
  collectLesson() 前端 parse JSON,失败即阻止保存。
- 数据模型:`data/courses/<course>/manifest.json` + `lessons/<lid>.json`
  (schema: `lesson.schema.json`,v1,required: id/module/kind/title/body/schema_version;
  可选 reading/defs/theorems/checkpoints/exercises/media/audio)。
- 校验规则(validate_courses.py):checkpoint options ≥2 且 ≥1 个 correct;id/qid/def-id 等
  均为 `^[A-Za-z0-9][A-Za-z0-9._-]*$`;重复 id/qid 报错。
- review 文档:`data/reviews/<slug>.json` — `{id,title,kind("plan"|"lesson-draft"|"course-draft"),
  status("open"|"done"),created_at,updated_at,blocks:[{id,title,text,decision,comments}]}`。
  **现状 block 是纯文本快照,与 lesson 文件无任何关联。**
- 安全:所有删除进 `data/.trash`,保存自动 .bak。UI 英文,player 不受影响。

## 2. P1 — Lesson 结构化编辑(4 sections 卡片表单)

### 2.1 界面结构(lesson 编辑页,替换 jsonSectionHtml)

每个 section 渲染为独立卡片组(`structured-section`),置于 body 预览之下、Save 之上,顺序同现状:

- **defs**:每张卡片 = id / name / statement(+ 可选 intuition)
- **theorems**:id / name / statement / proof(+ 可选 intuition)
- **checkpoints**:qid / question / options 行列表 / explanation
- **exercises**:id / prompt / hint / solution

卡片头部:序号 + 条目 id(灰字)+ 操作 [↑] [↓] [🗑(confirm)]。
底部:[+ Add def / theorem / checkpoint / exercise](沿用 BLANK_ENTRIES 模板生成空条目)。
空数组时显示空态提示 + Add 按钮。

字段控件约定:
- 单行短文本(id/name/qid)→ `<input type="text">`,mono 字体。
- 长文本(statement/proof/question/explanation/prompt/hint/solution/intuition)→ `<textarea>`。
- 数学字段(statement/proof/question/explanation/intuition/prompt/hint/solution 等含 LaTeX 的)→
  字段下方**内联 KaTeX 实时预览**:debounce 300ms 后 mdToHtml + renderMath 渲染该字段,高亮当前字段,预览只读。
- **KaTeX 约定**:admin.html 已加载 KaTeX 0.16.9(CDN css/js/auto-render)并已有 renderMath()
  ($/$$ delimiters,throwOnError:false)——**零新依赖**;任何含数学的字段与预览区一律走 renderMath,
  不引入第二套渲染。body 实时预览(现有)与卡片字段预览同一渲染链。
- options 行:每行 = `<input text>`(option 文案)+ radio(标记 correct)。行尾删除按钮(至少保留 2 行时可用)。
  “correct” 单选只允许一个;若用户改选另一行,自动取消旧选择(与 player 判题逻辑一致:
  checkpoint 单选题语义;未来多选题另议,见 §4)。

### 2.2 JSON 模式 toggle(高级出口)

每个 section 卡片组右上角 `[Card mode | JSON mode]` 切换(默认 Card)。JSON mode = 现状 textarea
+ Format 按钮。**两种模式共享同一数据源**,切换即时序列化/反序列化(JSON 非法时禁止切回 Card 并报错定位)。
保存路径统一走 state.lesson,与当前 collectLesson→PUT 一致。

### 2.3 内联校验(保存前全量,错误就地显示)

规则(镜像 lesson.schema.json + validate_courses.py,不引入新规则):

| 字段 | 规则 |
|---|---|
| defs[].id / theorems[].id / exercises[].id / checkpoints[].qid | pattern `^[A-Za-z0-9][A-Za-z0-9._-]*$` |
| 上述 id | section 内唯一(跨 section 不查) |
| defs/theorems | name、statement 非空 |
| checkpoints | question 非空;options ≥2;**≥1 个 correct**;每个 option text 非空;explanation 非空 |
| exercises | prompt、hint、solution 非空 |

错误呈现:出错的卡片红框 + 字段下红字(如 `cp2: no correct option`);Save 按钮点击时若有错,
不请求、在 ls-status 显示 "N field error(s) — see highlighted cards",并滚动到第一个错误卡片。
校验函数集中一份 `validateLessonStructured(L)` → `[{section, index, field, msg}]`,供 Card 实时
与 Save 共用。服务端 PUT 校验现状保留(双保险,错误已在 save-lesson 分支展示)。

### 2.4 保存流程(不变)

Card/JSON 模式数据都写回 `state.lesson` → collectLesson() 语义 → PUT lessons/<id>(现有端点,
服务端校验 + .bak)。保存后刷新 section 渲染。**服务端/player/schema 零改动**(若 PUT 校验缺
schema 级检查则仅补一行调用 validate_courses 的 lesson 级函数,待 codex 勘察后定)。

## 3. P2 — Review 锚定真实课程内容

### 3.1 数据模型扩展(向后兼容)

review 文档新增**可选**字段:

```jsonc
{
  // ……现有字段不变……
  "target": { "course": "pseudorandomness-primer", "lesson": "m1-three-theories" },
  // 可选;缺省 = 通用 review(plan/course-draft,现状行为)
  "blocks": [
    {
      "id": "b1",
      "title": "def: random",        // 自动生成或手动
      "text": "<抓取时的内容快照 markdown>",   // 审的是快照,之后 lesson 改了可 diff(留给 P3)
      "anchor": {                    // 可选;缺省 = 无锚定(现状纯文本 block)
        "section": "defs",           // "defs"|"theorems"|"checkpoints"|"exercises"|"body"
        "item": "random"             // defs/theorems/exercises → 条目 id;checkpoints → qid;body → 小节序号 "h1"|"h2"|…
      },
      "decision": null,
      "comments": []
    }
  ]
}
```

兼容规则:`_normalize_review` 忽略未知字段,老文件照常读取;anchor/target 缺失的 block 行为 = 现状。
新字段不做 schema_version 变更。

### 3.2 创建流程:两种入口

1. **空白 review(现状保留)**:`#/reviews/new` 原样;kind=plan/course-draft 时无 target。
2. **从 lesson 一键生成(review 内容自动抓取)**:
   lesson 编辑页头部加 `[Review this lesson]` 按钮 → `#/reviews/new?from=course/lid` →
   表单预填:kind=`lesson-draft`,target={course,lesson},并自动生成 blocks:

**body 拆分规则**(仅抓取,不改原文):
- 按 markdown 顶层小节拆分:`^## ` / `^### ` 作为小节边界;
- 每个小节 → 一个 block:`title` = 小节标题,`text` = 小节正文(不含标题),anchor=`{section:"body", item:"h1","h2",…}`(按文档序编号);
- defs/theorems:每条目 → block,title=`def: <name>` / `thm: <name>`,text=statement(含 proof 则拼上,用 markdown 分隔),anchor=`{section, item:<条目 id>}`;
- checkpoints:每条目 → block,title=`cp: <question 前 60 字符>`,text=question + 选项列表(渲染成 markdown 列表,不标答案,标注 [correct] 选项为答案?→ **不标注**,reviewer 看题目本身;需要判题质量时看 options 文本),anchor=`{section:"checkpoints", item:<qid>}`;
- exercises:每条目 → block,title=`ex: <prompt 前 60 字符>`,text=prompt(+hint),anchor=`{section:"exercises", item:<id>}`;
- 空 section 跳过;抓取时记录每 block 的 `text`,创建后即为快照。

生成后可手动增删 block、改 title/text,再 Create。

**KaTeX 预览覆盖**:① 创建/编辑页 blocks textarea 下加实时预览窗(debounce 300ms,mdToHtml + renderMath,
  与 lesson body 预览同款);② 生成的每条 block 立即以渲染态显示(非裸 markdown);③ review 详情页
  block 文本渲染已有 renderMath,保持不动。所有含数学内容的编辑入口都有所见即所得的 KaTeX 预览。

### 3.3 Review 详情页增强(renderReview)

- 顶部 sub 行:有 target 时显示 `Lesson: <course>/<lid>` + `[Open lesson ↗]` 链接(同窗口新路由)。
- 每个带 anchor 的 block:头部显示 section 徽标(defs/thm/cp/ex/body),title 处若 anchor 可解析,
  附 `[jump]` 链接 → `#/course/<id>/lesson/<lid>` 并定位该条目(见 3.5)。
- 其余(decision 三键、comments、status/done、delete)不变。

### 3.4 lesson 编辑页 ↔ review 互链

- lesson 页头部(标题行下方)加 **Reviews 条**:查询该 lesson 的 open reviews,
  显示 `N open review(s): [title(kind) decided a/b] [Open]`,点击进 review 详情。
  该查询走新端点(3.6),无结果时不渲染该行。
- 锚定块 jump 到 lesson 时:路由加可选定位参数(如 `#/course/<cid>/lesson/<lid>@defs:random`),
  lesson 渲染后滚动到对应 section 卡片并高亮 2s;Card 模式下展开对应条目,JSON 模式下仅滚动到 section。

### 3.5 服务端 API 变更(小)

| 端点 | 变更 |
|---|---|
| `POST /api/admin/reviews` | 接受可选 `target` 与 block 级 `anchor`;有 target 时校验 course/lesson 存在(404 语义转 400);其余不变 |
| `GET /api/admin/courses/<cid>/lessons/<lid>/reviews` | **新增**:返回该 lesson 的 review 摘要列表(复用 _review_summary,按 updated_at 倒序) |
| `GET/PUT /api/admin/reviews/<id>`、blocks decision/comments | 透传新字段,无逻辑变化 |

若 codex 勘察发现 `_load_lesson` 等校验锚点成本高,允许降级:POST 时 target 仅做格式校验,
存在性校验放 UI(lesson 页发起,天然存在)。

### 3.6 兼容性 / 迁移

- 老 review 文件零迁移,直接可读。
- player.html、reader API、schema 不动。
- admin.html 是单文件 SPA,改动集中于此 + course_server.py 少量路由。

## 4. 明确不做(留给后续,本文只保证不挡路)

- P3 决策闭环:revise → 修改 lesson → 自动标记 resolved、快照 diff 提示过期(review 已存 text 快照 + anchor,天然支持,后续做)。
- P4 草稿/发布状态、lesson status:draft|published、版本 diff UI。
- checkpoint 多选题语义变更(现为单选 correct;若未来支持多选,options 行 radio 改 checkbox,校验规则同改,影响 player 判题,单独设计)。
- 富文本/WYSIWYG(body 仍为 markdown textarea + 预览)。
- 移动端专项适配(结构表单在手机上可读可用即可,不重设计)。

## 5. 验收清单(codex 交付后我用浏览器 + API 实测)

1. Card 模式四 section 增/删/排序/编辑正常;空态与 Add 正常;↑↓ 边界正确。
2. options 行:添加/删除(≥2 下限)、correct 单选互斥;无 correct 或 <2 options 时保存被拦且错误就地显示。
3. 非法 id pattern、重复 id、空 statement/question 等各触发对应卡片红字;修正后保存成功。
4. JSON mode ↔ Card mode 往返无损;JSON 非法时禁止切回 Card 且报错定位。
5. Save 成功 → GET 返回内容一致;错误时服务端校验仍兜底(刻意构造非法数据 PUT 被拒)。
6. 从 lesson 生成 review:blocks 数与内容符合 3.2 拆分规则;target/anchor 正确落盘。
7. 空白 review 老流程(手动 blocks)不受影响;老 review 文件列表/详情打开正常。
8. review 详情 jump 链接 + lesson 页 Reviews 条 + 锚点定位高亮可用。
9. `/api/admin/courses/<cid>/lessons/<lid>/reviews` 返回正确;无 review 时 200 空数组。
10. validate_courses.py 对同一课程仍 ALL OK;player 端抽查 lesson 渲染无回归。

## 6. 开放决定点(请 ZD 拍板)

1. **P1 是否同时给 meta 区补 reading 编辑**(text + url,示例 lesson 已有 reading 字段,现 UI 不可编辑)?默认:补(顺手,防手改 JSON)。
2. **Review this lesson 的 body 拆分粒度**:按 `## / ###` 小节拆分(默认,推荐)vs 整段 body 一个 block。
3. 高级出口命名与位置:每 section 右上角 Card/JSON toggle(默认)即可,还是需要全局一个 toggle?
4. checkpoint 预览是否要在 review block 里**隐藏 correct 标记**(默认隐藏,便于审题质量)。

确认后我写 TASK_structured_editor_review.md 交 codex(英文,走 run_codex_once.sh)。
