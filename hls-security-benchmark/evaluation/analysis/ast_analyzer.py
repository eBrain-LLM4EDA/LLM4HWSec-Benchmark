#!/usr/bin/env python3
"""
Clang AST Analyzer for HLS Security Benchmark.

Replaces regex-based synthesis and security property checks with proper
AST traversal using libclang Python bindings.

Requirements:
    pip install libclang
    apt install libclang-dev   (or equivalent for your OS)

Usage:
    from analysis.ast_analyzer import ASTAnalyzer

    ast = ASTAnalyzer("secure.cpp", stubs_dir="sim_backend/hls_stubs/")
    synth_score = ast.score_synthesis_compatibility()
    ast_info = ast.get_analysis()
"""

import os
import json
from typing import Dict, List, Set, Tuple, Optional
from dataclasses import dataclass, field

try:
    from clang.cindex import (
        Index, CursorKind, TypeKind, TranslationUnit,
        Cursor, conf as clang_conf
    )
    HAS_CLANG = True
except ImportError:
    HAS_CLANG = False


# ---------------------------------------------------------------------------
# Data structures for analysis results
# ---------------------------------------------------------------------------

@dataclass
class FunctionInfo:
    name: str
    params: List[dict]           # [{name, type_str, is_output, is_reference}]
    has_hls_interface: bool
    is_top_level: bool
    calls: List[str]             # functions called
    line: int = 0


@dataclass
class VariableInfo:
    name: str
    type_str: str
    is_static: bool
    is_array: bool
    array_size: Optional[int]
    scope: str                   # function name or "global"
    line: int = 0


@dataclass
class LoopInfo:
    line: int
    has_fixed_bound: bool
    has_early_exit: bool         # break or return inside
    has_secret_dependent_cond: bool
    bound_expr: str
    body_branch_count: int       # number of if/else in body


@dataclass
class PragmaInfo:
    kind: str                    # PIPELINE, UNROLL, INTERFACE, etc.
    args: Dict[str, str]         # parsed key=value pairs
    line: int
    is_valid: bool
    error: str = ""


@dataclass
class AnalysisResult:
    functions: List[FunctionInfo] = field(default_factory=list)
    variables: List[VariableInfo] = field(default_factory=list)
    loops: List[LoopInfo] = field(default_factory=list)
    pragmas: List[PragmaInfo] = field(default_factory=list)
    synthesis_violations: List[str] = field(default_factory=list)
    output_ports: List[str] = field(default_factory=list)
    input_ports: List[str] = field(default_factory=list)
    has_taint_types: bool = False
    taint_type_names: List[str] = field(default_factory=list)
    has_declassification: bool = False
    secret_to_output_flows: List[str] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Unsynthesizable construct detection
# ---------------------------------------------------------------------------

UNSYNTHESIZABLE_KINDS = {
    CursorKind.CXX_NEW_EXPR: "dynamic allocation (new)",
    CursorKind.CXX_DELETE_EXPR: "dynamic deallocation (delete)",
    CursorKind.CXX_THROW_EXPR: "exception (throw)",
    CursorKind.CXX_TRY_STMT: "exception (try/catch)",
    CursorKind.CXX_CATCH_STMT: "exception (catch)",
} if HAS_CLANG else {}

UNSYNTHESIZABLE_CALLS = {
    "malloc", "calloc", "realloc", "free",
    "printf", "fprintf", "sprintf", "snprintf",
    "fopen", "fclose", "fread", "fwrite",
    "exit", "system",
    "rand", "srand", "time",
    # Note: abort and assert are NOT included — they appear in HLS library
    # headers (ap_int.h uses assert()) but are compiled away during synthesis.
}

# Functions that indicate recursion risk (self-calls checked separately)
STL_TYPES = {"std::vector", "std::map", "std::set", "std::list",
             "std::string", "std::deque", "std::unordered_map"}


