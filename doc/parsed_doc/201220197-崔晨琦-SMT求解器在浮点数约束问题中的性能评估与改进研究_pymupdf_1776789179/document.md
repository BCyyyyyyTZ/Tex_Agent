
<!-- page 1 -->

# 本科毕业论文

### 院
系
计算机科学与技术系

### 专
业
计算机科学与技术

### 题
目SMT 求解器在浮点数约束问题中

### 的性能评估与改进研究
年
级
2020
学
号201220197

### 学生姓名
崔晨琦
指导教师
王豫
职
称助理研究员

### 提交日期
2024 年5 月13 日


<!-- page 3 -->

## 南京大学本科生毕业论文（设计、作品）中文摘要
题目：SMT 求解器在浮点数约束问题中的性能评估与改进研究
院系：计算机科学与技术系
专业：计算机科学与技术
本科生姓名：崔晨琦
指导教师（姓名、职称）：王豫
助理研究员
摘要：
可满足性模理论（Satisfiability Modulo Theories, SMT）是在特定背景理论下
判断一阶逻辑公式是否可满足的问题，在软件测试、程序验证、静态分析等许
多领域都有应用，这些领域的很多问题都可以被转变为SMT 擅长描述和求解的
约束可满足性问题。浮点数背景理论是SMT 的背景理论之一，是一种重要理论，
实际问题中常常会出现数据用浮点数表示的情况，因此SMT 求解器经常需要求
解浮点数约束问题。但由于浮点数背景理论的复杂语义和精度缺陷等原因，SMT
求解器在面对一些复杂的、非线性的浮点数约束时通常会遇到困难、表现不佳。
为了了解和探索当前的SMT 求解器对浮点数约束问题的性能表现和能力范
围，本文选取了4 个SMT 求解器进行性能评估，分别是当前表现最好的主流
SMT 求解器之一Z3 与针对浮点数约束问题的JFS，XSat 和goSAT。从这4 个
SMT 求解器在选取的浮点数约束测试数据集上的实验结果来看，Z3 这类主流
SMT 求解器具有较好的稳定性，能应对更大范围的问题，而JFS，XSat 和goSAT
这类将浮点数约束问题转变为优化问题等其他问题的SMT 求解器具有更少的求
解时间和更多的求解数目。
本文根据XSat 将求解浮点数约束问题转变为求目标函数最小值点问题的基
本原理和XSat 在实际实现中的可改进之处，提出了两种基于启发式策略的帮助
求最小值点的改进方法，并设计了4 组实验进行测试，证明了这两种方法及其组
合能有效减少求解时间。
关键词：可满足性模理论（SMT）；SMT 求解器；浮点数约束；启发式策略
I


<!-- page 5 -->

## 南京大学本科生毕业论文（设计、作品）英文摘要
THESIS: Evaluation and Improvement of SMT Solvers in Soving Floating-Point
Constraints
DEPARTMENT: Department of Computer Science and Technology
SPECIALIZATION: Computer Science and Technology
UNDERGRADUATE: Chenqi Cui
MENTOR: Assistant researcher Yu Wang
ABSTRACT:
Satisfiability Modulo Theories(SMT) are the problems of determining the satis-
fiability of first-order logic formulas with specific background theories, which can be
applied in many fields, such as software testing, program verification and static analysis.
Many problems in these fields can be transformed to constraint satisfiability problems
which SMT is good at expressing and solving. Floating-point background theory is one
of the background theories of SMT, and it is an important theory. In practical problems,
data is often represented as floating-point numbers, so SMT solvers often need to solve
floating-point constraints. But due to the complex semantics, precision deficiency and
other problems of the floating-point background theory, SMT solvers often run into
difficulties when solving complex, non-linear floating-point constraints.
In order to research and explore the performance and capability of current SMT
solvers when solving floating-point constraints, this paper selected four SMT solvers for
evaluation, namely one of the state-of-the-art SMT solvers, Z3, and three SMT solvers
which are focus on floating-point constraints, JFS, XSat and goSAT. From the exper-
imental results of these SMT solvers on the selected floating-point constraints bench-
marks, it can be seen that the state-of-the-art SMT solvers, such as Z3, have better
stability and capability, while SMT solvers which transform floating-point constraints
to optimization problems and other problems, such as JFS, XSat and goSAT, have less
solving time and more solving results.
In this paper, according to the idea of XSat transforming floating-point constraints
to the problem of searching for the minimum point of objective functions and the de-
III


<!-- page 6 -->
ficiencies of XSat in implementation, two methods based on heuristic strategy to help
find the minimum point are proposed. Four experiences are designed to test the two
methods, proving that these methods and their combination can effectively reduce the
solving time.
KEYWORDS: Satisfiability Modulo Theories (SMT); SMT solver; floating-point con-
straints; heuristic
IV


<!-- page 7 -->

# 目
录
第一章绪论. . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . .
1
1.1
研究背景及意义. . . . . . . . . . . . . . . . . . . . . . . . . . . . .
1
1.2
相关工作. . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . .
2
1.2.1
SMT 求解技术. . . . . . . . . . . . . . . . . . . . . . . . . .
2
1.2.2
SMT 求解器. . . . . . . . . . . . . . . . . . . . . . . . . . .
3
1.2.3
SMT-LIB 和SMT-COMP . . . . . . . . . . . . . . . . . . . .
4
1.3
本文研究内容
. . . . . . . . . . . . . . . . . . . . . . . . . . . . . .
5
1.4
本文结构. . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . .
5
第二章背景知识. . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . .
7
2.1
SMT 相关概念. . . . . . . . . . . . . . . . . . . . . . . . . . . . . .
7
2.1.1
SAT . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . .
7
2.1.2
SMT
. . . . . . . . . . . . . . . . . . . . . . . . . . . . . . .
8
2.2
浮点数背景理论. . . . . . . . . . . . . . . . . . . . . . . . . . . . .
9
2.3
优化问题及其算法. . . . . . . . . . . . . . . . . . . . . . . . . . . .
11
2.4
启发式策略. . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . .
11
第三章SMT 求解器的评估. . . . . . . . . . . . . . . . . . . . . . . . .
13
3.1
待评估的SMT 求解器. . . . . . . . . . . . . . . . . . . . . . . . . .
13
3.1.1
Z3 . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . .
13
3.1.2
JFS . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . .
14
3.1.3
XSat . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . .
15
3.1.4
goSAT
. . . . . . . . . . . . . . . . . . . . . . . . . . . . . .
16
3.2
测试数据集. . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . .
17
3.3
评估方法. . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . .
17
V


<!-- page 8 -->
第四章SMT 求解器的改进研究. . . . . . . . . . . . . . . . . . . . . .
19
4.1
XSat 可改进的地方
. . . . . . . . . . . . . . . . . . . . . . . . . . .
19
4.2
改进方法与实现. . . . . . . . . . . . . . . . . . . . . . . . . . . . .
19
4.2.1
目标函数的代码形式. . . . . . . . . . . . . . . . . . . . . .
19
4.2.2
比例过滤. . . . . . . . . . . . . . . . . . . . . . . . . . . . .
20
4.2.3
迭代更新. . . . . . . . . . . . . . . . . . . . . . . . . . . . .
23
4.2.4
两个方法的组合. . . . . . . . . . . . . . . . . . . . . . . . .
24
第五章实验分析. . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . .
27
5.1
实验环境. . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . .
27
5.2
评估分析. . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . .
27
5.2.1
SMT 求解器配置
. . . . . . . . . . . . . . . . . . . . . . . .
28
5.2.2
测试数据集分析. . . . . . . . . . . . . . . . . . . . . . . . .
28
5.2.3
评估结果与分析. . . . . . . . . . . . . . . . . . . . . . . . .
29
5.3
改进研究. . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . .
32
5.3.1
实验设计. . . . . . . . . . . . . . . . . . . . . . . . . . . . .
32
5.3.2
效果分析. . . . . . . . . . . . . . . . . . . . . . . . . . . . .
35
第六章总结与展望
. . . . . . . . . . . . . . . . . . . . . . . . . . . . . .
39
6.1
总结. . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . .
39
6.2
不足与展望. . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . .
39
参考文献
. . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . .
41
致
谢
. . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . .
45
VI


<!-- page 9 -->

# 第一章
绪论

## 1.1
研究背景及意义
随着科技不断发展，人类社会进入信息化时代，越来越多的计算机软、硬件
走入人们的工作和生活中。在计算机技术不断进步的同时，软、硬件也变得越来
越复杂，如何确保软、硬件的正确性和可靠性成为计算机领域的重要研究问题之
一。在20 世纪80 到90 年代，人们开始重视用形式化方法（Formal Methods）对软、
硬件进行开发和验证，进而出现了包括以布尔可满足问题（Boolean Satisfiability
Problem, SAT）和可满足性模理论（Satisfiability Modulo Theories, SMT）为代表
的约束求解的形式化验证技术，并开发出了相关工程化工具[1]。如今，SMT 求
解技术和求解器已经被广泛运用于程序缺陷的检测与验证、静态分析、自动生
成测试用例、RTL 验证、云计算和云存储等领域[2]，具有很大研究意义。
SMT 是在SAT 的基础上发展而来的。SAT 问题研究命题逻辑公式的可满足
性，即给定一个布尔表达式，能否找到某种布尔变量的赋值方式使得表达式为
真。SAT 在1971 年被证明为非确定性多项式完全（Non-deterministic Polynomial
Complete, NPC）问题，也是第一个被证明了的NPC 问题，在硬件测试、电路验
证等许多领域都有广泛应用，很多实际问题都可以转化为SAT 问题[2]。但随着
SAT 的深入研究和应用，人们发现只面向命题逻辑的SAT 的表达能力较为有限，
很多实际问题在转变为SAT 问题进行求解时会丢失信息，这给人们带来了不便，
也会让结果不准确，同时还会增大问题规模和复杂性[3]，所以人们将SAT 问题
扩展为表达能力更强的SMT 问题。SMT 在SAT 的基础上结合了背景理论，将命
题逻辑公式扩充为一阶逻辑公式，补充了量词和项等内容，公式中的命题变量可
以解释为背景理论公式，因此SMT 具有更强的表达能力和更高的抽象层次[2,4]。
SMT 的常用背景理论包括整数、实数、浮点数、线性算术、非线性算术、数组、
位向量、字符串、未解释函数、差分逻辑等理论和它们的组合。
为了解决SMT 问题，人们开始研究SMT 求解技术，并研发了许多SMT 求
1


<!-- page 10 -->
解器。目前SMT 求解技术已经对一些背景理论以及这些背景理论的部分组合有
了优秀的判定方法，但仍存在局限性，例如对于带量词的或非线性算术领域的
一阶逻辑公式尚未有完全判定方法[5]。浮点数背景理论的SMT 求解问题，即浮
点数约束问题正是目前SMT 求解技术会陷入困难的问题之一。浮点数背景理论
是一种重要理论，实际问题中经常会遇到，在测试用例自动生成、程序合成等领
域都有应用[6]，但SMT 求解器在面对复杂的、非线性的浮点数约束时，由于浮
点数理论的复杂语义、精度缺陷等问题，常常会表现不佳[6-7]，因此评估和提升
SMT 求解器对浮点数约束的求解性能是十分有意义的。

