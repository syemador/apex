import glob, os, statistics
import attributability as A, bin_features as bf

base = os.path.dirname(os.path.abspath(A.__file__))
def dirs(root):
    return [d for d in sorted(glob.glob(os.path.join(base, root, '*', 'obj')))
            if os.path.basename(os.path.dirname(d)) not in A.OPT]

# --- exact gcc band stats over 30 ---
objdirs = dirs('corpus')
per_lib, ff = A.index_files(objdirs)
dist = {f for f, fs in ff.items() if len(fs) == 1}
ceils, attrs, gaps = [], [], []
tot_sc = tot_a = 0
cve = None
for lib, funcs in per_lib.items():
    N = len(funcs); sc = sum(1 for *_, s in funcs if s)
    a = sum(1 for _, _, fe, s in funcs if s and (fe & dist))
    tot_sc += sc; tot_a += a
    ceils.append(100*sc/N); attrs.append(100*a/N); gaps.append(100*sc/N - 100*a/N)
    if lib == 'zlib':
        for src, fn, fe, s in funcs:
            if fn == 'inflate' and src == 'inflate.c':
                cve = bool(fe & dist)
mc, ma = statistics.median(ceils), statistics.median(attrs)
print(f"median CEIL = {mc:.2f}%  median attributable = {ma:.2f}%  diff-of-medians = {mc-ma:.2f} pts")
print(f"median per-library gap = {statistics.median(gaps):.2f} pts")
print(f"CVE-2022-37434 (zlib inflate in inflate.c) file-attributable in 30-lib corpus: {cve}")
print(f"file-unique: {tot_a}/{tot_sc} = {100*tot_a/tot_sc:.0f}% of searchable functions are file-unique (attributable)")

# --- tightening: original 15 libraries, 15-lib reference vs 30-corpus reference ---
ORIG15 = {"zlib", "xxHash", "cJSON", "lz4", "yyjson", "parson", "tomlc99", "md4c",
          "http_parser", "inih", "utf8proc", "sds", "cwalk", "mongoose", "lua"}
o15 = [d for d in objdirs if os.path.basename(os.path.dirname(d)) in ORIG15]
p15, f15 = A.index_files(o15)
d15 = {f for f, fs in f15.items() if len(fs) == 1}
ref15, cor15 = [], []
for lib, funcs in p15.items():
    N = len(funcs)
    ref15.append(100*sum(1 for _, _, fe, s in funcs if s and (fe & d15))/N)
    cor15.append(100*sum(1 for _, _, fe, s in funcs if s and (fe & dist))/N)
print(f"tightening (original 15 libs): median attributable "
      f"{statistics.median(ref15):.1f}% (15-lib ref) -> {statistics.median(cor15):.1f}% (30-corpus ref)")

# --- clang band edge (attributable) over 30 ---
cobjdirs = dirs('corpus_clang')
cper, cff = A.index_files(cobjdirs)
cdist = {f for f, fs in cff.items() if len(fs) == 1}
cceils, cattrs = [], []
for lib, funcs in cper.items():
    N = len(funcs); sc = sum(1 for *_, s in funcs if s)
    a = sum(1 for _, _, fe, s in funcs if s and (fe & cdist))
    cceils.append(100*sc/N); cattrs.append(100*a/N)
print(f"clang: median CEIL = {statistics.median(cceils):.1f}%  median attributable edge = {statistics.median(cattrs):.1f}%")
