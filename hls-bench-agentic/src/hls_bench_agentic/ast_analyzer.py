"""
Clang-AST static analysis for HLS C/C++ source files.
Falls back to regex analysis when libclang is not installed.

Install libclang support:  pip install libclang
On macOS (Homebrew):       brew install llvm
"""
from __future__ import annotations

import re
import tempfile
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

# ---------------------------------------------------------------------------
# libclang availability probe
# ---------------------------------------------------------------------------

_CLANG_AVAILABLE = False
_ci: Any = None

def _probe_clang() -> bool:
    global _ci
    try:
        import clang.cindex as ci  # type: ignore[import]
        _search = [
            "/opt/homebrew/opt/llvm/lib/libclang.dylib",   # macOS M-series
            "/usr/local/opt/llvm/lib/libclang.dylib",       # macOS Intel
            "/usr/lib/llvm-16/lib/libclang.so.1",           # Ubuntu 22
            "/usr/lib/llvm-14/lib/libclang.so.1",           # Ubuntu 20
            "/usr/lib/x86_64-linux-gnu/libclang-14.so.1",
        ]
        if not ci.Config.loaded:
            for p in _search:
                if Path(p).exists():
                    ci.Config.set_library_file(p)
                    break
        _ = ci.Index.create()
        _ci = ci
        return True
    except Exception:
        return False

_CLANG_AVAILABLE = _probe_clang()


# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------

@dataclass
class LoopInfo:
    has_fixed_bound: bool = False
    has_early_exit: bool = False
    body_branch_count: int = 0


@dataclass
class FunctionInfo:
    name: str = ""
    params: list[str] = field(default_factory=list)
    calls: list[str] = field(default_factory=list)
    is_top_level: bool = False


@dataclass
class VariableInfo:
    name: str = ""
    type_str: str = ""
    is_static: bool = False
    is_array: bool = False


@dataclass
class PragmaInfo:
    kind: str = ""
    args: str = ""
    is_valid: bool = True


@dataclass
class AnalysisResult:
    functions: list[FunctionInfo] = field(default_factory=list)
    variables: list[VariableInfo] = field(default_factory=list)
    loops: list[LoopInfo] = field(default_factory=list)
    pragmas: list[PragmaInfo] = field(default_factory=list)
    synthesis_violations: list[str] = field(default_factory=list)
    output_ports: list[str] = field(default_factory=list)
    input_ports: list[str] = field(default_factory=list)
    has_taint_types: bool = False
    secret_to_output_flows: list[str] = field(default_factory=list)
    source_text: str = ""
    analysis_method: str = "none"   # "clang" | "regex"


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_UNSYNTHESIZABLE_CALLS = frozenset({
    "malloc", "calloc", "realloc", "free",
    "printf", "fprintf", "sprintf", "snprintf", "vprintf",
    "fopen", "fclose", "fread", "fwrite",
    "exit", "abort", "system",
    "rand", "srand", "time",
})

_VALID_PRAGMA_KINDS = frozenset({
    "pipeline", "unroll", "loop_bound", "inline",
    "interface", "array_partition", "array_reshape",
})


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def analyze_source(source_code: str, filename: str = "input.cpp") -> AnalysisResult:
    """Parse *source_code* and return an AnalysisResult.

    Uses libclang when available; falls back to regex analysis otherwise.
    """
    result = AnalysisResult(source_text=source_code)
    _extract_pragmas_regex(result)   # pragmas are preprocessor — always use regex
    if _CLANG_AVAILABLE:
        try:
            _analyze_clang(source_code, filename, result)
            result.analysis_method = "clang"
            return result
        except Exception:
            pass
    _analyze_regex(source_code, result)
    result.analysis_method = "regex"
    return result


def score_synthesis_compatibility(result: AnalysisResult) -> tuple[float, str]:
    """Return (score 0–1, human-readable reason)."""
    n = len(result.synthesis_violations)
    has_pragmas = bool(result.pragmas)
    if n == 0:
        if has_pragmas:
            return 1.00, "no violations; HLS pragmas present"
        return 0.80, "no violations; no HLS pragmas found"
    if n <= 2:
        return 0.50, f"{n} synthesis violation(s): {', '.join(result.synthesis_violations[:2])}"
    return 0.25, f"{n} synthesis violations"


# ---------------------------------------------------------------------------
# Clang-based analysis
# ---------------------------------------------------------------------------

def _analyze_clang(source: str, filename: str, result: AnalysisResult) -> None:
    ci = _ci
    suffix = ".cpp" if filename.endswith((".cpp", ".cxx", ".cc")) else ".c"
    with tempfile.NamedTemporaryFile(mode="w", suffix=suffix, delete=False,
                                     encoding="utf-8") as f:
        f.write(source)
        tmp = f.name
    try:
        idx = ci.Index.create()
        flags = ["-std=c++14", "-DHLS_BENCH=1",
                 "-Wno-unknown-pragmas", "-Wno-unused-variable"]
        tu = idx.parse(tmp, args=flags)
        _walk_clang(tu.cursor, tmp, result)
    finally:
        os.unlink(tmp)


