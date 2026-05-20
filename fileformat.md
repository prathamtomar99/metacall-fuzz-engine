# File Format & Architecture

## Project Structure

```
project/
│
├── makers.py                        ← classes that know HOW to emit code per language
├── generateFiles.py                 ← uses makers to generate all files
├── main.py                          ← deploys files, health checks, sequences test runs
├── proxy.py                         ← reads MetaCall terminal/core, serves parsed data
│
├── output/
│   │
│   ├── — Deployable files (SUT) —
│   ├── py_functions.py              ← prints received args + result to terminal, returns
│   ├── js_functions.js
│   ├── rb_functions.rb
│   │
│   ├── — Cross-language test files —
│   ├── test_py_to_js.py             ← py fuzz loop calling js functions
│   ├── test_py_to_rb.py
│   ├── test_js_to_py.js
│   ├── test_js_to_rb.js
│   ├── test_rb_to_py.rb
│   ├── test_rb_to_js.rb
│   │
│   ├── — Standalone test files (alternative to cross-language) —
│   ├── test.py                      ← discovers + calls all non-py deployed functions
│   ├── test.js
│   ├── test.rb
│   │
│   ├── — MetaCall config —
│   ├── metacall-py.json
│   ├── metacall-js.json
│   ├── metacall-rb.json
│   ├── testing-center.yaml
│   │
│   └── — Deployment packages —
│       ├── py_deploy.zip            ← py_functions.py + metacall-py.json
│       ├── js_deploy.zip
│       └── rb_deploy.zip
│
└── universalLog.txt                 ← written only by test files
```

> **Note on test files:** `test_lang_to_lang.lang` and `test.lang` are equivalent.
> Both do the same thing — fuzz loop + proxy check + validate + log.
> Only one set is needed. `main.py` controls which set runs and in what sequence.

---

## JSON Stdout Contract

**Every print in the entire system emits exactly one JSON line.**
Deployed functions print what they received and what they computed.
Test files print what they are doing at each step.
Terminal output is fully parseable. Line count per iteration is predictable.

### Line types

| `type` | Who prints | When |
|--------|-----------|------|
| `FUNC_ENTER` | `lang_functions.lang` | Received a call — prints args as received |
| `FUNC_RESULT` | `lang_functions.lang` | Computed result — prints before return |
| `ASSERT_FAIL` | `lang_functions.lang` | Type assertion fired — prints instead of FUNC_RESULT |
| `FUZZ_CALL` | `test.lang` | About to call a function — prints what is being sent |
| `FUZZ_RESULT` | `test.lang` | Got result — prints comparison verdict |
| `FUZZ_EXCEPTION` | `test.lang` | Caught exception — prints exception detail |
| `LOG_WRITE` | `test.lang` | Writing to universalLog.txt — prints the entry |

### Expected lines per fuzz iteration

```
FUZZ_CALL        ← test file: sending these args now
FUNC_ENTER       ← deploy file: received these args         ← missing = MetaCall crashed before function
FUNC_RESULT      ← deploy file: computed this result        ← missing = ASSERT_FAIL fired instead
FUZZ_RESULT      ← test file: got result, verdict is X
LOG_WRITE        ← test file: writing to universalLog.txt
────────────────────────────────────────────────────────
4–5 lines per iteration
```

### Verbose modes (controlled by test files / main.py)

| Mode | What gets printed |
|------|------------------|
| `DEBUG` | All 4–5 lines every iteration — PASS, FAIL, WARN, CRASH |
| `VERBOSE` | Only FAIL, WARN, CRASH iterations — skips PASS |

### JSON schemas

**`FUNC_ENTER`** — printed at start of every deployed function call:
```json
{
  "type": "FUNC_ENTER",
  "lang": "py",
  "func": "py_add",
  "received": { "a": 3, "b": 4 },
  "received_types": { "a": "int", "b": "int" }
}
```

**`FUNC_RESULT`** — printed just before return:
```json
{
  "type": "FUNC_RESULT",
  "lang": "py",
  "func": "py_add",
  "result": 7,
  "result_type": "int"
}
```

**`ASSERT_FAIL`** — printed when type assertion fires (replaces FUNC_RESULT):
```json
{
  "type": "ASSERT_FAIL",
  "lang": "py",
  "func": "py_add",
  "arg": "a",
  "expected_type": "int",
  "got_type": "str",
  "got_value": "hello"
}
```