## 1.2
相关工作
SMT 求解技术的研究起源于20 世纪70 年代末80 年代初，在20 世纪90 年
代，人们开始研究大规模问题的SMT 求解技术[8]。如今SMT 求解技术经历了蓬
勃的发展，许多SMT 求解器被研发出来，部分成熟的SMT 求解器还被集成到
了大型项目工具中，在学术界和工业界得到广泛应用。

## 1.2.1
SMT 求解技术
在SMT 求解技术的发展过程中，主要出现了三类算法策略，分别是积极类
算法（Eager 策略）[9]和惰性算法（Lazy 策略）[10]，以及DPLL(T) 策略[11]。
Eager 策略是在SMT 求解技术发展早期提出的方法，它首先根据不同背景
理论采用不同编码方式将一阶逻辑公式转变为等价的命题逻辑公式，即把SMT
问题转变为等价的SAT 问题，再用SAT 求解器进行求解。这一策略的优点是
不用为SMT 多种多样的背景理论开发理论求解器，缺点是过于依赖编码方式和
SAT 求解器的正确性，而且在处理规模稍大的问题时生成的公式长度会指数级
爆炸增长，因此难以应用到工业界中[2]。
Lazy 策略则是先在不考虑背景理论的情况下将SMT 公式当作SAT 公式求
解，若SAT 公式有解再利用理论求解器结合背景理论考察解的可行性，否则可
直接说明SMT 公式无解。Lazy 策略虽然需要专门设计理论求解器，但相比于
Eager 策略具有更好的扩展性，能更加灵活地处理大规模问题，因此很长一段时
间内的SMT 求解器都采用Lazy 策略[5]。
2


<!-- page 11 -->
DPLL(T) 策略是基于DPLL（Davis-Putnam-Logemann-Loveland）算法框架
的求解策略，将原本用于解决SAT 问题的DPLL 算法框架拓展到SMT 领域，可
用于建模实现Lazy 策略的一些变体，并同时具备Eager 策略的高效性和Lazy 策
略的灵活性[11]。DPLL 的基本思想是选择一个没有被赋值的命题变量进行赋值，
然后进行推导，如果没有冲突、能推导为真则SAT 公式可解，否则进行回溯，若
不能回溯则说明SAT 公式不可解。DPLL(T) 在DPLL 的基础上加入了可替换的
理论求解器部分，在推导时检查是否满足背景理论，并可以嵌入许多高效的启发
式策略，因而具有灵活的通用性和更高的效率，目前主流的SMT 求解器大多采
用DPLL(T) 策略[4]。

## 1.2.2
SMT 求解器
SMT 求解器是SMT 求解技术的具体实现[2]。随着SMT 求解技术的不断
发展，很多研究人员和科研机构积极开发和改进了许多SMT 求解器。目前主
流的SMT 求解器包括Z3[3]，CVC5[12]，MathSAT5[13]，Yices2[14]，Boolector[15]，
Bitwuzla[16]等，它们基本都支持多种背景理论及其组合，具有较好的求解能力，
有些已被集成在大型项目工具中，在许多领域发挥良好作用。另外也有专门研
究某一种背景理论的SMT 求解器，这些求解器在特定的背景理论下有时也会有
很好的表现，例如针对浮点数背景理论的JFS[17]，XSat[7]和goSAT[6]，它们将浮
点数约束问题转变为优化问题（optimization problem）等其他问题，再使用现成
的工具求解，从而避免了直接针对约束本身进行求解，因此具有更高的求解速
度[18]。Z3，JFS，XSat，goSAT 是本文待评估的SMT 求解器，将在第三章详细
介绍，这里简单介绍当前表现较好的CVC5，MathSAT5，Yices2 和Bitwuzla。
CVC5 是Barbosa 等人[12]在CVC3 和CVC4 的基础上开发的新求解器，采用
了基于DPLL 的改进算法CDCL（Conflict-Driven Clause Learning Algorithm）的
CDCL(T) 框架[19]。CVC5 的SMT Solver 模块由4 部分组成，分别是：对输入进
行预处理的Preprocessor、对公式进行抽象重写的Rewriter、对抽象后的公式进行
求解的Propositional Engine、检查解是否满足背景理论的Theory Engine。CVC5
支持多种背景理论及其组合，对无量词和量化公式都能很好地解决，在近年的
SMT-COMP 的多个赛道都取得了优秀成绩，目前已在Boogie，SPARK 等大型项
目中充当后端求解器[12]。
3


<!-- page 12 -->
MathSAT5 是Cimatti 等人[13]在MathSAT4 的基础上改进而来的新求解器，利
用DPLL(T) 框架和理论求解器进行求解，支持线性算术、位向量、数组、未解
释函数等大部分背景理论及其组合，并能为不可满足的SMT 公式提供具体的驳
斥证明[4]。MathSAT5 同样在SMT-COMP 取得过优异成绩，并已在工业界中得
到应用，例如在Intel 的RTL 形式化验证工具中充当后端工具[13]。
Yices2 是斯坦福大学的SRI International 研究院[14]在Yices 的基础上改进开
发的SMT 求解器，基于CDCL(T) 框架进行求解，支持整数和实数的线性算术、
位向量、数组、未解释函数、差分逻辑等多种背景理论及其组合，并对求解组合
背景理论的方法做出了改进。
Bitwuzla 是Niemetz 等人[16]为了解决Boolector 在架构上存在的局限而从零
开始重新开发的SMT 求解器，主要针对位向量、数组、浮点数、未解释函数等背
景理论的无量词和量化公式。Bitwuzla 的主要组件包括Node Manager 和Solving
Context，前者为后者构建数据结点，后者通过实现一个惰性SMT 范式Lemmas
on Demand[20]对SMT 公式进行求解，这也是Bitwuzla 相比于CVC5，MathSAT5
和Yices2 等基于DPLL(T) 和CDCL(T) 框架的求解器的主要区别。

## 1.2.3
SMT-LIB 和SMT-COMP
除了SMT 求解器自身的进步，SMT-LIB（Satisfiability Modulo Theories Li-
brary）标准[21]和SMT-COMP（International Satisfiability Modulo Theories Compe-
tition）竞赛[22]也为SMT 求解器的发展起到了很大作用。SMT-LIB 标准是目前
公认程度较高的SMT 研究标准[2]，它规定了SMT 求解器输入输出的语言规范，
对SMT 的不同背景理论进行分类，例如QF_BV（无量词位向量理论）、QF_AX
（无量词数组理论）、QF_FP（无量词浮点数理论）等，并定义了数据的表示形式、
对数据的各种操作等内容，形成了可基于不同背景理论的格式统一的测试集，使
得对SMT 求解器求解能力的评估和比较有了良好的标准。SMT-COMP 竞赛是
可满足性理论及其应用国际学术年会每年举办的当前SMT 领域公认度最高的比
赛[2]，利用来源于SMT-LIB 的标准测试用例集分不同赛道对SMT 求解器的性能
进行测试和评分，极大激发了研究者们对SMT 求解器的热情。
4


<!-- page 13 -->

## 1.3
本文研究内容
正如前文介绍，目前有许多SMT 求解技术和求解器，并且当前的SMT 求
解器在求解浮点数约束问题时还存在着困难。为了研究当前的SMT 求解器对浮
点数约束问题的性能表现和能力范围，探索进一步提升SMT 求解器对浮点数约
束问题的求解效果的方法，本文做了如下研究内容：
1. 选取当前表现较好的主流SMT 求解器Z3 和针对浮点数约束问题的JFS，
XSat，goSAT，详细了解它们的实现原理，并挑选浮点数背景理论的数据
集对选取的SMT 求解器进行测试，对它们在浮点数约束问题上的求解表
现进行性能评估。
2. 针对评估的SMT 求解器之一XSat 的实现原理和其在实际实现中存在的可
改进之处思考和实现了基于启发式策略的改进方法，并设计平行实验测试
了改进效果。

## 1.4
本文结构
本文共6 个章节，结构内容如下：
第一章为绪论，首先介绍了SMT 的发展历程和研究意义，接着介绍了SMT
的相关工作，包括SMT 求解技术和SMT 求解器的研究现状等，最后明确了本
文的研究内容和结构。
第二章为背景知识，主要介绍了SMT 的理论知识，重点介绍了SMT 背景
理论中的浮点数背景理论，还介绍了优化问题和启发式策略的相关概念与算法。
第三章为SMT 求解器的评估，详细介绍了待评估的4 个SMT 求解器：Z3、
JFS、XSat、goSAT 的基本原理和主要特点，并介绍了选取的测试数据集以及评
估方法。
第四章为SMT 求解器的改进研究，介绍了XSat 在实际实现中的可改进之
处，并提出了两个基于启发式策略的改进方法，描述了它们的具体实现方式。
第五章为实验分析，首先介绍了实验配置，接着介绍了SMT 求解器的的评
估结果，并进行了分析，最后展示了第四章提出的两个改进方法及其组合的改进
效果。
5


<!-- page 14 -->
第六章为总结与展望，总结了本文做的研究工作，指出了目前存在的不足之
处，并对未来的研究工作进行了展望。
6


<!-- page 15 -->

# 第二章
背景知识
本文研究关于浮点数背景理论的SMT 求解技术，并尝试利用启发式策略帮
助提高将浮点数约束问题转变为优化问题的SMT 求解器的求解效果，因此本章
将依次介绍SMT 的相关概念和浮点数背景理论，以及优化问题与启发式策略的
相关知识和算法。

## 2.1
SMT 相关概念
SMT 问题是判定结合了背景理论的一阶逻辑公式是否可满足的问题，是对
SAT 问题的扩充，因此本节先从SAT 的相关概念开始介绍。

## 2.1.1
SAT
SAT 的研究对象是命题逻辑公式（propositional logical formula），即由取值
为真（true）或假（false）的布尔变量（称为命题变元）和与（∧）、或（∨）、非
（¬）、蕴含（→）、等价（↔）、异或（⊕）等布尔逻辑运算符组成的公式。命题逻
辑公式具有以下定义和规则[2]：
1. 单独的命题变元也是命题逻辑公式，此时也可称为原子公式；
2. 若𝑓是命题逻辑公式，则¬𝑓也是命题逻辑公式；
3. 若𝑓1 和𝑓2 是命题逻辑公式，则𝑓1 ⟂𝑓2 也是命题逻辑公式，其中⟂指∧，
∨，¬，→，↔，⊕等；
4. 命题变元𝑓及其否定¬𝑓统称为文字，若干文字的析取（∨）称为一个子句，
若干子句的合取（∧）称为一个合取范式（Conjunctive Normal Form, CNF）；
5. 给命题逻辑公式中的所有命题变元赋值为真或者假的一种赋值方案称为一
种指派，一种指派连同以此得到的命题逻辑公式的真值称为该公式的一种
解释。
7