# ---------------------------------------------------------------------------
# System include path detection
# ---------------------------------------------------------------------------

def _detect_system_includes() -> List[str]:
    """
    Detect system include paths needed by libclang.

    libclang's Python bindings don't automatically find GCC's or Clang's
    built-in headers (stddef.h, stdarg.h, etc.). We need to discover and
    pass them explicitly via -isystem.
    """
    args = []
    import glob
    import subprocess

    # Strategy 0: Use libclang's own library path to find its resource dir
    # This is the most reliable approach inside Docker containers
    try:
        from clang.cindex import conf as clang_conf
        libclang_path = clang_conf.get_filename()
        if libclang_path:
            # libclang.so is typically at /usr/lib/llvm-XX/lib/libclang.so
            # resource dir is at /usr/lib/llvm-XX/lib/clang/XX/include
            lib_dir = os.path.dirname(os.path.realpath(libclang_path))
            # Try: lib_dir/../lib/clang/*/include
            clang_dirs = sorted(glob.glob(
                os.path.join(lib_dir, "clang", "*", "include")
            ), reverse=True)
            if not clang_dirs:
                # Try one level up: /usr/lib/llvm-XX/lib/clang/XX/include
                parent = os.path.dirname(lib_dir)
                clang_dirs = sorted(glob.glob(
                    os.path.join(parent, "lib", "clang", "*", "include")
                ), reverse=True)
            for d in clang_dirs:
                if os.path.isfile(os.path.join(d, "stddef.h")):
                    args.extend(["-isystem", d])
                    break
    except Exception:
        pass

    # Strategy 1: Find Clang's resource dir via command line
    if not args:
        try:
            result = subprocess.run(
                ["clang", "-print-resource-dir"],
                capture_output=True, text=True, timeout=5
            )
            if result.returncode == 0:
                resource_dir = result.stdout.strip()
                include_dir = os.path.join(resource_dir, "include")
                if os.path.isdir(include_dir):
                    args.extend(["-isystem", include_dir])
        except (FileNotFoundError, subprocess.TimeoutExpired):
            pass

    # Strategy 2: Brute-force search for clang built-in headers
    if not args:
        clang_patterns = [
            "/usr/lib/llvm-*/lib/clang/*/include",
            "/usr/lib/clang/*/include",
            "/usr/local/lib/clang/*/include",
        ]
        for pattern in clang_patterns:
            matches = sorted(glob.glob(pattern), reverse=True)
            for match in matches:
                if os.path.isfile(os.path.join(match, "stddef.h")):
                    args.extend(["-isystem", match])
                    break
            if args:
                break

    # Strategy 3: Find GCC's built-in include dir
    if not args:
        gcc_patterns = [
            "/usr/lib/gcc/x86_64-linux-gnu/*/include",
            "/usr/lib/gcc/aarch64-linux-gnu/*/include",
            "/usr/lib/gcc/*/*/include",
        ]
        for pattern in gcc_patterns:
            matches = sorted(glob.glob(pattern), reverse=True)
            for match in matches:
                if os.path.isfile(os.path.join(match, "stddef.h")):
                    args.extend(["-isystem", match])
                    break
            if args:
                break

    # Strategy 4: Ask GCC directly for its include paths
    if not args:
        try:
            result = subprocess.run(
                ["gcc", "-E", "-x", "c++", "-v", "/dev/null"],
                capture_output=True, text=True, timeout=5
            )
            in_search = False
            for line in result.stderr.split("\n"):
                if "#include <...> search starts here" in line:
                    in_search = True
                    continue
                if "End of search list" in line:
                    break
                if in_search:
                    path = line.strip()
                    if os.path.isdir(path):
                        args.extend(["-isystem", path])
        except (FileNotFoundError, subprocess.TimeoutExpired):
            pass

    return args


# Cache the result so we don't re-detect on every file
_cached_system_args = None

