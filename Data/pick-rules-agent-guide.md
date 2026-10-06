# Pick Rules — Detailed Agent Guide

**Purpose:** Help an AI agent accurately read, explain, test, and author Eaton Pick rules without inventing project facts or mixing up Pick’s different expression languages.

> **Important:** Pick projects and runtime integrations can contain legacy conventions and feature-specific syntax. Project data and verified technical documentation take precedence over examples in this guide. When syntax is uncertain, look it up; do not improvise.

## Contents

1. Agent operating principles
2. Pick’s rule-evaluation model
3. Table schema and data types
4. Rule-cell matching syntax
5. Row types and ordering
6. OR definitions
7. Table chaining
8. OF3 queries — advanced object lookup
9. Query prefixes, filters, grouping, and aggregation
10. Structure/compartment queries
11. Output expressions and math functions
12. Callbacks
13. Testing and debugging
14. Authoring and change-safety workflow
15. Project structure, identity, and compilation lifecycle
16. Common confusions and failure patterns
17. Explanation templates
18. Verified references

---

## 1. Agent operating principles

### 1.1 Evidence first

Use the actual project’s tables, comments, OR definitions, row types, chain outputs, and evaluation traces as evidence. Do not infer behavior from a table name, product name, similar project, or remembered convention.

For any conclusion about a specific rule, identify the table and row `_rid`, the relevant columns and values, and the line type. An `_rid` is a stable row identifier, **not** a displayed row number, and comments/disabled/continuation rows can also have one.

### 1.2 Preserve exact identity

- Preserve table, column, OR, and file names exactly, including case where names are case-sensitive.
- Check for duplicate table names in different files. If copies exist, establish which one the compiler uses before describing or changing behavior; report shadowed copies.
- Distinguish local OR definitions from global OR definitions and report their source.
- Follow only verified outbound `ss_chain` values when describing a forward evaluation path.

### 1.3 Separate the languages

Pick-related tables may contain several syntaxes that look similar but do different jobs:

1. **Rule match cells** — compare provided inputs to a row’s INPUT cells; blank input cells are wildcards.
2. **OF3 queries** — locate objects/attributes in an OF3 tree; clauses use operators and Boolean grouping.
3. **Output expressions** — calculate a returned OUTPUT value after the rule matches; often use `gv(...)`.
4. **Callbacks** — special parameterized attribute names evaluated by runtime code.
5. **Workbench calculation formulas** — formulas used by an editing dialog to recalculate stored numeric cells. These are not automatically Pick runtime expressions.

Never translate syntax from one category into another without checking its documented use.

### 1.4 Be explicit about uncertainty

If a callback/query name, parameter, prefix, function, or feature-specific convention is not verified, say so and consult the rule-authoring documentation. Never fabricate a plausible-looking function or claim that an example works in every table context.

---

## 2. Pick’s rule-evaluation model

A Pick table is a decision structure: inputs are matched against rows and matched rows produce outputs.

### PICK ONE

- Evaluate active rules from top to bottom.
- Stop at the first matching rule.
- Row order is priority. More specific rules usually belong above broad rules and fallbacks.
- A broad wildcard row before a specific row can prevent the specific row from ever being reached.

### PICK ALL

- Evaluate all applicable active rules.
- Return every matching result, rather than stopping at the first match.

### Rule conditions combine with AND

For a row to match, every INPUT column condition on that row must be satisfied. A blank INPUT cell imposes no condition and therefore matches any value, including a missing value. OUTPUT cells do not constrain matching.

A table’s type, column I/O, and row order must be verified from the actual table before explaining how it evaluates.

---

## 3. Table schema and data types

Each column has a name, an I/O direction, and a type.

### I/O direction

| Direction | Meaning |
|---|---|
| `INPUT` | A condition the engine matches against provided attributes. |
| `OUTPUT` | A result value returned when a rule matches. |

Anything not designated `OUTPUT` is treated as `INPUT`. Do not infer direction just from a column name.

### Common types