<!-- page 16 -->
在以上关于命题逻辑公式的定义和规则的基础上，SAT 问题可以描述为：给
定一个CNF 形式的命题逻辑公式𝑓，判断是否存在一种指派使得𝑓为真，若存在
则说明𝑓是可满足的（satisfiable, sat），否则说明𝑓是不可满足的（unsatisfiable,
unsat）。

## 2.1.2
SMT
SMT 的研究对象是一阶逻辑公式，它在命题逻辑公式的基础上加入了量词、
谓词、函数、项等如下内容[4]：
1. 量词（quantifier）包括全称量词（∀）和存在量词（∃），另外无量词（quantifier-
free, QF）公式也是SMT 的研究内容，本文主要关注无量词的SMT 公式；
2. 谓词和函数用于描述个体变元的性质和个体间的映射关系；
3. 项（term）由如下规则递归定义：公式中所有变量、常量是项；若𝑓是n
元函数，且每个参数𝑡𝑖均为项，则函数表示式𝑓(𝑡1, …, 𝑡𝑛) 也是项。
此外SMT 还在SAT 的基础上加入了背景理论，这是让SMT 具有更强表达
能力的关键。对于一个SMT 公式𝐹和一个背景理论𝑇，若存在一种赋值方案𝛼
使得𝐹和𝑇能同时满足，则称𝐹是𝑇-可满足的，𝛼就是该SMT 公式𝐹的解，
也被称为理论模型（model），记作𝛼⊧𝐹。因此SMT 问题可描述为判断SMT 公
式是否是𝑇-可满足的，并等价于判断𝐹是否存在一个理论模型[5]。例如下面的
SMT 公式：

### 例1 (𝑥+ 𝑦⩽10) ∧(𝑥⩾5)
例1 的命题逻辑形式是𝑓1 ∧𝑓2，其中的命题变量𝑓1 和𝑓2 在线性算术背景
理论下解释为两个不等式𝑥+ 𝑦⩽10 和𝑥⩾5，能否找到𝑥和𝑦的某种赋值方式
使得两个不等式同时成立就是要求解的问题。SMT 的背景理论包括：
1. 线性算术理论，包括基于整数集的线性算术（Linear Integer Arithmetic, LIA）
和基于实数集的线性算术（Linear Real Arithmetic, LRA），以及它们的混合。
该种理论公式表现为不等式或等式，其中的变量数据类型是整数或者实数，
符号只包含+，−，=，≠，⩽，⩾，例如(𝑥+ 𝑦⩽5) ∧(𝑥–𝑧= 10)；
8


<!-- page 17 -->
2. 非线性算术理论，该理论是线性算术理论的拓展和延伸，同样基于整数集
（Non-Linear Integer Arithmetic, NIA）或实数集（Non-Linear Real Arithmetic,
NRA），包含了乘、除、取余等非线性操作，可用于表述任意形式的数学表
达式[2]；
3. 差分逻辑理论，该理论是线性算术的一部分，包括整数差分逻辑（Integer
Difference Logic, IDL）和实数差分逻辑（Rational Difference Logic, RDL），形
式表现为两个变量的差值等于或小于等于常量，例如(𝑥−𝑦⩽3)∧(𝑦–𝑧= 10)。
差分逻辑的作用在于可以将SMT 公式建模为以顶点表示变量、带权有向
边表示约束条件的加权有向图，例如𝑥−𝑦⩽3 表示𝑦到𝑥有权重为3 的
有向边，再通过检查该图是否存在权重之和为负的回路来高效地判断SMT
公式的可满足性，若不存在则说明公式可满足，否则说明不可满足[4,23]；
4. 数组理论（Arrays, A），用于表示高级编程语言中数组的相关操作，如
𝑟𝑒𝑎𝑑(𝑎, 𝑖) 表示读取数组𝑎的第𝑖个位置的元素，𝑤𝑟𝑖𝑡𝑒(𝑎, 𝑖, 𝑣) 表示将数组𝑎
第𝑖个位置的元素设置为𝑣；
5. 位向量理论（Bit Vectors, BV），用于表示位向量中的各种位运算操作，例
如取反、与、或、异或、左移和右移等；
6. 未解释函数理论（Uninterpreted Functions, UF），用于表示还没有经过解释
的抽象函数；
7. 字符串等其他理论。
此外，由于实际问题的复杂和多元性，SMT 通常会面临需要同时处理多种
背景理论的情况，因此产生了将多种背景理论组合在一起的理论，称为组合理
论，例如数组、未解释函数、整数线性算术的组合理论（AUFLIA），并出现了
处理组合理论的判定方法，包括Nelson-Oppen（NO）方法[24]，Delayed Theory
Combination（DTC）方法[25]和Ackerman 方法[26]，这些方法也被广泛用于SMT
求解技术中。

## 2.2
浮点数背景理论
本文关注的背景理论是浮点数背景理论（Floating Point, FP），该理论包括多
种精度的浮点数类型以及各种操作。SMT-LIB 基于IEEE 754-2008 标准[27]对浮
9


<!-- page 18 -->
点数制定的格式和运算来表示浮点数和相关操作[21]，主要表示规则如下：
1. 浮点数类型表示为Float16，Float32，Float64 和Float128，分别对应IEEE
binary16，binary32，binary64 和binary128 形式。Float32 和Float64 即为32
位单精度和64 位双精度的浮点数类型；
2. 具体数值用二进制位向量的形式表示，以及用NaN 和±oo 表示非数和正负
无穷，例如：

### 例2 (fp #b1 #b01111110 #b11111111111111111111111)
3 个#b 开头的二进制位向量分别表示浮点数的符号位（Sign）、阶码（Ex-
ponent）、尾数（Mantissa），例2 表示的浮点数数值为-0.9999999403953552；
3. 运算操作主要包括：abs（取绝对值），neg（取负），add（加），sub（减），
mul（乘），div（除），fma（融合乘加，如𝑥∗𝑦+ 𝑧），sqrt（取平方根），
rem（取余），min/max（取最小/大值），leq（小于等于）等大小关系判断，
isPositive（是正数）等数值特征判断；
4. 由于浮点数是计算机用于近似表示现实中某实数的数据类型，所以在运算
中还需要规定舍入模式（rounding mode），在SMT-LIB 中包括RNE（向最
近的偶数舍入），RTP（向正无穷舍入），RTZ（向零舍入）等模式。
下面是一个简单的SMT-LIB 格式的无量词浮点数约束（QF_FP）示例：

### Listing 2.1: QF_FP 示例
1 (declare-fun a () Float64)
2 (declare-fun b () Float64)
3 (declare-fun c () Float64)
4 (assert (fp.eq (fp.add RNE a b) (fp.add RNE b c)))
5 (check-sat)
Listing 2.1 首先声明了3 个Float64 类型的浮点数变量a，b，c，然后提出约
束a + b = b + c，相加时舍入模式为RNE，最后判断可满足性。
10


<!-- page 19 -->

## 2.3
优化问题及其算法
优化问题一般指寻找最优解的数学问题，本文关注XSat 和goSAT 将SMT
求解问题转换为求目标函数（objective function）最小值点的优化问题，该优化
问题中的目标函数定义如下[6-7]：

### 定义2.3.1 给定一个无量词浮点数约束公式𝑐(𝑥)，𝑥∈𝐹𝑃𝑛，𝑐(𝑥) 可对应为
一个目标函数𝑓(𝑥)，𝑓(𝑥) 满足如下规则：
1. 𝑓(𝑥) 非负，即∀𝑥∈𝐹𝑃𝑛, 𝑓(𝑥) ⩾0；
2. 𝑓(𝑥) 的所有零点等价于𝑐(𝑥) 的所有解，即𝑓(𝛼) = 0 ⇔𝛼⊧𝑐(𝑥)。
从定义2.3.1 可以看出，若能找到目标函数的最小值点，即解决这个优化
问题，就能得到对应SMT 公式的可解性。本文采用Python 的SciPy 库[28]中的
scipy.optimize.fmin_cg1（简称fmin_cg）求解目标函数的最小值点。fmin_cg 实现
了一种较快的梯度下降算法：共轭梯度算法（Conjugate Gradient, CG）[29]，其基
本思路是从初始猜测点（initial guess）出发，沿着负梯度方向做线性搜索迭代
到该方向上的最小值点，再利用梯度等信息计算出新的共轭的下降方向和步长，
反复迭代直到得到函数的最小值点。fmin_cg 在目标函数只有全局最小值和选取
的初始猜测点接近最小值点时会有更好的表现，所以更适用于局部优化（local
optimization）[28]。

## 2.4
启发式策略
启发式策略（heuristic strategy）是指基于直观感受和实际经验帮助求解优化
问题实例的方法，不能保证找到最优解，但通常可以找到较优解或者可行解。一
些基于启发式策略思想的算法框架目前已得到广泛运用，例如爬山算法、模拟
退火算法、基因算法、进化策略、粒子群优化算法等[30]。这类算法的特点是模
仿自然界中的现象规律，例如基因算法模仿生物进化原理，将基因复制、交叉、
变异等操作用于筛选和生成候选解，经过多轮“进化”来寻找最优解；又例如粒
子群算法模仿自然界中鸟类等动物的群体行为，设立多个粒子，让各个粒子根
据自身和群体的信息进行搜索，从而寻找最优解。本文主要针对目标函数最小
1
https://docs.scipy.org/doc/scipy/reference/generated/scipy.optimize.fmin_cg.html
11


<!-- page 20 -->
值点的实际求解过程提出帮助选取初始猜测点的启发式策略，从而使得fmin_cg
能更好地求解。
12


<!-- page 21 -->

# 第三章
SMT 求解器的评估
目前已有许多研究人员针对浮点数背景理论的SMT 问题研究求解技术和开
发求解器，为了明确当前的SMT 求解器对浮点数约束问题的性能表现和能力范
围，了解SMT 求解器在浮点数约束问题中遇到的困难，探索进一步提升SMT 求
解器对浮点数约束问题求解效果的改进方法，本文选取了4 个SMT 求解器和1
个SMT-LIB 格式的无量词浮点数约束测试数据集（QF_FP benchmarks）进行评
估和分析。

## 3.1
待评估的SMT 求解器

## 3.1.1
Z3
Z3 是微软为解决软件验证和软件分析等领域的问题而研发的支持多种背景
理论的SMT 求解器，目前已经在工业领域得到应用，例如集成在Spec#/Boogie3、
Pex、HAVOC 等大型项目里[3]。Z3 是当前表现最好的主流SMT 求解器之一，具
有成熟的求解技术和工具框架，在SMT-COMP 也一直表现优秀，并且有良好的
扩展性。图3-1 是Z3 的体系架构图。
Z3 接收输入的SMT 公式后，先利用Simplifier 对公式进行初步的简化，降低
公式的复杂程度，然后使用Compiler 将公式转换为由子句集和congruence-closure
nodes 组成的特殊数据结构。Z3 采用基于DPLL 算法的SAT 求解器对SMT 公式
的命题逻辑形式进行赋值，核心理论求解器Congruence closure core 处理该赋值
以及SMT 公式中的未解释函数和等式。Theory Solvers 是处理线性算术、位向
量、数组等理论的附属求解器（satellite solvers），帮助Congruence closure core
处理这些背景理论及其组合。E-matching 则是用于处理量词的抽象机（abstract
machine）。
13


