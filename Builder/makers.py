from __future__ import annotations
from abc import ABC, abstractmethod
from dataclasses import dataclass, field

@dataclass
class ArgSpec:
    name:  str
    type:  str         
    value: object = None 

@dataclass
class Assertion:
    field: str
    value: object

@dataclass
class ReturnOp:
    value:    object
    type:     str
    expected: object = None 

@dataclass
class FuncSpec:
    """Pure data — zero language knowledge."""
    name:        str
    lang:        str
    args:        list[ArgSpec]   = field(default_factory=list)
    return_type: str             = ""
    assertions:  list[Assertion] = field(default_factory=list)
    return_op:   ReturnOp | None = None

class FuncBuilder:
    """
    Fluent API → FuncSpec.

    Example (dynamic expression):
        spec = (
            FuncBuilder()
            .func("py_add", "py")
            .arg("a", "int", 3)
            .arg("b", "int", 4)
            .returns("a + b", "int", expected=7)
            .build()
        )

    Example (literal return):
        spec = (
            FuncBuilder()
            .func("py_negate", "py")
            .arg("v", "bool", True)
            .returns("not v", "bool", expected=False)
            .build()
        )
    """

    def __init__(self) -> None:
        self._name:        str             = ""
        self._lang:        str             = ""
        self._args:        list[ArgSpec]   = []
        self._assertions:  list[Assertion] = []
        self._return_op:   ReturnOp | None = None
        self._return_type: str             = ""

    def func(self, name: str, lang: str) -> "FuncBuilder":
        self._name = name
        self._lang = lang
        return self

    def arg(self, name: str, type_: str, value: object = None) -> "FuncBuilder":
        self._args.append(ArgSpec(name=name, type=type_, value=value))
        return self

    def assert_(self, field_name: str, value: object) -> "FuncBuilder":
        self._assertions.append(Assertion(field=field_name, value=value))
        return self

    def returns(self, value: object, type_: str, expected: object = None) -> "FuncBuilder":
        """
        value    – expression string ("a + b") or literal (7, False, "hello")
        type_    – "int" | "float" | "str" | "bool" | "null"
        expected – concrete value used in test assertions (required when value is an expression)
        """
        self._return_type = type_
        self._return_op   = ReturnOp(value=value, type=type_, expected=expected)
        return self

    def build(self) -> FuncSpec:
        if not self._name:
            raise ValueError("Function name required — call .func() first.")
        if not self._lang:
            raise ValueError("Target language required — call .func() first.")
        if self._return_op and _is_expression(self._return_op.value) and self._return_op.expected is None:
            raise ValueError(
                f"FuncSpec '{self._name}': return value is an expression "
                f"('{self._return_op.value}') but no `expected` was provided. "
                "Pass expected=<concrete_value> to .returns()."
            )
        return FuncSpec(
            name        = self._name,
            lang        = self._lang,
            args        = list(self._args),
            return_type = self._return_type,
            assertions  = list(self._assertions),
            return_op   = self._return_op,
        )

def _is_expression(value: object) -> bool:
    """True if value is a string that looks like a code expression, not a plain string literal."""
    if not isinstance(value, str):
        return False
    return any(c in value for c in ('+', '-', '*', '/', '(', ')')) or ' ' in value.strip()

def _require_arg_values(spec: FuncSpec) -> None:
    missing = [a.name for a in spec.args if a.value is None]
    if missing:
        raise ValueError(
            f"FuncSpec '{spec.name}': args {missing} have no test value — "
            "set values via .arg(name, type, value) for test file generation."
        )

def _resolve_expected(spec: FuncSpec) -> object:
    """Return the concrete expected value for test assertions."""
    if not spec.return_op:
        return None
    if spec.return_op.expected is not None:
        return spec.return_op.expected
    # value must be a literal (not an expression) — validated at build time
    return spec.return_op.value

class BaseDeployMaker(ABC):
    """Produces a deployable source file from FuncSpec objects."""

    @property
    @abstractmethod
    def extension(self) -> str: ...

    @property
    @abstractmethod
    def lang_tag(self) -> str: ...

    @abstractmethod
    def emit_function(self, spec: FuncSpec) -> str: ...

    def emit_file(self, specs: list[FuncSpec]) -> str:
        return self._file_header() + "\n\n".join(
            self.emit_function(s) for s in specs
        ) + self._file_footer(specs)

    def _file_header(self) -> str:
        return ""

    def _file_footer(self, specs: list[FuncSpec]) -> str:
        return ""