| Type | General meaning and use |
|---|---|
| `ALPHA` | Text/string. Ordinary literal matching is exact and case-sensitive. |
| `NUM` | Numeric input. Supports numeric comparisons such as `>=600`; integer-oriented in common table conventions. |
| `FLOAT` / `REAL` | Decimal numeric values. These are treated equivalently by the engine in common Pick table usage. |
| `RANGE` | Numeric interval, conventionally used for whole-number ranges. |
| `REAL_RNG` | Numeric interval for decimal values. |

Legacy type labels may appear. If a type is unrecognized by the engine, it may be treated as `ALPHA`; verify instead of assuming an old label’s intended semantics.

### Interval notation

- `[a,b]`: includes both ends.
- `(a,b)`: excludes both ends.
- `[a,b)` or `(a,b]`: includes only the square-bracket endpoint.

For example, `[1,4)` includes 1 but excludes 4. Confirm the column type and the exact range cell before reasoning about a boundary.

### Operators in rule input cells

Common numeric operators are:

| Cell form | Meaning | Typical type restriction |
|---|---|---|
| `<n` | Input is less than `n` | `NUM` |
| `<=n` | Input is less than or equal to `n` | `NUM` |
| `>n` | Input is greater than `n` | `NUM` |
| `>=n` | Input is greater than or equal to `n` | `NUM` |
| `=n` | Input equals `n` | `NUM` |
| `<>x` | Input is not equal to `x` | Any column type |

The rule-cell format is a **match condition**, not an instruction to pass that text as the input. For a condition `>=600`, the input should be an actual number such as `600` or `700`, not the string `>=600`.

---

## 4. Rule-cell matching syntax

A row’s INPUT cells work together as a conjunction (AND): every nonblank condition must pass.

### Literal and wildcard cells

- A literal cell such as `F250` requires that input value.
- An empty cell is a wildcard: it accepts any value and does not require the input to exist.
- A blank OUTPUT cell is just a blank result; it is not an input wildcard.

### Missing or unrecognized input

If no input is supplied for a column—or the supplied value is not represented in the relevant table—the evaluation may report **no input** for that column. A rule cell that requires a value then fails. A blank wildcard cell can still match. A negated condition such as `<>X` can match when no value is supplied, because the missing value is not `X`.

Do not describe a missing input as if it were a literal empty string unless the trace or runtime data explicitly shows that.

### OR, ranges, and operators

- OR cell: pass an actual member value, not the OR’s name.
- Range cell: use a number within its interval for a matching test.
- Negation `<>X`: choose a real value other than `X` to satisfy it. Passing `X` is the excluded case; passing the literal text `<>X` is not a valid way to test it.
- For PICK ONE, also check whether an earlier row matches first.

---

## 5. Row types and ordering

Every row must be interpreted according to its line type.

| Line type | Runtime interpretation |
|---|---|
| `Rule` | Active rule row. |
| `Disable` | Retained in the source/grid but never matches at runtime. |
| `Comment` | Documentation, not a rule. The text can be in any column. |
| `Continuation` | Extends the previous rule’s cell values; not an independent rule. |

A continuation’s values append to the preceding rule’s corresponding cells. Disabled/comment lines between the rule and continuation do not turn the continuation into an independent rule. When copying or regenerating a table, preserve every line type and column alignment.

For PICK ONE tables, rule order can change behavior. A new catch-all or broad rule should not be inserted above specific rules unless that priority is intended.

---

## 6. OR definitions

An OR is a named list of values that can be used in an INPUT cell as a shorthand for matching any list member.

### OR rules

- The caller supplies a concrete member value; an OR name itself is not a valid substitute for one of its values.
- ORs can be defined locally in a file or globally in `GLOBALS.json`.
- A file-local OR is scoped to its file’s tables. A global OR is available throughout the project.
- Local OR names can be reused in different files. Repeated names within one scope can cause warnings or precedence effects; inspect the actual definition and source.
- A local OR that duplicates a global OR name is a compilation error.
- Some OR names literally include an `OR:` prefix and some do not. Use the name exactly as stored; do not add/remove the prefix.
- A negated OR cell means “not any value in this OR.”

When troubleshooting OR matching, expand the exact OR definition from the correct scope and compare the actual input against its members. Do not assume similarly named local and global ORs are the same list.

