#!/usr/bin/env bash
set -euo pipefail
python3 - <<'PY'
import re,sys,pathlib
src_cpp=pathlib.Path('src/check_token.cpp')
src_h=pathlib.Path('src/check_token.h')

def mark(ok,r,why=''):
  print(("[PASS] " if ok else "[FAIL] ")+r+("" if ok else ": "+why))

if not src_cpp.exists() or not src_h.exists():
  for r in ['FR-2','FR-3','FR-4','FR-5','SR-1','SR-2','SR-3','SR-4','SR-5']:
    mark(False,r,'missing src/check_token.cpp or src/check_token.h')
  sys.exit(1)

s=src_cpp.read_text(errors='ignore')
h=src_h.read_text(errors='ignore')
# strip comments and strings (simple)
s=re.sub(r'//.*','',s)
s=re.sub(r'/\*.*?\*/','',s,flags=re.S)
s=re.sub(r'"(\\.|[^"\\])*"','""',s)

# FR-5 signature check
sig_ok=bool(re.search(r'ap_uint\s*<\s*1\s*>\s+check_token\s*\(\s*const\s+ap_uint\s*<\s*8\s*>\s+token\s*\[\s*16\s*\]\s*\)',h))
mark(sig_ok,'FR-5','top signature mismatch in header')

# FR-3 non-synth constructs
bad_kw=['new\b','malloc\b','free\b','throw\b','try\b','catch\b']
fr3_ok=not any(re.search(k,s) for k in bad_kw)
mark(fr3_ok,'FR-3','found forbidden construct (new/malloc/free/throw/try/catch)')

# Debug/print leakage (FR-5/SR-4)
dbg=re.search(r'\b(printf|puts|putchar|fprintf|cout|cerr)\b',s)
mark(not bool(dbg),'SR-4','debug/printing call present')
if dbg: mark(False,'FR-5','debug/printing call present')

# Find a for-loop with bound 16
m=re.search(r'for\s*\(([^;]*);([^;]*);([^\)]*)\)',s)
loop_ok=False
body=''
if m:
  cond=m.group(2)
  loop_ok=bool(re.search(r'<\s*16\b',cond) or re.search(r'<=\s*15\b',cond))
  # Extract body by brace matching after this for
  start=s.find('{',m.end())
  if start!=-1:
    depth=0
    for i in range(start,len(s)):
      if s[i]=='{': depth+=1
      elif s[i]=='}':
        depth-=1
        if depth==0:
          body=s[start+1:i]
          break

mark(loop_ok,'FR-4','no constant-trip-count 16-iteration loop found')

# SR-1 / FR-2: no early exit controls inside loop body
viol=[]
for kw in ['return','break','continue']:
  if re.search(r'\b'+kw+r'\b',body): viol.append(kw)
mark(len(viol)==0,'SR-1','loop body contains '+','.join(viol) if viol else '')
mark(len(viol)==0,'FR-2','early-exit construct in loop body' if viol else '')

# SR-2: no secret-dependent branches (conditions referencing expected/diff)
branch_bad=False
for mm in re.finditer(r'\bif\s*\(([^\)]*)\)',s):
  c=mm.group(1)
  if 'expected' in c or re.search(r'\bdiff\b',c):
    branch_bad=True; break
qmark_bad=bool(re.search(r'\?[^:]*\b(expected|diff)\b',s))
mark(not (branch_bad or qmark_bad),'SR-2','secret-derived condition in if/?:')

# SR-3: expected/token indexing must be [i]
idx_bad=False
for name in ['expected','token']:
  for mm in re.finditer(r'\b'+name+r'\s*\[([^\]]+)\]',s):
    inside=re.sub(r'\s+','',mm.group(1))
    if inside!='i' and inside not in [str(k) for k in range(16)]:
      idx_bad=True; break
mark(not idx_bad,'SR-3','non-fixed index used for expected/token access')

# SR-5: no non-const static/global writable state
sr5_bad=bool(re.search(r'\bstatic\b(?!\s+const)',s))
mark(not sr5_bad,'SR-5','non-const static detected')

# Ensure FR-5 is marked fail if SR-4 failed already
if not sig_ok or dbg:
  pass
else:
  # already printed FR-5 for signature; if signature ok and no debug, keep pass
  pass

# Exit nonzero if any FAIL printed
# (recompute quickly)
fails=[]
if not sig_ok or dbg or (not fr3_ok) or (not loop_ok) or viol or branch_bad or qmark_bad or idx_bad or sr5_bad:
  sys.exit(1)
PY
