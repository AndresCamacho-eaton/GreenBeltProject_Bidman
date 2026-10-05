# Optimizing Pick Tables: A Detailed Guide to Reducing Rows Safely

**Audience:** Pick rule authors and AI agents helping them.  
**Goal:** Make rules smaller, clearer, and easier to maintain **without silently changing their behavior**.  
**Scope:** An ordinary Pick table and its dependencies. This guide does not assume any particular ECPP table has been inspected or optimized.

> **Core rule:** Fewer rows is not automatically better. Preserve which inputs match, the outputs they return, the order and multiplicity of matches where relevant, and any chain/runtime side effects. If equivalence cannot be demonstrated, present the proposal as a behavior change, not a cleanup.

## Contents

1. Define the behavior you must preserve
2. Inventory the table before touching rows
3. Build a behavioral baseline and test set
4. Find low-risk reduction candidates
5. Merge rows with OR definitions
6. Avoid the Cartesian-product trap
7. Use ranges and numeric operators responsibly
8. Use wildcards and fallbacks responsibly
9. Handle PICK ONE priority and shadowed rules
10. Handle PICK ALL multiplicity and alignment
11. Treat queries, callbacks, expressions, and chains as outputs or inputs that matter
12. Separate readability improvements from compression
13. A rigorous equivalence checklist and example audit
14. A practical Pick Workbench workflow
15. An agent workflow for suggesting and applying changes
16. Common unsafe rewrites
17. Optimization worksheet template
18. References

---

## 1. Define the behavior you must preserve

### 1.1 PICK ONE

PICK ONE checks active rules in file order and returns the **first** match. A safe optimization preserves, for every relevant input:

- whether there is a match;
- the selected rule's entire effective output (including blank/omitted outputs and `ss_chain`);
- any downstream chained behavior; and
- priority against all earlier and later rules.

Changing which `_rid` wins can be acceptable **only if the user wants output-level equivalence rather than identical trace identity**, and all downstream effects are the same. State that distinction: consolidating two rows necessarily changes which row a test trace identifies for one of the old cases.

### 1.2 PICK ALL

PICK ALL evaluates all active rules and returns every match. Preserve:

- the set of input conditions matched;
- the **number of results** and their order when the consumer uses order;
- each returned output's value and alignment with other returned outputs;
- chain-related behavior where applicable.

Two identical-looking PICK ALL rows can be intentional: removing one may remove a repeated output. Merging two rows with the same output means one result instead of two for inputs matching both originals. **Do not deduplicate PICK ALL solely from equal-looking outputs.**

### 1.3 Define the equivalence target first

Ask what must remain equal: (A) only final product/pricing outputs, (B) full output lists including multiplicity/order, (C) chained results, and/or (D) trace row identity. An output-equivalent simplification may still change diagnostics and rule IDs. If the caller or another table depends on list length, repeated values, ordering, or match counts, preserve those too.

This guide primarily targets **behavior-preserving** changes. A business decision to broaden a range or remove an exception is a separate rule change and must be labeled as such.

---

## 2. Inventory the table before touching rows

Record these facts from the actual table, not assumptions based on its name:

1. **Exact identity:** table name, source file, and whether another table of the same name shadows it. If the copy is shadowed, optimizing it alone will not affect the effective runtime table.
2. **Type:** PICK ONE or PICK ALL.
3. **Column schema:** exact column names, INPUT/OUTPUT directions, and types. An `ALPHA` cell is not automatically a numeric range just because its text looks numeric.
4. **All line types:** active `Rule`, inactive `Disable`, `Comment`, and `Continuation`. Keep row comments and the rule to which a continuation belongs straight.
5. **Stable row IDs (`_rid`):** identify candidate rows by `_rid`, not the displayed row number. A `_rid` does not imply that a row is an active rule.
6. **Whole output signature:** every OUTPUT column, `ss_chain`, any expression, and the difference between a blank cell and a literal marker such as `~` if the table/consumer distinguishes them.
7. **OR definitions:** exact members, scope (local/global), and all other uses before modifying a shared OR.
8. **Priority/fallbacks:** where specific rules, broad rules, deliberate overrides, and final fallback rules appear.
9. **Runtime dependencies:** callbacks, `gv(...)`, OF3 object queries, chain targets, and any external consumer that interprets the output list.
10. **Saved versus unsaved:** if there are pending grid edits, analyze the live state; an on-disk read may be stale.

