# Pseudorandomness 自学课程
### 基于 Oded Goldreich 的 Weizmann 公开资料（c-indist 页面）
> 生成日期：2026-08-22 ｜ 材料存放：`materials/`（已下载 PDF + 全文提取文本）
> 主教材：**Goldreich, "Pseudorandom Generators: A Primer" (Jul 2008)** —— 页面标注 "latest and most recommended exposition"

---

## 0. 课程总览

### 0.1 这门课讲什么

一句话：**"无法被高效算法区分于均匀分布的分布，就当它是随机的"** —— 这是复杂性理论对随机性的第三次回答。本课程从 computational indistinguishability（计算不可区分性）这个核心范式出发，系统学习：

1. 一般性伪随机生成器（general-purpose PRG）的定义、应用与构造
2. 支撑整个领域的核心证明技术：**hybrid argument（混合论证）**
3. 伪随机性的两个主要应用方向：**密码学**（one-way function ↔ PRG 等价性）与**去随机化**（BPP ⊆ P、NW generator）
4. 空间受限区分者（Nisan 生成器、INW 生成器）
5. 特殊目的生成器：pairwise independence、small-bias、expander random walks
6. 进阶：randomness extractors、Yao's XOR Lemma

### 0.2 为什么值得学

- 这是**理论计算机科学的地基**：BPP=P 猜想、密码学中"困难性 → 伪随机性"的完整证明链条都从这里长出来
- 会训练两种高价值技能：**量词精读**（定义里的 ε/δ/多项式 顺序错一个，整个定义就废了）和 **hybrid argument**（学界最通用的证明范式之一，统计不可区分、零知识、密码归约全都在用）
- 资料是 Goldreich 本人钦点的"最新最推荐版本"，自包含、含主要定理证明梗概

### 0.3 先修要求

| 领域 | 要求 | 不够的话补什么 |
|---|---|---|
| 概率 | 分布、期望、联合界（union bound）、Chebyshev | 任意概率论教材第 1–3 章 |
| 复杂性 | 多项式时间、P/NP/BPP、O() 记号、图灵机基本概念 | Sipser《Introduction to the Theory of Computation》ch. 7 |
| 密码学 | **不需要**——one-way function 会在 Module 4 内讲 | — |
| 数学成熟度 | 能读懂"∀ε ∃N ∀n>N"这种量词链、会做简单证明 | — |

### 0.4 教材分工（页面资料的完整盘点）

| 材料 | 定位 | 本课程用法 |
|---|---|---|
| **prg08.pdf**（Primer, 2008） | **主教材**。5 章，自包含，含主要定理证明梗概 | 逐模块精读 |
| **ln00a.pdf**（Goldreich Lecture Notes Part I, 2001） | 主教材的早期讲稿版，**证明更细**（含 GL 定理完整证明附录） | 主教材证明看不懂时的"第二通道" |
| **ln00b.pdf**（Trevisan Lecture Notes Part II） | 去随机化专题讲稿（NW generator、extractors），比 Primer ch.3 展开更多 | Module 6、Module 9 |
| prg10.pdf（AMS ULECT-55 正式版 primer, 2010） | 出版版，有图 | 可对照（页面说 figures 不出现在 2008 版 PDF） |
| cc-text17.pdf（2006 草稿） | Complexity 书 ch.8 早期自包含版 | 备查 |
| turing.pdf / prg88.pdf（1987 综述） | 历史视角："Randomness, Interaction, Proofs and Zero-Knowledge" | Module 9 阅读材料 |
| p_yao.html（Yao's XOR-Lemma, GNW 1995） | XOR 引理论文 | Module 9 阅读材料 |

### 0.5 学习节奏建议

**主线 8 周**（每周 6–8 小时），Module 9 为可选深入。核心路径依赖：

```
M1 CI 定义 ──► M2 PRG 定义 ──► M3 Hybrid Argument（核心技法）
                              ├──► M4 构造（OWF/BMY）
                              ├──► M5 PRF
M3 ──► M6 去随机化（NW）──► M7 空间受限 ──► M8 特殊目的
                                              └──► M9 进阶（可选）
```

**黄金法则**：每个定理先自己证 20 分钟再看证明；每章结束把定义/定理用自己的话写一遍（"无笔记不算学完"）。

---

## 1. 模块详情