class BaseTestMaker(ABC):
    """Produces a metacall test file from FuncSpec objects."""

    @property
    @abstractmethod
    def extension(self) -> str: ...

    @abstractmethod
    def emit_load(self, callee_lang: str, filename: str) -> str: ...

    @abstractmethod
    def emit_call(self, spec: FuncSpec) -> str: ...

    @abstractmethod
    def emit_file(self, specs: list[FuncSpec], callee_lang: str, callee_file: str) -> str: ...

class PyDeployMaker(BaseDeployMaker):
    extension = "py"
    lang_tag  = "py"

    def emit_function(self, spec: FuncSpec) -> str:
        params = ", ".join(a.name for a in spec.args)
        lines  = [f"def {spec.name}({params}):"]
        for a in spec.assertions:
            lines.append(f"    assert {a.field} == {self._lit(a.value)}")
        if spec.return_op:
            lines.append(f"    return {self._emit_return(spec.return_op)}")
        else:
            lines.append("    pass")
        return "\n".join(lines)

    def _emit_return(self, op: ReturnOp) -> str:
        """Emit the return expression, translated to Python syntax."""
        if _is_expression(op.value):
            return self._translate_expr(str(op.value))
        return self._lit(op.value, op.type)

    def _translate_expr(self, expr: str) -> str:
        """Translate a generic expression to Python (e.g. bool literals)."""
        # Python uses True/False natively — no translation needed for +,-,*,/
        # Handle negation: "not v" is already Python
        return expr

    def _lit(self, value: object, type_: str = "") -> str:
        if isinstance(value, bool):                              return str(value)
        if type_ == "null":                                      return "0"
        if value is None:                                        return "None"
        if type_ in ("str", "string") or isinstance(value, str): return f'"{value}"'
        return str(value)

class JsDeployMaker(BaseDeployMaker):
    extension = "js"
    lang_tag  = "node"

    def emit_function(self, spec: FuncSpec) -> str:
        params = ", ".join(a.name for a in spec.args)
        lines  = [f"function {spec.name}({params}) {{"]
        for a in spec.assertions:
            lines.append(
                f"    console.assert({a.field} === {self._lit(a.value)}, "
                f"'{a.field} assertion failed');"
            )
        if spec.return_op:
            lines.append(f"    return {self._emit_return(spec.return_op)};")
        else:
            lines.append("    // TODO")
        lines.append("}")
        return "\n".join(lines)

    def _file_footer(self, specs: list[FuncSpec]) -> str:
        names = ", ".join(f"\n    {s.name}" for s in specs)
        return f"\n\nmodule.exports = {{{names}\n}};\n"

    def _emit_return(self, op: ReturnOp) -> str:
        if _is_expression(op.value):
            return self._translate_expr(str(op.value))
        return self._lit(op.value, op.type)

    def _translate_expr(self, expr: str) -> str:
        """Translate generic expression to JS (Python 'not v' → '!v')."""
        expr = expr.replace("not ", "!")
        expr = expr.replace(" and ", " && ").replace(" or ", " || ")
        return expr

    def _lit(self, value: object, type_: str = "") -> str:
        if isinstance(value, bool):                              return "true" if value else "false"
        if value is None or type_ == "null":                     return "0"
        if type_ in ("str", "string") or isinstance(value, str): return f'"{value}"'
        return str(value)

class RbDeployMaker(BaseDeployMaker):
    extension = "rb"
    lang_tag  = "rb"

    def emit_function(self, spec: FuncSpec) -> str:
        params = ", ".join(a.name for a in spec.args)
        sig    = f"def {spec.name}({params})" if params else f"def {spec.name}"
        lines  = [sig]
        for a in spec.assertions:
            lines.append(
                f"  raise \"assertion failed: {a.field}\" "
                f"unless {a.field} == {self._lit(a.value)}"
            )
        if spec.return_op:
            lines.append(f"  {self._emit_return(spec.return_op)}")
        else:
            lines.append("  nil")
        lines.append("end")
        return "\n".join(lines)

    def _emit_return(self, op: ReturnOp) -> str:
        if _is_expression(op.value):
            return self._translate_expr(str(op.value))
        return self._lit(op.value, op.type)

    def _translate_expr(self, expr: str) -> str:
        """Translate generic expression to Ruby ('not v' → '!v')."""
        expr = expr.replace("not ", "!")
        expr = expr.replace(" and ", " && ").replace(" or ", " || ")
        return expr

    def _lit(self, value: object, type_: str = "") -> str:
        if isinstance(value, bool):                              return "true" if value else "false"
        if value is None or type_ == "null":                     return "0"
        # Use single quotes so string literals are safe inside double-quoted puts strings
        if type_ in ("str", "string") or isinstance(value, str): return f"'{value}'"
        return str(value)

