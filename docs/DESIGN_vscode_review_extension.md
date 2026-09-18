# DESIGN — MathFlow Review:VSCode 扩展方案(替代 web 端 review 桥)

日期:2026-09-12 · 状态:draft 待审 · 关联:`DESIGN_p1p2_editor_review.md`(web 编辑/评审)、PR 试点 #1(Review Workflow)

## 0. 结论

web 端做"选区 → 评论 → PR"需要三处自建管线:SPA 选区 UI + 后端 anchor→行号映射/发评端点 + 双向同步。
写成 VSCode 扩展后,这三件事大多是**原生能力**,总体更省:

- 文件与行号天然可得 → 不需要 HTTP 桥
- `vscode.comments` 原生评论线程(resolve 状态、评论区面板),官方 GitHub PR 扩展用的就是它
- webview 里用 KaTeX 渲染 → **数学可见**,补上 PR diff 的缺口
- `gh` CLI 已登录 → 无需管理 token、无需自建 GitHub 客户端
- VSIX 侧载,不用上市场;Cursor / Windsurf / VSCodium 同为 VS Code 内核,同一个包可用

## 1. 已核实事实(本机)

- **VS Code 未安装**(`code` / `code-insiders` 不存在,`~/.vscode` 无);开发需先装
- Node v24.15.0、npm 11.12.1 可用(扩展开发/打包就绪)
- `gh` 2.92.0,已登录 `sylqiu`(可创建分支/PR/评论)
- 内容 = 本地 JSON:`~/Documents/mathflow/data/courses/<course>/lessons/*.json`(私有镜像 `mathflow-content`)
- 渲染逻辑可复用:`templates/player.html` 的 mini-markdown + KaTeX(`renderMathInElement`,`$/$$`)
- GitHub 评论限制(实测):只有 diff 内的行可内联;文件级评论要求文件在 diff 内;否则只能会话评论 + permalink → **必须有降级链**

## 2. 分层方案

**L0 · 零代码(今天就能用)**
VS Code + 官方 GitHub Pull Requests 扩展(行级评论、线程、resolve)+ 浏览器开 `localhost:8788` 看渲染。
缺点:JSON 源码不渲染数学,仍要两个窗口对照。

**L1 · MVP 扩展(推荐先做)**
- 命令 `MathFlow: Preview Lesson` → webview 渲染当前 lesson(KaTeX),块级锚点
- 在预览中**选中文本 → Add comment** → 原生评论线程,锚定到 JSON 源位置
- 评论存 sidecar(`data/reviews/vscode/<file>.json`,格式与现有 review 文档兼容)
- 交付效果:数学渲染 + 就地评论 + 线程/resolve,全本地

**L2 · 闭环(接 L1)**
扩展内直接跑 `gh`:
- `Open/Update PR`:当前改动 → 分支 → commit → push → PR
- `Push comments`:本地线程 → PR 评论(内联 → 文件级 → 会话评论+permalink 降级链),URL 回写本地线程
- `Pull comments`:PR 评论拉回本地;resolve 状态双向同步

**L3 · 可选(以后)**
多课/模块审阅视图、审阅进度、与 web admin 共享 review 格式、市场发布。

## 3. 技术要点

- 结构:`package.json`(contributes: commands / customEditors)+ `src/extension.ts` + `media/`(webview)
- 预览:从 `player.html` 抽出渲染器(mdToHtml + KaTeX),katex 离线打包进 webview
- 锚定:选中 → JSON 范围。确定性扫描(id/field)或 `jsonc-parser`(MIT,拿 AST 位置,更稳)
- PR 操作:`child_process.execFile('gh', [...])`,复用登录态,不引新依赖
- 打包:`vsce package` → VSIX → `code --install-extension` 侧载;开发时 F5 Extension Host 调试
- 前置:先在 mini 装 VS Code(brew cask 或官网下载)

## 4. 非目标

- 手机端(VS Code 不覆盖;web player/admin 继续承担手机场景)
- 市场发布、多人协作、权限模型

## 5. 工作量估计

- L1:一个 codex 任务(数百行 TS + webview 渲染 + 评论线程 + sidecar)
- L2:再一个 codex 任务(gh 推拉 + 降级链 + 状态同步)

## 6. 备选(评估过,不推荐作主路径)

把 lesson 导出成临时 `.md`,VS Code **内置 Markdown 预览原生支持 KaTeX** —— 渲染几乎零成本。
但评论无法回落到 JSON 锚点(评论锚在临时 md 上),只适合"先读",不适合"批注闭环"。

## 7. 开放决定点

1. 代码放哪:`mathflow` 仓库 `tools/vscode-review/`(public 只有代码,无内容)还是独立私有 repo?
2. 评论存储:sidecar 落盘(可与 web admin 互通)vs 仅 VS Code 内置(更轻,但不持久)
3. 是否先跑 L0 体验一天,再决定 L1 范围?