Construct a small comparison sheet for candidate active rows:

| Identity | Input signature | Full output signature | Position | Dependencies |
|---|---|---|---|---|
| `_rid 12` | `frame=F100; poles=2; voltage=208` | `price=400; ss_chain=PriceMore` | above fallback | local OR in frame? |
| `_rid 13` | `frame=F100; poles=2; voltage=240` | `price=400; ss_chain=PriceMore` | adjacent | same chain |

These are **illustrative values**, not ECPP data. Include all output columns in a real inventory; differences hidden off-screen are a common reason an apparently safe merge is not safe.

---

## 3. Build a behavioral baseline and test set

Before a substantive rewrite, write down representative inputs **and the current outputs**. For a PICK ONE table also record the winning `_rid`; for PICK ALL record the ordered list of matched rows and outputs.

Include at least:

- Each candidate row's ordinary matching case.
- Cases matching any overlapping rule above or below it.
- Values outside the candidate group, including other values of the same input column.
- Missing inputs and empty input values when the application can produce them.
- Numeric values immediately below, on, and above proposed boundaries.
- Every exception and fallback case.
- Inputs exercising OR members and values not in the OR.
- Cases using a chain or runtime-calculated output, including the downstream result where possible.

For a table with two or more varying dimensions, deliberately test **cross-combinations**, not just the original rows. For example, if the originals cover `(frame=F100, poles=2)` and `(frame=F250, poles=3)`, test the cross-pairs `(F100,3)` and `(F250,2)` even if nobody thinks they are used. That is how accidental broadenings surface.

A test is not exhaustive proof for a large domain; combine tests with the logical checks in sections 5–9. Preserve a copy of the original rules and a before/after table of expected results so reviewers can see what changed.

---

## 4. Find low-risk reduction candidates

Work from safer transformations to riskier ones.

### 4.1 Exact duplicate active rows

If two PICK ONE rows have identical **complete input conditions and complete outputs**, the later row cannot win for any input that reaches the earlier identical row. Check continuations, comments, disabled lines, and whether deleting the later row would disrupt documentation or intentional test identity. For PICK ALL, **do not assume duplicates are redundant**: both can return results.

### 4.2 Same outputs, one input difference

This is the best OR-list candidate. Two or more rows have identical inputs **except for one column** and identical complete outputs. Consolidating the alternatives in that one column generally avoids cross-combining conditions across other columns. Still check missing-input behavior, OR membership, priority position, and any overlap with other rules.

### 4.3 Consecutive numeric cases

Rows sharing all other inputs and outputs might be expressed as an inclusive/exclusive numeric interval **if** the column type supports a range, the covered values are truly continuous, and there are no holes, overrides, or invalid inputs that matter.

### 4.4 Redundant conditions

An input column may repeat the same value or condition across a block. Repetition by itself does **not** justify removing the condition; it may prevent the block from catching another product or a missing input. Only make it a wildcard if every newly admitted input is proved safe.

### 4.5 Broad refactors

Splitting a table, introducing an output expression or lookup, changing column types, changing shared ORs, or consolidating nonadjacent PICK ONE rules has wider effects. Treat each as a separate design proposal, not a casual row cleanup.

---

## 5. Merge rows with OR definitions

An OR is a named set of allowed values, used in an INPUT cell. A local OR is defined in the file's OR table; a global OR is defined in `GLOBALS.json` and can be used across the project. Supply actual member values as inputs, never the OR name. Global and local definitions have different scopes; a local/global name collision stops compilation. See [OR lists › Local and global ORs](help/ors#local-and-global-ors) and [OR lists › Tips](help/ors#tips).

### 5.1 Ideal one-column consolidation

**Before — hypothetical PICK ONE table, `voltage` is INPUT:**

| Rule | frame | poles | voltage | price | chain |
|---|---|---:|---:|---:|---|
| A | F100 | 2 | 208 | 400 | PriceMore |
| B | F100 | 2 | 240 | 400 | PriceMore |
| C | F100 | 2 | 480 | 400 | PriceMore |

Define an OR with **exactly** the documented voltage members in the appropriate scope, e.g. an illustrative name `SupportedF100Voltages` containing `208`, `240`, and `480`. Then use one row:

| frame | poles | voltage | price | chain |
|---|---:|---|---:|---|
| F100 | 2 | SupportedF100Voltages | 400 | PriceMore |

This removes two rule rows, but only when:

- All other INPUT cells (including rarely-used ones) are identical.
- Every OUTPUT cell, expression, and `ss_chain` is identical.
- OR members are exactly the intended alternatives and valid for that input type.
- Missing-input handling and rule priority remain equivalent in this location.
- Other rules using the OR will not be changed unexpectedly; a new local OR is often narrower in scope than editing an existing global OR.

**Do not assume a convenient existing OR contains only these three values. Expand it and compare its complete membership first.**

### 5.2 What ORs do and do not do

- They can shorten many literal alternatives into a single input-cell condition.
- They do not automatically preserve behavior if different original rows returned different outputs.
- They do not make an OUTPUT cell a computed conditional value.
- They do not mean passing the OR's name as the external test input.
- They are not interchangeable with `OR` clauses inside an OF3 object query.

### 5.3 OR maintenance costs

A single-use OR can make a table shorter but move the complexity into a separate definition. Prefer descriptive names and document their scope. For widely reused groups, a global OR can reduce duplication, but changing one later can affect every referring table. Count the maintenance cost of the definition, not just the visible number of rule rows.

---

## 6. Avoid the Cartesian-product trap

This is the most important unsafe merge.

**Before — hypothetical rules:**

| frame | poles | price |
|---|---:|---:|
| F100 | 2 | 400 |
| F250 | 3 | 400 |

These cover **two correlated pairs**: `(F100,2)` and `(F250,3)`.

**Unsafe proposed row:**

| frame | poles | price |
|---|---|---:|
| OR of F100/F250 | OR of 2/3 | 400 |

Because separate INPUT columns are ANDed, the merged row accepts the **Cartesian product**:

```text
(F100,2)  (F100,3)
(F250,2)  (F250,3)
```

The two cross-pairs did not match the originals. If they previously fell through to another rule or returned nothing, behavior has changed.

### The rectangle test

When merging variation in two columns, ask whether the original rules contain **every** pair in the product of the chosen value sets, with the same complete outputs and priority effect. If the original covered set is not a full rectangle, **do not collapse it to independent ORs.**

For three varying columns, check the full three-dimensional product. The explosion is real: three options in each of three columns yields 27 possible combinations. A proposed merged row must be safe for all 27, not just the few listed originals.

### Safer alternatives

1. Group by one constant dimension and merge **only one changing column** at a time.
2. Keep a compact set of rows if the original cases are correlated.
3. Consider a verified lookup or a different table structure only if it improves clarity and the downstream consumer accepts it.

Do not call two correlated inputs independent merely because their outputs happen to agree for the known rows.

---

## 7. Use ranges and numeric operators responsibly