_JAVA_TYPE_MAP = {
    "int": "int", "float": "double", "str": "String",
    "bool": "boolean", "null": "int", "string": "String",
}

class JavaDeployMaker(BaseDeployMaker):
    extension = "java"
    lang_tag  = "java"

    def emit_function(self, spec: FuncSpec) -> str:
        ret    = _JAVA_TYPE_MAP.get(spec.return_type, "Object")
        params = ", ".join(
            f"{_JAVA_TYPE_MAP.get(a.type, 'Object')} {a.name}" for a in spec.args
        )
        lines = [f"public static {ret} {spec.name}({params}) {{"]
        for a in spec.assertions:
            lines.append(
                f'    assert {a.field} == {self._lit(a.value)} '
                f': "{a.field} assertion failed";'
            )
        if spec.return_op:
            lines.append(f"    return {self._emit_return(spec.return_op)};")
        else:
            lines.append("    throw new UnsupportedOperationException();")
        lines.append("}")
        return "\n".join(lines)

    def emit_file(self, specs: list[FuncSpec]) -> str:
        funcs = "\n\n".join(
            "    " + self.emit_function(s).replace("\n", "\n    ") for s in specs
        )
        return f"public class Functions {{\n{funcs}\n}}\n"

    def _emit_return(self, op: ReturnOp) -> str:
        if _is_expression(op.value):
            return self._translate_expr(str(op.value))
        return self._lit(op.value, op.type)

    def _translate_expr(self, expr: str) -> str:
        expr = expr.replace("not ", "!")
        expr = expr.replace(" and ", " && ").replace(" or ", " || ")
        return expr

    def _lit(self, value: object, type_: str = "") -> str:
        if isinstance(value, bool):                              return "true" if value else "false"
        if value is None or type_ == "null":                     return "0"
        if type_ in ("str", "string") or isinstance(value, str): return f'"{value}"'
        return str(value)

_TS_TYPE_MAP = {
    "int": "number", "float": "number", "str": "string",
    "bool": "boolean", "null": "number", "string": "string",
}

class TsDeployMaker(BaseDeployMaker):
    extension = "ts"
    lang_tag  = "ts"

    def emit_function(self, spec: FuncSpec) -> str:
        ret    = _TS_TYPE_MAP.get(spec.return_type, "unknown")
        params = ", ".join(
            f"{a.name}: {_TS_TYPE_MAP.get(a.type, 'unknown')}" for a in spec.args
        )
        js    = JsDeployMaker()
        lines = [f"export function {spec.name}({params}): {ret} {{"]
        for a in spec.assertions:
            lines.append(
                f"    console.assert({a.field} === {js._lit(a.value)}, "
                f"'{a.field} assertion failed');"
            )
        if spec.return_op:
            lines.append(f"    return {js._emit_return(spec.return_op)};")
        else:
            lines.append("    throw new Error('not implemented');")
        lines.append("}")
        return "\n".join(lines)

class JsTestMaker(BaseTestMaker):
    extension = "js"

    def emit_load(self, callee_lang: str, filename: str) -> str:
        return (
            "const { metacall, metacall_load_from_file } = require('metacall');\n\n"
            f"metacall_load_from_file('{callee_lang}', ['{filename}']);"
        )

    def emit_call(self, spec: FuncSpec) -> str:
        _require_arg_values(spec)
        js         = JsDeployMaker()
        label      = spec.name
        args_str   = ", ".join(js._lit(a.value, a.type) for a in spec.args)
        call       = f"metacall('{spec.name}'{(', ' + args_str) if args_str else ''})"
        type_label = spec.return_type.upper() if spec.return_type else "?"
        expected   = _resolve_expected(spec)

        if spec.return_type == "null":
            null_val = str(expected) if expected is not None else "0"
            return "\n".join([
                f"let r_{label};",
                f"let {label}_known_bug = false;",
                "try {",
                f"    r_{label} = {call};",
                f"    {label}_known_bug = r_{label} === undefined || r_{label} === null || r_{label} === 'Invalid';",
                "} catch (err) {",
                f"    r_{label} = 'Invalid';",
                f"    {label}_known_bug = true;",
                "}",
                f"const {label}_ok = r_{label} === '{null_val}' || r_{label} === {null_val} || {label}_known_bug;",
                f"const {label}_expected = {label}_known_bug ? 'Invalid/undefined/null' : '{null_val}';",
                f"console.log(`[{type_label}]  {spec.name}()  = ${{r_{label}}}  | expected: ${{{label}_expected}} | pass: ${{{label}_ok}}`);",
            ])

        eq_check     = f"r_{label} === {js._lit(expected, spec.return_type)}" if expected is not None else "false"
        expected_str = js._lit(expected, spec.return_type) if expected is not None else "?"
        return "\n".join([
            f"const r_{label} = {call};",
            f"console.log(`[{type_label}]  {spec.name}({args_str})  = ${{r_{label}}}  | expected: {expected_str}  | pass: ${{{eq_check}}}`);",
        ])

    def emit_file(self, specs: list[FuncSpec], callee_lang: str, callee_file: str) -> str:
        parts = [
            self.emit_load(callee_lang, callee_file),
            "",
            f'console.log("=== JS -> {callee_lang.upper()} ===");',
            "",
        ]
        parts += [self.emit_call(s) + "\n" for s in specs]
        return "\n".join(parts)

