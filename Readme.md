# MetaCall Fuzz Engine

### GSoC 2026 — Pratham Tomar
### Part of [metacall/testing-center](https://github.com/metacall/testing-center)

---

## Overview

This project is part of **Google Summer of Code 2026** under the MetaCall organization.

[MetaCall](https://metacall.io/) is a polyglot runtime that lets Python, JavaScript, Ruby, and other languages call each other seamlessly inside a single process. This project builds a **fuzzing engine** that stress-tests that cross-language communication — automatically generating thousands of inputs, firing them across every language boundary in both directions, and detecting crashes, type corruption, and incorrect outputs.

> *"With fuzzing we can generate thousands of test cases and detect when they fail. It would be great to abuse MetaCall to the maximum through fuzzing to see what can fail."*
> — viferga (MetaCall mentor)

---

## Motivation

When data crosses a language boundary — a Python value passed to a JavaScript function, or a Ruby string returned to Python — MetaCall handles the type translation internally. Even small inconsistencies in that translation can cause:

- Incorrect outputs that are hard to trace
- Type corruption that only shows up under specific inputs
- Crashes that only trigger at boundary values (`INT_MAX`, empty strings, `NaN`)
- Loader-level failures that never surface in normal testing

This engine finds those issues automatically, on every new MetaCall release, without manual test case writing.

---

## N:N Coverage

Most testing approaches are 1:N — one caller, many callees. This engine achieves **N:N**:

```
py → js    py → rb
js → py    js → rb
rb → py    rb → js
```

Every language is both a caller and a callee. Every boundary is exercised in both directions.

---

## How It Works

### Step 1 — Generate files (`makers.py` + `generateFiles.py`)

A builder API automatically generates three categories of files:

| Category | Files generated |
|----------|----------------|
| Deployable functions (SUT) | `py_functions.py`, `js_functions.js`, `rb_functions.rb` |
| Cross-language test runners | `test_py_to_js.py`, `test_py_to_rb.py`, `test_js_to_py.js`, ... (6 files) |
| MetaCall config | `metacall-py.json`, `metacall-js.json`, `metacall-rb.json` |

Adding a new language requires **one new class** in `makers.py` and **one line** in `generateFiles.py`. Nothing else changes.

### Step 2 — Deploy (`main.py`)

`main.py` deploys the generated function files onto MetaCall, checks the proxy is running, confirms deployed functions are reachable, and sequences the test runs.

### Step 3 — Fuzz and verify (`test_lang_to_lang.lang`)

Each test file:
- Owns the fuzz loop — iterates across type-aware input ranges
- Knows exactly what it sent
- Calls the deployed function via MetaCall
- Asks the proxy what the function actually received and returned
- Compares: **sent == received** and **output == expected**
- Writes a structured verdict to `universalLog.txt`

### Step 4 — Proxy (`proxy.py`)

The proxy reads MetaCall's terminal or core output, parses structured JSON lines emitted by deployed functions, and serves that data to test files on request. This is how the test file sees what happened inside the function at the language boundary.

---

## What Gets Verified Per Call

1. **Arguments sent == Arguments received** — did MetaCall deliver the value correctly across the boundary?
2. **Output == Expected output** — did the function compute the right result after receiving the args?

---

## Structured Output

Every `print` in the system emits exactly one JSON line. Terminal output is fully parseable.

Per fuzz iteration you see exactly these lines, in order:

```
{"type":"FUZZ_CALL",    "func":"js_add", "sent":{"a":3,"b":4},       "iter":1}
{"type":"FUNC_ENTER",   "func":"js_add", "received":{"a":3,"b":4}             }
{"type":"FUNC_RESULT",  "func":"js_add", "result":7                           }
{"type":"FUZZ_RESULT",  "func":"js_add", "verdict":"PASS", "iter":1           }
{"type":"LOG_WRITE",    "func":"js_add", "verdict":"PASS", "iter":1           }
```

A missing `FUNC_ENTER` means MetaCall crashed before reaching the function.
An `ASSERT_FAIL` instead of `FUNC_RESULT` means the type was corrupted at the boundary.

### `universalLog.txt`

One JSON object per line — every boundary crossing attempted, verdict, inputs, outputs.

```json
{"verdict":"PASS",  "caller":"py","callee":"js","func":"js_add","sent":{"a":3,"b":4},"received":{"a":3,"b":4},"result":7,"expected":7,"iter":1}
{"verdict":"FAIL",  "caller":"py","callee":"js","func":"js_add","sent":{"a":3,"b":4},"received":{"a":"3","b":4},"result":"34","expected":7,"iter":2}
{"verdict":"CRASH", "caller":"js","callee":"rb","func":"rb_add","sent":{"a":9223372036854775807,"b":1},"exception":"SegFault","iter":3}
```

| Verdict | Meaning |
|---------|---------|
| `PASS` | sent == received AND result == expected |
| `FAIL` | value corrupted crossing the language boundary |
| `WARN` | args ok but result unexpected or null |
| `CRASH` | MetaCall threw or died on this input |

---

## Fuzz Strategy

| Type | Strategy |
|------|----------|
| `int` | Boundary values + overflow values + full range with step |
| `float` | Precision traps (`0.1+0.2`), special values (`inf`, `-inf`, `nan`), boundary values |
| `str` | Empty, long, unicode, null bytes, injection strings, length boundaries |
| `bool` | `True`/`False` + coercion traps (`0`, `1`, `"true"`, `"false"`) |

---

## Project Structure

```
project/
├── makers.py              ← classes that emit code per language (SOLID)
├── generateFiles.py       ← drives file generation, owns fuzz values
├── main.py                ← deploys files, health checks, sequences tests
├── proxy.py               ← reads MetaCall output, serves data to test files
│
└── output/
    ├── py_functions.py    ← SUT: type assert + compute + print JSON + return
    ├── js_functions.js
    ├── rb_functions.rb
    ├── test_py_to_js.py   ← fuzz loop + proxy check + validate + log
    ├── test_py_to_rb.py
    ├── test_js_to_py.js
    ├── test_js_to_rb.js
    ├── test_rb_to_py.rb
    ├── test_rb_to_js.rb
    ├── metacall-py.json
    ├── metacall-js.json
    ├── metacall-rb.json
    └── testing-center.yaml
```

---

## Verbose Modes

| Mode | Behaviour |
|------|-----------|
| `DEBUG` | Prints every iteration — PASS, FAIL, WARN, CRASH |
| `VERBOSE` | Prints failures only — FAIL, WARN, CRASH |

Controlled via flag in `main.py`. Deployed functions always print — the mode controls what test files surface.

---

## Development Phases

| Phase | Scope | Status |
|-------|-------|--------|
| I | `makers.py` + `generateFiles.py` + `main.py` — file generation + deployment | ⏳ In progress |
| II | `proxy.py` — MetaCall core output reader | 🔜 Next |
| III | End-to-end testing + CI integration | 🔜 After Phase II |

---

## Current Status

| Item | Status |
|------|--------|
| N:N PoC — 6 cross-language files working | ✅ Done |
| Architecture + SOLID design finalised | ✅ Done |
| `makers.py` + `generateFiles.py` | ⏳ In progress |
| `main.py` | 🔜 |
| `proxy.py` | 🔜 Phase II |
| CI integration | 🔜 Phase III |

---

## Adding a New Language

| File | Change |
|------|--------|
| `makers.py` | Add `GoDeployMaker` + `GoTestMaker`, register in both dicts |
| `generateFiles.py` | Add `"go"` to `LANGUAGES` list |
| Everything else | No changes |

---

## Links

- N:N Demo: [Examples/](https://github.com/prathamtomar99/metacall-fuzz-engine/tree/main/Examples)
- GSoC Issue: [metacall/testing-center#24](https://github.com/metacall/testing-center/issues/24)
- MetaCall Core: [metacall/core](https://github.com/metacall/core)
- Testing Center: [metacall/testing-center](https://github.com/metacall/testing-center)

---

## Contributing

This project is under active GSoC development. Feedback, ideas, and discussions are welcome via the GSoC issue linked above.