<!-- page 22 -->

### 图3-1
Z3 的体系架构

## 3.1.2
JFS
JFS 是Liew 等人[17]开发的主要求解浮点数约束的SMT 求解器，将基于覆
盖引导的模糊测试方法（coverage-guided fuzzing）运用在了浮点数约束求解问题
中，其主要思想是将SMT 公式转变为一个程序，该程序的输入对应SMT 公式
里的自由变量赋值，并把SMT 公式里的每个约束都对应转变为一个if-else 语句
块，如果某个约束不满足就会在对应的else 语句返回0 退出，只有满足全部约束
才能通过所有if-else 语句块达到一个返回1 的语句（称为target），此时程序的输
入就对应SMT 公式的解。例如2.2 节的Listing 2.1 表示的SMT 约束可以转变为
如下的C++ 程序：

### Listing 3.1: JFS 程序示例
1 int FuzzOneInput(const uint8_t * data , size_t size){
2
double a = makeFloatFrom(data , size , 0, 63);
3
double b = makeFloatFrom(data , size , 64, 127);
4
double c = makeFloatFrom (data , size , 128, 191);
14


<!-- page 23 -->
5
double a_plus_b = add_rne(a, b);
6
double b_plus_c = add_rne(b, c)
7
if (a_plus_b == b_plus_c) {} else return 0;
8
return 1; // TARGET REACHED
9 }
第1 行的FuzzOneInput 接收size 字节的data 作为输入，第2-4 行分别用data
的第0-63 位、64-127 位、128-192 位构造64 位的浮点数变量a，b，c，第5-6 行
得到a 和b、b 和c 在RNE 舍入模式的相加结果，第7 行对应Listing 2.1 第4 行
的约束，即判断a + b 是否与b + c 相等，如果相等则能通过该if-else 语句块，到
达第8 行的target 语句返回1，否则返回0。
JFS 利用基于覆盖引导的模糊测试工具（coverage-guided fuzzer）反复调用
FuzzOneInput，每次提供不同的输入，寻找能覆盖所有if-else 语句块达到target 的
输入，从而找出SMT 公式的解，或者达到资源限制停止寻找，因此JFS 是sound
和incomplete 的，即找到的解是可以信任为一定正确的，但由于资源限制无法完
全证明SMT 公式是unsat 的[17]。

## 3.1.3
XSat
XSat 是Fu 等人[7]针对浮点数约束问题开发的SMT 求解器，建立了浮点数
约束可满足性问题与一类优化问题之间的等价关系，从而避免了直接对复杂的
浮点数约束进行编码和推理。XSat 将浮点数约束公式转化为满足2.3 节的定义
2.3.1 的目标函数𝑓(𝑥)，𝑓(𝑥) 的返回值表示输入𝑥与约束的解之间的距离，当距
离为0 时就说明𝑥是约束的解，若距离的最小值大于0 则说明约束不可解。例如
约束𝑥⩽4 可转变为如下的分段函数：
𝑓(𝑥) =
⎧⎪
⎨
⎪⎩
0
if 𝑥⩽4
(𝑥−4)2
𝑜𝑡ℎ𝑒𝑟𝑤𝑖𝑠𝑒
(3-1)
𝑓(𝑥) 每个最小值点（即值为0 的点）实际上就是𝑥⩽4 的每个解，因此约束
求解问题被转变为了求目标函数的最小值点问题。XSat 采用马尔可夫链蒙特卡
15


<!-- page 24 -->
洛方法（Monte Carlo Markov Chain method, MCMC）[31]求解函数的最小值点。在
具体实现方面，XSat 先用一个code generator 生成目标函数的C 语言代码，再用
Python 的SciPy 库中的scipy.optimize.basinhopping1（简称basinhopping）作为求
函数最小值点的方式。basinhopping 实现了MCMC 的一种变体：盆地跳跃算法
（Basin Hopping, BH）[32]，其基本思路是先从随机的初始位置𝑥0 开始，利用局部
优化算法（例如2.3 节介绍的fmin_cg）得到𝑥0 附近的极小值点（即“盆地”）作
为候选解，再对𝑥0 进行某种扰动，从而“跳跃”到另一个位置𝑥1，用同样的方
式得到𝑥1 附近的极小值点（即新的“盆地”）作为候选解，经过反复迭代后得到
一系列候选解，从中选出最小的作为全局最小值点。该算法的优势在于可以利用
“跳跃”避免被困在局部的最小值点。
XSat 与JFS 一样都是sound 和incomplete 的。因为目标函数是非负的，如果
能得到目标函数的最小值为0 则说明对应的SMT 公式一定是sat 的，但仍可能
存在如下情况：目标函数存在为0 的最小值点，但XSat 在求解时得到了错误的
大于0 的“最小值点”，从而将实际是sat 的SMT 公式报告为unsat，因此XSat
无法完全证明SMT 公式是unsat 的。XSat 尚未支持所有浮点数背景理论的操作，
目前仅支持浮点数背景理论的算术操作，如fp.add（加），fp.mult（乘），fp.leq
（小于等于）等，但不支持fp.isNormal（是常数，即不是无穷或NaN）等其他操
作。

## 3.1.4
goSAT
goSAT 是Khadra 等人[6]对XSat 进行改进和再实现的SMT 求解器，其基本
原理和特点与Xsat 相同，都将浮点数约束问题转变为求目标函数最小值的优化
问题，但goSAT 采用即时编译方法（Just-in-Time (JIT) compilation）简化了将约
束公式转化为目标函数的步骤，使用起来比XSat 更加方便，还采用了功能更丰
富的优化工具NLopt[33]求解目标函数的最小值点，能解决的问题范围比BH 算
法更广。
1
https://docs.scipy.org/doc/scipy/reference/generated/scipy.optimize.basinhopping.html#scipy.optimize.basinhopping
16


<!-- page 25 -->

## 3.2
测试数据集
本文选取了JFS 的作者用于测试JFS 的数据集中的QF_FP 部分1作为用于评
估的测试数据集（benchmarks）。该benchmarks 部分来源于SMT-COMP 的竞赛
测试集，覆盖了浮点数背景理论的大部分语义操作，如：fp.lt（小于），fp.leq（小
于等于），fp.gt（大于），fp.geq（大于等于），fp.eq（等于），fp.add（加），fp.sub
（减），fp.mul（乘），fp.div（除），fp.neg（取负），fp.isNaN（非数），fp.isInfinite
（无穷），fp.isZero（零值），fp.isNormal（是常数）等浮点数操作，以及and，or，
not 等其他操作。
JFS 的作者还基于JFS 不能完全证明unsat 的局限性对该benchmarks 进行了
筛选，只保留了sat 和unknown（可满足性未知，这类情况SMT 求解器一般会
求解超时）的部分，而XSat 和goSAT 同样不能完全证明unsat，但Z3 可以。如
果用于测试的benchmarks 中存在unsat 的部分，将对JFS，XSat 和goSAT 的评
估带来不利的影响因素，因此该benchmarks 能更公平地测试Z3，JFS，XSat 和
goSAT 的求解能力。
在5.2.2 节将对该benchmarks 进行具体分析。

## 3.3
评估方法
为了评估当前SMT 求解器在浮点数约束问题中的性能表现，本文设计评估
方法流程如下：
1. 选取3.1 节介绍的Z3，JFS，XSat 和goSAT 作为待评估的SMT 求解器，并
安装这些求解器公开发布的稳定版本2, 3, 4, 5；
2. 选取3.2 节介绍的benchmarks，分析和记录其特征；
3. 在相同的实验环境中让Z3，JFS，XSat 和goSAT 分别对benchmarks 进行
求解，记录它们花费的时间和给出的判断结果；
1
https://github.com/mc-imperial/jfs-fse-2019-artifact/tree/master/data/benchmarks/3-stratified-random-
sampling/benchmarks/QF_FP
2
https://github.com/Z3Prover/z3
3
https://github.com/mc-imperial/jfs
4
https://github.com/zhoulaifu/xsat
5
https://github.com/abenkhadra/gosat
17


<!-- page 26 -->
4. 分析实验结果，评估SMT 求解器的性能表现。
18


<!-- page 27 -->

# 第四章
SMT 求解器的改进研究
第三章介绍的XSat 将浮点数约束问题转化为求目标函数最小值点的优化问
题进行求解，这一思路使得XSat 具有较快的求解速度（第五章的实验结果将表
明这一点），在了解其具体实现时，我们发现了一些可改进之处。本章将介绍
XSat 可改进的地方以及我们对此提出和实现的改进方法。

## 4.1
XSat 可改进的地方
Xsat 在具体的代码实现1里采用3.1.3 节介绍的basinhopping 求解目标函数
的最小值点，在此过程中会使用局部优化方法（例如2.3 节介绍的fmin_cg）得
到局部的最小值点。而fmin_cg 这类方法在选取的初始猜测点质量较高，即接近
最小值点时能更快、更准确地成功求解[28]，但XSat 并未对这方面进行专门的处
理，只进行了较为随意的选择。因此我们认为可以在选取初始猜测点的方式上进
行改进，让fmin_cg 使用更高质量的初始猜测点进行求解，从而提升求解效果。

## 4.2
改进方法与实现
我们提出并实现了2 个基于启发式策略的选取初始猜测点的改进方法：比
例过滤和迭代更新。我们使用Python 编写具体代码，在开始求解前会随机生成
一定数目的初始猜测点，并对这些初始猜测点进行改进，最后调用fmin_cg 使用
改进后的初始猜测点求解目标函数的最小值。

## 4.2.1
目标函数的代码形式
在介绍改进方法前，首先介绍我们的目标函数的代码形式。一个SMT 问题
通常会包含许多具体约束，对应目标函数的代码则会表现为有许多if-else 语句
块，例如2.1.2 节的SMT 公式例1 对应目标函数的Python 代码如下：
1
https://github.com/zhoulaifu/xsat/blob/master/xsat.py#L125
19


<!-- page 28 -->

### Listing 4.1: 目标函数示例
1 def objective_function(x0):
2
x, y = x0
3
segment0 = None
4
if (x + y) <= 10:
5
segment0 = 0.0
6
else:
7
segment0 = ((x + y) - 10) ** 2
8
segment1 = None
9
if x >= 5:
10
segment1 = 0.0
11
else:
12
segment1 = (5 - x) ** 2
13
return segment0 + segment1
第3 和8 行的segment0 和segment1 变量分别对应输入x 和y 与约束𝑥+ 𝑦⩽
10 和𝑥⩾5 的解之间的距离值，当x 和y 满足某个约束时，对应的segment 变量
就赋值为0，否则将赋值为非负的表达式（第4-7，9-12 行的if-else 语句块），最
后返回segment0 与segment1 的和。当这两个变量都为0，即两个约束都满足时，
目标函数的返回值才会是0，此时x 和y 的值就是例1 的解。