---

## 7. Table chaining (`ss_chain`)

A matched rule may return an `ss_chain` output naming a downstream table.

1. The current table matches a row.
2. The engine evaluates the table named by that row’s `ss_chain` value using the same input attributes.
3. Outputs merge into the result. A downstream table overrides an upstream output with the same column name; outputs that exist only downstream are added.
4. A downstream table may chain onward, creating a recursive path. Self-reference is blocked to avoid infinite recursion.

### Reading chain direction correctly

- **Outbound `ChainsTo` / `ss_chain`** identifies where the current table sends evaluation.
- **Inbound `ChainsFrom`** only means another table can reach this table. It does not imply a reverse chain.
- Do not infer an edge from names, matching folder structure, or apparent symmetry.

When testing a parent table, chain-table inputs that share names with parent inputs receive the same values. Only genuinely additional input attributes need separate values.

---

## 8. OF3 queries — advanced object lookup

An OF3 query is used to find an object in an OF3 object tree and/or retrieve an attribute from that object. This is **not** the same as a normal Pick rule-cell condition.

The documented general shape is:

```text
<optional prefix> <query clauses>:<attribute name>
```

- **Prefix:** optional object relation or function/search indicator; some query consumers allow more than one prefix.
- **Query clauses:** conditions on attributes of candidate OF3 objects.
- **Attribute name after the colon:** the attribute whose value is requested from the found object(s).

A simple condition has this shape:

```text
attribute operator value
```

Common query operators:

| Operator | Meaning |
|---|---|
| `=` | Equal |
| `<>` or `!=` | Not equal |
| `<`, `<=` | Less than, less than or equal |
| `>`, `>=` | Greater than, greater than or equal |

In query clauses, the documentation requires a blank on both sides of comparison operators. Values that contain spaces must be surrounded by the documented left-single-quote/backtick character. Follow the consuming feature’s syntax exactly.

### Spaces and caret encoding

In a query used in an INPUT column’s header/line-type definition, embedded spaces are represented by `^` (caret, Shift+6). This is an encoding convention for query/header text—not a Boolean operator by itself.

Conceptually, a readable clause:

```text
CLASS = LVA2_Incoming AND (in_BusCTtype1 <> None OR in_ComptCTtype <> None)
```

is represented in the encoded query form with carets in place of spaces, for example:

```text
CLASS^=^LVA2_Incoming^AND^(^in_BusCTtype1^<>^None^OR^in_ComptCTtype^<>^None^)
```

Do not replace punctuation or invent additional escaping. Confirm the exact location (column header, output cell, callback parameter, or another feature-specific field) before applying caret encoding.

### Query example and parse

A documented aggregation example is:

```text
SUM:CLASS^=^LVA2_Incoming^AND^(^in_BusCTtype1^<>^None^OR^in_ComptCTtype^<>^None^):II_QUANTITY
```

Interpretation:

- `SUM:` selects an aggregation over matching objects.
- `CLASS = LVA2_Incoming` filters candidate objects.
- `AND (...)` requires at least one of the two parenthesized conditions to be true.
- `in_BusCTtype1 <> None OR in_ComptCTtype <> None` is a grouped OR expression.
- `:II_QUANTITY` names the attribute to aggregate.

The grouping is significant. Without parentheses, the Boolean expression may group differently and select a different set of objects.

Another documented nested query example is:

```text
gv(VALUEPOS:7~CHILD:CLASS^=^LVA2_GlInvItem^AND^attr^=^Voltage:myAttr)
```

This uses `VALUEPOS` to retrieve a character from `myAttr` on an object found by a `CHILD` query. It illustrates nested query composition; do not reuse the exact object class/attribute names outside the matching application context.

---

## 9. Query prefixes, filters, grouping, and aggregation

### Relation prefixes

The documented relation/query prefixes include:

| Prefix | Documented purpose |
|---|---|
| `PARENT:` | Begin from the current object’s parent. |
| `ANCESTOR:` | Search up toward the takeoff’s main object; in child-takeoff contexts this can be the child takeoff’s main object. |
| `ROOT:` | Search upward to the highest-level object. |
| `CHILD:` | Search child objects and find a matching object. |
| `SIBLING:` | Search sibling objects; in some forms, descendants of siblings are included. |
| `FRIEND:` | Search related “friend” objects for a match. |
| `SUM:` | Aggregate the selected attribute across matching objects. |
| `MAX:` / `MIN:` | Return the maximum/minimum selected attribute across matching objects. |

The `[I]` (immediate) qualifier is documented for restricting searches to direct relationships. Without that qualifier, some relations—such as sibling search—can include descendants. Exact qualifier placement and supported forms depend on the query consumer; check its documentation before generating a query.

The query documentation specifically warns not to combine `CHILD:` with `MAX:` or `MIN:` because that prevents the query from working properly.

### Boolean logic

Query clauses can combine conditions with `AND` and `OR`, and use parentheses for grouping. Use parentheses to state intent explicitly, especially when mixing operators.

Example logic:

```text
CLASS = LVA2_Incoming AND (BusCT <> None OR ComptCT <> None)
```

means the object must be of class `LVA2_Incoming` and at least one of the two CT-type conditions must be non-`None`.

Do not confuse query Boolean logic with Pick row matching: Pick input columns on a rule row are ANDed together; query clauses can express AND/OR logic over attributes of candidate objects.

### Recursive searches and feature-specific prefixes

Some consumers support a leading `R:` to request recursive object search; for example, a documented query is `R:CLASS^=^GTOAdder`. However, recursion/sort prefixes are **consumer-specific**. A price-sheet feature documents additional forms such as `RS:`, `RL:`, `S:`, and `N:` with particular traversal/sorting behavior. Do not apply a prefix documented for one feature to another feature without checking.

### Query validation checklist

Before emitting or editing a query:

1. Identify the field/table feature that consumes it.
2. Confirm whether it expects a query, callback, or plain value.
3. Confirm the traversal origin and relation prefix.
4. Confirm recursive vs direct search requirements.
5. Verify candidate attribute names and values in the relevant domain.
6. Put spaces around comparison operators in readable query syntax; apply caret encoding only in the documented encoded context.
7. Use parentheses to make mixed AND/OR logic explicit.
8. Confirm the attribute suffix after the colon is the attribute whose value is required.
9. Check whether the consumer returns one object, multiple objects, a sum, or an extrema.
10. Test in the correct runtime context; a Pick Workbench trace may not execute OF3-dependent expressions.

---

## 10. Structure/compartment queries

Some layout queries use a special three-character code inside braces before a relation query:

```text
{<scope><direction><distance>}<relation query>
```

Documented components:

- **Scope:** a non-negative integer denoting recursive container scope; `*` can denote the root layout structure.
- **Direction:** `L` left, `R` right, `T` above, `B` below, `F` front, `A` behind, or `C` container.
- **Distance:** number of compartments to move; `*` can search to the furthest object.
- If direction is `C`, the scope component is ignored.

This syntax is specialized for structure/compartment lookup. Do not treat braces as normal attribute references or use this form in unrelated table fields without confirming the feature supports it.

---

## 11. Output expressions and math functions

An OUTPUT cell can contain a runtime expression when it begins with the output column’s own name, followed by `=`. `gv(...)` retrieves an attribute/query value.

Example:

```text
price = gv(base_price) * 1.05
```

This expression is evaluated after the rule matches. It is not an input-cell condition and not a one-time edit formula.

### Token spacing

For documented Pick output math, separate operators and operands with spaces. Some operators have additional formatting requirements.

### Documented math operators/functions

The Pick table operator documentation lists:

- Arithmetic: `+`, `-`, `*`, `/`, `%`.
- Power: `^` or `pow`; enclose the operation in parentheses and put spaces around it, e.g. `(5 ^ 2)` or `(5 pow 2)`.
- `min` / `max`: compare two operands; enclose the operation in parentheses and use spaces, e.g. `(5 min 2)`.
- Constants: `pi`, `e`.
- Trigonometric: `sin(x)`, `cos(x)`, `tan(x)` / `tg(x)`, `atan(x)` / `atg(x)`, `asin(x)`, `acos(x)`.
- Numeric: `abs(x)`, `sqrt(x)`, `ceil(x)`, `floor(x)`, `round(x)` / `rnd(x)`, `int(x)`, `exp(x)`, `log(x)` / `ln(x)`, `log10(x)`.

