"""
evaluation/private/static_checks.py

Hidden-from-participant static structural checks for SR1, SR2, and SR3.

These checks are intentionally *fail-on-presence* only: they look for the
data-dependent early-exit construct (SR1/SR2), an interface deviation from
the pinned fixed-size signature (SR3 interface half), and dynamic/heap
allocation constructs (SR3 no-alloc half) that are the actual
vulnerabilities being guarded against. A correct, hardened implementation
that scans all 16 bytes unconditionally, keeps the pinned two-parameter
fixed-16-byte-array signature, and uses only fixed-size stack buffers will
simply not contain any of these constructs and will therefore pass
vacuously.

Anchor: the shipped baseline's comparison loop is

    for (int i = 0; i < 16; ++i) {
        if (computed_tag[i] != received_tag[i]) {
            return false;
        }
    }

which contains a `return` (and hence trips both SR1 and SR2) inside the
loop body.

Anchor: the SR3 mutant redefines the interface with a pointer+length
signature and a heap-allocated diff buffer, e.g.

    bool verify(const unsigned char* computed_tag, const unsigned char* received_tag, size_t len = 16) {
        unsigned char* diff = (unsigned char*)malloc(len);
        ...
        free(diff);
    }

which SR3's interface check must reject (extra/defaulted `len` parameter,
pointer instead of fixed-size array) and which SR3's alloc-scan check must
reject (via `malloc`/`free`).

All check_* functions return a `(bool_ok, reason_string)` tuple.
`reason_string` is empty when `bool_ok` is True.
"""


def _strip_comments_and_strings(text):
    """Blank out //, /* */ comments and "..."/'...' literals, preserving
    the original character offsets (so brace/paren counting downstream
    stays correct) but eliminating false matches of loop/return keywords
    or banned tokens that might otherwise appear inside comments or
    string literals."""
    result = list(text)
    n = len(text)
    i = 0
    while i < n:
        c = text[i]
        if c == '/' and i + 1 < n and text[i + 1] == '/':
            j = i
            while j < n and text[j] != '\n':
                result[j] = ' '
                j += 1
            i = j
        elif c == '/' and i + 1 < n and text[i + 1] == '*':
            j = i + 2
            while j + 1 < n and not (text[j] == '*' and text[j + 1] == '/'):
                j += 1
            end = min(j + 2, n)
            for k in range(i, end):
                result[k] = ' '
            i = end
        elif c == '"':
            j = i + 1
            result[i] = ' '
            while j < n and text[j] != '"':
                if text[j] == '\\' and j + 1 < n:
                    result[j] = ' '
                    result[j + 1] = ' '
                    j += 2
                    continue
                result[j] = ' '
                j += 1
            if j < n:
                result[j] = ' '
                j += 1
            i = j
        elif c == "'":
            j = i + 1
            result[i] = ' '
            while j < n and text[j] != "'":
                if text[j] == '\\' and j + 1 < n:
                    result[j] = ' '
                    result[j + 1] = ' '
                    j += 2
                    continue
                result[j] = ' '
                j += 1
            if j < n:
                result[j] = ' '
                j += 1
            i = j
        else:
            i += 1
    return ''.join(result)


def _is_word_char(ch):
    return ch.isalnum() or ch == '_'


def _find_token(text, token, start=0):
    """Find the next word-boundary-matched occurrence of `token` in
    `text` at or after `start`. Returns the start index, or -1."""
    idx = start
    n = len(text)
    tlen = len(token)
    while True:
        pos = text.find(token, idx)
        if pos == -1:
            return -1
        before_ok = (pos == 0) or (not _is_word_char(text[pos - 1]))
        after_idx = pos + tlen
        after_ok = (after_idx >= n) or (not _is_word_char(text[after_idx]))
        if before_ok and after_ok:
            return pos
        idx = pos + 1


def _contains_token(text, token):
    return _find_token(text, token, 0) != -1


def _next_keyword(text, start, keywords):
    """Find the earliest word-boundary-matched occurrence, at or after
    `start`, of any keyword in `keywords`. Returns (keyword, start_idx,
    end_idx) or None if none found."""
    best = None
    for kw in keywords:
        pos = _find_token(text, kw, start)
        if pos != -1:
            if best is None or pos < best[1]:
                best = (kw, pos, pos + len(kw))
    return best


