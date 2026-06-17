#!/usr/bin/env python3
"""Build-axis robustness of the attributability ceiling.

Static linking: a statically linked binary has no PLT, so the external-call
signal disappears. We model this by recomputing CEIL with that signal disabled
(reproducible from the gcc corpus alone).

Compiler: if a clang-built corpus is present at corpus_clang/<lib>/obj (build it
with `CC=clang` -- recompile the same core sources with clang -O2), we compare the
median ceiling against gcc.
"""
import os, glob, subprocess, statistics
import bin_features as bf

OPT = {'zlib-O0', 'zlib-O3', 'zlib-Os'}

def spearman(a, b):
    """Spearman rank correlation with average-rank tie handling (no SciPy needed)."""
    def ranks(x):
        order = sorted(range(len(x)), key=lambda i: x[i])
        r = [0.0] * len(x); i = 0
        while i < len(x):
            j = i
            while j + 1 < len(x) and x[order[j + 1]] == x[order[i]]:
                j += 1
            for k in range(i, j + 1):
                r[order[k]] = (i + j) / 2 + 1
            i = j + 1
        return r
    ra, rb = ranks(a), ranks(b); n = len(a)
    ma, mb = sum(ra) / n, sum(rb) / n
    cov = sum((ra[i] - ma) * (rb[i] - mb) for i in range(n))
    va = sum((x - ma) ** 2 for x in ra) ** 0.5
    vb = sum((x - mb) ** 2 for x in rb) ** 0.5
    return cov / (va * vb) if va and vb else 0.0

def gcc_objdirs(base):
    return [d for d in sorted(glob.glob(os.path.join(base, 'corpus', '*', 'obj')))
            if os.path.basename(os.path.dirname(d)) not in OPT]

def ceil_full_and_static(objdir):
    """Return (CEIL with calls, CEIL with the external-call signal removed)."""
    objs = sorted(glob.glob(os.path.join(objdir, '*.o')))
    defined = set()
    for line in subprocess.run(['nm'] + objs, capture_output=True, text=True).stdout.splitlines():
        p = line.split()
        if len(p) >= 3 and p[-2] in ('T', 't'):
            defined.add(p[-1])
    N = full = static = 0
    for obj in objs:
        for _, fe in bf.analyze_object(obj, defined, 4096, True).items():
            N += 1
            if fe['c'] or fe['s'] or fe['anon'] or fe['e']:
                full += 1
            if fe['c'] or fe['s'] or fe['anon']:          # static: drop external-call signal
                static += 1
    return (100.0 * full / N, 100.0 * static / N) if N else (0.0, 0.0)

def main():
    base = os.path.dirname(os.path.abspath(__file__))
    objdirs = gcc_objdirs(base)

    full, static = [], []
    for d in objdirs:
        f, s = ceil_full_and_static(d)
        full.append(f); static.append(s)
    print("Static-linking axis (no PLT -> external-call signal removed):")
    print(f"  median CEIL dynamic = {statistics.median(full):.1f}%   "
          f"static = {statistics.median(static):.1f}%   "
          f"delta = {statistics.median(full)-statistics.median(static):.1f} pts")

    clang_dirs = sorted(glob.glob(os.path.join(base, 'corpus_clang', '*', 'obj')))
    if clang_dirs:
        g, c = [], []
        print("\nCompiler axis (gcc vs clang):")
        print(f"  {'library':14s} {'gcc CEIL':>9s} {'clang CEIL':>11s}")
        for d in objdirs:
            lib = os.path.basename(os.path.dirname(d))
            cd = os.path.join(base, 'corpus_clang', lib, 'obj')
            if not os.path.isdir(cd):
                continue
            rg = bf.measure_library(d)['ceil']
            rc = bf.measure_library(cd)['ceil']
            g.append(rg); c.append(rc)
            print(f"  {lib:14s} {rg:8.1f}% {rc:10.1f}%")
        print(f"  median gcc = {statistics.median(g):.1f}%   "
              f"clang = {statistics.median(c):.1f}%   "
              f"delta = {statistics.median(c)-statistics.median(g):+.1f} pts")
        print(f"  Spearman rho (gcc vs clang CEIL, {len(g)} libraries) = {spearman(g, c):.2f}")
    else:
        print("\nCompiler axis: build a clang corpus to enable "
              "(recompile the core sources with clang -O2 into corpus_clang/<lib>/obj).")

if __name__ == '__main__':
    main()