Example:

```text
OutCol = int(gv(NumS)) * 6
```

Do not assume every runtime build or every expression location supports every documented function; verify the context and compile/test.

### Keep calculation systems separate

A Workbench “calculate column” formula edits stored numeric cells across rows; it is not the same as a Pick OUTPUT expression evaluated at runtime. Do not write a runtime expression into a numeric literal cell, or use a Workbench calculation formula as if it were a Pick table expression. For bulk numeric updates, use the calculation feature; for a dynamic rule output, use the verified Pick expression syntax.

---

## 12. Callbacks

A callback is a special attribute name implemented by runtime code. It is often used inside `gv(...)` in an OUTPUT cell, or as a specially defined INPUT-column header. Callbacks are **not generic function calls**.

A callback can be:

- A fixed callback name.
- A parameterized callback whose arguments are embedded in its attribute name, often separated by `~`.
- A callback that accepts an OF3 query or another callback as a parameter.

Use only the documented callback name, case rules, parameter order, and allowed table location. The documentation says callbacks, functions, and queries may be used in INPUT column headers or OUTPUT cells; OR names belong in INPUT row cells, not headers.

### Verified examples

#### `CB_Round`

Documented parameterized form:

```text
CB_Round~<FloatAttr>~<DecimalPlaces>
```

`<FloatAttr>` is an attribute/callback/query holding a decimal value. `<DecimalPlaces>` is optional; omitting it means zero decimal places. Example: `CB_Round~gAmperage~1` rounds `gAmperage` to one decimal place. It can be used as a callback attribute, e.g. within `gv(...)` in an output expression. If a parameter contains spaces, the callback documentation specifies caret encoding for those spaces.

#### `CB_AttrExists`

Documented forms include:

```text
CB_AttrExists~<attrname>
CB_AttrExists~<attrname>~<Immediate>
CB_AttrExists~<attrname>~<Immediate>~<query>
CB_AttrExists~<attrname>~~<query>
```

It returns `Y` or `N` for whether an attribute exists in the selected object/search scope. `Immediate=Y` restricts lookup to the found object; other values allow parent searching. Query behavior depends on the form; a query beginning with case-sensitive `R:` is documented as recursive. Example:

```text
gv(CB_AttrExists~myAttr)
```

means check for `myAttr` on the current object or a parent, according to the callback’s documented default behavior.

#### `CB_CountObjs`

Documented parameterized forms include:

```text
CB_CountObjs~<Query>
CB_CountObjs~R:<Query>
```

It counts child objects matching the query; `R:` requests recursive search. Example:

```text
CB_CountObjs~CLASS^=^GTO_Structure
```

Only use callback examples when the target runtime/feature actually supports them. The implemented-callback reference may be incomplete; search it for the exact callback before authoring. If no authoritative documentation is found, say so instead of inventing syntax.

---

## 13. Testing and debugging

### Fresh table test

For an exploratory test, discover the table’s own input columns and relevant downstream chain inputs first. Use real candidate values from the project; expand an OR candidate if necessary. Inputs shared between a parent and downstream table are set once because the same inputs flow through the chain.

### Target a specific row

To test a particular `_rid`:

1. Read that exact row, including line type and all INPUT cells.
2. Build concrete input values from the target row’s conditions. Do not pass raw operators or OR names.
3. For wildcards, choose values that avoid an earlier PICK ONE rule if needed.
4. Run the test and verify the trace’s matched `_rid` is the intended target.
5. If an earlier row wins, add further values from the target row to exclude that earlier row, then rerun.
6. Treat invalid-input/definition-table warnings as a signal to fix the test values, even if another row happened to match.

### Explain a failure precisely

For each failed rule shown in the trace, report:

- Table and `_rid`.
- First failing column, if provided by the trace.
- Rule cell condition versus actual input (or **no input**).
- Whether the problem is a literal mismatch, OR membership, range/operator boundary, missing input, or higher-priority earlier match.

