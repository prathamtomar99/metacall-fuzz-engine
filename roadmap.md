# MetaCall Cross-Language Fuzzing Engine
### GSoC 2026 — Pratham Tomar
### Sub-project of: https://github.com/metacall/testing-center

---

## Goal

Generate a **testing engine for N:N function calls** — each language (py, js, rb) is both a caller and a callee.

Stress-test the MetaCall core runtime by automatically running type-aware fuzz inputs across every language boundary in both directions — detecting crashes, type corruption, and incorrect outputs.

> **Mentor (viferga):** *"With fuzzing we can generate thousands of test cases and detect when they fail. It would be great to abuse MetaCall to the maximum through fuzzing to see what can fail."*

---

## N:N Coverage

```
py → js    py → rb
js → py    js → rb
rb → py    rb → js
```

Every language is both caller and callee simultaneously.

---

## What We Verify Per Call

1. **Arguments sent == Arguments received** — did MetaCall deliver values correctly across the boundary?
2. **Output == Expected output** — did the function compute correctly after receiving args?

Both verified inside `test.lang` — never inside deployed files.

---

## Old Flow (Already Implemented — PoC)

**What was built:**
- `makers.py` + `generateFiles.py` — API for generating caller/callee files
- Generated deployable files: `js_functions.js`, `py_functions.py`, `rb_functions.rb`
- Generated test files: `test_js_to_py.js`, `test_js_to_rb.js`, `test_py_to_js.py`, `test_py_to_rb.py`, `test_rb_to_js.rb`, `test_rb_to_py.rb`

**Issues identified:**
- No print statements in deployed functions — terminal shows nothing on call
- No verification: args sent vs args received not checked
- No verification: output vs expected output not checked

---

## New Flow (Updated)

### File generation (`makers.py` + `generateFiles.py`)

Generates three categories of files:

| Category | Files |
|----------|-------|
| Deployable (SUT) | `py_functions.py`, `js_functions.js`, `rb_functions.rb` |
| Cross-language tests | `test_py_to_js.py`, `test_py_to_rb.py`, `test_js_to_py.js`, `test_js_to_rb.js`, `test_rb_to_py.rb`, `test_rb_to_js.rb` |
| Standalone tests | `test.py`, `test.js`, `test.rb` |

> **Note:** `test_lang_to_lang.lang` and `test.lang` serve the same purpose.
> Only one set is needed. `main.py` controls which files are called and in what sequence.
> The difference is only what `main.py` runs first — same validation logic either way.

### What `test.lang` does (the new fuzz loop)

```
test.py / test.js / test.rb
    ├── discovers deployed files in its domain (py discovers js + rb functions)
    ├── owns the fuzz loop
    ├── KNOWS what it sent (generated the values itself)
    ├── calls deployed function via MetaCall
    ├── asks proxy: "what did you see on terminal?"
    ├── gets back: received_args + output from function stdout
    ├── compares: sent == received AND output == expected
    └── writes PASS/WARN/FAIL/CRASH to universalLog.txt
```

### What `lang_functions.lang` does (deployed SUT)

```
py_functions.py / js_functions.js / rb_functions.rb
    ├── receives call from MetaCall
    ├── prints what it received to terminal (JSON)
    ├── type assertion: assert isinstance(a, int) — structural only
    ├── computes result
    ├── prints result to terminal (JSON)
    └── returns result

    NO logger functionality
    NO access to universalLog.txt
    NO knowledge of fuzzing
    ONLY prints + returns
```

### Verbose modes

| Mode | Behaviour |
|------|-----------|
| `DEBUG` | logs everything — every call, every result, every PASS |
| `VERBOSE` | logs only incorrect output — FAIL, WARN, CRASH only |

Controlled by a flag in `main.py` / test files — not in deployed functions.

---

## Phases

---

### Phase I — File Generation + Deployment

**Files:** `makers.py`, `generateFiles.py`, `main.py`

**`makers.py`**
- Classes that know HOW to emit code per language
- SOLID: one class per language, registries for extension
- Never does file I/O, never orchestrates