**`FUZZ_CALL`** — printed by test file before every metacall:
```json
{
  "type": "FUZZ_CALL",
  "caller": "py",
  "callee": "js",
  "func": "js_add",
  "sent": { "a": 3, "b": 4 },
  "iter": 142
}
```

**`FUZZ_RESULT`** — printed by test file after receiving result:
```json
{
  "type": "FUZZ_RESULT",
  "caller": "py",
  "callee": "js",
  "func": "js_add",
  "sent": { "a": 3, "b": 4 },
  "received": { "a": 3, "b": 4 },
  "result": 7,
  "expected": 7,
  "verdict": "PASS",
  "iter": 142
}
```

**`FUZZ_EXCEPTION`** — printed by test file on exception:
```json
{
  "type": "FUZZ_EXCEPTION",
  "caller": "py",
  "callee": "js",
  "func": "js_add",
  "sent": { "a": 3, "b": 4 },
  "exception": "AssertionError: type error: a expected number, got string",
  "verdict": "FAIL",
  "iter": 142
}
```

**`LOG_WRITE`** — printed just before writing to universalLog.txt:
```json
{
  "type": "LOG_WRITE",
  "verdict": "PASS",
  "caller": "py",
  "callee": "js",
  "func": "js_add",
  "sent": { "a": 3, "b": 4 },
  "received": { "a": 3, "b": 4 },
  "result": 7,
  "expected": 7,
  "iter": 142
}
```

---

## Core Files

---

### `makers.py`
**Single responsibility:** knows HOW to emit code for each language. No I/O. No orchestration. No fuzz values.

**Data layer (pure value objects):**
- `ArgSpec` — `name: str`, `type_: str`
- `ReturnOp` — `expr: str` (e.g. `"a + b"`), `type_: str`
- `FuncSpec` — `name`, `lang`, `args: list[ArgSpec]`, `return_op`, `log_spec`
- `LogSpec` — `file: str` (absolute path to universalLog.txt)
- `FuncBuilder` — fluent API:
  ```python
  FuncBuilder()
    .func("py_add", "py")
    .arg("a", "int")
    .arg("b", "int")
    .returns("a + b", "int")
    .log(LogSpec(file="/abs/universalLog.txt"))
    .build()  # → FuncSpec
  ```

**Interfaces (ABCs):**
- `BaseDeployMaker` — `emit_function(spec) → str`, `emit_file(specs) → str`
- `BaseTestMaker` — `emit_file(specs, callee_lang, callee_file, proxy_url, log_path, verbose_mode) → str`

**Deploy makers** (emit `lang_functions.lang`):
- `PyDeployMaker` — `isinstance` type asserts + `FUNC_ENTER` + `FUNC_RESULT` JSON prints
- `JsDeployMaker` — `typeof` type asserts + JSON prints + `module.exports`
- `RbDeployMaker` — `.is_a?` type asserts + JSON prints

Each deploy maker rule:
- Print `FUNC_ENTER` at top (what was received)
- Type assert (structural only — no value checks)
- Compute result
- Print `FUNC_RESULT` before return
- Return result
- **Never** write to log file
- **Never** import fuzz values

**Test makers** (emit `test.lang` / `test_lang_to_lang.lang`):
- `PyTestMaker`
- `JsTestMaker`
- `RbTestMaker`

Each test maker generates:
- Load deployed file via MetaCall
- Fuzz loop (from `FUZZ_PLAN` inlined as literals)
- Print `FUZZ_CALL` before each metacall
- Call function via metacall
- Ask proxy for `received_args` + `output`
- Compare `sent == received` and `result == expected`
- Print `FUZZ_RESULT` or `FUZZ_EXCEPTION`
- Print `LOG_WRITE` and write to `universalLog.txt`
- Respect `verbose_mode` — skip printing PASS if `VERBOSE`

**Registries:**
```python
DEPLOY_MAKERS: dict[str, BaseDeployMaker] = {
    "py": PyDeployMaker(),
    "js": JsDeployMaker(),
    "rb": RbDeployMaker(),
    # add new language here only
}
TEST_MAKERS: dict[str, BaseTestMaker] = {
    "py": PyTestMaker(),
    "js": JsTestMaker(),
    "rb": RbTestMaker(),
    # add new language here only
}
```

---

### `generateFiles.py`
**Single responsibility:** defines WHAT to generate and WHERE to write. Calls makers. Does not emit code.