def _match_balanced(text, open_idx, open_ch, close_ch):
    """Given the index of an opening delimiter (already confirmed to be
    `open_ch`), return the index just past the matching closing
    delimiter, or -1 if unbalanced."""
    n = len(text)
    depth = 1
    k = open_idx + 1
    while k < n and depth > 0:
        if text[k] == open_ch:
            depth += 1
        elif text[k] == close_ch:
            depth -= 1
        k += 1
    if depth != 0:
        return -1
    return k


def _find_function_body(stripped_text):
    """Locate the definition of `verify(...)` (matching the pinned
    signature name) in `stripped_text` (comments/strings already
    blanked) and return the text of its body (the content strictly
    between the outermost `{` and its matching `}`). Returns None if no
    function *definition* (as opposed to a declaration) is found."""
    n = len(stripped_text)
    search_from = 0
    while True:
        pos = _find_token(stripped_text, "verify", search_from)
        if pos == -1:
            return None
        search_from = pos + 1

        j = pos + len("verify")
        while j < n and stripped_text[j].isspace():
            j += 1
        if j >= n or stripped_text[j] != '(':
            continue

        k = _match_balanced(stripped_text, j, '(', ')')
        if k == -1:
            continue

        m = k
        while m < n and stripped_text[m].isspace():
            m += 1

        if m < n and stripped_text[m] == '{':
            p = _match_balanced(stripped_text, m, '{', '}')
            if p == -1:
                continue
            body_start = m + 1
            body_end = p - 1
            return stripped_text[body_start:body_end]
        else:
            # This occurrence is a declaration (e.g. ends with ';') or
            # something else that isn't a function definition; keep
            # searching for the actual definition.
            continue


def _find_loops(body_text):
    """Find every `for`/`while`/`do-while` loop construct in
    `body_text` and return a list of the text of each loop's own body
    (the statement or braced block controlled by the loop)."""
    loops = []
    i = 0
    n = len(body_text)
    while i < n:
        m = _next_keyword(body_text, i, ['for', 'while', 'do'])
        if m is None:
            break
        kw, kw_start, kw_end = m

        if kw in ('for', 'while'):
            j = kw_end
            while j < n and body_text[j].isspace():
                j += 1
            if j < n and body_text[j] == '(':
                k = _match_balanced(body_text, j, '(', ')')
                if k == -1:
                    i = kw_end
                    continue
                mm = k
                while mm < n and body_text[mm].isspace():
                    mm += 1
                if mm < n and body_text[mm] == '{':
                    p = _match_balanced(body_text, mm, '{', '}')
                    if p == -1:
                        i = kw_end
                        continue
                    loops.append(body_text[mm + 1:p - 1])
                    i = p
                    continue
                else:
                    semi = body_text.find(';', mm)
                    if semi == -1:
                        i = mm
                        continue
                    loops.append(body_text[mm:semi + 1])
                    i = semi + 1
                    continue
            else:
                i = kw_end
                continue

        elif kw == 'do':
            j = kw_end
            while j < n and body_text[j].isspace():
                j += 1
            if j < n and body_text[j] == '{':
                p = _match_balanced(body_text, j, '{', '}')
                if p == -1:
                    i = kw_end
                    continue
                loops.append(body_text[j + 1:p - 1])
                i = p
                continue
            else:
                # `do` without a braced body is unusual; skip past it to
                # avoid an infinite loop.
                i = kw_end
                continue
        else:
            i = kw_end

    return loops


def check_sr1(source_text):
    """SR1: the comparison loop (if any) must not contain a data-dependent
    early exit (`return`, `break`, or `goto`) that would make its trip
    count depend on buffer contents. A fully unrolled implementation
    with no loop construct at all vacuously satisfies this."""
    stripped = _strip_comments_and_strings(source_text)
    body = _find_function_body(stripped)
    if body is None:
        return False, "could not locate a definition of verify() in inputs/mac_verify.cpp"

    loops = _find_loops(body)
    if not loops:
        return True, ""

    for loop_body in loops:
        for token in ('return', 'break', 'goto'):
            if _contains_token(loop_body, token):
                return False, (
                    "a loop inside verify() contains a data-dependent early exit "
                    "('{}'), so its iteration count is not fixed at 16 regardless "
                    "of buffer contents".format(token)
                )
    return True, ""