---

### Module 1：随机性的三种理论 & 一般范式
**主题**：为什么复杂性理论对随机性的回答与前人不同；这个回答的"三个基本面"。
**时间**：4–5 小时 ｜ **阅读**：prg08 Preface + §1.1–1.4（pp. 1–10）

**核心内容**
- Shannon 信息论：随机 = 信息缺失（分布视角）；Kolmogorov：随机 = 无结构（单对象视角，不可计算）；**复杂性理论：随机 = 对观察者的效果**（observer-relative）
- Alice & Bob 抛硬币思想实验（prg08 §1.1）：三种 Bob 的差别就是"观察者能力"的差别
- **一般范式三基本面**（§1.4.1，全文最重要的框架）：
  1. **stretch measure**（生成器把种子拉多长）
  2. **区分者类别**（要骗过谁：多项式时间？空间受限？固定时间？）
  3. **生成器自身资源**（允许生成器用多少计算）
- 范式实例化一览（§1.4.3）：general-purpose、derandomization、space-bounded、special-purpose —— 这就是后五个章节的地图

**产出（写下来）**：用自己的话回答——"为什么说伪随机性是主观的？"（50 词以内）

**检查点**（自测，答案见 §4）：
1. 为什么 Shannon/Kolmogorov 意义下"确定性生成随机串"在定义上就不可能，而复杂性理论意义下可以？
2. 三基本面分别固定成什么，就得到 general-purpose PRG？

---

### Module 2：计算不可区分性（CI）—— 定义精读
**主题**：整个领域的定义核心。**本模块唯一目标：把定义读到每个量词都不含糊。**
**时间**：5–6 小时 ｜ **阅读**：prg08 §2.1–2.3.2（pp. 11–17）+ ln00a §1.1–1.4

**核心定义（必须默写）**
- PRG 定义（prg08 Def. 2.1）：确定性、多项式时间、stretch 函数 ℓ(n) > n、对任意 PPT 区分者 D 有
  `|Pr[D(G(Un)) = 1] − Pr[D(Uℓ(n)) = 1]| < μ(n)`（可忽略函数）
- **计算不可区分性**（§2.3.1）：ensemble 的语言。`{Xn} ≡c {Yn}` ⟺ ∀PPT D, ∀多项式 p, ∀足够大 n: `|Pr[D(Xn)=1] − Pr[D(Yn)=1]| < 1/p(n)`
- **统计不可区分 vs 计算不可区分**（§2.3.2）：统计距离 ≤ ε 蕴含 CI；反之不成立（CI 弱得多）。注意量词顺序：CI 对**每个**区分者有个体化的 ε，不是统一 ε

**关键洞察（务必消化）**
- "可忽略"（negligible）的三个等价视角：比任何 1/poly 小 / 比任何 poly 的倒数小 / 最终小于 n^{−c} ∀c
- 区分者 D 的输出是 1 bit——为什么这就够了一般性（任何"判断"都能编码成 bit）
- 生成器可以比区分者慢（固定多项式 vs 任意多项式）——这是密码学场景的关键

**检查点**：
1. 把 CI 定义中"∀D ∃ε"写成"∃ε ∀D"会发生什么？（提示：定义会变成平凡或不可能——自己想清楚哪个）
2. CI 与统计接近的关系：证明统计距离 ≤ 1/poly 蕴含 CI（5 行证明）
3. **错题本**：为什么"G 的输出没有明显模式"不是伪随机性的充分条件？

---

### Module 3：Hybrid Argument 与多采样（核心技法）
**主题**：唯一一个必须练到肌肉记忆的证明技术。
**时间**：6–7 小时 ｜ **阅读**：prg08 §2.3.3（pp. 17–20）+ ln00a §1.5（Theorem 1.5 完整证明）+ prg08 §2.4（stretch 放大）

**核心定理**
- **Proposition 2.6（prg08）/ Theorem 1.5（ln00a）**：X ≡c Y（单采样）⟹ 任意多项式个独立采样下仍不可区分
- **Construction 2.7 / Prop 2.8**：stretch 放大——把 ℓ(n)=n+1 的生成器叠成任意多项式 stretch