**Contains:**
- `OUT_DIR` — absolute path to `output/`
- `LOG_PATH` — absolute path to `universalLog.txt`
- `PROXY_URL` — `http://localhost:5001`
- `LANGUAGES` — `["py", "js", "rb"]`
- `TEST_PAIRS` — `[("py","js"), ("py","rb"), ("js","py"), ("js","rb"), ("rb","py"), ("rb","js")]`
- `FUZZ_PLAN` — single source of truth for all fuzz values:
  ```python
  FUZZ_PLAN = {
      "int": {
          "boundaries": [0, -1, 1, 2**31-1, -(2**31)],
          "overflow":   [2**31, -(2**31)-1, 2**63],
          "range":      range(-(2**31), 2**31, 500_000),
      },
      "float": {
          "pool": [0.0, -0.0, 3.14, 0.1+0.2, 1e308, -1e308,
                   float('inf'), float('-inf'), float('nan')],
      },
      "str": {
          "pool":    ["", " ", "hello", "unicode_é", "中文"],
          "lengths": ["a"*n for n in [0, 1, 255, 256, 1000, 10_000]],
          "edge":    ["\x00", "\n", "'; DROP TABLE--"],
      },
      "bool": {
          "pool":   [True, False],
          "coerce": [0, 1, "true", "false"],
      },
  }
  ```
- `make_specs(lang)` — builds `FuncSpec` list per language
- `make_metacall_json(lang, filename)` — `{"language_id": "py", "path": ".", "scripts": [...]}`
- `make_testing_center_yaml(languages)` — N:N call graph YAML
- `make_zip(lang, deploy_path, json_path)` — packages deploy file + JSON
- `generate_all()` — full pipeline
- `verify(generated)` — confirms all expected files were produced

---

### `main.py`
**Single responsibility:** deploy files, health checks, sequence test runs.

**Does NOT validate. Does NOT write to universalLog.txt (test files do that).**

**Contains:**
- `check_proxy_running()` — GET proxy health endpoint, fail fast if not up
- `check_test_files_exist()` — confirm all test files are present in `output/`
- `deploy(lang)` — deploy `lang_deploy.zip` onto MetaCall, confirm success
- `check_deployed(lang)` — verify deployed function is reachable
- `run_tests(mode)` — call test files in sequence, pass `verbose_mode`
- `main()` — orchestration:
  ```
  1. check_proxy_running()
  2. check_test_files_exist()
  3. for each lang: deploy(lang)
  4. for each lang: check_deployed(lang)
  5. run_tests(mode=DEBUG|VERBOSE)
  ```

---

### `proxy.py`
**Single responsibility:** read MetaCall terminal/core output, parse JSON lines, serve to test files.

**Priority: FaaS core** (exposes internal loader errors) over plain terminal stdout.

**Contains:**
- `StdoutReader` — background thread reading MetaCall process stdout
- Parses `FUNC_ENTER`, `FUNC_RESULT`, `ASSERT_FAIL` JSON lines
- Stores last event per function name in memory
- HTTP server:
  ```
  GET /last?func=py_add
  → {
      "received":     {"a": 3, "b": 4},
      "result":       7,
      "assert_fail":  null  or  {"arg": "a", "expected": "int", "got": "str"}
    }

  GET /health
  → {"status": "ok"}
  ```

**Does NOT validate. Does NOT write to log. Does NOT know about fuzz values.**

---

## Generated Files

---

### `output/py_functions.py` — deployed SUT

```python
import json, sys

def py_add(a, b):
    print(json.dumps({
        "type": "FUNC_ENTER", "lang": "py", "func": "py_add",
        "received": {"a": a, "b": b},
        "received_types": {"a": type(a).__name__, "b": type(b).__name__}
    }), flush=True)

    assert isinstance(a, int),  f"type error: a expected int, got {type(a).__name__}"
    assert isinstance(b, int),  f"type error: b expected int, got {type(b).__name__}"

    _result = a + b

    print(json.dumps({
        "type": "FUNC_RESULT", "lang": "py", "func": "py_add",
        "result": _result, "result_type": type(_result).__name__
    }), flush=True)

    return _result
```

**Rules:**
- No imports except `json`, `sys`
- No file I/O
- No logger
- No fuzz values
- Only prints + type asserts + compute + return

---

### `output/test_py_to_js.py` — cross-language test file

