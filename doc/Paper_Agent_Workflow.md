1. General Checking list
    1. For each method choice that is different from existing ways, explain: (1) what it is? (2) Why do we need to do it this way? (3) How do we do it? (4) Why is doing it this way is a good idea?
    2. It's a good idea to avoid making the reader do any thinking of their own (they might get it wrong and draw the wrong conclusion, and we're all a bit lazy).
    3. Conceptual Abstraction (vs. Implementation): Does the text focus on the logic and architectural choices rather than specific code-level mechanics (e.g., library calls, variable setup, or boilerplate) that are only relevant for a literal reimplementation?
    4. Scientific Modesty: Are the findings presented without overclaiming, using appropriate qualifiers (e.g., "suggests" or "in this context") and avoiding unsubstantiated generalizations or superlative adjectives?
    5. Proper Categorization of Claims: Are speculative or not-yet-proven implications strictly confined to the Discussion or Conclusion sections, ensuring that the Results section remains limited to claims directly substantiated by data?
    6. Dry-to-Concrete Translation: Throughout the paper, it is important to have small illustrative examples for those places that contain “dry” descriptions of your approach.
    7. Notation/Terminology:
        1. Name your baby: Give unique names to things and use them consistently
        2. Consistency: Is the notation and terminology consistent across the paper?
        3. Accessibility: Is every specialized or non-standard term either defined, rephrased in plain language, or omitted if the specific detail is not vital to the core argument?
            1. Example: several places in the paper, you say "deep crashes", what does it mean? How does "deep crashes" differ from normal crashes
    8. For each paragraph:
        1. Old-to-New Linkage: Does the beginning of each sentence anchor the reader with familiar information from the previous text to create a logical bridge?
        2. Single-Point Focus: Does each paragraph lead with a clear "point sentence" that establishes one main idea, ensuring every subsequent sentence in that paragraph directly supports that specific contribution to the paper’s big picture?
    9. Just in time: Give information precisely when it is needed, not before.
    10. Short subjects: Subject of sentence should be at most 8 words long.
    11. Overarching Principle:
        1. Top-down: Explain your work at multiple levels of abstraction, starting at a high level (accessible to non-experts) and getting progressively more detailed.
        2. Tell them what they want to know: How is your work important? How is your work novel? How is your work interesting?
    
