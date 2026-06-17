#!/usr/bin/env python3
"""APEX binary-level feature extractor and attributability-ceiling (CEIL) measurer.

Reconstructs the identifiability gate from objdump/nm only (no decompiler):
per function we count three classes of compilation-invariant signal taken from
the compiled object, then a function clears the gate (is searchable) if it
carries at least one of them.

  c = number of distinct rare numeric constants (|v| >= T, not architectural
      noise) plus any catalogued magic constant
  s = number of references into read-only data (string / table use)
  e = number of distinct external calls (callees not defined in this library;
      i.e. PLT-routed in the linked image)

CEIL = (#functions with c>=1 or s>=1 or e>=1) / N.
Magic-constant baseline: a function is attributed iff it embeds a catalogued
globally-unique magic; precision is 1.0 by construction, recall = hits / N,
F1 = 2R / (1+R).
"""
import os, re, sys, json, glob, subprocess
from collections import defaultdict

# --- catalogue of globally-unique magic constants (for the baseline and gate) ---
MAGIC = {
    # CRC-32 polynomials
    0xEDB88320, 0x04C11DB7, 0x82F63B78, 0x1EDC6F41,
    # Adler-32 modulus (largest prime < 2^16)
    65521,
    # xxHash 32-bit primes
    0x9E3779B1, 0x85EBCA77, 0xC2B2AE3D, 0x27D4EB2F, 0x165667B1,
    # xxHash 64-bit primes
    0x9E3779B185EBCA87, 0xC2B2AE3D27D4EB4F, 0x165667B19E3779F9,
    0x85EBCA77C2B2AE63, 0x27D4EB2F165667C5,
    # XXH3 golden-ratio mixer
    0x9E3779B97F4A7C15,
    # LZ4 frame / legacy / skippable magics
    0x184D2204, 0x184C2102, 0x184D2A50,
}

# --- ubiquitous / architectural immediates to drop from "rare constants" ---
BLOCKLIST = {
    0xffffffff, 0x7fffffff, 0x80000000,
    0xffffffffffffffff, 0x7fffffffffffffff, 0x8000000000000000,
    0xfffffffe, 0xfffffffd, 0x100000000,
    0xff, 0xffff, 0xffffff, 0xff00, 0xffff0000, 0x0000ff00, 0xff000000,
    0x00ff00ff, 0xff00ff00, 0x00ffff00, 0xffff00ff,
    # 32-bit signed/unsigned division reciprocals emitted by gcc
    0x55555555, 0x55555556, 0xaaaaaaaa, 0xaaaaaaab, 0xcccccccc, 0xcccccccd,
    0x66666666, 0x66666667, 0x33333333, 0x33333334, 0x24924925, 0x92492493,
    0x49249249, 0x38e38e39, 0x8e38e38f, 0x2e8ba2e9, 0xb60b60b7, 0xe38e38e4,
    0x6db6db6d, 0x6db6db6e, 0x88888889, 0x11111111, 0x10842108, 0x42108421,
    # 64-bit division reciprocals
    0xaaaaaaaaaaaaaaab, 0xcccccccccccccccd, 0x5555555555555556,
    0x8888888888888889, 0x2492492492492493, 0x6db6db6db6db6db7,
}

RODATA_SECTIONS = ('.rodata', '.data.rel.ro')   # prefixes
CALL_MNEMONICS = ('call', 'callq', 'jmp', 'jmpq')

# common libc/runtime callees treated as non-distinctive; filtered out of e in
# the canonical measurement (the "distinctive external call" criterion) and the
# subject of the sensitivity sweep
LIBC_COMMON = {
    'malloc', 'free', 'calloc', 'realloc', 'memcpy', 'memmove', 'memset',
    'memcmp', 'memchr', 'memrchr', 'strlen', 'strnlen', 'strcmp', 'strncmp',
    'strcasecmp', 'strncasecmp', 'strcpy', 'strncpy', 'strcat', 'strncat',
    'strchr', 'strrchr', 'strstr', 'strdup', 'strndup', 'strpbrk', 'strspn',
    'strcspn', 'strtok', 'strtol', 'strtoul', 'strtoll', 'strtoull', 'strtod',
    'strtof', 'atoi', 'atol', 'atof', 'labs', 'llabs', 'abs',
    'printf', 'fprintf', 'sprintf', 'snprintf', 'vsnprintf', 'vfprintf',
    'puts', 'fputs', 'fputc', 'putchar', 'fgets', 'fgetc',
    'fwrite', 'fread', 'fopen', 'fclose', 'fflush', 'fseek', 'ftell',
    'abort', 'exit', '_exit', '__assert_fail', '__stack_chk_fail',
    '__stack_chk_guard', 'qsort', 'bsearch', '__errno_location', 'getenv',
    'tolower', 'toupper', 'isalpha', 'isalnum', 'isdigit', 'isspace', 'isupper',
    'islower', 'isxdigit', 'ispunct', 'iscntrl', 'isprint', 'isgraph',
    '__ctype_tolower_loc', '__ctype_toupper_loc', '__ctype_b_loc',
    '__memcpy_chk', '__memset_chk', '__memmove_chk', '__sprintf_chk',
    '__snprintf_chk', '__strcpy_chk', '__strncpy_chk', '__strcat_chk',
    '__vsnprintf_chk', '__longjmp_chk',
}