## 4.2.2
比例过滤
记初始猜测点为𝑥0，如果𝑥0 能满足SMT 公式中的所有约束就相当于直接
找到了该SMT 问题的解，因此在直观感受上，如果𝑥0 满足的约束数目越多，就
越可能接近真正的解（最小值点），fmin_cg 的求解效果就可能越好。另一方面，
由于fmin_cg 在运行时需要多轮迭代反复调用目标函数计算函数值以及进行其
他操作和处理，所以其开销远大于只调用一次目标函数的开销。基于这两个方面，
我们提出了如下方法流程寻找能尽量满足更多约束数目的𝑥0 提供给fmin_cg：
1. 根据目标函数的复杂程度设置𝑥0 需要预先满足的约束数目的比例𝑝𝑒𝑟𝑐𝑒𝑛𝑡𝑎𝑔𝑒，
并改写目标函数的代码形式（可见后文的Listing 4.2 ）；
20


<!-- page 29 -->
2. 将𝑥0 作为输入调用一次目标函数，并对𝑥0 满足的约束数目计数，判断𝑥0
满足的约束数目占总数的比例是否小于𝑝𝑒𝑟𝑐𝑒𝑛𝑡𝑎𝑔𝑒；
3. 如果𝑥0 满足的约束数目占总数的比例小于𝑝𝑒𝑟𝑐𝑒𝑛𝑡𝑎𝑔𝑒，则目标函数返回一
个特殊值表示直接过滤掉该𝑥0，不进入fmin_cg 求解，反之目标函数和该
𝑥0 将进入fmin_cg 求解。
相比于直接使用fmin_cg 求解，该方法额外花费了调用一次目标函数的开
销，但能过滤掉低质量的𝑥0，避免fmin_cg 使用低质量的𝑥0 花费大量时间求解，
从总体上降低开销和提升求解效果。
我们基于如下思路粗略地衡量目标函数的复杂程度：一个具体约束会涉及
到多个变量，该约束其实只要求涉及到的变量在某个取值范围内，对其他变量则
不做任何要求。因此我们认为约束涉及的变量种数越多该约束就越复杂，进而可
以使用所有约束的复杂程度衡量目标函数的总体复杂程度。具体采用如下计算
策略：
1. 记目标函数的变量个数为𝑣𝑎𝑟_𝑛，约束个数为𝑐𝑜𝑛𝑠_𝑛，每个约束涉及到的
变量种数之和为𝑐𝑜𝑛𝑠_𝑣𝑎𝑟_𝑛（如𝑥+ 𝑥+ 𝑦和𝑥−𝑦均涉及2 种变量，则
𝑐𝑜𝑛𝑠_𝑣𝑎𝑟_𝑛= 2 + 2 = 4）；
2. 此时可计算出平均每条约束涉及到的变量种数𝑐𝑜𝑛𝑠_𝑣𝑎𝑟_𝑛
𝑐𝑜𝑛𝑠_𝑛
，进而得到所有变
量中平均有
𝑐𝑜𝑛𝑠_𝑣𝑎𝑟_𝑛
𝑐𝑜𝑛𝑠_𝑛∗𝑣𝑎𝑟_𝑛比值的变量出现在每条约束里；
3. 该比值越高，说明目标函数越复杂，反之则越不复杂。
目标函数越复杂，𝑥0 满足约束的数目可能就越少，因此𝑝𝑒𝑟𝑐𝑒𝑛𝑡𝑎𝑔𝑒应该设
置低一些，否则绝大部分𝑥0 都会被直接过滤掉，很容易错失原本能成功求解的
𝑥0；反之则应该设置得高一些，让𝑥0 尽量满足更多的约束，起到过滤的效果。因
此实际的𝑝𝑒𝑟𝑐𝑒𝑛𝑡𝑎𝑔𝑒应该由
1 −
𝑐𝑜𝑛𝑠_𝑣𝑎𝑟_𝑛
𝑐𝑜𝑛𝑠_𝑛∗𝑣𝑎𝑟_𝑛
(4-1)
得到。此外，我们设置了一个区间[𝑙𝑜𝑤, ℎ𝑖𝑔ℎ] 作为𝑝𝑒𝑟𝑐𝑒𝑛𝑡𝑎𝑔𝑒的取值范围，避
免出现𝑝𝑒𝑟𝑐𝑒𝑛𝑡𝑎𝑔𝑒过高或过低的极端情况，影响到实际效果，根据实际测试中的
经验总结，该区间的数值设置为[0.3, 0.5]。综上，𝑝𝑒𝑟𝑐𝑒𝑛𝑡𝑎𝑔𝑒的计算公式如等式
4-2 所示：
21


<!-- page 30 -->
𝑝𝑒𝑟𝑐𝑒𝑛𝑡𝑎𝑔𝑒= (1 −
𝑐𝑜𝑛𝑠_𝑣𝑎𝑟_𝑛
𝑐𝑜𝑛𝑠_𝑛∗𝑣𝑎𝑟_𝑛) ∗(ℎ𝑖𝑔ℎ−𝑙𝑜𝑤) + 𝑙𝑜𝑤
(4-2)
采用比例过滤的方法后，目标函数的代码形式将在Listing 4.1 的基础上添
加对𝑥0 满足的约束数目计数和根据设置的比例判断是否要过滤𝑥0 的部分，如
Listing 4.2 所示：

### Listing 4.2: 改写后的目标函数示例
1 def new_objective_function(x0):
2
count = 0
3
x, y = x0
4
segment0 = None
5
if (x + y) <= 10:
6
count += 1
7
segment0 = 0.0
8
else:
9
segment0 = ((x + y) - 10) ** 2
10
segment1 = None
11
if x >= 5:
12
count += 1
13
segment1 = 0.0
14
else:
15
segment1 = (5 - x) ** 2
16
if count < 2 * 0.35: # cons_n * percentage
17
return 1e10
18
return segment0 + segment1
第2 行设置了计数变量count，并在第6 和12 行插入了因为满足约束而进
行的计数操作，在第16 和17 行对𝑥0 满足的约束比例进行判断（该目标函数
有2 个变量，和2 个分别涉及2 种、1 种变量的约束，因此根据公式4-2 可得
𝑝𝑒𝑟𝑐𝑒𝑛𝑡𝑎𝑔𝑒= (1 −2+1
2×2) × (0.5 −0.3) + 0.3 = 0.35），若小于设置的比例则返回特殊
22


<!-- page 31 -->
值1e10 表示𝑥0 应该被过滤掉，否则正常返回。
图4-1 表示了比例过滤方法的运行流程。
目标函数和
初始𝑥0 列表
设置𝑝𝑒𝑟𝑐𝑒𝑛𝑡𝑎𝑔𝑒，
改写目标函数代码形式
输入下一个𝑥0
调用目标函数
是否返回特殊值
进入fmin_cg 求解
过滤该𝑥0
否
是

### 图4-1
比例过滤的运行流程

## 4.2.3
迭代更新
fmin_cg 有时会因为某些原因（例如无法得到合适的下降步长等）不能正确
迭代到目标函数的最小值点，此时fmin_cg 会在最后停止迭代的位置𝑥𝑒𝑥𝑖𝑡退出。
但根据2.3 节介绍的梯度下降算法的基本流程可以知道，虽然𝑥𝑒𝑥𝑖𝑡不是真正的
最小值点，但相比于一开始的𝑥0，进行了下降操作的𝑥𝑒𝑥𝑖𝑡应该是更接近最小值
点的。基于这一思路，我们提出了如下方法帮助fmin_cg 对求解失败的目标函数
进行重新求解：
1. 获取上一次调用fmin_cg 求解失败时得到的𝑥𝑒𝑥𝑖𝑡；
2. 在𝑥𝑒𝑥𝑖𝑡附近选取新的𝑥0 提供给下一次fmin_cg 的求解；
3. 重复以上步骤，直到成功求解或达到资源限制。
在实际实现中，我们设置了一个值𝑑作为𝑥𝑒𝑥𝑖𝑡附近的搜索范围，即在区间
[𝑥𝑒𝑥𝑖𝑡−𝑑, 𝑥𝑒𝑥𝑖𝑡+ 𝑑] 内选取𝑥0 作为新的初始猜测点，而不是重新随机地选取𝑥0。
根据实际的测试表现，我们设置𝑑的值为100。
图4-2 表示了迭代更新方法的运行流程。
23


<!-- page 32 -->
目标函数和
初始𝑥0 列表
输入下一个𝑥0
进入fmin_cg 求解
是否求解成功
输出𝑥𝑒𝑥𝑖𝑡
在𝑥𝑒𝑥𝑖𝑡附近选取新的𝑥0
输出解，结束
否
是

### 图4-2
迭代更新的运行流程

## 4.2.4
两个方法的组合
上述两个方法从不同的方面对𝑥0 的选取进行了改进，在实际运用中它们可
以组合起来共同发挥作用，组合后的完整步骤如下：
1. 随机生成一定数目的初始𝑥0；
2. 根据目标函数的复杂程度设置𝑥0 需要预先满足的约束数目的比例𝑝𝑒𝑟𝑐𝑒𝑛𝑡𝑎𝑔𝑒，
并改写目标函数的代码形式；
3. 将当前𝑥0 作为输入调用一次目标函数，并对该𝑥0 满足的约束数目计数，
判断该𝑥0 满足的约束数目占总数的比例是否小于𝑝𝑒𝑟𝑐𝑒𝑛𝑡𝑎𝑔𝑒；
4. 如果该𝑥0 满足的约束数目占总数的比例小于𝑝𝑒𝑟𝑐𝑒𝑛𝑡𝑎𝑔𝑒，则目标函数返回
一个特殊值表示需要过滤掉该𝑥0，不进入fmin_cg 求解，直接处理下一个
𝑥0，反之将进入fmin_cg 求解；
5. 若当前𝑥0 未被过滤进入了fmin_cg 求解，则查看其求解结果：若求解成功，
则直接输出解结束求解，否则输出fmin_cg 最后停止迭代的位置𝑥𝑒𝑥𝑖𝑡；
6. 若fmin_cg 未求解成功，在𝑥𝑒𝑥𝑖𝑡附近选取新的𝑥0 作为之后输入的𝑥0，重
复上述第3 到5 步，直到求解成功或达到资源限制。
图4-3 表示了两个方法组合之后的运行流程。
24


<!-- page 33 -->
目标函数和
初始𝑥0 列表
设置𝑝𝑒𝑟𝑐𝑒𝑛𝑡𝑎𝑔𝑒，
改写目标函数代码形式
输入下一个𝑥0
调用目标函数
是否返回特殊值
过滤该𝑥0
进入fmin_cg 求解
是否求解成功
输出𝑥𝑒𝑥𝑖𝑡
在𝑥𝑒𝑥𝑖𝑡附近选取新的𝑥0
输出解，结束
否
是
否
是

