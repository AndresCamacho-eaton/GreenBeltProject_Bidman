# Agent Playbook: Read Pick Rule Files and Optimize Tables Safely

**Purpose:** Instructions for an agent asked to inspect a legacy Pick `.prn` file (for example, `Category.prn`) or a Pick Workbench `.json` project and independently propose or perform row reduction, OR creation, and rule reordering.  
**Success criterion:** The resulting effective tables produce the same required behavior for every relevant input, or every intentional behavior change is explicitly identified and approved.  
**Important limitation:** This document is **not** a complete normative byte-level `.prn` grammar. The available references confirm the existence of legacy PRN files but do not specify enough to infer every version's exact table-start directive, field widths, quoting, encodings, or serialization. The agent must inspect a real file or use a trusted parser/importer before writing raw PRN. Do not invent syntax.

## 0. Agent contract: what to do, what not to do

**Do:**

- Identify the actual source format and effective table before modifying anything.
- Preserve a byte-for-byte original of each supplied legacy file and a baseline export or snapshot of each Workbench table.
- Read and preserve schema, file-local and global OR definitions, row types, comments, continuations, and table order.
- Derive proposed optimizations from complete input and output signatures, not one visible output cell.
- Prove or test that coverage, precedence, outputs, downstream chains, and multiplicity stay equivalent.
- Make the smallest understandable change, report old row identities, new rows/ORs, exact placement, net reduction, and test results.
- Distinguish *suggested* changes, *unsaved* grid changes, *saved* branch changes, *compiled* results, and *published* rules.

**Do not:**

- Treat `.prn` as `.json` with a different extension, or invent a PRN grammar when a real file has not been inspected.
- Split legacy text at arbitrary whitespace and assume the resulting fields map to columns.
- Interpret a disabled row or comment as active; drop or relocate a continuation without checking which rule it extends.
- Replace a finite set of input values with a wildcard or `<>X` unless the newly covered inputs are intentional.
- Merge independent ORs in multiple input columns without checking every cross-combination.
- Deduplicate PICK ALL matches just because the returned text looks identical.
- Reorder PICK ONE rules by apparent specificity without a precedence proof.
- Create a new OR by guessing a name, members, scope, or how it is serialized.
- Save, compile, push, or deploy merely because the user asked for an analysis; use only authorized actions.

---

## 1. Establish which format and version you actually have

### Legacy PRN path

The input might be a raw text file called `Category.prn`, another legacy Pick rule file, a screenshot of an older table editor, or an exported text rendering. Treat the **actual bytes/text** as the evidence, not the extension alone.

1. Record file path/name, encoding if known, line endings, and whether a project-level manifest or other files accompany it.
2. Preserve the original unchanged. If writing text, keep the original whitespace and line structure until you can explain its role.
3. Inspect enough complete examples to identify table boundaries; table name and PICK ONE/PICK ALL setting; headers; INPUT/OUTPUT and type declarations; local/global OR declarations; active, disabled, comment, and continuation lines; and how column positions are expressed. **Do not assume a particular directive spelling without seeing it in that file.**
4. If the file uses positional/fixed-width columns, determine boundaries from authoritative metadata or consistent header/rule alignment, and cross-check against multiple rows containing values with internal spaces or punctuation. Do not infer boundaries from one short row or whitespace runs alone. If a column containing a query or description could spill into another, stop and resolve ambiguity with a real editor/parser or a known-good import.
5. Verify that every source line belongs to exactly one table or known file-level directive, and that round-tripping an unchanged file through any proposed parser/reformatter leaves its effective content unchanged. If a section remains unexplained, **do not autonomously rewrite raw PRN**; ask for the project's canonical PRN specification or trusted converted representation.
6. Record the original source line numbers for audit. PRN line numbers are **not** Workbench `_rid`s and may change after edits.