**Hybrid 论证的解剖**（必须能独立复述）：
1. 假设存在区分者 D 能区分 k 个采样 → 构造 hybrid 链 H₀, H₁, …, H_k（相邻只差一个坐标）
2. 三角不等式/平均论证：D 必在某一步 Hᵢ vs Hᵢ₊₁ 上有非可忽略优势
3. 用这个优势构造单采样区分者（关键：**归约**——把 D 当作黑盒）
4. 常见坑：hybrid 里的"中间分布"必须可高效采样（否则归约不合法）——ln00a 特别强调 X、Y 要 poly-time constructible

**必做练习（每题先自己写证明再看答案）**：
1. 完整写出 Prop 2.6 的 hybrid 证明（提示：Hᵢ = X^i Y^{k−i}，注意 D 的输入分布）
2. 为什么 hybrid 论证里损失因子是 1/k 而不是 1/2^k？（这决定了为什么要"可忽略"而不是"指数小"）
3. **stretch 放大**：证明 Prop 2.8（提示：把 G1 的输出分段喂回；hybrid 按"G1 用了几次真随机"分层）
4. 反例练习：构造两个统计距离为 1 但计算不可区分的分布（提示：用 PRG 输出 vs 均匀——需要先假设 PRG 存在；或者用 one-way permutation 的像）

**检查点**：不看笔记，写出 hybrid argument 的四步模板。

---

### Module 4：构造 —— OWF、Hard-Core Predicate、BMY 生成器
**主题**：从"困难性"到"伪随机性"的正面构造；以及那个漂亮的等价定理。
**时间**：8–10 小时（本课程最难模块）｜ **阅读**：prg08 §2.5–2.6（pp. 21–27）+ ln00a §2.3 + **Appendix（GL 定理完整证明）**

**路线图**
```
One-way function f
   │  Theorem 2.11 (Goldreich–Levin 泛化): 随机子集 S 的 f(x)|S 与 ⟨x,S⟩ 构成 hard-core
   ▼
hard-core predicate b（给定 f(x) 猜 b(x) 不比 1/2+ε 好）
   │  Prop 2.12: G(s) = f(s) b(s) 是 ℓ(n)=n+1 的 PRG
   ▼
Construction 2.7: stretch 放大
   ▼
Theorem 2.13 / 2.14: PRG 存在 ⟺ OWF 存在（必要方向：PRG ⇒ OWF 是简单的；充分方向就是上面这条链）
```

**必须掌握的定理**
- **Theorem 2.11（generic hard-core predicate）**：任何 OWF f，`b(x,S) = ⟨x,S⟩ mod 2` 对输入 `(f(x), S)` 是 hard-core。**这是全书最美的定理之一**——把"任何困难函数"变成"可用的困难谓词"
- **Theorem 2.14（存在性刻画）**：PRG 存在 ⟺ OWF 存在。非均匀版本（§2.6）对应 BPP 去随机化
- **Theorem 2.16（prg08）**：非均匀强 PRG 存在 ⟹ BPP ⊆ P（预告 Module 6）

**必做练习**：
1. **证 PRG ⇒ OWF**（简单方向，5 行）：设 G 是 PRG，定义 f(x) = G(x) 的前 |x| 位…… 补完并证明
2. 复述 Theorem 2.11 的证明框架：假设能猜 b(x,S) → 用自归约（self-reduction）逐位恢复 x → 反转 f。**自归约**这个动作要能默写
3. 为什么 hard-core 必须加随机 S？为什么不能直接说"f 的每个 bit 都难猜"？（反例：f(x) = x 丢掉最后一位）
4. 读 ln00a Appendix，对照 prg08 的 sketch，列出 sketch 省略的 3 个关键细节

**检查点**：独立画出"OWF ⟺ PRG"双向证明的完整依赖图。

---

### Module 5：伪随机函数（PRF）与更强概念
**主题**：从"伪随机串"到"伪随机函数"——对象从静态变成动态。
**时间**：4–5 小时 ｜ **阅读**：prg08 §2.7–2.8（pp. 27–31）+ ln00a §3.1–3.2

