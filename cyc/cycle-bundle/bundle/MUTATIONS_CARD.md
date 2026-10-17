---
license: other
license_name: per-record-upstream-permissive
pretty_name: Marsad verified mutation bug-fix pairs (Python)
---
# Marsad verified mutation pairs

Each record: a function from a real open-source Python project (`fixed_code`), a deterministic AST mutation of it
(`buggy_code`), and the upstream test that **passes before and fails after** the mutation (`failing_test`).
Accepted only if the project's original test suite passed first. No LLM involved.
`origin = procedural`: synthetic AST mutation. `origin = real_commit`: a human bug-fix from the project's git history
(`buggy_code` = parent commit, `fixed_code` = fix commit, `failing_test` fails on the parent with the fix's tests and passes on the fix);
these carry `bug_confidence` (high / medium; low is excluded) and `commit_message`.

- train: 2454 | eval: 0 | projects: 8 | cap per project: 800
- split is by whole project (sha1(project) % 100 < 15 -> eval), so no project appears on both sides.
- mutation types: {"real_fix": 75, "return_none": 526, "cmp": 523, "if_negate": 664, "int_const": 258, "binop": 134, "boolop": 158, "bool_flip": 116}

## Licenses
Code comes from projects under MIT, Apache-2.0 or BSD licenses. Every record carries `license`, `repo_url`,
`commit_sha`. See NOTICE.md for the full attribution list. Full upstream license texts are in `licenses/`. `procedural` records are synthetic edits; `real_commit` records are human fixes.

## Limitations
- `procedural`: synthetic simple bugs (operator swap, off-by-one, negated condition, dropped return). `real_commit`: labels are heuristic (`bug_confidence`); `medium` may include feature-like changes.
- A mutation counts as detected if any upstream test failed; the failing test may not be the most relevant one.
- Function-level snippets (formatting normalized through ast.unparse; comments removed).