def check_sr2(source_text):
    """SR2: the final boolean result must not be returned from mid-loop
    partial state; any loop body must not contain a `return`. A fully
    unrolled implementation with no loop construct vacuously satisfies
    this."""
    stripped = _strip_comments_and_strings(source_text)
    body = _find_function_body(stripped)
    if body is None:
        return False, "could not locate a definition of verify() in inputs/mac_verify.cpp"

    loops = _find_loops(body)
    if not loops:
        return True, ""

    for loop_body in loops:
        if _contains_token(loop_body, 'return'):
            return False, (
                "a loop inside verify() contains a 'return', indicating the boolean "
                "result may be produced from partial state before the full 16-byte "
                "scan completes"
            )
    return True, ""


def _split_top_level_commas(text):
    """Split `text` on commas that are not nested inside any
    (), [], or {} delimiter. Returns a list of (possibly empty after
    stripping) parameter substrings."""
    parts = []
    depth_paren = 0
    depth_bracket = 0
    depth_brace = 0
    current = []
    for ch in text:
        if ch == '(':
            depth_paren += 1
        elif ch == ')':
            depth_paren -= 1
        elif ch == '[':
            depth_bracket += 1
        elif ch == ']':
            depth_bracket -= 1
        elif ch == '{':
            depth_brace += 1
        elif ch == '}':
            depth_brace -= 1

        if ch == ',' and depth_paren == 0 and depth_bracket == 0 and depth_brace == 0:
            parts.append(''.join(current))
            current = []
        else:
            current.append(ch)
    parts.append(''.join(current))
    return parts


def _find_verify_paramlist(stripped_text):
    """Locate a `verify(` occurrence in `stripped_text` (declaration or
    definition; comments/strings already blanked) and return the raw
    text between its matching parentheses. Returns None if not found."""
    n = len(stripped_text)
    pos = _find_token(stripped_text, "verify", 0)
    while pos != -1:
        j = pos + len("verify")
        while j < n and stripped_text[j].isspace():
            j += 1
        if j < n and stripped_text[j] == '(':
            k = _match_balanced(stripped_text, j, '(', ')')
            if k != -1:
                return stripped_text[j + 1:k - 1]
        pos = _find_token(stripped_text, "verify", pos + 1)
    return None


# Length/size-typed tokens that would indicate a pointer+length
# redefinition of the interface rather than the pinned fixed-size
# 16-byte-array signature.
#
# NOTE: 'unsigned' was previously (incorrectly) included here. Every
# valid parameter of the pinned signature is itself typed
# 'const unsigned char ...[16]', so a bare 'unsigned' token is a required
# substring of every correct parameter and must never be treated as a
# length/size-type indicator. Removing it does not weaken detection of
# the SR3 mutant's added length parameter, since that mutant is already
# rejected by the exactly-two-parameters check below regardless of which
# type token the extra parameter uses.
_LENGTH_TYPE_TOKENS = (
    "size_t", "ssize_t", "int", "long", "short",
    "uint32_t", "uint64_t", "int32_t", "int64_t", "std::size_t",
)