```python
import json, metacall, requests

LOG_PATH   = "/abs/path/universalLog.txt"
PROXY_URL  = "http://localhost:5001"
VERBOSE    = False   # True = only log failures

def write_log(entry: dict) -> None:
    if VERBOSE and entry["verdict"] == "PASS":
        return
    print(json.dumps({**entry, "type": "LOG_WRITE"}), flush=True)
    with open(LOG_PATH, "a") as f:
        f.write(json.dumps(entry) + "\n")

def proxy_last(func: str) -> dict:
    return requests.get(f"{PROXY_URL}/last", params={"func": func}).json()

metacall.metacall_load_from_file("node", ["js_functions.js"])

_iter = 0
for a in [0, -1, 1, 2147483647, -2147483648, 2147483648, ...]:
    for b in [0, -1, 1, 2147483647, -2147483648, 2147483648, ...]:
        _iter += 1
        expected = a + b

        print(json.dumps({
            "type": "FUZZ_CALL", "caller": "py", "callee": "js",
            "func": "js_add", "sent": {"a": a, "b": b}, "iter": _iter
        }), flush=True)

        result, received, verdict = None, {}, "CRASH"
        try:
            result   = metacall.metacall("js_add", a, b)
            proxy    = proxy_last("js_add")
            received = proxy.get("received", {})

            args_ok = received == {"a": a, "b": b}
            out_ok  = result == expected
            verdict = "PASS" if args_ok and out_ok else \
                      "FAIL" if not args_ok else "WARN"

            print(json.dumps({
                "type": "FUZZ_RESULT", "caller": "py", "callee": "js",
                "func": "js_add", "sent": {"a": a, "b": b},
                "received": received, "result": result,
                "expected": expected, "verdict": verdict, "iter": _iter
            }), flush=True)

        except Exception as e:
            verdict = "CRASH"
            print(json.dumps({
                "type": "FUZZ_EXCEPTION", "caller": "py", "callee": "js",
                "func": "js_add", "sent": {"a": a, "b": b},
                "exception": str(e), "verdict": verdict, "iter": _iter
            }), flush=True)

        write_log({
            "verdict": verdict, "caller": "py", "callee": "js",
            "func": "js_add", "sent": {"a": a, "b": b},
            "received": received, "result": result,
            "expected": expected, "iter": _iter
        })
```

---

### `output/testing-center.yaml`

```yaml
functions:
  py_functions:
    language: py
    path: output/
    scripts: [py_functions.py]
    calls: [js_functions, rb_functions]

  js_functions:
    language: node
    path: output/
    scripts: [js_functions.js]
    calls: [py_functions, rb_functions]

  rb_functions:
    language: rb
    path: output/
    scripts: [rb_functions.rb]
    calls: [py_functions, js_functions]
```

---

### `universalLog.txt`

One JSON object per line. Written only by test files.

```json
{"verdict":"PASS",  "caller":"py","callee":"js","func":"js_add","sent":{"a":3,"b":4},"received":{"a":3,"b":4},"result":7,"expected":7,"iter":1}
{"verdict":"FAIL",  "caller":"py","callee":"js","func":"js_add","sent":{"a":3,"b":4},"received":{"a":"3","b":4},"result":"34","expected":7,"iter":2}
{"verdict":"WARN",  "caller":"py","callee":"js","func":"js_add","sent":{"a":3,"b":4},"received":{"a":3,"b":4},"result":null,"expected":7,"iter":3}
{"verdict":"CRASH", "caller":"js","callee":"rb","func":"rb_add","sent":{"a":9223372036854775807,"b":1},"exception":"SegFault","iter":4}
```

| Verdict | Meaning |
|---------|---------|
| `PASS` | `sent == received` AND `result == expected` |
| `FAIL` | `sent != received` — boundary corrupted the value |
| `WARN` | args ok but `result != expected` or result is null |
| `CRASH` | MetaCall threw or died on this input |

---

## Copilot Dos and Don'ts

*(Pass with every Copilot session)*

**DO:**
- One class = one responsibility, always
- Every print = one JSON line with `json.dumps()` + `flush=True`
- Add languages only via registries — never modify existing classes
- Keep deployed functions pure: print + assert type + compute + return
- All validation in test files only
- All deployment logic in `main.py` only
- Respect `verbose_mode` in test files

**DON'T:**
- No logger in `lang_functions.lang`
- No file I/O in `lang_functions.lang`
- No fuzz values in `makers.py`
- No code emission in `generateFiles.py`
- No validation in `main.py`
- No writing to `universalLog.txt` in deployed functions or proxy
- No hardcoded language names in logic — use registries

---

## Adding a New Language

| File | Change |
|------|--------|
| `makers.py` | Add `GoDeployMaker` + `GoTestMaker`, register in both dicts |
| `generateFiles.py` | Add `"go"` to `LANGUAGES` |
| Everything else | **No changes** |