### 图4-3
比例过滤和迭代更新组合后的运行流程
25


<!-- page 35 -->

# 第五章
实验分析
本章将介绍对选取的SMT 求解器：Z3，JFS，XSat 和goSAT 进行性能评估
的具体操作和结果，同时分析和总结了它们的表现，并设计了4 组实验测试第四
章提出的两种改进方法及其组合的实际效果，证明这两种方法能为求解目标函
数的最小值带来帮助，从而能实现对XSat 的改进。

## 5.1
实验环境
本文的实验在表5-1 所示的实验环境中进行，同时展示了实现改进方法时所
用的Python 及相关库：SciPy 和Autograd 的版本。

### 表5-1
实验环境
操作系统
Ubuntu 18.04.6 LTS
CPU
Intel(R) Xeon(R) Gold 5117 CPU @ 2.00GHz
RAM
64GB
Python 版本
Python 3.9.0
SciPy 版本
scipy 1.13.0
Autograd 版本
autograd 1.6.2

## 5.2
评估分析
本节将详细介绍对Z3，JFS，XSat 和goSAT 进行性能评估的具体操作，展
示评估结果并进行分析。
27


<!-- page 36 -->

## 5.2.1
SMT 求解器配置
目前JFS，XSat 和goSAT 都只公开发布了一个稳定版本，但Z3 是一个不断
更新的、发布过很多版本的SMT 求解器，我们在进行实验时选取了Z3 当时发
布的最新版本，表5-2 中展示了本文选取的SMT 求解器及其版本信息。

### 表5-2
SMT 求解器的版本
选取的SMT 求解器
版本信息
Z3
version 4.12.3 - 64 bit - build hashcode 19e9212
JFS
0.0.0.0(d38b368) (fse_2019_paper_version-3-gd38b368)
XSat
version 12/18/2015
goSAT
v0.1

## 5.2.2
测试数据集分析
我们选取在3.2 节介绍的测试数据集（benchmarks）对SMT 求解器进行评估。
该benchmarks 共有160 个SMT-LIB 格式的smt2 文件，每个文件代表一个QF_FP
理论的SMT 问题，其中声明了变量和具体约束。为了判断对应SMT 问题的复
杂程度从而比较SMT 求解器的求解能力和范围，本文统计了该benchmarks 每个
smt2 文件中declare-fun 语句（如Listing 2.1 第1-3 行）的个数，得到该benchmarks
中每个smt2 文件声明的变量数目𝑣𝑎𝑟_𝑛，并以此大致判断对应SMT 问题的复杂
程度，即𝑣𝑎𝑟_𝑛越大对应的SMT 问题越复杂。该benchmarks 根据𝑣𝑎𝑟_𝑛的范围
可分为以下3 部分：
1. 𝑣𝑎𝑟_𝑛< 10：共102 个smt2 文件；
2. 10 ⩽𝑣𝑎𝑟_𝑛⩽50：共37 个smt2 文件；
3. 𝑣𝑎𝑟_𝑛> 50：共21 个smt2 文件。
在统计和分析选取的SMT 求解器的评估结果时，我们统计了全部的结果和
按以上3 部分𝑣𝑎𝑟_𝑛分类后的结果，并分别进行分析。另外，正如3.2 节所介绍
的，该benchmarks 不包含unsat 的部分，只包含sat 或unknown，因此在评估的
时候我们将主要以SMT 求解器求解出sat 的数目作为SMT 求解器的评估指标之
一。
28


<!-- page 37 -->

## 5.2.3
评估结果与分析
我们按照在3.3 节介绍的评估方法流程对选取的SMT 求解器进行评估，编
写了Shell 脚本进行对benchmarks 的分析和对SMT 求解器的使用，并获取和统
计求解信息。
在使用选取的SMT 求解器对benchmarks 求解时，我们采用其默认的工作模
式，并设置超时时间为900 秒，利用Linux 的timeout 命令限制SMT 求解器的求
解时间。我们根据使用SMT 求解器进行求解的执行命令的返回值判断是顺利求
解完毕（返回值为0）还是发生了超时（返回值为124）或者报错（返回值为其
他非零值），并获取SMT 求解器的求解时间和报告信息，记录在csv 文件里。
Z3，JFS，XSat，goSAT 在选取的benchmarks 上的全部求解结果如表5-3 所
示，根据变量数目𝑣𝑎𝑟_𝑛分为3 部分后的结果分别如表5-4 ，表5-5 ，表5-6 所
示。表的第1 列是SMT 求解器的名称，第2 到5 列是求解结果，分别是：求解为
sat，求解为unsat 或unknown，求解超时（timeout）和报错（error），第6 列是对
benchmarks 求解花费的平均时间（单位秒，包括timeout 和error 的部分）。由于
goSAT 将不能判断为sat 的部分全部报告为unknown，而其他3 个SMT 求解器则
会报告unsat，并且我们更关注求解为sat 的数目，因此我们将unsat 和unknown
的数目放在一起记录。

### 表5-3
总体求解结果
SMT 求解器
sat
unsat/unknown
timeout
error
平均求解时间（秒）
Z3
89
0
71
0
464.708
JFS
87
0
73
0
420.427
XSat
100
24
5
31
42.497
goSAT
84
51
0
25
4.217

### 表5-4
𝑣𝑎𝑟_𝑛< 10 部分的求解结果
SMT 求解器
sat
unsat/unknown
timeout
error
平均求解时间（秒）
Z3
72
0
30
0
344.852
JFS
72
0
30
0
274.408
XSat
63
14
0
25
1.276
goSAT
61
20
0
21
0.066
29


<!-- page 38 -->

### 表5-5
10 ⩽𝑣𝑎𝑟_𝑛⩽50 部分的求解结果
SMT 求解器
sat
unsat/unknown
timeout
error
平均求解时间（秒）
Z3
16
0
21
0
561.198
JFS
14
0
23
0
565.134
XSat
28
3
0
6
3.703
goSAT
20
13
0
4
0.616

### 表5-6
𝑣𝑎𝑟_𝑛> 50 部分的求解结果
SMT 求解器
sat
unsat/unknown
timeout
error
平均求解时间（秒）
Z3
1
0
20
0
876.855
JFS
1
0
20
0
874.706
XSat
9
7
5
0
311.062
goSAT
3
18
0
0
30.719
我们根据表5-3 展示的总体结果从以下方面进行分析：
1. 在求解时间方面，Z3 花费的时间最久，有44.38% 的benchmarks 求解超
时；JFS 的求解时间略少于Z3，但仍属于比较久的程度，并且有45.63% 的
benchmarks 超时；而XSat 和goSAT 花费的时间则极大地少于Z3 和JFS，
到达了数量级的减少，timeout 的数目也很少或者没有。另外，goSAT 作为
在XSat 的基础上改进而来的SMT 求解器，求解时间也相对于XSat 有很
大提升。
从表5-3 的结果可得，XSat 花费的时间比Z3 少90.86%，比JFS 少89.89%，
而goSAT 花费的时间比Z3 少99.09%，比JFS 少99.00%，比XSat 少90.08%；
2. 在求解数目方面，Z3，JFS 和goSAT 在总体上的表现相近，XSat 的表现最
好，求解出了最多数目的sat 结果，比Z3 多12.36%，比JFS 多14.94%，比
goSAT 多19.05%；
3. 在求解器的稳定性方面，Z3 和JFS 具有较好的稳定性，没有出现error，也
没有报告unsat 或unknown；而XSat 和goSAT 的稳定性则稍差，分别有
19.38% 和15.62% 的benchmarks 出现了error，主要原因包括求解器自身
程序的不完善和部分benchmarks 中存在XSat 和goSAT 暂时不支持的浮点
数操作，例如fp.isZero（零值），fp.isNormal（是常数）等。此外XSat 和
goSAT 还报告了不少unsat/unknown，说明出现了如3.1.3 节最后介绍的求
30


<!-- page 39 -->
解错误的情况。
根据表5-4 ，表5-5 和表5-6 展示的按照变量数目分类后的结果，我们分别
进行了如下的分析：
1. 对于复杂程度较低的SMT 问题，Z3 和JFS 在求解数目和稳定性上的表现
相同，但JFS 的求解时间比Z3 少20.43%；XSat 和goSAT 的求解数目比Z3
和JFS 少，并且出现了一些求解错误和报错的情况，但求解时间仍然提升
很大：XSat 的求解数目比Z3 和JFS 少12.50%，求解时间比Z3 快99.63%，
比JFS 快99.53%；goSAT 的求解数目比Z3 和JFS 少15.28%，求解时间比
Z3 和JFS 快99.98%，比XSat 快94.83%；
2. 对于复杂程度适中的SMT 问题，JFS 在求解数目和时间上的表现接近但略
低于Z3，而XSat 和goSAT 的求解数目和时间则相比于Z3 和JFS 有很大提
升：XSat 的求解数目比Z3 多75.00%，比JFS 多100.00%，求解时间比Z3
和JFS 少99.34%；goSAT 的求解数目比Z3 多25.00%，比JFS 多42.86%，
求解时间比Z3 和JFS 少99.89%；XSat 的求解数目比goSAT 多40.00%，但
goSAT 的求解时间比XSat 少83.36%；另外，XSat 和goSAT 仍出现了错误
求解和报错的情况；
3. 对于复杂程度较高的SMT 问题，Z3 和JFS 都只求解出来了1 个，绝大部
分都超时了；XSat 和goSAT 求解出来了更多个，但求解出错的情况也较
多。在求解时间上，Z3 和JFS 表现很接近（因为绝大部分都超时了），而
XSat 花费的时间比Z3 少64.53%，比JFS 少64.44%，goSAT 花费的时间比
Z3 少96.50%，比JFS 少96.49%。
经过上面的分析，我们对选取的SMT 求解器的性能评估总结如下：
1. 相比于直接对浮点数约束进行推理的主流SMT 求解器，将浮点数约束问
题转变为优化问题等其他问题进行求解的SMT 求解器的求解能力更强，能
在求解时间上得到很大的提升，在求解数目上也能有所增加；
2. 将浮点数约束问题转变为优化问题等其他问题进行求解的SMT 求解器在
稳定性上可能存在不足（这也和SMT 求解器是否不断进行维护和更新有
关），会出现错误求解和程序报错的情况；
31


<!-- page 40 -->
3. 将浮点数约束问题转变为优化问题等其他问题进行求解的SMT 求解器的
能力范围比主流SMT 求解器小，存在只能完全证明sat、不能完全证明
unsat，以及不支持一些浮点数操作的问题。

## 5.3
改进研究
本节将详细介绍对第四章提出和实现的两种改进方法及其组合进行测试的
实验设计，并展示改进效果。