def check_sr3_interface(header_text):
    """SR3 (interface half): the verify() declaration in mac_verify.h
    must match the pinned two-parameter, fixed-16-byte-array signature
    exactly:

        bool verify(const unsigned char computed_tag[16],
                    const unsigned char received_tag[16]);

    Rejects:
      - any parameter count other than exactly 2,
      - any parameter containing a default value ('='),
      - any variadic parameter ('...'),
      - any additional length/size-typed parameter (e.g. `size_t len = 16`),
      - any parameter that is not an `unsigned char` array-or-pointer type
        (with `const` required somewhere in the parameter).

    Vulnerability anchor: the SR3 mutant redefines the signature as
    `bool verify(const unsigned char* computed_tag, const unsigned char* received_tag, size_t len = 16)`
    -- an extra defaulted length parameter that must be rejected here.
    """
    stripped = _strip_comments_and_strings(header_text)

    paramlist_raw = _find_verify_paramlist(stripped)
    if paramlist_raw is None:
        return False, "could not locate a verify( declaration in inputs/mac_verify.h"

    paramlist_raw = paramlist_raw.strip()
    if paramlist_raw == "" or paramlist_raw == "void":
        return False, "verify() declaration in mac_verify.h takes no parameters; expected exactly 2 fixed-size unsigned-char array parameters"

    params = [p.strip() for p in _split_top_level_commas(paramlist_raw)]
    params = [p for p in params if p != ""]

    if len(params) != 2:
        return False, (
            "verify() declaration in mac_verify.h has {} parameter(s); expected exactly 2 "
            "(a variadic, defaulted-length, or pointer+length redefinition of the pinned "
            "signature is not permitted)".format(len(params))
        )

    for param in params:
        if '=' in param:
            return False, (
                "verify() parameter '{}' contains a default value; the pinned signature "
                "does not permit defaulted/optional parameters (e.g. an added length "
                "parameter with a default)".format(param.strip())
            )
        if '...' in param:
            return False, (
                "verify() parameter '{}' is variadic; the pinned signature does not "
                "permit variadic parameters".format(param.strip())
            )
        for tok in _LENGTH_TYPE_TOKENS:
            if _contains_token(param, tok):
                return False, (
                    "verify() parameter '{}' appears to introduce a length/size-typed "
                    "parameter ('{}'); the pinned signature takes only two fixed-size "
                    "16-byte 'const unsigned char' buffers, with no separate length "
                    "argument".format(param.strip(), tok)
                )
        if not _contains_token(param, "const"):
            return False, (
                "verify() parameter '{}' is missing 'const'; the pinned signature requires "
                "'const unsigned char' buffers".format(param.strip())
            )
        if not _contains_token(param, "unsigned") or not _contains_token(param, "char"):
            return False, (
                "verify() parameter '{}' is not an 'unsigned char' buffer as required by "
                "the pinned signature".format(param.strip())
            )
        # Must be either an array form (contains '[' ... ']') or a
        # pointer form (contains '*'); either is acceptable for a
        # "const unsigned char computed_tag[16]"-equivalent parameter,
        # since arrays decay to pointers in the ABI, but nothing else
        # (e.g. a bare value type, a reference to something else) is.
        if '[' not in param and '*' not in param:
            return False, (
                "verify() parameter '{}' is neither an array nor a pointer form of "
                "'const unsigned char'; the pinned signature requires a fixed-size "
                "16-byte buffer parameter".format(param.strip())
            )

    return True, ""


# Vulnerability in SR3 mutant: "unsigned char* diff = (unsigned char*)malloc(len);"
# and "free(diff);" used for a heap-allocated comparison buffer instead of the
# pinned fixed-size 16-byte stack arrays.
_DYNAMIC_ALLOC_TOKENS = (
    "malloc", "calloc", "realloc", "free", "alloca",
    "new", "std::vector", "std::string",
)


def check_sr3_dynamic_alloc(source_text):
    """SR3 (no-dynamic-allocation half): fail-on-presence scan of
    mac_verify.cpp for dynamic/heap allocation constructs. malloc/calloc/
    realloc/free bypass any operator-new override used by the behavioral
    SR3 counter in the harness, so this static scan is required to catch
    them.

    Vulnerability anchor: the SR3 mutant's
    `unsigned char* diff = (unsigned char*)malloc(len); ... free(diff);`
    heap diff-buffer pattern.
    """
    stripped = _strip_comments_and_strings(source_text)

    for token in _DYNAMIC_ALLOC_TOKENS:
        if _contains_token(stripped, token):
            return False, (
                "inputs/mac_verify.cpp contains a dynamic/heap allocation construct "
                "('{}'); the comparison path must use only fixed-size stack-resident "
                "16-byte buffers, with no malloc/calloc/realloc/free/alloca/new or "
                "variable-length container (std::vector/std::string)".format(token)
            )

    return True, ""