def _get_callee_name(cursor) -> str:
    """Extract the called function name from a CALL_EXPR cursor.

    clang sometimes leaves CALL_EXPR.spelling empty for variadic C functions
    (e.g. printf) and puts the name in a child OVERLOADED_DECL_REF instead.
    """
    ci = _ci
    _ref_kinds = (
        ci.CursorKind.DECL_REF_EXPR,
        ci.CursorKind.MEMBER_REF_EXPR,
        ci.CursorKind.OVERLOADED_DECL_REF,
    )
    name = cursor.spelling
    if name:
        return name
    for child in cursor.get_children():
        if child.kind in _ref_kinds and child.spelling:
            return child.spelling
        for grandchild in child.get_children():
            if grandchild.kind in _ref_kinds and grandchild.spelling:
                return grandchild.spelling
    return ""


def _walk_clang(root, src_file: str, result: AnalysisResult) -> None:
    ci = _ci

    def in_src(cursor) -> bool:
        loc = cursor.location
        return loc.file is not None and loc.file.name == src_file

    def walk(cursor, depth: int = 0) -> None:
        if not in_src(cursor) and depth > 0:
            return

        kind = cursor.kind

        if kind == ci.CursorKind.FUNCTION_DECL:
            _extract_function(cursor, result, in_src)

        if kind in (ci.CursorKind.VAR_DECL,):
            if in_src(cursor):
                vi = VariableInfo(
                    name=cursor.spelling,
                    type_str=cursor.type.spelling,
                    is_static="static" in cursor.type.spelling or _has_static(cursor),
                    is_array=cursor.type.kind == ci.TypeKind.CONSTANTARRAY,
                )
                result.variables.append(vi)

        if kind in (ci.CursorKind.FOR_STMT, ci.CursorKind.WHILE_STMT,
                    ci.CursorKind.DO_STMT):
            if in_src(cursor):
                li = LoopInfo(
                    has_fixed_bound=_loop_has_fixed_bound(cursor),
                    has_early_exit=_loop_has_early_exit(cursor),
                    body_branch_count=_loop_branch_count(cursor),
                )
                result.loops.append(li)
                return  # don't double-count nested loops

        if kind == ci.CursorKind.STRUCT_DECL and in_src(cursor):
            _check_taint_struct(cursor, result)

        if kind in (ci.CursorKind.CXX_NEW_EXPR,) and in_src(cursor):
            result.synthesis_violations.append("dynamic allocation (new)")

        if kind in (ci.CursorKind.CXX_DELETE_EXPR,) and in_src(cursor):
            result.synthesis_violations.append("dynamic deallocation (delete)")

        if kind in (ci.CursorKind.CXX_THROW_EXPR,) and in_src(cursor):
            result.synthesis_violations.append("C++ exception (throw)")

        if kind == ci.CursorKind.CALL_EXPR and in_src(cursor):
            fn = _get_callee_name(cursor)
            if fn in _UNSYNTHESIZABLE_CALLS:
                result.synthesis_violations.append(f"unsynthesizable call: {fn}()")

        for child in cursor.get_children():
            walk(child, depth + 1)

    walk(root)


def _has_static(cursor) -> bool:
    try:
        return _ci.StorageClass.STATIC in (cursor.storage_class,)
    except Exception:
        return False


def _extract_function(cursor, result: AnalysisResult, in_src) -> None:
    ci = _ci
    if not in_src(cursor):
        return
    fi = FunctionInfo(
        name=cursor.spelling,
        params=[p.spelling for p in cursor.get_arguments()],
        is_top_level=(cursor.semantic_parent.kind == ci.CursorKind.TRANSLATION_UNIT),
    )
    # Collect calls inside this function
    for child in cursor.walk_preorder():
        if child.kind == ci.CursorKind.CALL_EXPR and child.spelling:
            fi.calls.append(child.spelling)
    # Identify output ports (pointer/array params)
    for arg in cursor.get_arguments():
        tp = arg.type.spelling
        name = arg.spelling
        if "*" in tp or "[]" in tp or "& " in tp:
            result.output_ports.append(name)
        else:
            result.input_ports.append(name)
    result.functions.append(fi)


def _loop_has_fixed_bound(cursor) -> bool:
    ci = _ci
    children = list(cursor.get_children())
    for node in cursor.walk_preorder():
        if node.kind == ci.CursorKind.INTEGER_LITERAL:
            return True
    return False