## 5.3.1
实验设计
我们采用Python 作为实验的编程语言，并从在3.2 节介绍的benchmarks 中
的160 个SMT 约束问题里选取了135 个转变为对应的目标函数，保存在py 文
件里，用于实现和测试两种改进方法，并记作original_objective_function。正如
5.2.2 节的分析，该benchmarks 不包含unsat 的部分，所以我们统计对目标函数
求得的最小值为0 的数目作为成功求解的数目，以此来判断改进效果。
我们首先利用正则匹配等操作解析original_objective_function 的代码文本，
按照4.2.2 节介绍的流程获取目标函数的变量个数、约束个数等用于计算过滤比
例的数据，从而将original_objective_function 的代码形式改写为如Listing 4.2 所
示的形式，并写入到了新的py 文件里，记作new_objective_function，用于实现
和测试比例过滤方法。
然后我们为每个目标函数随机生成初始的输入𝑥0，具体做法是根据每个目
标函数定义的变量参数个数，在[−1000, 1000] 范围内随机生成浮点数数组，共
生成500 组，保存在txt 文件里，即每个目标函数都有500 组随机生成的不同的
𝑥0 用于之后的求解。
最后我们使用在2.3 节介绍的fmin_cg 依次求解所有目标函数的最小值，并
对得到的最小值保留9 位小数判断其是否为0，进而判断是否求解成功，还设置
了每个目标函数的求解总时间限制为1800 秒。调用fmin_cg 时需要提供目标函
数的梯度作为参数，因此我们采用Python 的Autograd 库1中的grad 计算目标函
数的梯度。
1
https://github.com/hips/autograd
32


<!-- page 41 -->
我们分不同情况设计了如下4 组实验进行测试，并记录求解时间和成功数
目：
1. 不采用任何改进方法，使用original_objective_function 和对应的500 组初
始𝑥0 进行测试。每个目标函数将和它的一组𝑥0 进入fmin_cg 进行求解，若
解得的最小值不为0 则再使用下一组𝑥0 求解，直到求解成功，或者500 组
𝑥0 全部都没能求解成功，或者达到总时间限制，如Algorithm 1 所示；

### Algorithm 1 不采用任何改进方法
Input: The 𝑜𝑏𝑗𝑒𝑐𝑡𝑖𝑣𝑒_𝑓𝑢𝑛𝑐𝑡𝑖𝑜𝑛and the list of 𝑥0.
Output: The minimum of 𝑜𝑏𝑗𝑒𝑐𝑡𝑖𝑣𝑒_𝑓𝑢𝑛𝑐𝑡𝑖𝑜𝑛is 0 if such a minimum can be found,
or is not 0, or timeout.

### while use fmin_cg solving the minimum of 𝑜𝑏𝑗𝑒𝑐𝑡𝑖𝑣𝑒_𝑓𝑢𝑛𝑐𝑡𝑖𝑜𝑛do
get the next 𝑥0
test_cg(𝑜𝑏𝑗𝑒𝑐𝑡𝑖𝑣𝑒_𝑓𝑢𝑛𝑐𝑡𝑖𝑜𝑛, 𝑥0)
check the solving result and solving time
end while
2. 仅采用比例过滤方法，使用改写后的new_objective_function 和对应的500
组初始𝑥0 进行测试。每个目标函数和它的一组𝑥0 在进入fmin_cg 进行求
解前，该组𝑥0 将先作为参数调用一次目标函数，若目标函数返回了特殊值
1e10 则直接抛弃该组𝑥0，继续尝试下一组𝑥0，否则再进入fmin_cg 进行求
解，如Algorithm 2 所示。将该组𝑥0 将作为参数调用目标函数的时间也会
被计算在求解总时间内；

### Algorithm 2 比例过滤
Input: The 𝑜𝑏𝑗𝑒𝑐𝑡𝑖𝑣𝑒_𝑓𝑢𝑛𝑐𝑡𝑖𝑜𝑛and the list of 𝑥0.
Output: The minimum of 𝑜𝑏𝑗𝑒𝑐𝑡𝑖𝑣𝑒_𝑓𝑢𝑛𝑐𝑡𝑖𝑜𝑛is 0 if such a minimum can be found,
or is not 0, or timeout.

### while use fmin_cg solving the minimum of 𝑜𝑏𝑗𝑒𝑐𝑡𝑖𝑣𝑒_𝑓𝑢𝑛𝑐𝑡𝑖𝑜𝑛do

### get the next 𝑥0
if 𝑜𝑏𝑗𝑒𝑐𝑡𝑖𝑣𝑒_𝑓𝑢𝑛𝑐𝑡𝑖𝑜𝑛(𝑥0) = 1𝑒10 then

### continue
else
test_cg(𝑜𝑏𝑗𝑒𝑐𝑡𝑖𝑣𝑒_𝑓𝑢𝑛𝑐𝑡𝑖𝑜𝑛, 𝑥0)
check the solving result and solving time
end if
end while
33


<!-- page 42 -->
3. 仅采用迭代更新方法，使用original_objective_function 和对应的500 组初
始𝑥0 中的前50 组进行测试。每个目标函数将和它的一组𝑥0 进入fmin_cg
进行求解，并获取fmin_cg 退出时所在的位置𝑥𝑒𝑥𝑖𝑡，若解得的最小值不为
0，则在𝑥𝑒𝑥𝑖𝑡附近，即4.2.3 节介绍的搜索范围[𝑥𝑒𝑥𝑖𝑡−100, 𝑥𝑒𝑥𝑖𝑡+ 100] 中随
机生成新一组𝑥0 补充到待测的𝑥0 中，即第𝑖组𝑥0 将生成第50 + 𝑖组𝑥0，
以50 组作为一个轮次不断进行迭代更新，如Algorithm 3 所示。最终的𝑥0
组数将与另外3 种情况的实验相同，都是500 组（假设全部求解失败且未
超时），从而确保比较的公平性；

### Algorithm 3 迭代更新
Input: The 𝑜𝑏𝑗𝑒𝑐𝑡𝑖𝑣𝑒_𝑓𝑢𝑛𝑐𝑡𝑖𝑜𝑛and the list of 𝑥0.
Output: The minimum of 𝑜𝑏𝑗𝑒𝑐𝑡𝑖𝑣𝑒_𝑓𝑢𝑛𝑐𝑡𝑖𝑜𝑛is 0 if such a minimum can be found,
or is not 0, or timeout.

### while use fmin_cg solving the minimum of 𝑜𝑏𝑗𝑒𝑐𝑡𝑖𝑣𝑒_𝑓𝑢𝑛𝑐𝑡𝑖𝑜𝑛do
get the next 𝑥0
𝑥𝑒𝑥𝑖𝑡←test_cg(𝑜𝑏𝑗𝑒𝑐𝑡𝑖𝑣𝑒_𝑓𝑢𝑛𝑐𝑡𝑖𝑜𝑛, 𝑥0)
𝑛𝑒𝑤_𝑥0 ←random_select([𝑥𝑒𝑥𝑖𝑡−100, 𝑥𝑒𝑥𝑖𝑡+ 100])
add 𝑛𝑒𝑤_𝑥0 to the list of 𝑥0
check the solving result and solving time
end while
4. 同时采用比例过滤和迭代更新方法，使用改写后的new_objective_function
和对应的500 组初始𝑥0 中的前50 组进行测试。每个目标函数和它的一组
𝑥0 在进入fmin_cg 进行求解前先判断是否会被过滤，若会被过滤则直接继
续尝试下一组，若不会被过滤则再进入fmin_cg 进行求解，并在fmin_cg 退
出时所在的位置附近生成新一组𝑥0，如Algorithm 4 所示。最终的𝑥0 组数
在全部求解失败且未超时的情况下同样会是500 组，如果出现了初始的𝑥0
和生成的新𝑥0 都有很多被过滤导致尝试完所有𝑥0 后没有成功求解且𝑥0
不足500 组，则会再在[−1000, 1000] 内随机生成一组𝑥0 进行补充，直到
求解成功或足够500 组。
34


<!-- page 43 -->

### Algorithm 4 比例过滤+ 迭代更新
Input: The 𝑜𝑏𝑗𝑒𝑐𝑡𝑖𝑣𝑒_𝑓𝑢𝑛𝑐𝑡𝑖𝑜𝑛and the list of 𝑥0.
Output: The minimum of 𝑜𝑏𝑗𝑒𝑐𝑡𝑖𝑣𝑒_𝑓𝑢𝑛𝑐𝑡𝑖𝑜𝑛is 0 if such a minimum can be found,
or is not 0, or timeout.

### while use fmin_cg solving the minimum of 𝑜𝑏𝑗𝑒𝑐𝑡𝑖𝑣𝑒_𝑓𝑢𝑛𝑐𝑡𝑖𝑜𝑛do

### get the next 𝑥0
if 𝑜𝑏𝑗𝑒𝑐𝑡𝑖𝑣𝑒_𝑓𝑢𝑛𝑐𝑡𝑖𝑜𝑛(𝑥0) = 1𝑒10 then

### continue
else
𝑥𝑒𝑥𝑖𝑡←test_cg(𝑜𝑏𝑗𝑒𝑐𝑡𝑖𝑣𝑒_𝑓𝑢𝑛𝑐𝑡𝑖𝑜𝑛, 𝑥0)
𝑛𝑒𝑤_𝑥0 ←random_select([𝑥𝑒𝑥𝑖𝑡−100, 𝑥𝑒𝑥𝑖𝑡+ 100])
add 𝑛𝑒𝑤_𝑥0 to the list of 𝑥0
check the solving result and solving time
end if
if current 𝑥0 is the last one then
𝑛𝑒𝑤_𝑥0 ←random_select([−1000, 1000])
add 𝑛𝑒𝑤_𝑥0 to the list of 𝑥0
end if
end while

## 5.3.2
效果分析
5.3 节设计的4 组实验的结果如表5-7 所示，第1 列是采用的改进方法（或
不采用任何改进方法），第2 列是该方法在所有目标函数里成功求解出最小值为
0 的数目，第3 列是该方法求解完所有目标函数花费的平均时间（包括了超时的
部分）。

### 表5-7
4 组实验的求解结果
采用方法
成功求解数目
平均花费时间（秒）
不采用任何改进方法
99
365.91
比例过滤
100
337.32
迭代更新
100
350.44
比例过滤+ 迭代更新
101
323.33
采用改进方法相比于不采用任何改进方法，在成功求解数目和平均花费时
间上的提升如表5-8 所示，可以看出比例过滤和迭代更新都能为求解效果带来提
升，当两种方法组合时效果最好。
35


<!-- page 44 -->

### 表5-8
改进效果
采用方法
成功求解数目增加
平均花费时间减少
比例过滤
1.01%
7.81%
迭代更新
1.01%
4.24%
比例过滤+ 迭代更新
2.02%
11.64%
我们分析了采用改进方法后多出的成功求解的目标函数的求解情况，如表
5-9 所示，griggio_fmcad12_gaussian_c_125 和griggio_fmcad12_div2_c_10 是在不
采用任何改进方法时未能成功求解，但分别在采用了比例过滤或迭代更新方法
后能成功求解的目标函数，并且它们在采用了比例过滤和迭代更新的组合之后
也能成功求解。