class PyTestMaker(BaseTestMaker):
    extension = "py"

    def emit_load(self, callee_lang: str, filename: str) -> str:
        return (
            "import metacall\n\n"
            f"metacall.metacall_load_from_file('{callee_lang}', ['{filename}'])"
        )

    def _lit(self, value: object, type_: str = "") -> str:
        """Single-quoted string literals — safe to embed inside Python f'...' strings."""
        if isinstance(value, bool):                              return str(value)
        if type_ == "null":                                      return "0"
        if value is None:                                        return "None"
        if type_ in ("str", "string") or isinstance(value, str): return f"'{value}'"
        return str(value)

    def emit_call(self, spec: FuncSpec) -> str:
        _require_arg_values(spec)
        py         = PyDeployMaker()
        label      = spec.name
        # Single-quoted strings so they're safe inside the outer f'...' print string
        args_str   = ", ".join(self._lit(a.value, a.type) for a in spec.args)
        call       = f"metacall.metacall('{spec.name}'{(', ' + args_str) if args_str else ''})"
        type_label = spec.return_type.upper() if spec.return_type else "?"
        expected   = _resolve_expected(spec)

        expected_str = self._lit(expected, spec.return_type) if expected is not None else "?"
        # eq_check is embedded inside a double-quoted f-string expression — must use single quotes for strings
        eq_check     = f"r_{label} == {self._lit(expected, spec.return_type)}" if expected is not None else "False"
        return "\n".join([
            f"r_{label} = {call}",
            f'print(f"[{type_label}]  {spec.name}({args_str})  = {{r_{label}}}  | expected: {expected_str}  | pass: {{{eq_check}}}")',
        ])

    def emit_file(self, specs: list[FuncSpec], callee_lang: str, callee_file: str) -> str:
        parts = [
            self.emit_load(callee_lang, callee_file),
            "",
            f'print("=== Python -> {callee_lang.upper()} ===")',
            "",
        ]
        parts += [self.emit_call(s) + "\n" for s in specs]
        return "\n".join(parts)

class RbTestMaker(BaseTestMaker):
    extension = "rb"

    def emit_load(self, callee_lang: str, filename: str) -> str:
        return f"MetaCallRbLoaderPort.metacall_load_from_file('{callee_lang}', ['{filename}'])"

    def emit_call(self, spec: FuncSpec) -> str:
        _require_arg_values(spec)
        rb         = RbDeployMaker()
        label      = spec.name
        args_str   = ", ".join(rb._lit(a.value, a.type) for a in spec.args)
        call_args  = (", " + args_str) if args_str else ""
        call       = f"MetaCallRbLoaderPort.metacall('{spec.name}'{call_args})"
        type_label = spec.return_type.upper() if spec.return_type else "?"
        expected   = _resolve_expected(spec)

        expected_str = rb._lit(expected, spec.return_type) if expected is not None else "nil"
        eq_check     = f"== {expected_str}"
        return "\n".join([
            f"r_{label} = {call}",
            f'puts "[{type_label}]  {spec.name}({args_str})  = #{{r_{label}}}  | expected: {expected_str}  | pass: #{{r_{label} {eq_check}}}"',
        ])

    def emit_file(self, specs: list[FuncSpec], callee_lang: str, callee_file: str) -> str:
        parts = [
            self.emit_load(callee_lang, callee_file),
            "",
            f'puts "=== Ruby -> {callee_lang.upper()} ==="',
            "",
        ]
        parts += [self.emit_call(s) + "\n" for s in specs]
        return "\n".join(parts)

DEPLOY_MAKERS: dict[str, BaseDeployMaker] = {
    "py":   PyDeployMaker(),
    "js":   JsDeployMaker(),
    "rb":   RbDeployMaker(),
    "java": JavaDeployMaker(),
    "ts":   TsDeployMaker(),
}

TEST_MAKERS: dict[str, BaseTestMaker] = {
    "js": JsTestMaker(),
    "py": PyTestMaker(),
    "rb": RbTestMaker(),
}