The documented input-cell operators `<`, `<=`, `>`, `>=`, and `=` require `NUM`, except `<>`, which works on any type. Range notation uses square/round brackets for included/excluded endpoints, and the range type must support that notation; verify `RANGE` versus `REAL_RNG` in the specific table. See [Pick Table Operators, Types, Ranges and Functions](https://dev.azure.com/etn-BidManager/7b29899a-fe07-44f6-94db-693b3738308a/_wiki/wikis/b6d5373b-e910-458a-8f94-b3961f20d3ba?pagePath=%2FPick%20Developers%20Technical%20Guide%20-%20The%20Encyclopedia%2FPick%20Development%2FPick%20Table%20Operators%2C%20Types%2C%20Ranges%20and%20Functions).

### 7.1 Contiguous cases

**Before — illustrative numeric input, identical outputs:**

```text
amps=100 → code=A
amps=101 → code=A
amps=102 → code=A
```

A proposed `[100,102]` interval also matches **noninteger numeric values** such as `100.5` if the input/domain admits them. A `RANGE` type and documented integer-only business domain may make it appropriate, but do not infer domain restrictions solely from the displayed rows. Confirm the input type, actual runtime values, and boundaries before replacing the three literals.

### 7.2 Open and closed boundaries

`[100,200)` includes `100` but excludes `200`. `(100,200]` excludes `100` and includes `200`. For adjacent intervals, test the shared boundary and just above/below it. Avoid gaps and overlaps that alter which PICK ONE rule wins.

### 7.3 Holes and exceptions

If the intended set is `100–199` except `150`, one interval alone adds the excluded value. Possible remedies include retaining separate ranges or an earlier explicit exception **only if the original fallback/priority behavior is preserved**. In PICK ALL, an exception row does not cancel a later broad matching row: both may return. An exception therefore is not a universal fix for a broad range.

### 7.4 Avoid changing column types as a shortcut

Changing `ALPHA` to `RANGE` or `NUM` is a table-wide semantic change. Review every row in the column and every caller first. It is not a safe way to make only one optimization possible.

### 7.5 Avoid assuming output equations are equivalent to many literals

An output expression such as `OutCol = int(gv(NumS)) * 6` has documented runtime syntax and can replace repetitive literal outputs **only** if every original output equals the expression on every covered input, the required attribute is present in the actual runtime context, and the consumer tolerates the expression. It is a different kind of change from grouping rows and may not be evaluable in a simple Workbench trace. See the [supported math functions reference](https://dev.azure.com/etn-BidManager/7b29899a-fe07-44f6-94db-693b3738308a/_wiki/wikis/b6d5373b-e910-458a-8f94-b3961f20d3ba?pagePath=%2FPick%20Developers%20Technical%20Guide%20-%20The%20Encyclopedia%2FPick%20Development%2FPick%20Table%20Operators%2C%20Types%2C%20Ranges%20and%20Functions).

---

## 8. Use wildcards and fallbacks responsibly

An empty **INPUT** cell is a wildcard. It matches any provided input and can still match when that input is missing. It is not equivalent to enumerating a finite set of currently known values unless all other values are genuinely meant to behave the same way.

### 8.1 Removing an apparently redundant condition

**Before — hypothetical:**

| frame | voltage | result |
|---|---|---|
| F100 | 208 | A |
| F100 | 240 | A |

Replacing both with `frame=F100; voltage=(blank); result=A` also covers 480, missing voltage, and any future voltage. This is a **broadening**, not a provably lossless compression. Prefer a finite OR containing only 208 and 240 when those are the intended alternatives.

### 8.2 Fallback position

A catch-all rule at the bottom of a PICK ONE table provides a fallback. Moving it upward may hide specific rules. A newly created blank enabled rule above real rules is an accidental catch-all; do not leave blank starter rows when populating a table.

### 8.3 Negation is not a finite OR

A condition `<>Y` accepts more than a finite list like `N` and `Unknown`; it may also match missing input. Do not replace a finite OR with `<>Y` unless all other possible values and missing-input behavior are intentionally included.

---

## 9. Handle PICK ONE priority and shadowed rules

### 9.1 Why same-output rows can still be unsafe to merge

Consider:

```text
1. frame=F100, voltage=208             → A
2. frame=F100, voltage=240, trip=LSIG  → B
3. frame=F100, voltage=240             → A
```

Rows 1 and 3 both return A, but they are separated by a more specific B rule. A new row before row 2 with `voltage=OR(208,240)` and blank trip would wrongly catch `voltage=240, trip=LSIG` before the B rule. A new row after row 2 may preserve those outputs, **but only after checking every input newly covered by that placement**, including missing trip and other rows. Do not merge nonadjacent rows without examining all intervening rules.

### 9.2 Reachability, not just overlap

For a proposed row at a particular position, look at inputs that reach that position (inputs not already caught by earlier rules). On those inputs, the proposed condition must return the same full output as the original table would. Anything matching the proposed row that previously reached a later rule with a different output is a regression.

### 9.3 Earlier-rule shadowing

A later rule may never win because an earlier broader row always matches its inputs. This can be a genuine dead rule, but do not delete it blindly:

- A missing input or negated condition may change your apparent subset relationship.
- Continuation rows or callbacks may affect effective cells.
- The rule might be a deliberately preserved future configuration or documentation.
- Removing it changes future maintenance and trace identity even if today's output is the same.

Show a reachability argument and tell the owner why it appears shadowed. Where intent is unclear, annotate it rather than silently deleting it.

---

## 10. Handle PICK ALL multiplicity and alignment

PICK ALL needs stricter review than PICK ONE for deduplication and mergers.

### 10.1 Overlap changes count

Suppose two original rules each return `part=X`, and both match the same input. That input originally receives two matches. One consolidated row produces one match. Even if the visible value `X` looks the same, a BOM, drawing operation, quantity, or other consumer may depend on the repeated result.

A simple merge from rows A and B to one row is only a candidate when the two original match sets are **disjoint** on the relevant input domain and the merged row matches exactly their union, with no count/order difference for any input. Verify downstream interpretation as well.

### 10.2 Output alignment matters

If multiple output columns carry parallel result lists, an optimization that removes/empties a value in only one output can misalign the lists. Runtime `gv(...)` expressions can produce empty values for absent attributes; in catalog resolve documentation, a Pick All result with empty `gv(...)` values can yield differing output counts and break alignment. Do not collapse such rows without checking attribute presence and column-wise returned counts. See [Catalog Number Tables — Issues With Regular Expression Group Names](https://dev.azure.com/etn-BidManager/7b29899a-fe07-44f6-94db-693b3738308a/_wiki/wikis/b6d5373b-e910-458a-8f94-b3961f20d3ba?pagePath=%2FPick%20Developers%20Technical%20Guide%20-%20The%20Encyclopedia%2FPick%20Development%2FCatalog%20Number%20Tables).

### 10.3 Ordering matters where consumed

Even if a PICK ALL table matches the same number of rows before and after, reordering output rows may change a drawing/BOM/printed sequence. Identify how the consumer treats ordering before rearranging rows for appearance.

---

## 11. Treat queries, callbacks, expressions, and chains as behavior

### 11.1 INPUT headers can query runtime state

An INPUT column might represent an ordinary attribute, a callback, or an OF3 query. Identical-looking row cells do not prove equivalence if the header resolves differently after a column change. If a query can return no value, test the missing-input case. Do not rewrite the query merely to save rule rows; verify syntax and runtime context first.

### 11.2 OUTPUT cells may calculate dynamically

Two cells are not interchangeable just because they produced the same output for one test. A literal `400` differs from an expression that happens to evaluate to 400 today. Compare the entire output definition and test the attributes it reads across representative runtime cases.

### 11.3 `ss_chain` is part of the output signature

If one row chains to `TableB` and another has no chain—or chains to a different table—they are not equivalent, even if their immediately visible `price` output is the same. Downstream results can override earlier outputs and add new ones. Follow only real outbound `ss_chain` references; an inbound relationship does not imply a reverse edge.

### 11.4 OR changes can have project-wide effects

Changing a global OR to make one merge possible may alter matching in unrelated files. Locate all uses and choose a new, narrowly scoped definition if that better preserves behavior. Local ORs apply to tables in their defining file; a name used locally in one file does not necessarily mean the same list in another.

---

## 12. Separate readability improvements from compression

A table can become more readable **without deleting rows**:

- Add an accurate table-level description explaining priority, scope, fallbacks, and exceptional inputs.
- Use Comment rows to label logical sections; keep comment text under the intended column and preserve line type.
- Place specific cases above their fallback in PICK ONE, **only after proving behavior does not change**.
- Use a well-named OR for a genuine group rather than a cryptic numeric abbreviation; document its members and scope.
- Keep intentional exceptions explicit when compression would obscure them.
- Remove truly dead rows only after establishing reachability and preserving author intent; a disabled row or comment may be intentional documentation, not garbage.
- Avoid over-condensing a small, easy-to-scan table into one opaque row and a large remote OR definition.

A useful review metric is **maintenance complexity**, not only active row count. Count new ORs, complexity of conditions, number of priority exceptions, hidden dependencies, and effort required to understand or test a rule.

---

## 13. A rigorous equivalence checklist and example audit

For every proposed transformation, write a before/after statement. For a proposed rule at position P, answer:

1. **Original coverage:** Which concrete input combinations match the rows to be removed, and which are actually reachable after earlier rules?
2. **Proposed coverage:** Which inputs does the new row accept, including unseen values and no-input cases?
3. **Coverage delta:** `newly accepted = proposed coverage − original winning coverage`; `lost = original winning coverage − proposed coverage`.
4. **Output equality:** Is the complete output vector (including blank outputs, expression text, and chain) the same on all relevant inputs?
5. **Priority:** Do any earlier, intervening, or later rules win differently?
6. **Multiplicity:** In PICK ALL, does any input return a different number/order of rows or a different arrangement of output values?
7. **Dependencies:** Does the OR definition, query, callback, or chain affect other tables/consumers?
8. **Runtime limits:** Which parts can Test mode actually verify, and which require a real takeoff/runtime check?
9. **Trace identity:** Which previous `_rid`s disappear, and is that acceptable for debugging/auditing?
10. **Reversibility:** Is the original state documented or exported, and have the proposed unsaved edits been reviewed before save?

### Mini audit: safe candidate

```text
PICK ONE, adjacent rules, identical other INPUTs and all OUTPUTs:
frame=F100, poles=2, voltage=208 → code=A, ss_chain=PriceMore
frame=F100, poles=2, voltage=240 → code=A, ss_chain=PriceMore
```

A local OR containing **only** `{208, 240}` is a candidate. Check OR semantics for numeric column and missing inputs, compare intervening/earlier/later rules, then test 208, 240, 480, missing voltage, and overlap cases. It is a candidate until validated, not an automatic rewrite.

### Mini audit: unsafe candidate

```text
frame=F100, poles=2 → code=A
frame=F250, poles=3 → code=A
```

One row with an OR in `frame` and another OR in `poles` adds `(F100,3)` and `(F250,2)`. **Reject** unless those cross-pairs already had identical effective results and priority behavior and the owner explicitly accepts the changed rule coverage.

---

## 14. A practical Pick Workbench workflow

The steps below describe the documented UI, not a claim that any ECPP table was changed.

### 14.1 Locate and inspect

1. Open the target table, verify its first header rows for column name, INPUT/OUTPUT, and Type; inspect **Line Type** for active rules, comments, disabled rules, and continuations. [Reading a table › Row types](help/reading-a-table#row-types-rule-disable-comment-continuation)
2. To find repeated outputs or literals in the current table or file, use **Find** (`Ctrl+F`); **Replace** is available via `Ctrl+H`. Find & Replace supports a whole-cell match option. Do not blindly use **All** on an OR name or output without checking other uses. [Find, filter and search › Find and replace](help/find-filter-search#find-and-replace)
3. If needed, use **Export ▾ → Current Table** or **Whole File** to obtain a before-state spreadsheet for review. [The project screen › Toolbar](help/workspace#toolbar)
4. If the table is a shared file, or is in **Test**/**Diff** mode, editing is read-only; leave the mode or edit the owning project as appropriate. `_rid` is also read-only. [Editing a table › When you can't edit](help/editing#when-you-can-t-edit)

### 14.2 Establish a test baseline

1. With the table open, select **Test**. If it has unsaved changes, the UI asks you to save first because the test runs saved rules; do not mistake an unsaved proposal for the tested version. OR tables themselves cannot be tested this way. [Testing a table › Run a test](help/testing#run-a-test)
2. Enter concrete input values in the test-input row, then select **Run Test**. Record outputs for the baseline matrix from section 3. [Testing a table › Run a test](help/testing#run-a-test)
3. Inspect why rules matched or failed by clicking the relevant result rows and reading their column-by-column trace. Increase **Max failed rules** via the settings control if the rule you need is beyond the current trace cap. [Testing a table › Test history](help/testing#test-history) and [Colors and visual cues › Test mode colors](help/grid-colors#test-mode-colors-lavender-row-green-red-and-grey-rows-red-edge)
4. Leave Test mode before editing; it is read-only. [Editing a table › When you can't edit](help/editing#when-you-can-t-edit)

### 14.3 Create or verify an OR definition

1. For a file-local OR, open the **OR** entry under that file. For a global OR, open the OR entry in `GLOBALS.json`. Each row has the OR name in the first column and **one member value per following column**. [OR lists › Edit OR lists](help/ors#edit-or-lists)
2. Check its complete membership and other uses. Never expand an existing global OR just to make one candidate merge appear convenient unless those other consumers should expand too. Local/global collisions cause compile errors. [OR lists › Local and global ORs](help/ors#local-and-global-ors)
3. Edit the definition as needed and save it along with the table changes when ready. The documented file delimiter is `;`; do not type a semicolon as part of one member value in a rule cell. [OR lists › Edit OR lists](help/ors#edit-or-lists)
4. Return to the rule table and use the OR's exact name in the intended **INPUT cell**. The external input remains an actual member value, not the name of the OR. [OR lists › Tips](help/ors#tips)

### 14.4 Make a careful table edit

1. Edit a cell by clicking and typing; use `F2`/double-click to edit inside an existing value. **Line Type**, **I/O**, and **Type** use drop-downs. [Editing a table › Edit a cell](help/editing#edit-a-cell)
2. To insert a rule in a priority-sensitive position, right-click a cell and choose **Insert Row(s)**; to add at the bottom use **Append Row(s)...**. **Delete Row(s)** removes selected rows. Check exact row selection before deletion and keep continuations together with the rule they extend. [Editing a table › Rows (right-click a cell)](help/editing#rows-right-click-a-cell) and [Reading a table › Row types](help/reading-a-table#row-types-rule-disable-comment-continuation)
3. For copying existing rows, use copy/paste; **Insert Copied Row(s)** (`Ctrl+Shift+V`) inserts without overwriting existing rows, while **Append Copied Row(s)** adds them to the end. Ordinary Paste overwrites cells under the cursor. [Editing a table › Copy, cut and paste](help/editing#copy-cut-and-paste)
4. Inspect the live grid for unintended blank enabled rules, orphaned continuations, changed line types, and broadened wildcard cells. Use Undo (`Ctrl+Z`) for an accidental edit before committing. [Keyboard and mouse shortcuts › In the grid](help/keyboard-shortcuts#in-the-grid)

### 14.5 Save, retest, and compare

1. Save deliberately: **Save Table** saves one table, **Save File** saves changes in the active file, and **Save All** saves project-wide edits. Saving commits to **your own branch**, not Dev. When a change spans the OR definition and the rule table, make sure **both** are saved, even if they are in different files. [Saving your work › Save buttons](help/saving#save-buttons)
2. Rerun the complete baseline matrix and compare the result for each case, including new combinations introduced by a proposed OR or wildcard. If runtime queries or callbacks cannot be evaluated in Test mode, verify those scenarios in the appropriate runtime environment.
3. **Diff** compares **saved** content of your branch against Dev, not automatically against your personal before-state. Use it to review the scope of saved changes, but use your baseline/export to prove behavioral equivalence. [Comparing with Dev › Open a diff](help/diff#open-a-diff) and [Comparing with Dev › Read a diff](help/diff#read-a-diff)
4. Compile the saved branch to validate it. **Compile to Zip** checks/builds the branch and downloads bins without deploying. **Deploy for Testing** makes the saved branch available in Bid Manager Dev **for you only**, not for everybody. Never claim a rule is shared or live merely because it compiled. [Compile and Deploy](help/compile-deploy) and [Compile and Deploy › Compile to Zip](help/compile-deploy#compile-to-zip)

**Important sequencing:** The UI test asks to save before testing unsaved edits. A disciplined review therefore makes a before-state test/export, stages edits, reviews the pending changes, saves consciously, and then runs after-state tests. Saving is a commit to your branch, not a reversible unsaved draft. Do not tell someone a Diff-vs-Dev view by itself proves equivalence with their baseline.

---

## 15. An agent workflow for suggesting and applying changes

If the user asks an agent to **analyze only**:

1. Read the exact effective table and any unsaved live copy.
2. Discover related OR definitions, comments, continuations, and chain targets.
3. Identify concrete candidate `_rid`s with complete before/after rule snippets.
4. Classify each suggestion: safe candidate, needs a domain decision, or behavior-changing.
5. Include a coverage/priority/multiplicity proof sketch and a test matrix.
6. Do not edit, save, or claim equivalence based only on visual similarity.

If the user explicitly asks the agent to **optimize the table**:

1. Verify the specific table and intended equivalence standard; do not guess a target if several tables are possible.
2. Inspect saved versus live rows and preserve comments/disabled/continuations.
3. Prefer a surgical edit preserving unrelated `_rid`s instead of regenerating the entire table.
4. Apply all justified rule edits to the live grid, explain exactly which `_rid`s changed/deleted/added, and state what is still unverified.
5. Do not silently create/change an OR if the editing tool does not support OR tables; give the user the exact definition needed and identify the appropriate scope.
6. Leave changes **unsaved** unless the user explicitly asks to save. Offer validation/compilation after review.
7. Re-read the **live** unsaved grid if checking edits before saving; the saved-file view may not yet include them.

An optimization is not complete merely because the row count dropped. It is complete when its behavioral claims have been checked, any exceptions documented, and the owner can still understand how the rules work.

---

## 16. Common unsafe rewrites

| Proposal | Why it may be wrong | Safer approach |
|---|---|---|
| Merge rows by matching only the `price` output | Other outputs or `ss_chain` differ | Compare **all** outputs and downstream behavior |
| Merge ORs in two independent input columns | Admits cross-combinations that did not exist | Merge one varying dimension or prove full Cartesian coverage |
| Replace enumerated values with a blank input cell | Admits unknown, future, and missing values | Use an exact OR when the set is finite |
| Merge two nonadjacent PICK ONE rows above an exception | Broad row steals the exception's priority | Inspect intervening rules; keep exceptions ordered and test |
| Delete repeated PICK ALL rows | Removes a result/quantity | Confirm overlapping match counts and consumer semantics |
| Replace numeric literals with an inclusive interval | May add gaps' missing values or decimals; may change boundaries | Confirm type/domain and test boundaries |
| Replace a finite OR with `<>X` | Negation admits all other values and possibly missing input | Keep the finite set unless broadening is intended |
| Alter a shared global OR for one table | Affects every other use | Inspect references; use a narrower local/new OR if appropriate |
| Treat `Comment`/`Disable` as redundant rules | They are documentation or intentionally inactive | Preserve line type and author intent |
| Delete only a rule while leaving a continuation | Continuation may attach to another rule above | Inspect and update its continuation lines together |
| Assume Test mode proves runtime `gv(...)` behavior | Runtime-only expressions/queries may not evaluate there | Validate in the correct takeoff/runtime context |
| Review only a Diff vs Dev | Diff compares branches, not necessarily before vs after your cleanup | Retain a before-state export and result matrix |

---

## 17. Optimization worksheet template

Copy and fill this out before each proposed group of row reductions:

```text
Project / effective table / file:
Saved or live-unsaved version inspected:
Table type: PICK ONE / PICK ALL
Candidate _rids and line types:
Adjacent or nonadjacent? Intervening rules:
Input columns, types, and original conditions:
All output columns, expressions, and ss_chain:
Current OR definitions and source / other uses:
Existing matching input set:
Proposed matching input set:
Inputs newly admitted by proposal:
Inputs lost by proposal:
Missing-input, case, and numeric-boundary effects:
PICK ONE priority / earlier and later winners:
PICK ALL count / order / output alignment:
Downstream chains and runtime-only dependencies:
Proposed replacement rules (exact cells, placement):
Rows removed / rows added / net active-rule reduction:
New OR definitions and maintenance cost:
Baseline test cases and expected before/after results:
Validation gaps requiring runtime testing:
Status: proved candidate / needs owner decision / behavior change
```

## 18. References

- [Pick Table Operators, Types, Ranges and Functions](https://dev.azure.com/etn-BidManager/7b29899a-fe07-44f6-94db-693b3738308a/_wiki/wikis/b6d5373b-e910-458a-8f94-b3961f20d3ba?pagePath=%2FPick%20Developers%20Technical%20Guide%20-%20The%20Encyclopedia%2FPick%20Development%2FPick%20Table%20Operators%2C%20Types%2C%20Ranges%20and%20Functions) — documented input operators, range notation, output math.
- [Catalog Number Tables](https://dev.azure.com/etn-BidManager/7b29899a-fe07-44f6-94db-693b3738308a/_wiki/wikis/b6d5373b-e910-458a-8f94-b3961f20d3ba?pagePath=%2FPick%20Developers%20Technical%20Guide%20-%20The%20Encyclopedia%2FPick%20Development%2FCatalog%20Number%20Tables) — example of Pick All output-alignment hazards.
- [OR lists › Edit OR lists](help/ors#edit-or-lists) and [OR lists › Local and global ORs](help/ors#local-and-global-ors) — how ORs are stored, edited, and scoped.
- [Editing a table › Rows](help/editing#rows-right-click-a-cell) and [Editing a table › Copy, cut and paste](help/editing#copy-cut-and-paste) — documented grid editing actions.
- [Testing a table › Run a test](help/testing#run-a-test) and [Testing a table › Test history](help/testing#test-history) — test workflow and trace depth.
- [Saving your work › Save buttons](help/saving#save-buttons), [Comparing with Dev › Open a diff](help/diff#open-a-diff), and [Compile and Deploy](help/compile-deploy) — validation and persistence scopes.

**Final principle:** Compress a rule set only when you can explain why the new conditions cover exactly the intended inputs and produce the same complete results. Otherwise, document the opportunity and ask for a business decision rather than silently broadening the table.
