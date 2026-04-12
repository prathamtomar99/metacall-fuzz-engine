import os, sys
sys.path.insert(0, '/home/claude')
from makers import FuncBuilder, DEPLOY_MAKERS, TEST_MAKERS
OUT_DIR = "./output"
os.makedirs(OUT_DIR, exist_ok=True)

DISPLAY = {"rb": "rb", "py": "py", "js": "js"}


def make_specs(lang: str) -> list:
    B = FuncBuilder
    return [
        B().func(f"{lang}_add", lang)
          .arg("a", "int", 3)
          .arg("b", "int", 4)
          .returns("a + b", "int", expected=7)
          .build(),

        B().func(f"{lang}_sub", lang)
          .arg("a", "float", 5.5)
          .arg("b", "float", 2.5)
          .returns("a - b", "float", expected=3.0)
          .build(),

        B().func(f"{lang}_mul", lang)
          .arg("a", "int", 3)
          .arg("b", "int", 4)
          .returns("a * b", "int", expected=12)
          .build(),

        B().func(f"{lang}_concat", lang)
          .arg("a", "str", "hello")
          .arg("b", "str", "world")
          .returns("a + b", "str", expected="helloworld")
          .build(),

        B().func(f"{lang}_negate", lang)
          .arg("v", "bool", True)
          .returns("not v", "bool", expected=False)
          .build(),

        B().func(f"{lang}_zero", lang)
          .returns(0, "null")
          .build(),
    ]

generated = []

for lang in ["js", "py", "rb"]:
    maker = DEPLOY_MAKERS[lang]
    specs = make_specs(lang)
    code  = maker.emit_file(specs)
    fname = f"{DISPLAY[lang]}_functions.{maker.extension}"
    path  = os.path.join(OUT_DIR, fname)
    with open(path, "w") as f:
        f.write(code)
    generated.append(fname)
    print(f"[deploy]  {path}")

pairs = [
    ("js", "py"),
    ("js", "rb"),
    ("py", "js"),
    ("py", "rb"),
    ("rb", "js"),
    ("rb", "py"),
]

for caller, callee in pairs:
    tmaker      = TEST_MAKERS[caller]
    dmaker      = DEPLOY_MAKERS[callee]
    specs       = make_specs(callee)
    callee_file = f"{DISPLAY[callee]}_functions.{dmaker.extension}"
    callee_tag  = dmaker.lang_tag
    code        = tmaker.emit_file(specs, callee_tag, callee_file)
    fname       = f"test_{DISPLAY[caller]}_to_{DISPLAY[callee]}.{tmaker.extension}"
    path        = os.path.join(OUT_DIR, fname)
    with open(path, "w") as f:
        f.write(code)
    generated.append(fname)
    print(f"[test]    {path}")

print(f"\n✓ {len(generated)} files written to {OUT_DIR}/")
for f in generated:
    print(f"  {f}")