### 表5-9
多出的成功求解的目标函数的求解情况
目标函数
采用方法
求解结果
花费时间（秒）
尝试𝑥0 组数
griggio_fmcad12
_gaussian_c_125
不采用任何改进方法
超时
1800.00
146
比例过滤
成功
772.93
169
迭代更新
超时
1800.00
308
比例过滤+ 迭代更新
成功
576.88
136
griggio_fmcad12
_div2_c_10
不采用任何改进方法
失败
307.60
500
比例过滤
失败
235.52
500
迭代更新
成功
86.52
171
比例过滤+ 迭代更新
成功
69.45
164
可以看出，griggio_fmcad12_gaussian_c_125 采用了比例过滤方法后，在更短
的时间内尝试了更多组的𝑥0，从而成功求解；采用迭代更新方法后，虽然未能
求解成功，但也尝试了更多组的𝑥0，我们推测失败的原因是该情况对前50 组𝑥0
都进行迭代更新，导致花费时间较长，迭代不够深入，最终超时未能成功求解；
采用比例过滤和迭代更新的组合后，效果提升比只采用比例过滤方法更明显，并
且没有像只采用迭代更新方法那样超时，我们推测这是因为比例过滤方法保留
了更高质量的𝑥0，让迭代更新方法只使用这些更高质量的𝑥0 进行更多轮次、更
深入的迭代，因此取得了更好的效果。
griggio_fmcad12_div2_c_10 采用了比例过滤方法后使用更短的时间尝试完
了500 组𝑥0，但因为这500 组𝑥0 均不能成功求解，所以求解失败；而采用了迭
36


<!-- page 45 -->
代更新方法后则生成了能成功求解的𝑥0，并在采用比例过滤和迭代更新的组合
后花费的时间更短。
37


<!-- page 47 -->

# 第六章
总结与展望

## 6.1
总结
本文研究了当前SMT 求解器在浮点数约束问题上的性能表现和能力范围，
具体选取了当前主流的SMT 求解器Z3 和针对浮点数约束问题的JFS，XSat，
goSAT 进行了评估分析，并得出了如下结论：相比于主流SMT 求解器，将浮点
数约束问题转变为优化问题等其他问题进行求解的SMT 求解器在处理浮点数约
束问题时具有更好的表现，能大幅度缩短求解时间和增加求解数目，但也存在稳
定性不足和能力范围不够全面等问题。
本文还针对XSat 的可改进之处提出并实现了两个改进方法：比例过滤和迭
代更新，并设计了4 组实验证明了这两种方法及其组合能提高初始猜测点的质
量，有效缩短求解目标函数最小值点的时间，提升求解效果。

## 6.2
不足与展望
由于时间、精力和能力有限，本文的研究工作还存在不少不足之处，一些研
究还处于比较简陋和不够深入的状态，希望在未来能做出改进和进行更加深入
的思考与研究：
1. 选取的进行评估的SMT 求解器数量较少，覆盖范围不够全面，例如在1.2.2
节的相关工作中介绍的近年来表现较好的CVC5 和Bitwuzla，XSat 的作
者设计的另一个工具CoverMe[34]，He 等人基于随机局部搜索（Stochastic
Local Search, SLS）实现的针对浮点数约束问题的OL1V3R[18]等，也都值得
进行评估。选取的用于评估的测试数据集也可以从更多来源进行搜集，评
估方法也还存在改进空间。
2. 提出的改进方法比较简陋，还存在缺陷，例如比例过滤方法仍然存在可能
把原本能成功求解的初始猜测点过滤掉的问题，衡量目标函数复杂程度的
39


<!-- page 48 -->
方式也较为简陋，未来可以考虑更全面和健壮的衡量策略，以及设置动态
比例等过滤方式。
40


<!-- page 49 -->

# 参考文献
[1]
王戟, 詹乃军, 冯新宇, 等. 形式化方法概貌[J]. 软件学报, 2019, 30(01): 33-61.
DOI: 10.13328/j.cnki.jos.005652.
[2]
王翀, 吕荫润, 陈力, 等. SMT 求解技术的发展及最新应用研究综述[J]. 计算
机研究与发展, 2017, 54(07): 1405-1425.
[3]
De MOURA L, BJØRNER N. Z3: An Efficient SMT Solver[C]//Tools and
Algorithms for the Construction and Analysis of Systems. Springer Berlin Hei-
delberg: 337-340.
[4]
唐傲, 王晓峰, 何飞. 可满足性模理论综述[J]. 计算机工程与科学, 2024, 46(03):
400-415.
[5]
李婧. SMT 求解器技术对比分析及其能力扩展研究[D]. 2010.
[6]
KHADRA M A B, STOFFEL D, KUNZ W. GoSAT: Floating-point satisfiability
as global optimization[C]//2017 Formal Methods in Computer Aided Design
(FMCAD): 11-14. DOI: 10.23919/FMCAD.2017.8102235.
[7]
FU Z, SU Z. XSat: A Fast Floating-Point Satisfiability Solver[C]//Computer
Aided Verification. Springer International Publishing: 187-209.
[8]
金继伟, 马菲菲, 张健. SMT 求解技术简述[J]. 计算机科学与探索, 2015,
9(07): 769-780.
[9]
BARRETT C, TINELLI C. Satisfiability Modulo Theories[M]//CLARKE E M,
HENZINGER T A, VEITH H, et al. Handbook of Model Checking. Cham: Springer
International Publishing, 2018: 305-343. DOI: 10.1007/978-3-319-10575-8_11.
[10]
SEBASTIANI R. Lazy Satisfiability Modulo Theories[J]. Journal on Satisfiabil-
ity, Boolean Modeling and Computation, 2007, 3: 141-224. DOI: 10.3233/SAT
190034.
41


<!-- page 50 -->
[11]
NIEUWENHUIS R, OLIVERAS A, TINELLI C. Solving SAT and SAT Modulo
Theories: From an abstract Davis–Putnam–Logemann–Loveland procedure to
DPLL(T)[J]. J. ACM, 2006, 53(6): 937-977. DOI: 10.1145/1217856.1217859.
[12]
BARBOSA H, BARRETT C, BRAIN M, et al. Cvc5: A Versatile and Industrial-
Strength SMT Solver[C]//Tools and Algorithms for the Construction and Anal-
ysis of Systems. Springer International Publishing: 415-442.
[13]
CIMATTI A, GRIGGIO A, SCHAAFSMA B J, et al. The MathSAT5 SMT Solver[C]
//Tools and Algorithms for the Construction and Analysis of Systems. Springer
Berlin Heidelberg: 93-107.
[14]
DUTERTRE B. Yices 2.2[C]//Computer Aided Verification. Springer Interna-
tional Publishing: 737-744.
[15]
NIEMETZ A, PREINER M, BIERE A. Boolector 2.0[J]. Journal on Satisfiabil-
ity, Boolean Modeling and Computation, 2014, 9: 53-58. DOI: 10.3233/SAT19
0101.
[16]
NIEMETZ A, PREINER M. Bitwuzla[C]//Computer Aided Verification. Springer
Nature Switzerland: 3-17.
[17]
LIEW D, CADAR C, DONALDSON A F, et al. Just Fuzz It: Solving Floating-
Point Constraints using Coverage-Guided Fuzzing[EB/OL]. Association for Com-
puting Machinery. 2019. https://doi.org/10.1145/3338906.3338921.
[18]
HE S, BARANOWSKI M, RAKAMARIĆ Z. Stochastic Local Search for Solv-
ing Floating-Point Constraints[C]//Numerical Software Verification. Springer
International Publishing: 76-84.
[19]
BIERE A, HEULE M, van MAAREN H, et al. Conflict-Driven Clause Learning
SAT Solvers[J]. Handbook of Satisfiability, Frontiers in Artificial Intelligence
and Applications, 2009: 131-153.
[20]
MOURA L M D. Lemmas on Demand for Satisfiability Solvers[C]//.
[21]
BARRETT C, FONTAINE P, TINELLI C. The Satisfiability Modulo Theories
Library (SMT-LIB)[EB/OL]. 2016. www.SMT-LIB.org.
42


<!-- page 51 -->
[22]
WEBER T, CONCHON S, DÉHARBE D, et al. The SMT Competition 2015–
2018[J]. Journal on Satisfiability, Boolean Modeling and Computation, 2019, 11:
221-259. DOI: 10.3233/SAT190123.
[23]
De MOURA L, BJØRNER N. Satisfiability Modulo Theories: An Appetizer[C]
//Formal Methods: Foundations and Applications. Springer Berlin Heidelberg:
23-36.
[24]
NELSON G, OPPEN D C. Simplification by Cooperating Decision Procedures[J].
ACM Trans. Program. Lang. Syst., 1979, 1(2): 245-257. DOI: 10.1145/357073
.357079.
[25]
BOZZANO M, BRUTTOMESSO R, CIMATTI A, et al. Efficient Satisfiability
Modulo Theories via Delayed Theory Combination[C]//Computer Aided Ver-
ification. Springer Berlin Heidelberg: 335-349.
[26]
NELSON G, OPPEN D C. Fast Decision Procedures Based on Congruence Clo-
sure[J]. J. ACM, 1980, 27(2): 356-364. DOI: 10.1145/322186.322198.
[27]
IEEE Standard for Floating-Point Arithmetic[J]. IEEE Std 754-2008, 2008: 1-70.
DOI: 10.1109/IEEESTD.2008.4610935.
[28]
VIRTANEN P, GOMMERS R, OLIPHANT T E, et al. SciPy 1.0: fundamental
algorithms for scientific computing in Python[J]. Nature Methods, 2020, 17(3):
261-272. DOI: 10.1038/s41592-019-0686-2.
[29]
Sequential Quadratic Programming[M]//NOCEDAL J, WRIGHT S J. Numerical
Optimization. New York, NY: Springer New York, 1999: 526-573. DOI: 10.100
7/0-387-22742-3_18.
[30]
丛明煜王丽萍. 现代启发式算法理论研究[J]. 高技术通讯, 2003(05): 105-
110.
[31]
ANDRIEU C, de FREITAS N, DOUCET A, et al. An Introduction to MCMC for
Machine Learning[J]. Machine Learning, 2003, 50(1): 5-43. DOI: 10.1023/A:10
20281327116.
43


<!-- page 52 -->
[32]
WALES D J, DOYE J P K. Global Optimization by Basin-Hopping and the Low-
est Energy Structures of Lennard-Jones Clusters Containing up to 110 Atoms[J].
The Journal of Physical Chemistry A, 1997, 101(28): 5111-5116. DOI: 10.1021
/jp970984n.
[33]
JOHNSON S G. The NLopt nonlinear-optimization package[EB/OL]. 2007. ht
tps://github.com/stevengj/nlopt.
[34]
FU Z, SU Z. Achieving High Coverage for Floating-Point Code via Uncon-
strained Programming[EB/OL]. Association for Computing Machinery. 2017.
https://doi.org/10.1145/3062341.3062383.
44


<!-- page 53 -->

# 致
谢
感谢王豫老师和陈谦学姐的悉心指导和帮助，感谢南京大学提供的学习环
境和成长机会，感谢父母一直以来的关心爱护。
45