def signed_magnitude(v):
    """Distance from 0 modulo 2^64, so small negatives (e.g. 0xfff...ff = -1) read small."""
    if v == 0:
        return 0
    return min(v, (1 << 64) - v)

def is_rare_constant(v, T):
    if v in MAGIC:
        return True
    if v in BLOCKLIST:
        return False
    return signed_magnitude(v) >= T

def object_symbol_sections(obj):
    """name -> section, from objdump -t (to spot read-only data symbols)."""
    out = subprocess.run(['objdump', '-t', obj], capture_output=True, text=True).stdout
    sec = {}
    for line in out.splitlines():
        # columns: value flags section ... name   (section is field index varies)
        parts = line.split()
        if len(parts) < 5:
            continue
        # the section is the token after the flag group; locate a token that looks like a section
        name = parts[-1]
        for tok in parts:
            if tok.startswith('.'):
                sec[name] = tok
                break
    return sec

FUNC_HDR = re.compile(r'^[0-9a-fA-F]+ <([^>]+)>:$')
INSN = re.compile(r'^\s+[0-9a-fA-F]+:\t(\S+)\s*(.*)$')
IMM = re.compile(r'\$0x([0-9a-fA-F]+)')
RELOC = re.compile(r'R_X86_64_(\S+)\s+(\S+)')
ADDEND = re.compile(r'([+-])0x([0-9a-fA-F]+)')
PCREL = ('PC32', 'PLT32', 'GOTPCREL', 'GOTPCRELX', 'REX_GOTPCRELX')

def _section_bytes(obj, sec):
    """Return the bytes of a section (indexed from 0), via objdump -s; {} -> empty."""
    out = subprocess.run(['objdump', '-s', '-j', sec, obj], capture_output=True, text=True).stdout
    buf = bytearray()
    for line in out.splitlines():
        m = re.match(r'^ ([0-9a-f]+) ((?:[0-9a-f]{2,8} ?){1,4})', line)
        if not m:
            continue
        off = int(m.group(1), 16)
        b = bytes.fromhex(m.group(2).replace(' ', ''))
        if len(buf) < off + len(b):
            buf.extend(b'\x00' * (off + len(b) - len(buf)))
        buf[off:off + len(b)] = b
    return bytes(buf)

def _data_fingerprint(data, target, rtype):
    """Content fingerprint of the read-only object a reference points at. Jump tables
    and relocated data read as zeros in the object and so collapse to a common,
    non-distinctive fingerprint; real const tables fingerprint to distinctive bytes."""
    if not data:
        return None
    m = ADDEND.search(target)
    addend = (int(m.group(2), 16) * (-1 if m.group(1) == '-' else 1)) if m else 0
    off = addend + (4 if rtype in PCREL else 0)
    if 0 <= off < len(data):
        import hashlib
        return hashlib.md5(data[off:off + 24]).hexdigest()[:12]
    return None