**核心内容**
- PRF 定义：对 PPT 区分者（可自适应查询 oracle），随机函数 vs 伪随机函数族不可区分
- **Theorem 2.18 / ln00a Theorem 3.2（GGM 构造）**：PRG ⟹ PRF。**构造核心：二叉树**——种子在树上做 PRG 扩展，叶子是函数值；树深 d 对应输入长度 d
- 应用：密码学（消息认证、对称加密、挑战-响应）、复杂性（hardness amplification 的构件）
- §2.7.1：fooling 更强区分者（non-uniform circuits）的概念层次
- §2.8 Conceptual reflections：为什么"stretch 是伪随机性的全部"（生成器本身不增加信息量，只是重排）

**必做练习**：
1. 写出 GGM 构造中"第 i 位输入决定走左/右子树"的细节；为什么深度 d 的树只需 O(d) 次 PRG 调用？
2. PRF ⇒ PRG 的反向：为什么平凡成立（固定输入求值即可）？这说明 PRF 严格更强
3. 讨论：PRF 区分者能自适应查询，为什么定义里仍然只要 1 bit 输出？

---

### Module 6：去随机化 —— Canonical Derandomizer 与 NW Generator
**主题**：为了去随机化，我们愿意"生成器比区分者更复杂"——范式第三基本面反转。
**时间**：8–9 小时 ｜ **阅读**：prg08 ch.3（pp. 32–41）+ **ln00b Lectures 1–3**（Trevisan 版展开更细，强烈建议）

**核心内容**
- **范式反转**：derandomization 场景下，生成器允许指数时间（在种子长度上），只要区分者时间有固定上界
- **Canonical derandomizer 定义**（§3.1）：stretch ℓ(k)，输出对任意 t = poly 的 Dtime(t) 区分者不可区分
- **Theorem 3.3**：stretch ℓ(k) = 2^{Ω(k)} 的 canonical derandomizer ⟹ BPP = P
- **Construction 3.4（NW 构造）**：输入是"平均情况困难"的布尔函数 f（来自 E 中无子指数电路的假设），用 **combinatorial design**（S₁,…,S_m，成对小交集）把 f 的 m 个输出位"解相关"
- **Theorem 3.5（分析）**：若 f 对任意 s(k) 规模电路有 1/s(k) 平均困难，则 G 是 canonical derandomizer。证明用 hybrid + **局部困难 → 全局困难**的归约（f 的一个输出位错，就得到一个能算 f 的电路——注意这是"witness 式"论证的关键）
- ln00b Lecture 1：IW98/IW97 定理谱系（uniform vs non-uniform、指数 vs 超多项式困难）
- ln00b Lecture 2：NW 证明的完整链条——**ECC 与 worst-case-to-average-case 归约**（Thm 7/8/9，用 list-decodable code 把"平均困难"提升为"最坏困难"）+ design 的存在性（Thm 11）

**必做练习**：
1. 为什么 NW 构造要求 design 的 pairwise 交集小？（提示：hybrid 里要保证"改一个坐标只影响少数 f 调用"）
2. 复述 Theorem 3.5 的证明骨架：假设区分者 D → 找到小电路计算 f → 矛盾
3. 对比 general-purpose PRG 与 canonical derandomizer 的三个基本面差异（表格形式）
4. ln00b Exercise：从 Thm 5（NW 特例）到 Thm 6（BFNW/Imp/IW）的增强路径，每一步增强了什么假设/结论

**检查点**：不看笔记，画出 NW 生成器的输入-输出-参数关系图。

---

### Module 7：空间受限区分者
**主题**：不靠任何计算假设，纯组合构造——因为"空间小"本身就是可用的结构。
**时间**：5–6 小时 ｜ **阅读**：prg08 ch.4（pp. 42–51）

**核心内容**
- 定义问题（§4.1）：区分者是空间受限（非均匀自动机）时，"可忽略"的含义变化——gap 要与空间 m 关联
- **Theorem 4.2（Nisan 生成器）**：stretch 指数级（2^{s(k)}），种子长 O(m²) 骗过空间 m 的自动机。**证明核心：近似独立性 via 逐层"分裂"（利用空间受限 ⇒ 状态少 ⇒ 可 union bound）**
- **Theorem 4.3（INW 生成器）**：stretch 多项式、空间线性，但 gap 只有亚指数（**警告：这是历史上被误用过的点**，务必记住 Theorem 4.3 的 gap 限制）
- 应用（§4.2.2）：**BPL ⊆ Dspace(log²)**、RL ⊆ Dspace(log²)