2. Similar to presenting your work. Write a pre-defined presentation written in Latex
    1. Abstract
        1. Outline:
            1. Short motivation (problem); 
            2. Proposed solution; 
            3. Evaluation and results
        2. Checklist:
            1. Explain clearly in the abstract and intro how this work is related to the Submitted Venue.
            2. Don’t put unexplained or undefined terms whose meanings are not well known.
    2. Intro:
        1. Outline: 
            1. What is the problem to be solved
            2. Why is the problem significant (desirable to use concrete statistics, concrete examples, or citations)
            3. Summary of existing work
                1. Summary of existing work focusing on the problem you are trying to solve.
                2. For very closely related work, you should clearly point out the
                differences in this section.
            4. Present the core limitation of existing work
                1. Why existing solutions are not sufficient (sometimes examples help)
                2. The problem-level challenges that existing solutions cannot fully address
            5. Insights of this work
            6. [Optional] The solution-level challenges and solutions of the proposed method
                1. Any challenges when using this insight
                2. How to resolve the challenges
            7. The workflow of the proposed work
            8. Evaluation summary
            9. Core contributions:
                1. [Optional] New problems
                2. The overall approach and a list of specific techniques in the approach
                3. Implementation and evaluation
                4. Evaluation results
        2. Checklist
            1. The intro section is completely self-consistent, with relevant background information provided for each topic. For example, it covers the background of setup backend-oriented features (which are considered important backend code generation components).
            2. Explain clearly in the abstract and intro how this work is related to the Submitted Venue.
            3. The significance of Challenges:  If your challenges are so obvious and easy, you cannot impress readers/reviewers and justify their significance.
    3. [Optional] Background (or Preliminaries):
        1. For all notations, terminologies, steps, modules, methods used in our methods, on which we do not make any contribution, we should put them in the background.
        2. Place 
    4. [Suggested] Motivating Example
        1. Outline
            1. Origin and Context: Briefly state where the example comes from (e.g., a real-world bug report, a simplified snippet from a popular library, or a common synthetic benchmark) to establish its relevance.
            2. The Visual Anchor: A figure displaying source code.
            3. The Problem Scenario: Describe how existing methods or a "naive" approach would fail or struggle with this specific example.
            4. The Insight: State the "Aha!" moment—the core observation or intuition that your approach uses to solve the problem where others cannot.
            5. High-Level Walkthrough: Describe your approach’s execution on this example.
                1. Inputs: What does your tool/method take in?
                2. Outputs: What is the specific, improved result?
            6. The "Teaser" for the next section (e.g., Formalization): A concluding sentence that explains (1) how this specific example generalizes into the formal definitions provided in the next section, or (2) how these steps generalize into the methodology in the next section.
        2. Checklists
            1. Source Transparency: Is the origin of the example clearly stated so the reader knows it represents a realistic or significant challenge?
            2. Self-Contained Figure: Does the figure include a caption that allows the reader to understand the core problem without reading the full text of the section?
            3. Insight Identification: Is the core "Insight" clearly articulated? Does it explain why your method is effective rather than just that it is effective?
            4. Strategic Abstraction: Does the walkthrough avoid low-level implementation details (e.g., library calls, specific data structures) to focus on high-level logic?
            5. Contrastive Value: Does the example explicitly highlight the importance of your task by showing where a baseline or related work falls short?
            6. Goal Alignment: Does the example's successful outcome directly map to the "Contributions" listed in your Introduction?
            7. Clarity over Complexity: Is the example "distilled"? (i.e., Have you removed all code or logic that doesn't directly contribute to illustrating your main point?)
    5. [Optional] Problem Statement
        1. Outline
            1. Contextual Motivation: A brief transition from the Introduction that explains why a formal definition is necessary for this specific research scope.
            2. Preliminary Definitions: Formalize the fundamental concepts or "primitives" (the "nouns" of your problem space) that the reader must understand before the core problem can be stated.
            3. Formal Problem Statement: A concise, mathematical, or logical representation of the core challenge (e.g., "Given $X$, find $Y$ such that $Z$ is optimized").
            4. Assumptions & Constraints (If applicable): Explicitly state the boundaries of the problem—what is being considered and what is out of scope.
            5. Lemmas or Properties (If applicable): Essential logical building blocks that prove the problem is solvable or characterize its complexity.
            6. Narrative Synthesis: A concluding paragraph that bridges the formal definition to the "Proposed Approach" section.
        2. Checklists:
            1. Logical Narrative Flow: Does every definition, lemma, or theorem follow a prose explanation of why it is necessary at that specific point in the section
            2. Conceptual Grounding: Are all important concepts (in both the problem and solution space) formally defined before they are used in the core problem statement?
            3. Framework Independence: Is the problem defined in terms of its inherent logic rather than being limited to the specific implementation or library used in your experiment?
            4. Precision of Terminology: Does the section avoid undefined or "well-known-only" terms, ensuring that a reader from a related sub-field can grasp the formalization?
            5. Mathematical Rigor: Are symbols and notations used consistently, and is there a "Summary of Notation" or clear introduction for each symbol?
            6. Defensive Scoping: Does the section avoid overclaiming by clearly defining the constraints and assumptions under which this problem exists?
    6. Methodology
        1. Outline:
            1. High-Level Overview:
                1. Workflow Diagram: A central figure (e.g., created in [Draw.io](http://draw.io/)) illustrating the data flow from inputs to final outputs.
                2. Phase-by-Phase Synopsis:
                    1. Major Phases: Provide a 1–2 sentence "teaser" for the heavy-hitting components that will get their own subsections later.
                    2. Minor/Utility Phases: Fully explain smaller, "one-off" steps here (e.g., data cleaning, format conversion, or final reporting) so they don't clutter the later technical deep dives.
            2. Component-by-Component Walkthrough:
                1. For each major phase of the workflow:
                    1. Objective: What is this step trying to achieve?
                    2. Rationale: Why is this step necessary or beneficial (especially if steps are independent)?
                    3. Technical Logic: Describe the core mechanism without library-specific jargon.
                2. When writing  Algorithms: 
                    1. Intuitive Example: A brief "mini-example" to ground the algorithm’s logic before showing the formal version.
                    2. High-Level Algorithm Description: Present pseudocode or a modular breakdown. Focus on explaining what each logic block accomplishes rather than narrating the code line-by-line.
        2. Checklist:
            1. Conceptual Abstraction: Is the approach presented as a generalized framework or algorithm that could theoretically be implemented in other languages or environments?
            2. Strategic Emphasis: Does the text devote more space to the novel/key techniques rather than providing equal, "tool-paper" style coverage of every minor component?
            3. Non-Narrative Algorithm Description: Does the algorithm explanation avoid "reading the code" (e.g., avoid saying "variable X is assigned to Y") and instead explain the semantic purpose of each part?
            4. Visual Workflow Alignment: Does the text explicitly reference the Workflow Diagram and follow the same sequence of steps shown in the figure?
            5. Explicit Rationale: Is the "Why" and "Benefit" of each independent step clearly stated to justify its inclusion in the methodology?
            6. Illustrative Grounding: Is there a small example accompanying complex logic to ensure the "dry" descriptions remain accessible to a general reader?
            7. Logic over Library: Are references to specific libraries, frameworks, or APIs kept to a minimum, ensuring the focus remains on the underlying research idea?
    7. Implementation
        1. Outline:
            1. Technical Stack & Environment: List the primary programming languages, frameworks, and third-party libraries/frontends used (e.g., Soot, LLVM, Daikon).
                1. Specify the versions of critical tools to ensure environment parity.
            2. Mapping Theory to Tool:
                1. A brief walkthrough of how the conceptual components described in the Methodology are realized in code (e.g., "The 'Analysis Engine' is implemented as a custom 5,000-line Java extension for the BCEL library").
            3. Engineering Complications & Workarounds:
                1. Identify non-trivial hurdles encountered during development (e.g., handling specific edge cases in the library, performance bottlenecks, or data format incompatibilities).
                2. Explain the specific "hacks" or elegant workarounds used to bypass these issues.
            4. Optimizations (If applicable):
                1. Describe specific engineering-level optimizations (e.g., multi-threading, caching mechanisms) that are not part of the core "idea" but are necessary for the tool to function effectively.
    8. Evaluation
        1. Outline: 
            1. Research Questions (RQs):
                1. Explicitly state the 3–4 questions your evaluation seeks to answer (e.g., RQ1: Effectiveness, RQ2: Efficiency/Performance, RQ3: Sensitivity/Ablation Study).
            2. Experimental Setup:
                1. Subject Programs/Datasets: Describe the benchmarks used and why they were selected.
                    1. If using standard benchmarks: List the names, versions, and citations (e.g., "We used the 12 most complex subsets of the SMT-LIB 2025 library").
                    2. If using self-constructed benchmarks:
                        1. The "Why": Explain why existing standard benchmarks were insufficient or unavailable for this specific task.
                        2. The "How": Describe the collection or generation process (e.g., "We crawled 500 GitHub repositories with >1k stars").
                        3. Data Filtering/Pruning: Justify why certain data points were included while others were excluded (e.g., "We excluded scripts under 50 lines of code to focus on non-trivial logic").
                    3. Descriptive Statistics: A summary table listing key metrics of the subjects (e.g., Lines of Code, number of assertions, density of floating-point operations).
                2. Baselines: 
                    1. Selection & Identification: List the specific tools, solvers, or methods being compared against.
                        1. Provenance: Provide the exact version numbers, commit SHAs, or citations for each to ensure experiment version-parity.
                        2. A summary table (e.g., "Table 1") that maps each baseline to its underlying techniques/algorithms for a quick bird's-eye comparison.
                    2. Justification of Competitors: Explain why these specific baselines were chosen (e.g., they are the current SMT-COMP gold medalists, state-of-the-art in a specific sub-field, or the industry standard).
                    3. Technical Adaptation (If applicable): If a baseline was designed for a different task (e.g., testing vs. solving), detail the specific steps taken to adapt it for the current study.
                        1. Describe the "Bridge" logic (e.g., "We replaced the translation rules of Tool A with those of Tool B").
                    4. Correctness Verification: Describe how you ensured the adapted baseline still functions correctly (e.g., via differential testing or cross-validation on a small dataset).
                3. Environment: Specify hardware (CPU/GPU/RAM) and OS details.
                4. Configuration: List hyperparameter settings, seeds, or tool-specific flags.
                5. Metrics: Define how success is measured (e.g., Precision/Recall, Execution Time, Memory Overhead, Code Coverage).
            3. For each RQ: use Results and Analysis subsection whose title is the RQ or its answer:
                1. RQ-Centric Subheadings: Use the Research Question (or better yet, its definitive answer) as the subsection title (e.g., "RQ1: Grater significantly outperforms SOTA solvers in efficiency").
                2. Comparative Data Grouping: * Organize data by Benchmark Source (e.g., Standard vs. Custom) to show the breadth of the results.
                    1. Use Tables for precise statistical comparisons (Mean, Median, Solved counts) and Figures (Cactus Plots) to show performance scaling.
                3. The "Evidence Claim": Start with a high-level summary that explicitly states how the referenced data answers the RQ (e.g., "As shown in Table 2, our tool solves 15% more constraints than the nearest baseline...").
                4. Highlight & Anomaly Analysis:
                    1. The Successes: Identify the "Winning" cases where your approach excelled and explain the technical reason for this advantage.
                    2. The "Wired" (Outlier/Counter-Intuitive) Results: Honestly identify cases where the tool performed poorly or unexpectedly. Provide a technical "Post-Mortem" explaining the bottleneck (e.g., specific constraint types, memory limits, or heuristic failures).
            4. [Optional] Threats to Validity:
                1. Internal: Could something else explain your results (e.g., implementation bugs)?
                2. External: Do the results generalize beyond these specific benchmarks?
                3. Construct: Do your metrics actually measure what you claim they measure?
        2. Checklist:
            1. Ablation study: compare the results of including or not including an important technique  claimed to be a major contribution
            2. Justify the reason why you chose the experimental subjects or a subset of subjects used by previous work.
            3. Reproducibility completeness: Does the experimental setup include all essential parameters (e.g., hardware, software versions, hyperparameters, and dataset splits) required for a reader to achieve the same results?
            4. Baseline Fairness: Are the baselines you compared against state-of-the-art and configured using their recommended "optimal" settings?
            5. "Deep Dive" Analysis: Does the text go beyond describing the numbers (e.g., "Method A is 10% faster") to explain why certain results occurred?
            6. Result Explanation: Are the reasons for such results clearly explained, especially for unusual results?
            7. Benchmarking Transparency: Is the selection of datasets justified? (e.g., Why these 10 projects and not others?)
            8. Metric Justification: Is it clear why the chosen metrics are the most relevant for the problem space?
            9. Stand-alone Visuals: Do all tables and charts have descriptive captions and clear axis labels so they can be understood at a glance?
            10. Redundancy Check: Does the text avoid repeating every single number found in the tables, focusing instead on trends, outliers, and takeaways?
            11. Validity Acknowledgement: Does the "Threats to Validity" subsection provide a humble and realistic assessment of the study's limitations?
            12. Assertive Subheadings: Does the subsection title clearly state the main takeaway of that specific Research Question?
            13. Data-Claim Coupling: Is every interpretive claim (e.g., "Our tool is more stable") immediately followed by a reference to the specific table or figure that proves it?
            14. Benchmark Stratification: Are results broken down by benchmark type to demonstrate that the tool’s effectiveness isn't limited to a single, narrow dataset?
            15. The "Why" of Success: Beyond stating that the tool won, does the text explain which specific feature of the methodology (e.g., the new pruning algorithm) caused the improvement?
            16. Transparent Anomaly Reporting: Are "wired" or poor results explained with the same level of technical detail as the successful results?
            17. Contextualized Efficiency: If the tool is "faster," is the speedup explained in a way that matters (e.g., "Reducing median solving time from minutes to seconds enables real-time IDE integration" )?
            18. Visual Redundancy Check: Does the text avoid simply "reading the table" to the reader, focusing instead on trends, deltas, and significant outliers?
    9. Related work
        1. Outline:
            1. Categorized Literature Review: Group related papers into 2–3 thematic clusters (e.g., "Static Analysis Approaches" vs. "Dynamic Frameworks") rather than listing them chronologically.
            2. Comparative Analysis: For each cluster, describe the state-of-the-art and immediately relate it to your work using contrastive language.
            3. Problem Space Impact: Explain how the technical differences in the "solution space" (e.g., using a different algorithm) translate to observable benefits in the "problem space" (e.g., fewer false positives for the user).
            4. Ancestry & Evolution: Explicitly cite your own relevant prior work, clearly articulating the non-incremental delta (the "new" contribution) to avoid "Least Publishable Unit" (LPU) concerns.
            5. Gap Summary: A concluding synthesis that reinforces the unique niche your paper fills, which has been left unaddressed by the aforementioned categories.
        2. Checklists:
            1. Active Relational Linking: Does the section use transition keywords (e.g., whereas, in contrast, however) to explicitly connect others' work to your own, rather than just summarizing them?
            2. Problem-Space Comparison: Does the critique go beyond technical implementation to explain the impact on the user or the problem (e.g., "Unlike [X], our approach reduces manual specification overhead")?
            3. Objective Criticism: Are all criticisms of related work either backed by your own experimental results or supported by citations of others' experiments?
            4. Self-Citation Integrity: Have you included your own highly relevant previous papers and clearly explained how this current work provides a significant, non-marginal advancement?
            5. Venue Relevance: Does the section include relevant work from Program Committee (PC) members or key figures in the submitted venue’s community to show alignment with the field's current discourse?
            6. Avoidance of Overclaiming: Does the text refrain from dismissive language (e.g., "Work [X] is flawed") and instead use objective comparisons (e.g., "[X] focuses on a different sub-problem")?
            7. Strategic Grouping: Are similar approaches described together to allow for a high-level comparison against your method, rather than a repetitive "paper-by-paper" list?