def _get_system_include_args() -> List[str]:
    global _cached_system_args
    if _cached_system_args is None:
        _cached_system_args = _detect_system_includes()
    return _cached_system_args


# ---------------------------------------------------------------------------
# Main Analyzer Class
# ---------------------------------------------------------------------------

class ASTAnalyzer:
    """
    Parses HLS C++ source with Clang and extracts structural information
    for synthesis compatibility and security property verification.
    """

    def __init__(self, source_path: str, stubs_dir: str = None,
                 include_dirs: List[str] = None,
                 extra_args: List[str] = None):
        if not HAS_CLANG:
            raise ImportError(
                "libclang not found. Install with: pip install libclang\n"
                "Also ensure libclang-dev is installed on your system."
            )

        self.source_path = os.path.abspath(source_path)
        self.stubs_dir = stubs_dir
        self.result = AnalysisResult()

        # Build compilation args
        args = ["-std=c++17", "-fsyntax-only"]
        # Legacy single stubs_dir
        if stubs_dir:
            args.append(f"-I{os.path.abspath(stubs_dir)}")
        # Multiple include dirs
        if include_dirs:
            for d in include_dirs:
                if os.path.isdir(d):
                    args.append(f"-I{os.path.abspath(d)}")
        if extra_args:
            args.extend(extra_args)

        # Auto-detect system include paths that libclang needs but doesn't
        # find on its own (GCC builtins like stddef.h, stdarg.h, etc.)
        args.extend(_get_system_include_args())

        # Parse with Clang
        index = Index.create()
        self.tu = index.parse(
            self.source_path, args=args,
            options=TranslationUnit.PARSE_DETAILED_PROCESSING_RECORD
        )

        # Check for parse errors
        self.parse_errors = []
        fatal_errors = False
        for diag in self.tu.diagnostics:
            if diag.severity >= 4:  # Fatal only (missing headers, etc.)
                self.parse_errors.append(str(diag))
                fatal_errors = True
            elif diag.severity >= 3:  # Error (type mismatches from stubs, etc.)
                # Errors from HLS stubs are expected — our stubs don't implement
                # every ap_uint conversion. Only treat as fatal if they're in
                # the user's source file, not in stub headers.
                err_str = str(diag)
                if "hls_stubs" not in err_str:
                    self.parse_errors.append(err_str)

        # Always attempt analysis even with non-fatal errors — Clang builds
        # a partial AST that still contains useful structural information
        self._analyze()

    def _analyze(self):
        """Run all analysis passes over the AST."""
        self._extract_functions(self.tu.cursor)
        self._extract_variables(self.tu.cursor)
        self._extract_loops(self.tu.cursor)
        self._extract_pragmas()
        self._check_synthesis_violations(self.tu.cursor)
        self._detect_taint_types(self.tu.cursor)
        self._identify_ports()
        self._trace_secret_flows(self.tu.cursor)

    # --- Function extraction ---

    def _extract_functions(self, cursor: 'Cursor', depth: int = 0):
        for child in cursor.get_children():
            if child.location.file and \
               os.path.abspath(child.location.file.name) != self.source_path:
                continue  # Skip headers

            if child.kind == CursorKind.FUNCTION_DECL and child.is_definition():
                params = []
                for p in child.get_arguments():
                    is_ref = p.type.kind == TypeKind.LVALUEREFERENCE
                    is_ptr = p.type.kind == TypeKind.POINTER
                    params.append({
                        "name": p.spelling,
                        "type_str": p.type.spelling,
                        "is_output": is_ref or is_ptr,
                        "is_reference": is_ref,
                    })

                calls = []
                self._find_calls(child, calls)

                info = FunctionInfo(
                    name=child.spelling,
                    params=params,
                    has_hls_interface=False,  # filled in by pragma pass
                    is_top_level=False,
                    calls=calls,
                    line=child.location.line,
                )
                self.result.functions.append(info)

            self._extract_functions(child, depth + 1)

    def _find_calls(self, cursor: 'Cursor', calls: List[str]):
        for child in cursor.get_children():
            if child.kind == CursorKind.CALL_EXPR:
                # Only count calls that originate in the user's source file
                if self._is_in_user_source(child):
                    if child.referenced and child.referenced.spelling:
                        calls.append(child.referenced.spelling)
            self._find_calls(child, calls)

    # --- Variable extraction ---

    def _extract_variables(self, cursor: 'Cursor', scope: str = "global"):
        for child in cursor.get_children():
            if child.location.file and \
               os.path.abspath(child.location.file.name) != self.source_path:
                continue

            if child.kind == CursorKind.FUNCTION_DECL:
                self._extract_variables(child, child.spelling)
                continue

            if child.kind == CursorKind.VAR_DECL:
                type_str = child.type.spelling
                is_array = child.type.kind == TypeKind.CONSTANTARRAY
                array_size = None
                if is_array:
                    array_size = child.type.element_count

                is_static = "static" in [
                    t.spelling for t in child.get_tokens()
                    if t.spelling == "static"
                ]

                self.result.variables.append(VariableInfo(
                    name=child.spelling,
                    type_str=type_str,
                    is_static=is_static,
                    is_array=is_array,
                    array_size=array_size,
                    scope=scope,
                    line=child.location.line,
                ))

            self._extract_variables(child, scope)

    # --- Loop analysis ---

    def _extract_loops(self, cursor: 'Cursor'):
        for child in cursor.get_children():
            if child.location.file and \
               os.path.abspath(child.location.file.name) != self.source_path:
                continue

            if child.kind == CursorKind.FOR_STMT:
                loop = self._analyze_loop(child)
                self.result.loops.append(loop)

            if child.kind == CursorKind.WHILE_STMT:
                self.result.loops.append(LoopInfo(
                    line=child.location.line,
                    has_fixed_bound=False,  # while loops don't have fixed bounds
                    has_early_exit=self._has_early_exit(child),
                    has_secret_dependent_cond=False,
                    bound_expr="while",
                    body_branch_count=self._count_branches(child),
                ))

            self._extract_loops(child)

    def _analyze_loop(self, for_stmt: 'Cursor') -> LoopInfo:
        children = list(for_stmt.get_children())

        # Check for fixed bound (condition uses literal comparison)
        has_fixed = False
        bound_expr = ""
        if len(children) >= 2:
            cond = children[1]
            tokens = [t.spelling for t in cond.get_tokens()]
            bound_expr = " ".join(tokens)
            # Fixed bound if condition compares with a literal or #define constant
            has_fixed = any(t.isdigit() or t.startswith("0x") for t in tokens)

        return LoopInfo(
            line=for_stmt.location.line,
            has_fixed_bound=has_fixed,
            has_early_exit=self._has_early_exit(for_stmt),
            has_secret_dependent_cond=False,  # refined by secret flow analysis
            bound_expr=bound_expr,
            body_branch_count=self._count_branches(for_stmt),
        )

    def _has_early_exit(self, cursor: 'Cursor') -> bool:
        """Check if a loop body contains break or return."""
        for child in cursor.get_children():
            if child.kind == CursorKind.BREAK_STMT:
                return True
            if child.kind == CursorKind.RETURN_STMT:
                return True
            # Don't recurse into nested loops (their break is fine)
            if child.kind in (CursorKind.FOR_STMT, CursorKind.WHILE_STMT):
                continue
            if self._has_early_exit(child):
                return True
        return False

    def _count_branches(self, cursor: 'Cursor') -> int:
        count = 0
        for child in cursor.get_children():
            if child.kind == CursorKind.IF_STMT:
                count += 1
            count += self._count_branches(child)
        return count

    # --- HLS Pragma extraction ---

    def _extract_pragmas(self):
        """Extract and validate #pragma HLS directives from source text."""
        with open(self.source_path, "r") as f:
            lines = f.readlines()

        for i, line in enumerate(lines):
            stripped = line.strip()
            if stripped.startswith("#pragma") and "HLS" in stripped:
                pragma = self._parse_pragma(stripped, i + 1)
                self.result.pragmas.append(pragma)

                # Mark functions with INTERFACE pragmas as top-level
                if pragma.kind == "INTERFACE":
                    for func in self.result.functions:
                        # Pragma is inside this function if line numbers overlap
                        func.has_hls_interface = True
                        func.is_top_level = True

    def _parse_pragma(self, text: str, line: int) -> PragmaInfo:
        """Parse a single HLS pragma and validate its syntax."""
        # Remove "#pragma HLS "
        parts = text.replace("#pragma", "").strip()
        parts = parts.replace("HLS", "", 1).strip()

        # First token is the pragma kind
        tokens = parts.split()
        if not tokens:
            return PragmaInfo(kind="UNKNOWN", args={}, line=line,
                              is_valid=False, error="Empty pragma")

        kind = tokens[0].upper()
        args = {}

        # Parse key=value pairs
        for token in tokens[1:]:
            if "=" in token:
                key, val = token.split("=", 1)
                args[key.lower()] = val
            else:
                args[token.lower()] = "true"

        # Validate based on kind
        is_valid = True
        error = ""

        if kind == "INTERFACE":
            if "port" not in args:
                is_valid = False
                error = "INTERFACE pragma missing 'port=' argument"
        elif kind == "PIPELINE":
            pass  # II is optional (defaults to 1)
        elif kind == "UNROLL":
            pass  # factor is optional (defaults to full unroll)
        elif kind == "BIND_STORAGE":
            if "variable" not in args:
                is_valid = False
                error = "BIND_STORAGE missing 'variable=' argument"
        elif kind in ("ARRAY_PARTITION", "ARRAY_RESHAPE",
                       "LOOP_TRIPCOUNT", "DATAFLOW", "INLINE",
                       "STREAM", "LATENCY", "ALLOCATION"):
            pass  # All valid pragma kinds
        else:
            # Unknown pragma kind — flag but don't fail
            error = f"Unknown pragma kind: {kind}"

        return PragmaInfo(kind=kind, args=args, line=line,
                          is_valid=is_valid, error=error)

    # --- Synthesis violation checks ---

    def _is_in_user_source(self, cursor) -> bool:
        """Check if a cursor is in the user's source file (not headers)."""
        if not cursor.location.file:
            return False
        file_path = os.path.abspath(cursor.location.file.name)
        return file_path == self.source_path

    def _check_synthesis_violations(self, cursor: 'Cursor'):
        for child in cursor.get_children():
            if not self._is_in_user_source(child):
                continue

            # Check AST node kind
            if child.kind in UNSYNTHESIZABLE_KINDS:
                desc = UNSYNTHESIZABLE_KINDS[child.kind]
                self.result.synthesis_violations.append(
                    f"Line {child.location.line}: {desc}"
                )

            # Check function calls
            if child.kind == CursorKind.CALL_EXPR:
                callee = child.referenced
                if callee and callee.spelling in UNSYNTHESIZABLE_CALLS:
                    self.result.synthesis_violations.append(
                        f"Line {child.location.line}: "
                        f"unsynthesizable call to {callee.spelling}()"
                    )

            # Check for STL types in user code (not in HLS library internals)
            if child.kind == CursorKind.VAR_DECL:
                type_str = child.type.spelling
                for stl_type in STL_TYPES:
                    if stl_type in type_str:
                        # Skip if the variable is an hls::stream (which uses
                        # std::queue internally in simulation but synthesizes fine)
                        if "hls::stream" in type_str or "hls_stream" in type_str:
                            continue
                        self.result.synthesis_violations.append(
                            f"Line {child.location.line}: "
                            f"STL type {stl_type} not synthesizable"
                        )

            # Check for virtual functions
            if child.kind == CursorKind.CXX_METHOD and child.is_virtual_method():
                self.result.synthesis_violations.append(
                    f"Line {child.location.line}: "
                    f"virtual function {child.spelling}() not synthesizable"
                )

            # Recursion detection: function calls itself
            if child.kind == CursorKind.FUNCTION_DECL and child.is_definition():
                calls = []
                self._find_calls(child, calls)
                if child.spelling in calls:
                    self.result.synthesis_violations.append(
                        f"Line {child.location.line}: "
                        f"recursive function {child.spelling}() not synthesizable"
                    )

            self._check_synthesis_violations(child)

    # --- Taint type detection ---

    def _detect_taint_types(self, cursor: 'Cursor'):
        """Find struct/class types that carry a security label field."""
        for child in cursor.get_children():
            if child.location.file and \
               os.path.abspath(child.location.file.name) != self.source_path:
                continue

            if child.kind in (CursorKind.STRUCT_DECL, CursorKind.CLASS_DECL):
                fields = [c.spelling for c in child.get_children()
                          if c.kind == CursorKind.FIELD_DECL]
                # A taint type has both a data field and a label/taint field
                has_data = any("data" in f.lower() for f in fields)
                has_label = any(
                    kw in f.lower()
                    for f in fields
                    for kw in ("label", "taint", "security", "tag", "level")
                )
                if has_data and has_label:
                    self.result.has_taint_types = True
                    self.result.taint_type_names.append(child.spelling)

            # Also check for enums with SECRET/PUBLIC
            if child.kind == CursorKind.ENUM_DECL:
                members = [c.spelling for c in child.get_children()
                           if c.kind == CursorKind.ENUM_CONSTANT_DECL]
                if any("SECRET" in m.upper() for m in members) and \
                   any("PUBLIC" in m.upper() for m in members):
                    self.result.has_taint_types = True

            self._detect_taint_types(child)

    # --- Port identification ---

    def _identify_ports(self):
        """Identify input and output ports from top-level function signatures."""
        for func in self.result.functions:
            if not func.is_top_level:
                continue
            for param in func.params:
                if param["is_output"]:
                    self.result.output_ports.append(param["name"])
                else:
                    self.result.input_ports.append(param["name"])

    # --- Secret flow tracing ---

    def _trace_secret_flows(self, cursor: 'Cursor'):
        """
        Simplified secret-to-output flow detection.

        Full implementation would build a proper def-use graph and do
        iterative dataflow analysis. This version does a name-based
        approximation: if any variable with 'key', 'secret', or 'rk'
        in its name is assigned to a variable that appears in an output
        port assignment, flag it.
        """
        secret_names = set()
        for var in self.result.variables:
            name_lower = var.name.lower()
            if any(kw in name_lower for kw in ("key", "secret", "rk", "hmac_key")):
                secret_names.add(var.name)

        # Check if any output port name appears in an assignment from a secret
        # This is still approximate — a full solution needs SSA form
        with open(self.source_path, "r") as f:
            source = f.read()

        for port in self.result.output_ports:
            for secret in secret_names:
                # Look for direct assignment patterns like: port = secret
                # or: port = expr(secret)
                import re
                pattern = rf"{re.escape(port)}\s*=.*{re.escape(secret)}"
                if re.search(pattern, source):
                    self.result.secret_to_output_flows.append(
                        f"{secret} -> {port}"
                    )

        # Check for declassification patterns
        for func in self.result.functions:
            if any(kw in func.name.lower()
                   for kw in ("declassif", "check_output", "authorize")):
                self.result.has_declassification = True

    # --- Scoring functions ---

    def score_synthesis_compatibility(self) -> tuple:
        """Score 0.0–1.0 for synthesis compatibility. Returns (score, reason)."""
        if self.parse_errors:
            return 0.0, f"parse errors ({len(self.parse_errors)})"

        violations = len(self.result.synthesis_violations)
        has_pragmas = any(p.kind == "INTERFACE" for p in self.result.pragmas)
        
        # Check for HLS types in variables AND function parameters
        all_type_strings = [v.type_str for v in self.result.variables]
        all_type_strings += [p["type_str"] for f in self.result.functions for p in f.params]
        
        has_hls_types = any(
            "ap_uint" in t or "ap_int" in t or "ap_fixed" in t
            for t in all_type_strings
        )
        has_streams = any("hls::stream" in t or "stream" in t for t in all_type_strings)

        # Also check source text as fallback (Clang may resolve template names)
        if not has_hls_types or not has_pragmas:
            with open(self.source_path, "r") as f:
                source = f.read()
            if not has_hls_types:
                has_hls_types = "ap_uint" in source or "ap_int" in source
            if not has_pragmas:
                has_pragmas = "#pragma HLS INTERFACE" in source or \
                              "#pragma HLS interface" in source
            if not has_streams:
                has_streams = "hls::stream" in source

        invalid_pragmas = sum(1 for p in self.result.pragmas if not p.is_valid)

        if violations == 0 and has_pragmas and (has_hls_types or has_streams):
            if invalid_pragmas == 0:
                return 1.0, "clean"
            else:
                return 0.9, f"{invalid_pragmas} invalid pragma(s)"
        elif violations == 0 and (has_hls_types or has_streams):
            return 0.85, "no INTERFACE pragmas detected"
        elif violations == 0:
            parts = []
            if not has_pragmas: parts.append("no HLS pragmas")
            if not has_hls_types: parts.append("no ap_uint/ap_int types")
            if not has_streams: parts.append("no hls::stream")
            return 0.7, "; ".join(parts) if parts else "no HLS constructs found"
        elif violations <= 2:
            return 0.5, f"{violations} violation(s)"
        else:
            return 0.25, f"{violations} violations"

    def get_analysis(self) -> AnalysisResult:
        return self.result

    def to_dict(self) -> dict:
        """Serialize analysis results to a dictionary."""
        return {
            "source": self.source_path,
            "parse_errors": self.parse_errors,
            "functions": [
                {"name": f.name, "params": f.params, "line": f.line,
                 "is_top_level": f.is_top_level, "calls": f.calls}
                for f in self.result.functions
            ],
            "variables": [
                {"name": v.name, "type": v.type_str, "static": v.is_static,
                 "array": v.is_array, "scope": v.scope}
                for v in self.result.variables
            ],
            "loops": [
                {"line": l.line, "fixed_bound": l.has_fixed_bound,
                 "early_exit": l.has_early_exit, "branches": l.body_branch_count}
                for l in self.result.loops
            ],
            "pragmas": [
                {"kind": p.kind, "args": p.args, "line": p.line,
                 "valid": p.is_valid, "error": p.error}
                for p in self.result.pragmas
            ],
            "synthesis_violations": self.result.synthesis_violations,
            "output_ports": self.result.output_ports,
            "input_ports": self.result.input_ports,
            "has_taint_types": self.result.has_taint_types,
            "taint_type_names": self.result.taint_type_names,
            "secret_to_output_flows": self.result.secret_to_output_flows,
        }


# ---------------------------------------------------------------------------
# CLI for standalone use
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import sys
    if len(sys.argv) < 2:
        print("Usage: python ast_analyzer.py <source.cpp> [stubs_dir]")
        sys.exit(1)

    source = sys.argv[1]
    stubs = sys.argv[2] if len(sys.argv) > 2 else None

    analyzer = ASTAnalyzer(source, stubs_dir=stubs)

    print(json.dumps(analyzer.to_dict(), indent=2))
    print(f"\nSynthesis score: {analyzer.score_synthesis_compatibility()}")