**必做练习**：
1. 用自己的话解释：为什么空间受限区分者可以用"状态计数 + union bound"来骗，而时间受限不行？
2. 对照 Theorem 4.2 vs 4.3：stretch、空间、gap 三个参数的权衡表
3. 为什么 Theorem 4.2 的种子长 O(m²) 是"信息论下界意义上的自然"？（提示：要骗过 m 空间自动机，多少熵才够？—— 这题是开放的，想 10 分钟即可）

---

### Module 8：特殊目的生成器
**主题**：不需要任何假设、可证明地"足够随机"的轻量工具——工程上最常用的一章。
**时间**：5–6 小时 ｜ **阅读**：prg08 ch.5（pp. 52–62）

**核心内容**
- **Pairwise independence（§5.1）**：任意两位均匀独立。构造：GF(2^m) 上线性函数族 `{x ↦ ax+b}`（种子 2m bit，输出 2^m 个点）；**只用 2n bit 种子就能让 n 个随机变量两两独立**——去随机化、负载均衡、哈希的基石。应用：universal hashing、随机化算法去随机（如随机选择 pivot）
- **Small-bias（§5.2）**：对任意非空 S，`E[∏_{i∈S} χᵢ] ≤ ε`（线性测试几乎随机）。**Theorem 5.3**：stretch 指数、bias 指数小。构造之一：**LFSR**（种子 = 不可约多项式 + 初态）；另一：基于 error-correcting codes（[NN90]）。应用：derandomization 的构件、AM 协议、近似计数
- **Expander random walks（§5.3）**：在 expander 上走 t 步只需 log|V| + O(t) bit 种子，但 hitting 性质与独立采样几乎一样好。**这就是"用少量随机性模拟大量独立性"的典范**。应用：随机游走 derandomization、概率证明

**必做练习**：
1. 构造 pairwise independent 族并验证性质（线性代数 3 行证明）
2. 为什么 pairwise independence 不能用于需要 3 路独立性的场景？构造反例分布
3. small-bias ⟹ 对任意线性测试不可区分：写出 1 行证明（用 Fourier）
4. expander walk：写出 hitting property 的陈述，并说明它为什么比独立采样"省随机性"

---

### Module 9（可选进阶）：Extractors、XOR Lemma 与历史视角
**主题**：把"伪随机"推广到"从烂熵源提纯"；以及这个领域的历史脉络。
**时间**：6–8 小时 ｜ **阅读**：ln00b Lecture 4 + p_yao.html（GNW 1995）+ turing.pdf / prg88.pdf 选读

**核心内容**
- **Randomness extractor（ln00b L4）**：min-entropy 定义；extractor = 用短真随机种子把 (n, k)-source 提纯成接近均匀；**NW 构造稍加改造就是 extractor（Trevisan 发现）**；应用：密码学中的弱随机源、量子随机性
- **Yao's XOR Lemma**：若 f 以 δ 优势难猜，则 f(x₁)⊕…⊕f(x_t) 以 ~(1−2δ)^t 优势难猜。GNW 1995 给出了干净证明（与 hybrid/归约血脉相连）；该引理是 hardness amplification 的发动机
- 历史阅读：turing.pdf（1987）——随机性、交互、证明、零知识四者如何交织；prg88.pdf 是其中"计算随机性"部分的修订版

---

## 2. 全课程定理地图（背下来你就通关了）

```
CI 定义 (prg08 Def 2.1, §2.3.1)
├─ 统计接近 ⇒ CI (§2.3.2)
├─ 多采样不变性 Prop 2.6 / ln00a Thm 1.5   ← hybrid argument
├─ stretch 放大 Const 2.7 / Prop 2.8
├─ OWF ⟺ PRG (Thm 2.14)
│   ├─ PRG ⇒ OWF（简单）
│   └─ OWF ⇒ PRG: GL hard-core (Thm 2.11) → Prop 2.12 → 放大
├─ PRF (Thm 2.18, GGM)：PRG ⇒ PRF（二叉树）
└─ 非均匀强 PRG ⇒ BPP ⊆ P (Thm 2.16)

去随机化
├─ canonical derandomizer (Def 3.1) + stretch 2^{Ω(k)} ⇒ BPP=P (Thm 3.3)
└─ NW 构造 (Const 3.4) + 分析 (Thm 3.5)：E 中无子指数电路假设 ⇒ BPP=P
    └─ 提升链：ECC/worst-to-average (ln00b Thm 7-9) + design (Thm 11)

空间受限
├─ Nisan (Thm 4.2)：指数 stretch，种子 O(m²)，gap 2^{-m}
└─ INW (Thm 4.3)：poly stretch，种子 O(m)，gap 亚指数 ⚠️
    └─ BPL, RL ⊆ Dspace(log²)

特殊目的（无条件）
├─ pairwise independence（GF 线性族，种子 2n）
├─ small-bias（LFSR / ECC；Thm 5.3）
└─ expander random walks（hitting property）

进阶
├─ extractor（Trevisan：NW ⇒ extractor）
└─ XOR Lemma（GNW 1995）
```