def _loop_has_early_exit(cursor) -> bool:
    ci = _ci
    _nested = (ci.CursorKind.FOR_STMT, ci.CursorKind.WHILE_STMT, ci.CursorKind.DO_STMT)
    _exits = (ci.CursorKind.BREAK_STMT, ci.CursorKind.RETURN_STMT)

    def walk(c, inside_loop: bool) -> bool:
        if c.kind in _nested and inside_loop:
            return False   # skip nested loops
        if c.kind in _exits and inside_loop:
            return True
        return any(walk(ch, inside_loop or c.kind in _nested) for ch in c.get_children())

    return any(walk(ch, True) for ch in cursor.get_children())


def _loop_branch_count(cursor) -> int:
    ci = _ci
    _branch_kinds = (ci.CursorKind.IF_STMT, ci.CursorKind.SWITCH_STMT,
                     ci.CursorKind.CONDITIONAL_OPERATOR)
    return sum(1 for n in cursor.walk_preorder() if n.kind in _branch_kinds)


def _check_taint_struct(cursor, result: AnalysisResult) -> None:
    fields = [c.spelling for c in cursor.get_children()
              if _ci and c.kind == _ci.CursorKind.FIELD_DECL]
    has_data = "data" in fields
    has_label = any(f in fields for f in ("label", "taint", "security", "tag"))
    if has_data and has_label:
        result.has_taint_types = True


# ---------------------------------------------------------------------------
# Regex-based analysis (fallback)
# ---------------------------------------------------------------------------

_RE_FUNC = re.compile(
    r"(?:static\s+)?(?:inline\s+)?\w[\w\s*<>:,]*?\s+(\w+)\s*\(([^)]*)\)\s*\{",
    re.MULTILINE,
)
_RE_STATIC_ARRAY = re.compile(r"static\s+\w[\w\s*<>]*\s+(\w+)\s*\[", re.MULTILINE)
_RE_FOR = re.compile(r"\bfor\s*\(", re.MULTILINE)
_RE_WHILE = re.compile(r"\bwhile\s*\(", re.MULTILINE)
_RE_BREAK = re.compile(r"\bbreak\s*;")
_RE_RETURN_EARLY = re.compile(r"\breturn\b[^;]{0,50};")
_RE_SYNTH_BAD = re.compile(
    r"\b(new\s+\w|delete\s+[\[*\w]|malloc\s*\(|calloc\s*\(|printf\s*\(|"
    r"fprintf\s*\(|sprintf\s*\(|fopen\s*\(|system\s*\(|throw\s+)"
)
_RE_TAINT = re.compile(r"\bstruct\s+\w+\s*\{[^}]*\bdata\b[^}]*\b(?:label|taint|tag)\b", re.DOTALL)
_RE_STRUCT_DATA_LABEL = re.compile(
    r"struct\s+\w+\s*\{[^}]*\bdata\b[^}]*\b(label|taint|tag|security)\b[^}]*\}", re.DOTALL
)
_RE_PRAGMA = re.compile(r"#\s*pragma\s+HLS\s+(\w+)(.*?)$", re.MULTILINE | re.IGNORECASE)
_RE_FOR_LITERAL = re.compile(r"for\s*\([^;]*;\s*\w+\s*[<>=!]+\s*(\d+)\s*;")


def _analyze_regex(source: str, result: AnalysisResult) -> None:
    # Functions
    for m in _RE_FUNC.finditer(source):
        name, params_str = m.group(1), m.group(2)
        params = [p.strip().split()[-1].lstrip("*") for p in params_str.split(",") if p.strip()]
        result.functions.append(FunctionInfo(name=name, params=params, is_top_level=True))

    # Static arrays
    for m in _RE_STATIC_ARRAY.finditer(source):
        result.variables.append(VariableInfo(name=m.group(1), is_static=True, is_array=True))

    # Loops (approximate)
    for _ in _RE_FOR.finditer(source):
        has_fixed = bool(_RE_FOR_LITERAL.search(source))
        has_break = bool(_RE_BREAK.search(source))
        result.loops.append(LoopInfo(has_fixed_bound=has_fixed, has_early_exit=has_break))
    for _ in _RE_WHILE.finditer(source):
        result.loops.append(LoopInfo(has_fixed_bound=False, has_early_exit=bool(_RE_BREAK.search(source))))

    # Synthesis violations
    for m in _RE_SYNTH_BAD.finditer(source):
        result.synthesis_violations.append(m.group(1).strip())

    # Taint types
    if _RE_STRUCT_DATA_LABEL.search(source):
        result.has_taint_types = True

    # Ports (from first function signature)
    for fi in result.functions[:1]:
        for p in fi.params:
            if "*" in p or p.endswith("[]"):
                result.output_ports.append(p.lstrip("*"))
            else:
                result.input_ports.append(p)


def _extract_pragmas_regex(result: AnalysisResult) -> None:
    for m in _RE_PRAGMA.finditer(result.source_text):
        kind = m.group(1).lower()
        args = m.group(2).strip()
        result.pragmas.append(PragmaInfo(
            kind=kind,
            args=args,
            is_valid=kind in _VALID_PRAGMA_KINDS,
        ))