The wiki discusses legacy `.PRN` files but the references consulted here do **not** provide a reliable universal serialization grammar. The instructions above deliberately describe a validation process rather than fictional PRN directives. See [Freight Estimator Support — PRN file context](https://dev.azure.com/etn-BidManager/7b29899a-fe07-44f6-94db-693b3738308a/_wiki/wikis/b6d5373b-e910-458a-8f94-b3961f20d3ba?pagePath=%2FPick%20Developers%20Technical%20Guide%20-%20The%20Encyclopedia%2FPick%20Development%2FFreight%20Estimator%20Support).

### Pick Workbench JSON path

Prefer reading the project through the workbench's table/OR views or validated project data rather than assuming the internal JSON object shape. One JSON member file can contain several tables and a file-local OR table; `GLOBALS.json` contains global OR definitions. The project manifest lists member files. Enumerate tables by **file path**, not by assuming `Category.json` contains only a table named `Category`. [Pick Workbench basics — Projects, files and tables](help/basics#projects-files-and-tables)

If the table has unsaved changes, read the **live** grid to analyze the version that would be edited. A saved-file read is intentionally stale for that table. The Workbench `_rid` is a row identifier, not the displayed row number; it is assigned on save and exists on comment/disabled/continuation lines as well. [Reading a table — Row number and `_rid`](help/reading-a-table#the-row-number-and-rid-columns)

**Do not conflate representations:** a parsed PRN source line, a converted JSON row, and a Workbench `_rid` are different identities. Maintain a mapping only if a trusted import/conversion provides one; otherwise show source line and table separately from `_rid`.

### Shared intermediate reading model (conceptual, NOT an on-disk schema)

For analysis, describe each table as:

- identity: exact table name + source file + effective/shadowed status;
- evaluation mode: PICK ONE or PICK ALL;
- ordered columns: exact name, I/O direction, Pick type, and any query/callback in the header;
- ordered source lines: line type, original identity (line number or `_rid`), per-column **raw** cell text, and effective value after any continuation lines;
- table-level comment and row comments;
- OR definitions: exact name, source file/scope, delimiter and members;
- outbound `ss_chain` references and any runtime expressions;
- uncertain/unknown fields preserved verbatim and marked unresolved.

This is a reasoning model, **not** instructions to generate arbitrary JSON or rewrite a PRN into a guessed format. Always retain raw cell text alongside interpreted conditions. Do not trim internal spaces from queries, descriptions, callback parameters, or expressions by accident.

---

## 2. Parse row types and effective cells before reasoning

Pick has active `Rule` rows, inactive `Disable` rows, `Comment` rows, and `Continuation` rows. A continuation appends to the nearest preceding **Rule** in corresponding columns; a Disable or Comment between them is skipped. Preserve their alignment and grouping. [Reading a table — Row types](help/reading-a-table#row-types-rule-disable-comment-continuation)

**Procedure:**

1. Locate table metadata and ordered column boundaries.
2. Read the ordered lines and tag each with its authentic line type.
3. Assemble each active rule's effective per-column cells by applying its continuations in the correct columns. Keep the original source lines intact for round-trip checks.
4. Associate comments with their intended location; do not delete an informative comment just because it does not evaluate.
5. Check whether a continuation follows an intervening Disable/Comment and therefore belongs to an earlier Rule.
6. Treat Disable lines as preserved, nonmatching material unless the owner explicitly wants to remove them.

**Parsing gate:** If any candidate rule's complete effective input/output cells cannot be established confidently, **exclude it from automated optimization**. A continuation of a catalog number or output expression can change the conclusion completely.

---

## 3. Understand matching and the equivalence target

A rule matches when **every INPUT cell** passes; a blank INPUT cell is a wildcard. PICK ONE returns the **first** matching active rule; PICK ALL returns **every** matching active rule top-to-bottom. [Pick Workbench basics — How a pick table works](help/basics#how-a-pick-table-works)

Handle these distinct notions of equivalence:

- **Final-value equivalence:** same observable outputs for every relevant input; winner `_rid` may change.
- **Full-result equivalence:** same list/count/order of outputs, including blank entries as the consumer interprets them and results from downstream chains.
- **Diagnostic equivalence:** same matching row identity and trace details. Deleting or merging rows usually makes this impossible; disclose the expected trace change.

Ask which notion is required if the consuming application depends on result order, count, or trace IDs. If unknown, default to preserving **full-result behavior** and disclose diagnostic changes.

### Input-condition interpretation

- Ordinary literal: exact equality according to the column's Pick type; for ALPHA do not silently case-fold.
- Blank INPUT: wildcard, including potentially no input.
- OR name: matches the real member values from the correct scope; the caller provides a **member**, not the OR name. [OR lists — Tips](help/ors#tips)
- `<>X`: not-equal condition, and missing input can match; it is not the same as a finite set of allowed values.
- Numeric comparison `<`, `<=`, `>`, `>=`, `=`: the documented rule-cell operators require `NUM`; `<>` works for any column type. [Pick Table Operators — Operators](https://dev.azure.com/etn-BidManager/7b29899a-fe07-44f6-94db-693b3738308a/_wiki/wikis/b6d5373b-e910-458a-8f94-b3961f20d3ba?pagePath=%2FPick%20Developers%20Technical%20Guide%20-%20The%20Encyclopedia%2FPick%20Development%2FPick%20Table%20Operators%2C%20Types%2C%20Ranges%20and%20Functions)
- Range interval: verify the column's supported range type and inclusion/exclusion of each endpoint. Test boundary values and gaps.
- Header query/callback: may resolve dynamically from an OF3 object; do not assume the displayed cell is the actual runtime input. Confirm its documented syntax and context before simplifying.

**Missing-input gate:** For every new wildcard, OR, negation, and range, compare behavior not only for recorded values but also for absent inputs and values not previously present in the table. If unable to prove no change, mark the rewrite *conditional on domain confirmation*.

### Complete output signature

Compare **all** OUTPUT cells, not merely the most obvious `price`/catalog number. Include literal text, blank output, expressions, `gv(...)`, callback references, `ss_chain`, and consumer-sensitive output order. An expression that happens to evaluate to the same price for one test is **not** equivalent to a fixed number across all runtime states.

`ss_chain` evaluates another table with the same inputs; downstream outputs can override upstream values. Follow actual outbound chains only. Inbound references are not outbound chains. Runtime queries, callbacks, and dynamic outputs may not be evaluable in Workbench trace; use runtime validation where necessary.

---

## 4. Create a baseline before any edit

Document at minimum:

- table identity, source format, mode, all columns/types, complete active row count and line count;
- ordered active rules with effective cells, raw text, and source identity;
- complete OR definitions and scopes, including existing usages;
- outbound chain targets and relevant downstream behavior;
- table/row comments, disabled lines, and continuations;
- a representative before-state input → output/test matrix;
- no-match cases, missing inputs, fallback behavior, and numeric/OR boundary cases;
- expected row-ID/trace changes if consolidated.

For PICK ALL, baseline **the ordered results, including duplicate outputs**, not just a set of unique values. A notes table, for example, can use the first returned line as a name and the later lines as text, so reordering is functional rather than cosmetic. [Comments and Clarifications — `note` table](https://dev.azure.com/etn-BidManager/7b29899a-fe07-44f6-94db-693b3738308a/_wiki/wikis/b6d5373b-e910-458a-8f94-b3961f20d3ba?pagePath=%2FPick%20Developers%20Technical%20Guide%20-%20The%20Encyclopedia%2FPick%20Development%2FComments%20and%20Clarifications%20%28Notes%29)

---

## 5. Generate row-reduction candidates by increasing risk

### A. Exact duplicates

Compare **all effective INPUT and OUTPUT cells** and row type. In PICK ONE, a later exact duplicate active rule is unreachable whenever the earlier one is reached, but check comments/continuations, priority and intended retention. In PICK ALL, both matching duplicate rules can produce two results: **do not automatically delete**.

### B. Same output, one varying input

This is the strongest candidate for a new exact OR. All other INPUT cells and **every** OUTPUT cell must be identical. The resulting OR members should be exactly the original alternatives, without adding other existing or future values.

### C. Adjacent numeric intervals

Combine only if the union is exactly the intended numeric domain, including endpoint inclusion, fractional values where possible, and missing-input behavior. The column type must genuinely support the chosen expression. Never change an entire column type as a shortcut without reviewing every row and caller.

### D. Remove or generalize an input condition

Changing a cell to blank broadens to **every** value and possibly missing input, not merely values observed in the current table. This is usually a behavior change, not a safe row reduction. Use a finite OR when the intended alternatives are finite.

### E. Reorder rules or split/refactor tables

Reordering PICK ONE changes priority wherever rules overlap. Reordering PICK ALL may change the order in which outputs are returned. A broad restructuring should be separately justified, not bundled as a supposedly harmless row cleanup.

---

## 6. OR creation: exact method, scope, and safety

### When an OR is appropriate

**Illustrative before-state (not data from ECPP):**

| Mode | Frame (INPUT) | Poles (INPUT) | Voltage (INPUT) | Price (OUTPUT) | `ss_chain` (OUTPUT) |
|---|---|---:|---:|---:|---|
| PICK ONE | F100 | 2 | 208 | 400 | PriceNext |
| PICK ONE | F100 | 2 | 240 | 400 | PriceNext |
| PICK ONE | F100 | 2 | 480 | 400 | PriceNext |

Potential replacement: one row with unchanged `Frame=F100`, `Poles=2`, `Price=400`, `ss_chain=PriceNext`, and `Voltage=<exact OR containing 208, 240, 480>`. Make sure this membership works for the column type and the table's actual definition/runtime. Report two fewer active rules, plus the cost of one OR definition.

### Before creating the OR

1. Find the **source file** of the target table. A local OR lives in that file's `OR` table. A global OR lives in `GLOBALS.json` and is accessible across the project. [OR lists — Local and global ORs](help/ors#local-and-global-ors)
2. Check every existing OR name and definition that might be reused, including its scope. Do not assume an identically named OR in another file has identical members.
3. Choose a unique, descriptive name according to the project's naming practices. Some names include `OR:` as literal text; do not automatically add or remove that prefix.
4. Choose membership **exactly** equal to the set being combined. Avoid a broader existing OR. Check for duplicate or special entries, order where the consumer cares, and delimiter conflicts.
5. Inspect all other tables that would consume a changed **existing** OR. Prefer a **new local** OR for a one-file optimization when sharing is not intended; consider global only if cross-file reuse is deliberate. A local name colliding with a global name causes a compile error. [OR lists — Local and global ORs](help/ors#local-and-global-ors)
6. Specify which old rows will be removed, where the replacement goes, and why no other rule's priority changes.

### In Workbench

Open `OR` under the chosen file (or under `GLOBALS.json` for global). The first column of an OR row is its name, and subsequent columns hold **one value each**. The Workbench delimiter is `;`; do not paste `208;240;480` as one member cell. Then use the exact OR name in the appropriate rule INPUT cell and save both files/tables when ready. [OR lists — Edit OR lists](help/ors#edit-or-lists)

### In a raw PRN

**Do not guess the source directive or column layout.** First locate a known-good local/global OR in the same PRN/project and establish the actual syntax, delimiter, file scope, and toolchain behavior. Then follow the canonical PRN editor or parser and perform a round-trip/compile check. If no example or validated parser is available, provide an exact **conceptual** name-and-member proposal but leave raw PRN serialization to an engineer with the correct specification. A legacy OR declaration and a Workbench OR grid row represent similar logic; they are **not interchangeable file formats**.

### OR change report

Record: name, file/scope, complete members, old references (if editing an existing definition), added/removed rows with source IDs, replacement position, before/after test results, and any compile warning/error. Do not say “OR created” if you only drafted a proposed definition or your editing tool cannot change an OR table.

---

## 7. Reject the Cartesian-product trap

**Original rules:**

```text
(Frame=F100 AND Poles=2) → Catalog=A
(Frame=F250 AND Poles=3) → Catalog=A
```

**Unsafe merged rule:** `Frame∈{F100,F250} AND Poles∈{2,3}`.

The merged rule also covers `(F100,3)` and `(F250,2)`. These were **not** represented by the two original rules; they may have matched a different table row or failed entirely.

**Exact rectangle test:** Let each changed INPUT column have a candidate value set. The new row covers their full Cartesian product, subject to the unchanged input conditions. Accept a multi-column merge only if *every combination* in that product had the **same effective full-result behavior and priority** before the change. For N columns, check every cross-combination, including ones not in the existing table. Otherwise merge one changing dimension at a time or leave correlated rows separate.

---

## 8. Reordering: prove it is safe, do not just sort by specificity

### PICK ONE

Two active rows A and B can swap without changing effective outputs only if, for **every input that reaches their positions**, either (1) their match conditions do not overlap, or (2) when both match they produce identical **complete effective results**, including chains/runtime side effects. A guarantee only on their individually expected cases is insufficient. Check all other rules they cross while moving: a move over five rows involves interactions with **each** of the five, not just old and new neighbors.

**Example:**

```text
Before:
1. Voltage=208, Frame=F100           → A
2. Voltage=240, Frame=F100, Trip=LSIG → B
3. Voltage=240, Frame=F100           → A
```

Replacing rules 1 and 3 with a broad OR row at the top wrongly steals the `240/LSIG` case from rule 2. A position after rule 2 might be a candidate, but still needs missing-input, overlap, and fallback checks. Do not automatically “put all general rules last” if doing so crosses a deliberate override.

### PICK ALL

Matching row **order** can matter to downstream consumers. Reordering can change an ordered result list even when every row still matches. Prove the consumer is order-insensitive or preserve the order for every input. In a table that builds lines or sequential actions, assume order is meaningful unless demonstrated otherwise. The wiki's `note` table is a concrete example where the first returned line has a special meaning. [Comments and Clarifications — `note` table](https://dev.azure.com/etn-BidManager/7b29899a-fe07-44f6-94db-693b3738308a/_wiki/wikis/b6d5373b-e910-458a-8f94-b3961f20d3ba?pagePath=%2FPick%20Developers%20Technical%20Guide%20-%20The%20Encyclopedia%2FPick%20Development%2FComments%20and%20Clarifications%20%28Notes%29)

### Movement units

Move a rule **with its continuation lines** and review nearby comments before and after. Never move a continuation independently so that it attaches to a different active rule. Disabled rules and comments are also authored information; keep their intended relationship with the rule block.

### Safe reporting

For every reorder, report: original order of source IDs; new order; every crossed rule and potential overlap; proof of equivalent full outputs or order-insensitivity; tests for overlapping inputs; and any changed diagnostic `_rid`/match sequence. If you cannot establish these, **leave the order unchanged** and explain the risk.

---

## 9. PICK ALL: prove count, order, and alignment

A PICK ALL result is not merely a set of unique values. Two overlapping rows can both return the same output; merging them may remove a duplicate. For a proposed merge, compare each input's **ordered list of matched outputs** before and after, including duplicates and all output columns. A merge of two rows into one is most plausible when their match domains are disjoint and the merged row's match domain is **exactly** their union. Even then, test row ordering against other rows and downstream expectations.

Dynamic `gv(...)` outputs can be empty in one output column but not another; removing or merging rows may change the alignment of parallel result columns. The catalog resolve documentation describes a case where empty group attributes cause PICK ALL output-column lists to drift out of sync. [Catalog Number Tables — Regex group-name pitfalls](https://dev.azure.com/etn-BidManager/7b29899a-fe07-44f6-94db-693b3738308a/_wiki/wikis/b6d5373b-e910-458a-8f94-b3961f20d3ba?pagePath=%2FPick%20Developers%20Technical%20Guide%20-%20The%20Encyclopedia%2FPick%20Development%2FCatalog%20Number%20Tables)

If consumer behavior is unknown, **do not collapse PICK ALL rows automatically**. Prepare a proposal with the specific overlap and output-count question for the owner instead.

---

## 10. Runtime expressions, queries, callbacks, and chains require extra proof

- An OUTPUT expression beginning with its own column name and `=` can compute a value from `gv(attribute)` after the rule matches. It is not a spreadsheet formula applied to stored numeric cells. Syntax, token spacing, and math functions must follow the technical guide. [Pick Table Operators — Supported Math Functions](https://dev.azure.com/etn-BidManager/7b29899a-fe07-44f6-94db-693b3738308a/_wiki/wikis/b6d5373b-e910-458a-8f94-b3961f20d3ba?pagePath=%2FPick%20Developers%20Technical%20Guide%20-%20The%20Encyclopedia%2FPick%20Development%2FPick%20Table%20Operators%2C%20Types%2C%20Ranges%20and%20Functions)
- Callbacks are special attribute names, sometimes parameterized with `~`; **not** generic function calls. Verify exact names, parameters, casing, and location against the implemented callback documentation. [Implemented Callbacks](https://dev.azure.com/etn-BidManager/7b29899a-fe07-44f6-94db-693b3738308a/_wiki/wikis/b6d5373b-e910-458a-8f94-b3961f20d3ba?pagePath=%2FPick%20Developers%20Technical%20Guide%20-%20The%20Encyclopedia%2FPick%20Development%2FImplemented%20Callbacks)
- OF3 queries can retrieve attributes from other objects and contain relation prefixes, comparisons, AND/OR grouping, and caret-encoded spaces in certain contexts. They are **not** a general replacement for rule-cell OR groups. Identify the consuming table/header and runtime object before touching them. [Pick Table Operators — OF3 Queries](https://dev.azure.com/etn-BidManager/7b29899a-fe07-44f6-94db-693b3738308a/_wiki/wikis/b6d5373b-e910-458a-8f94-b3961f20d3ba?pagePath=%2FPick%20Developers%20Technical%20Guide%20-%20The%20Encyclopedia%2FPick%20Development%2FPick%20Table%20Operators%2C%20Types%2C%20Ranges%20and%20Functions)
- Two rows that return the same immediate output but different `ss_chain` values can yield different final results. Follow the actual outbound chain and include its effective result in the comparison.
- Test Mode may not resolve OF3-dependent callbacks/queries; a compile plus the correct Bid Manager runtime scenario may be required. Explicitly mark this validation gap rather than claiming a trace proved everything.

---

## 11. Equivalent-result audit: required before any autonomous rewrite

For **every** proposed OR/group/range/wildcard/reorder transformation, fill out the following:

1. **Old effective rules:** exact source lines or `_rid`s, type, priority and continuation-attached cells.
2. **Old match coverage:** input combinations each old rule accepts, accounting for OR expansion, types, blanks, missing inputs, and earlier PICK ONE winners.
3. **New match coverage:** exact combinations the proposal accepts; enumerate extra cross-pairs, range boundaries, and absent inputs.
4. **Coverage difference:** inputs newly admitted and inputs lost. If either is nonempty, this is a behavior change unless a proven earlier PICK ONE row makes the difference unreachable with equivalent output.
5. **Outputs:** every output, including chains and runtime expressions, same effective value under all matched runtime states?
6. **Priority:** do earlier/intervening/later rules change which case wins? For each reorder, review all crossed rules.
7. **PICK ALL multiplicity:** does any input return a different number of matches or different ordered output list?
8. **OR scope:** are other rules affected by a changed OR? Is the name unique against the global/local scopes?
9. **Serialization:** is the file format and its column alignment/OR definition trusted enough to write correctly?
10. **Test results:** before/after match/output matrix, boundary cases, cross-products, missing input, fallback, and real runtime checks for unevaluable expressions.
11. **Uncertainty:** what assumptions rely on undocumented domains or runtime behavior?
12. **Disposition:** proven equivalent / conditionally equivalent pending domain confirmation / behavior-changing / not safely parseable.

**STOP RULE:** For raw PRN with uncertain syntax, unknown OR semantics, unclear continuations, unresolved duplicate table identity, PICK ALL overlap, runtime-dependent output without tests, or unproven priority changes: do **not** assert equivalence or commit an automatic rewrite. Deliver the candidate and the missing evidence instead. This is a targeted technical stop, not a general refusal to help.

---

## 12. Test strategy and action sequence

### Test matrix

For each changed candidate, include:

- each original literal/OR member;
- at least one input outside the new OR;
- all cross-products of independently changing dimensions;
- no-input cases where appropriate;
- exact boundary, below-boundary, above-boundary, gap, and fractional values for numeric rewrites;
- special PICK ONE overrides and fallback cases;
- PICK ALL overlap/count/order cases;
- downstream chain outputs and runtime-only cases.

Record original **winning row and full outputs** for PICK ONE, and original **ordered match/output list** for PICK ALL. After an accepted merge, winning `_rid`/trace identity may legitimately differ; compare agreed observable behavior and disclose that trace difference.

### Pick Workbench test and edit sequence

1. Inspect the table and file-local/global OR lists. An OR row's name is in its first cell and members in later cells. [OR lists — Edit OR lists](help/ors#edit-or-lists)
2. Capture a before-state export and run test cases on the **saved** version. The Workbench **Test** mode requests a save when a table has unsaved changes; it evaluates saved rules. [Testing a table — Run a test](help/testing#run-a-test)
3. Apply only the verified changes to the live grid. Keep comments, disables, continuations, and unrelated rows. A right-click cell menu offers Insert Row(s), Append Row(s), and Delete Row(s); do not use whole-table deletion for a row. [Editing a table — Rows](help/editing#rows-right-click-a-cell)
4. For a new OR, edit the appropriate file's **OR** table or the global OR table in `GLOBALS.json` as intended; ensure the group and rule-cell changes are both present before validating. [OR lists — Edit OR lists](help/ors#edit-or-lists)
5. Review unsaved changes in the grid. Do **not** auto-save unless authorized: Save Table, Save File, and Save All commit different scopes to the user's branch. A rule in one file and a global OR in another may require saving both. [Saving your work — Save buttons](help/saving#save-buttons)
6. Once saved with authorization, rerun the before-state tests and compare. Increase **Max failed rules** in Test settings if a target row is beyond the trace cap. [Testing a table — Test history](help/testing#test-history)
7. Compile the saved branch to check compiler problems, including OR name collisions. Compilation is not proof of behavioral equivalence. **Compile to Zip** does not deploy. **Deploy for Testing** affects the user alone in Bid Manager Dev, not everyone. [Compile and Deploy](help/compile-deploy)
8. Diff-versus-Dev compares saved branch with Dev; it is not automatically a before/after diff for your own optimization. Keep the before-state snapshot and recorded outputs. [Comparing with Dev — Open a diff](help/diff#open-a-diff)

For a legacy PRN, the equivalent workflow depends on the validated canonical PRN toolchain. Inspect/round-trip, apply the minimal source edit only when syntax is known, compile using that toolchain, and compare before/after behavior. Do not falsely present Pick Workbench JSON actions as raw PRN editing steps.

---

## 13. Agent output format: make autonomous decisions reviewable

Provide a report before or with each edit:

```text
Target: exact file + table, effective/shadowed status
Format: legacy PRN / Pick Workbench JSON / unknown
Table mode and full schema:
Before: active rules N; total source rows M
Candidate: original source lines or _rids; all effective input and output cells
Proposed OR(s): name, source file, scope, exact members, other existing uses
Proposed table changes: new row cells, placement, removed/edited source identities
Proposed reorder: old and new order; every crossed rule and overlap proof
Proof: coverage before and after, no-input behavior, priority, full outputs,
       chain result, PICK ALL count/order; counterexamples considered
Test matrix: exact inputs, before result, after result, validation limits
After: active rules K; net reduction N-K; new OR definitions
Status: suggestion only / edited but unsaved / saved to own branch / compiled
Remaining risks and decisions required:
```

If an OR table is unsupported by the agent's available editing tools, say so and provide the manual OR definition/location. Never claim it was created because the agent authored text describing it. If input lacks actual `.prn` text or project-specific JSON rules, produce this workflow, **not invented optimized rows**.

## Bottom line

Read the real source accurately first; reduce one dimension at a time; prove coverage and precedence; preserve all outputs and line types; test old vs new; and be transparent about format, runtime limits, and what was actually modified. A smaller table is only an optimization if its behavior and maintenance story are demonstrably better.