---

## 3. 学习协议（每模块固定流程）

1. **热身（15 min）**：先读"核心内容"清单，明确本模块 3–5 个必会名词
2. **精读（2–3 h）**：按"阅读"清单读原文。定理先遮住证明自己写 20 分钟
3. **产出（30 min）**：用自己的话写"定义卡"和"定理卡"（见 §5 模板）
4. **练习（1–2 h）**：做"必做练习"，对照答案（§4）批改
5. **检查点（15 min）**：不看书回答检查点问题；答不上来 → 标记并重读对应小节
6. **错题本**：所有卡住 20 分钟以上的点进 `mistakes.md`，每周日复习

---

## 4. 练习与检查点答案（要点）

> 详细解答写在这里，但**先做再看**。只给骨架，细节回原文。

- **M1-1**：Shannon/Kolmogorov 的"随机"是对象的固有属性（分布熵最大/串不可压缩），而确定性地从短种子生成 = 输出只有 2^|seed| 种可能，熵/复杂度有上界，故不可能。复杂性理论的"随机"是观察者属性，只要求"看不出来"，生成器制造的是"看起来随机"。
- **M2-1**：若 ∃ε 统一成立（∀D 同一个 ε），则对任意固定 D 取 ε<1/2 平凡成立——定义失效。正确顺序 ∀D ∃ε（ε 可以依赖 D）才是"对每个 D 都小"。反过来 ∃ε ∀D 则要求"存在一个 ε 对所有 D 都小"，等价于统计接近，过强。
- **M2-2**：|Pr[D(X)=1]−Pr[D(Y)=1]| ≤ Σ_x |Pr[X=x]−Pr[Y=x]|·|…| ≤ Δ(X,Y) ≤ 1/poly。第一个不等式是"把 D 当成指示函数的加权和"（三角不等式），严格写见 prg08 §2.3.2。
- **M2-3**："没有明显模式"不可形式化；伪随机性的定义是针对**可计算检验族**的，不是人类直觉。
- **M3-1**：H_i = X^i Y^{k−i}（前 i 个来自 X 采样，后 k−i 个来自 Y）。D 区分 H₀ vs H_k ⇒ 存在 i 区分 H_i vs H_{i+1}（平均论证：k 项和 ≥ ε ⇒ 某项 ≥ ε/k）。单采样归约：输入 z，以概率 1 输出 D(H_i 把 z 放在第 i+1 位)。注意 H_i 里"来自 X 的部分"要独立重采样——所以要求 X、Y 可高效采样（ln00a 强调的点）。
- **M3-2**：hybrid 链长度 k = poly，损失 1/k 仍是可忽略（1/k·(1/poly) 还是 1/poly'）。若链长指数则损失 1/2^k 不可忽略——这正是"多项式个采样"而不是"指数个"的原因。
- **M3-3（stretch 放大）**：G(s) = G1^ℓ(n)(s)：反复把当前串喂给 G1 取最后 1 bit 拼接。Hybrid 按"真随机段长度"分层，每层差一个 G1 调用，用 G1 的 PRG 性 + 归约证相邻不可区分。
- **M4-1（PRG ⇒ OWF）**：f(x) = G(x) 前 |x| 位。若 f 可逆（PPT 求逆成功概率 ≥ 1/poly），则区分者 D(y) = [G(f^{-1}(y)) = y] 能以不可忽略优势区分 G(U_n) 与 U_{ℓ(n)}（后者落在 G 值域的概率 ≤ 2^n/2^{ℓ(n)} = 可忽略）。矛盾。
- **M4-2**：GL 自归约框架：① 用"猜 b(x,S) 成功 > 1/2+ε"构造对固定 S 的多数恢复；② 对随机 S、S⊕e_i 两两配对消去噪声（巧妙的重采样技巧）；③ 逐位恢复 x。细节以 ln00a Appendix 为准。
- **M4-3**：f 的个别 bit 可能总等于 0（如 f(x)=(x_1…x_{n-1},0) 仍需单向性检查……更简单反例：f(x)=x 的奇偶校验位与其余位拼接），hard-core 要的是"给定 f(x) 后仍难猜的位"，只能对随机化谓词成立。
- **M5-1**：GGM：G(s) = (G₀(s), G₁(s))。函数 f_s(x)：从根 s 开始，按 x 的每一位选择 G_{x_i} 分支，深度 |x| 后叶子即值。d 层每层 1 次 PRG 调用，共 d 次。安全性：hybrid 从叶到根逐层替换。
- **M5-3**：1 bit 输出足够——任何多 bit/自适应策略都能编码成单个 bit 判定（"是否输出 1"），且 oracle 自适应查询已含在区分者模型里。
- **M6-1**：design 保证任意两集合交集 ≤ log m 量级：改变一个输入位至多影响 O(log m) 个 f 调用；hybrid 每步只"动"一个坐标时，受影响的 f 调用数少 ⇒ 局部错误可被电路吸收 ⇒ 归约成立。
- **M6-2**：D 区分 G(U_k) 与 U_m ⇒ 存在 i 使 H_i 与 H_{i+1} 可分 ⇒ 由 f 的"局部可算"性，把 D 硬编码进电路，得到能算 f 的电路（大小 s(k)，与假设矛盾）。
- **M7-1**：空间 m 的自动机状态 ≤ 2^m 个；用 union bound 扫状态即可控制"碰撞"概率，而时间受限的区分者没有这种可枚举结构。
- **M8-2**：3 个变量需要 3 路独立；pairwise 族可构造 X₃ = X₁⊕X₂（在 GF(2) 上）使三者线性相关，任意两两独立但三者不独立。
- **M8-3**：bias(S) = E[∏_{i∈S} χᵢ] ≤ ε ⟹ 对任意线性测试 L(x) = ⊕_{i∈S} xᵢ，|Pr[L(X)=1]−Pr[L(U)=1]| ≤ ε/2（用 E[χ_L(X)] = bias(S)，Fourier 系数即 bias）。
- **M9**：extractor 定义与 Trevisan 构造见 ln00b L4；XOR Lemma 陈述与 GNW 证明骨架见 p_yao.html。