**`generateFiles.py`**
- Uses objects from `makers.py`
- Decides WHAT to generate and WHERE to write
- Never knows HOW to emit code

**`main.py`**
- Deploys `lang_functions.lang` files onto MetaCall
- Checks proxy is running
- Checks test files exist
- Checks deployed files are active
- Calls test files in sequence (controls test order)
- Does NOT validate — test files validate

**Phase I verification checklist:**
- [ ] `generateFiles.py` produces correctly formatted files
- [ ] Manually deploy generated files on MetaCall server and confirm they run
- [ ] `main.py` correctly deploys files
- [ ] `main.py` correctly checks proxy is running
- [ ] `main.py` correctly sequences test file execution
- [ ] Validation logic in test files works correctly

---

### Phase II — Proxy

**File:** `proxy.py`

- Reads MetaCall terminal stdout (or FaaS core — priority)
- Parses JSON lines emitted by deployed functions
- Returns structured data to test files on request:
  - `received_args` — what the function actually got
  - `output` — what the function returned
- Test files use this to verify `sent == received` and `output == expected`

> FaaS core is priority over terminal — core exposes internal loader errors, type transformations, and calls that never reach the function body.

---

### Phase III — Testing & Integration

- End-to-end fuzz run across all 6 language pairs
- Validate `universalLog.txt` output
- Integrate into `testing-center` CI pipeline (YAML test suite format)
- Document how to add a new language

---

## SOLID Mapping

| Principle | How it applies |
|-----------|---------------|
| **S** | `makers.py` emits only. `generateFiles.py` orchestrates generation only. `main.py` deploys + sequences only. `proxy.py` reads terminal only. Test files validate + log only. |
| **O** | Add a language: one new class in `makers.py` + one registry entry. Nothing else changes. |
| **L** | All `BaseDeployMaker` / `BaseTestMaker` subclasses are substitutable. |
| **I** | `BaseDeployMaker`, `BaseTestMaker` are separate interfaces. |
| **D** | `generateFiles.py` depends on `BaseDeployMaker` abstraction, never `PyDeployMaker` directly. |

---

## Copilot Dos and Don'ts

*(Pass this with every Copilot session)*

**DO:**
- Follow SOLID principles — one class, one responsibility
- Emit exactly one JSON line per print — always use `json.dumps()`
- Use `flush=True` on every print in deployed files
- Add new languages only by extending registries — never by modifying existing classes
- Keep `lang_functions.lang` files pure — no file I/O, no log access, no fuzz logic
- Put all validation logic in test files only
- Put all deployment logic in `main.py` only

**DON'T:**
- Never add logger functionality to `lang_functions.lang` files
- Never write to `universalLog.txt` from deployed functions
- Never hardcode language names in logic — always use registries
- Never put oracle/expected-value logic inside deployed functions
- Never mix code emission (makers) with file writing (generateFiles)
- Never put fuzz loop inside `makers.py` — fuzz values belong in `generateFiles.py`
- Never assume test order — `main.py` controls sequence

---

## Implementation Progress

| Step | Task | Status |
|------|------|--------|
| 1 | N:N PoC — 6 cross-language files working | ✅ Done |
| 2 | Architecture + SOLID design finalised | ✅ Done |
| 3 | `fileformat.md` + `roadmap.md` written | ✅ Done |
| 4 | `makers.py` — deploy makers + test makers | ⏳ Next |
| 5 | `generateFiles.py` — specs + FUZZ_PLAN + configs | ⏳ Next |
| 6 | `main.py` — deploy + health checks + sequence | 🔜 |
| 7 | Verify generated files manually on MetaCall | 🔜 |
| 8 | `proxy.py` — terminal/core reader + data server | 🔜 Phase II |
| 9 | End-to-end fuzz run + validate log output | 🔜 Phase III |
| 10 | CI integration with testing-center YAML format | 🔜 Phase III |

---

## Adding a New Language

| File | Change |
|------|--------|
| `makers.py` | Add `GoDeployMaker` + `GoTestMaker`, register in `DEPLOY_MAKERS` + `TEST_MAKERS` |
| `generateFiles.py` | Add `"go"` to `LANGUAGES` |
| Everything else | **No changes** |