Do not claim to know why a row failed if the trace did not include it. The user’s failed-rule cap may exclude the target; ask them to increase it and rerun.

### Trace/runtime limitations

Some constructs—especially `gv(...)`, callbacks, child/aggregate queries, and other OF3-dependent values—are runtime-only and may not be evaluable in Workbench trace/test mode. Distinguish “trace cannot evaluate this expression” from “the runtime rule is wrong.” Test in the appropriate runtime environment when needed.

---

## 14. Authoring and change-safety workflow

### Before changing a table

1. Inspect the exact table and file.
2. Verify table type, full column names, I/O directions, and types.
3. Read comments and all row types; honor author intent.
4. Read the live unsaved version if the table has pending edits; the saved copy may be stale.
5. Confirm exact `_rid`s before modifying existing rows.
6. Check OR source, duplicate table names, and chain dependencies where relevant.
7. For PICK ONE, decide whether a new rule appends or must be deliberately inserted to take priority.

### Rule editing

- Edit a few known rows surgically using stable `_rid`s.
- When defining a new or empty table’s full body, replace the body with the intended rows rather than leaving blank starter rows. A leading blank enabled rule is dangerous: it can match everything in PICK ONE or emit empty output in PICK ALL.
- Preserve `Comment`, `Disable`, and `Continuation` line types when regenerating a body.
- Append new rules by default. Insert after a particular row only when the user’s priority/order request requires it.
- Do not store spreadsheet formula text like `=115*1.5` in a numeric cell. Numeric cells need values/ranges/operator conditions that the table type accepts. Use a bulk calculation feature for arithmetic over many stored numeric cells.
- Do not edit an OR table as if it were an ordinary rule table if the editing interface/tool does not support OR tables.

### Persistence lifecycle

- Rule and schema edits may remain unsaved in the live grid.
- Save commits the user’s changes to their own branch.
- Compile validates/builds saved content; it does not by itself publish source to shared branches.
- Pushing to a shared branch and deploying for an environment are separate actions with different scopes.
- Never claim an edit is saved, pushed, or deployed unless that exact operation was performed and its result confirms it.

---

## 15. Project structure, identity, and compilation lifecycle

### Project files and OR scope

A Pick project can contain a manifest listing JSON member files, nested folders, tables, and file-local OR tables. `GLOBALS.json` commonly carries global OR definitions. Treat the manifest and file paths as project metadata, not as Pick tables.

A single JSON file can contain multiple tables as well as an OR table. When asked for every table in a file or folder, filter by each table’s **File/path**, not by a table-name search.

### Duplicate table names

The same table name can occur in more than one file. Compiler order determines the effective copy; commonly, the later definition wins and an earlier one is shadowed. Verify which copy is used before describing or editing. Editing a shadowed copy may not change runtime behavior.

### Compilation lifecycle

Conceptually, JSON rule files are compiled into runtime binary/index files. Compilation catches syntax/definition issues that may not be visible from reading rules alone. Typical duplicate-table conditions may warn while allowing a build; conflicts such as a local OR colliding with a global OR can stop compilation. Report the actual compile output rather than predicting success.

---

## 16. Common confusions and failure patterns

| Confusion | Correct interpretation |
|---|---|
| Treating a blank INPUT cell as “input must be blank” | It is a wildcard; it matches any value, including no value. |
| Passing `OR:GroupName` as the test value | Pass a real member value from the OR definition. |
| Passing `>=600` as a test value | That is a rule condition; pass a concrete value such as `600` or `700`. |
| Treating `ChainsFrom` as an outbound chain | It is inbound only. Follow `ss_chain`/`ChainsTo` forward. |
| Treating a comment/disable/continuation as an active rule | Check line type; comments and disables are not active rules, continuations extend prior rows. |
| Assuming a matching row was the intended PICK ONE row | Verify the matched `_rid`; an earlier row can win. |
| Confusing a Pick query with a row condition | OF3 queries search object trees; rule cells match input attributes. |
| Confusing query `AND`/`OR` with rule columns | Separate Pick INPUT columns are ANDed; query clauses can combine Boolean expressions. |
| Treating `gv(...)` or a callback as a plain value | It may be a runtime expression and unavailable in trace mode. |
| Treating callback syntax as `Fn(args)` | Callbacks are special/parameterized attribute names; verify exact documented syntax. |
| Using caret `^` as an ordinary Boolean operator | In encoded query contexts, it represents spaces; power `^` in math is a separate context. |
| Assuming a prefix works in every query-consuming feature | Recursion/sorting prefixes can be feature-specific. Verify the consumer. |
| Writing math into a numeric rule cell | Numeric cells require valid numeric/match syntax; use a supported expression in OUTPUT or a calculation tool for stored data. |
| Claiming no change because Change Log is empty | Change Log may cover shared branches only; inspect the user’s unsaved or feature-branch state separately. |