---

## 5. 卡片模板

```
定义卡：<名词>
- 形式定义（原文 + 自己版本）
- 关键量词顺序
- 直观含义（一句话）
- 反例/边界情形

定理卡：<编号+名字>
- 陈述（条件/结论）
- 证明骨架（3-5 步）
- 用到的技法（hybrid? 归约? 平均论证?）
- 为什么重要 / 用在哪儿
```

---

## 6. 完成标准（自评）

- [ ] 能默写 CI 与 PRG 的完整定义（含所有量词）
- [ ] 能独立写出 hybrid argument 的完整证明（多采样 + stretch 放大）
- [ ] 能画出 OWF ⟺ PRG 双向证明依赖图并解释每步
- [ ] 能讲清楚 NW 生成器为什么需要 design 和平均情况困难
- [ ] 能对比 general-purpose / derandomization / space-bounded / special-purpose 四类生成器的三基本面
- [ ] 完成全部检查点与必做练习
- [ ] （进阶）能陈述 extractor 定义与 Trevisan 构造的对应关系

---

## 7. 配套资料索引

- 页面：https://www.wisdom.weizmann.ac.il/~oded/c-indist.html
- 主教材 PDF（已下载）：`materials/prg08.pdf`（含文本版 `prg08.txt`）
- 讲稿 Part I（已下载）：`materials/ln00a.pdf` / `ln00a.txt`
- 讲稿 Part II（已下载）：`materials/ln00b.pdf` / `ln00b.txt`
- 出版版 primer（AMS ULECT-55, 2010）：`PDF/prg10.pdf`（未下载，需要时说一声）
- XOR Lemma：https://www.wisdom.weizmann.ac.il/~oded/p_yao.html