def analyze_object(obj, defined_funcs, T, filter_libc, want_data=False):
    sym_sec = object_symbol_sections(obj)
    rodata = _section_bytes(obj, '.rodata') if want_data else b''
    txt = subprocess.run(['objdump', '-dr', '--no-show-raw-insn', obj],
                         capture_output=True, text=True).stdout
    feats = {}            # func -> dict(c=set, s=int, e=set, magic=bool)
    cur = None
    last_mn = ''
    for line in txt.splitlines():
        m = FUNC_HDR.match(line)
        if m:
            cur = m.group(1)
            feats.setdefault(cur, {'c': set(), 's': 0, 'e': set(), 'anon': 0, 'tables': set(), 'data': set(), 'magic': False})
            last_mn = ''
            continue
        if cur is None:
            continue
        mi = INSN.match(line)
        if mi:
            last_mn = mi.group(1)
            ops = mi.group(2)
            if last_mn in ('jmp', 'jmpq', 'notrack') and '*%' in ops:
                feats[cur]['anon'] = max(0, feats[cur]['anon'] - 1)   # jump-table base, not data
            for hx in IMM.findall(ops):
                v = int(hx, 16)
                if v in MAGIC:
                    feats[cur]['magic'] = True
                if is_rare_constant(v, T):
                    feats[cur]['c'].add(v)
            continue
        mr = RELOC.search(line)
        if mr:
            rtype = mr.group(1)
            target = mr.group(2)
            base = re.split(r'[-+]0x', target)[0].split('@')[0]
            is_call = last_mn.startswith(CALL_MNEMONICS)
            if base.startswith('.rodata.str'):
                feats[cur]['s'] += 1                      # string literal
            elif base.startswith('.rodata.cst'):
                pass                                      # FP/SIMD constant pool (vectorization), not distinctive
            elif (not base.startswith('.')) and base in sym_sec and \
                 sym_sec[base].startswith(RODATA_SECTIONS):
                feats[cur]['s'] += 1                      # ref to a named const table in rodata
                feats[cur]['tables'].add(base)
            elif base.startswith('.rodata'):
                feats[cur]['anon'] += 1                   # bare anon .rodata: data table unless an indirect jump discounts it
                if want_data:
                    fp = _data_fingerprint(rodata, target, rtype)
                    if fp:
                        feats[cur]['data'].add(fp)
            elif base.startswith('.data.rel.ro'):
                pass                                      # relocated read-only data, not counted
            elif is_call and not base.startswith('.'):
                if base in defined_funcs:
                    pass                                  # intra-library call (not PLT)
                else:
                    if not (filter_libc and base in LIBC_COMMON):
                        feats[cur]['e'].add(base)         # external call (PLT in linked image)
            # other relocs (.data/.bss/extern data) are not searchable signal here
    return feats

def measure_library(objdir, T=4096, filter_libc=True, strict_data=False):
    objs = sorted(glob.glob(os.path.join(objdir, '*.o')))
    # defined function symbols across the whole library (for intra vs external calls)
    defined = set()
    nm = subprocess.run(['nm'] + objs, capture_output=True, text=True).stdout
    for line in nm.splitlines():
        p = line.split()
        if len(p) >= 3 and p[-2] in ('T', 't'):
            defined.add(p[-1])
    # per-function features (keyed by object to avoid static-name collisions)
    inventory = 0
    searchable = 0
    magic_hits = 0
    per_func = []
    for obj in objs:
        feats = analyze_object(obj, defined, T, filter_libc)
        for fn, d in feats.items():
            inventory += 1
            c = len(d['c'])
            s = d['s'] if strict_data else d['s'] + d['anon']
            e = len(d['e'])
            hit = (c >= 1 or s >= 1 or e >= 1)
            searchable += 1 if hit else 0
            magic_hits += 1 if d['magic'] else 0
            per_func.append({'obj': os.path.basename(obj), 'func': fn,
                             'c': c, 's': s, 'e': e, 'searchable': hit, 'magic': d['magic']})
    N = inventory
    ceil = 100.0 * searchable / N if N else 0.0
    rec = 100.0 * magic_hits / N if N else 0.0
    f1 = (2 * rec) / (1 + rec / 100.0) / 100.0 * 100.0 if rec else 0.0
    # F1 with precision 1.0: 2R/(1+R) on fractions
    R = magic_hits / N if N else 0.0
    f1 = (2 * R / (1 + R) * 100.0) if R else 0.0
    return {'N': N, 'searchable': searchable, 'ceil': ceil,
            'magic_hits': magic_hits, 'baseline_recall': rec, 'baseline_f1': f1,
            'per_func': per_func}

if __name__ == '__main__':
    objdir = sys.argv[1]
    T = int(sys.argv[2]) if len(sys.argv) > 2 else 4096
    fl = not (len(sys.argv) > 3 and sys.argv[3] == 'nofilter')
    r = measure_library(objdir, T, fl)
    name = os.path.basename(os.path.dirname(objdir))
    bl = f"{r['baseline_recall']:.1f}% / {r['baseline_f1']:.1f}%" if r['magic_hits'] else "--"
    print(f"{name:14s} N={r['N']:4d}  CEIL={r['ceil']:5.1f}%  baseline(R/F1)= {bl}")