---

## 17. Explanation templates

### Explain a rule

> **TableName** `_rid 42` is a **PICK ONE** rule. It requires `voltage >= 600` and `frame = F250`; blank INPUT cells are wildcards. It returns `catalog_no = ABC123`. The trace provided `voltage = 480`, so the voltage condition did not match.

Only state values verified from the table and trace.

### Explain an OF3 query

> This is an OF3 object query, not a normal Pick row condition. `CHILD:` selects the child-search scope; `CLASS = GTO_Structure` filters candidate objects; the suffix after the final colon selects the attribute to retrieve. The caret characters encode spaces in this query context. The query is used by **[verified consumer]**.

Only describe scope, recursion, and result cardinality when verified for that consumer.

### Explain a chain

> **TableA** `_rid 8` returns `ss_chain = TableB`, so the forward path is **TableA → TableB**. **TableB** receives the same inputs. Its `price` output overrides TableA’s `price` if both return one. No reverse link is implied by TableB being reached from TableA.

### Explain uncertainty

> I can identify this as a callback/query pattern, but I can’t verify this exact parameter form from the available documentation. I won’t guess at it; we should check the callback reference or an existing working example for this feature.

---

## 18. Verified references

The following technical references informed the advanced syntax sections. They are authoritative starting points; consult the specific section for exact syntax and feature scope.

- [Pick Table Operators, Types, Ranges and Functions — operators, types, ranges, OF3 queries, relation prefixes, structure/compartment queries, and math functions](https://dev.azure.com/etn-BidManager/7b29899a-fe07-44f6-94db-693b3738308a/_wiki/wikis/b6d5373b-e910-458a-8f94-b3961f20d3ba?pagePath=%2FPick%20Developers%20Technical%20Guide%20-%20The%20Encyclopedia%2FPick%20Development%2FPick%20Table%20Operators%2C%20Types%2C%20Ranges%20and%20Functions)
- [Implemented Callbacks — callback names, parameters, and examples](https://dev.azure.com/etn-BidManager/7b29899a-fe07-44f6-94db-693b3738308a/_wiki/wikis/b6d5373b-e910-458a-8f94-b3961f20d3ba?pagePath=%2FPick%20Developers%20Technical%20Guide%20-%20The%20Encyclopedia%2FPick%20Development%2FImplemented%20Callbacks)
- [Price Sheet — feature-specific query prefixes and sorting examples](https://dev.azure.com/etn-BidManager/7b29899a-fe07-44f6-94db-693b3738308a/_wiki/wikis/b6d5373b-e910-458a-8f94-b3961f20d3ba?pagePath=%2FPick%20Developers%20Technical%20Guide%20-%20The%20Encyclopedia%2FPick%20Development%2FPrice%20Sheet)

## Quick mental model

```text
Pick rule row:
  all INPUT cells must match (AND)
  blank INPUT cell = wildcard
  PICK ONE = first matching active row
  PICK ALL = all matching active rows

After a match:
  literal outputs return values
  OUTPUT expressions/callbacks may calculate runtime values
  ss_chain may forward the same inputs to another table

OF3 query:
  optional traversal/aggregation prefix
  + object-attribute filter clauses (AND/OR/parentheses)
  + colon + requested attribute
  + context-specific syntax/encoding
```
