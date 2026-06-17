#!/usr/bin/env python3
"""Roll up the canonical attributability-ceiling measurement across the corpus.

Writes CEILING_TABLE.csv and prints the per-library table plus the headline
statistics (range, median, count below 40%) used in the paper.
"""
import os, glob, csv, statistics
import bin_features as bf

OPT = {'zlib-O0', 'zlib-O3', 'zlib-Os'}   # optimization-sweep builds, reported separately

def fmt_bl(r):
    return f"{r['baseline_recall']:.1f}% / {r['baseline_f1']:.1f}%" if r['magic_hits'] else "--"

def main():
    base = os.path.dirname(os.path.abspath(__file__))
    rows = []
    for objdir in sorted(glob.glob(os.path.join(base, 'corpus', '*', 'obj'))):
        name = os.path.basename(os.path.dirname(objdir))
        r = bf.measure_library(objdir)          # canonical: T=4096, distinctive-call filtering on
        rows.append((name, r))

    main_libs = [(n, r) for n, r in rows if n not in OPT]
    main_libs.sort(key=lambda nr: nr[1]['ceil'])
    opt_libs = [(n, r) for n, r in rows if n in OPT]

    print(f"{'library (-O2)':16s} {'N':>5s} {'CEIL':>7s}  {'baseline R / F1':>18s}")
    print('-' * 52)
    for n, r in main_libs:
        print(f"{n:16s} {r['N']:5d} {r['ceil']:6.1f}%  {fmt_bl(r):>18s}")
    print('-' * 52)
    for n, r in sorted(opt_libs):
        print(f"{n:16s} {r['N']:5d} {r['ceil']:6.1f}%  {fmt_bl(r):>18s}")

    ceils = [r['ceil'] for _, r in main_libs]
    med = statistics.median(ceils)
    below40 = sum(1 for c in ceils if c < 40)
    lo, hi = min(ceils), max(ceils)
    # searchable counts for the zlib optimization story
    z = {n: r for n, r in rows if n.startswith('zlib')}
    print()
    print(f"{len(main_libs)}-library range : {lo:.1f}% to {hi:.1f}%   median {med:.1f}%   below-40%: {below40}/{len(main_libs)}")
    if 'zlib' in z:
        order = ['zlib-O0', 'zlib', 'zlib-O3', 'zlib-Os']
        sc = ", ".join(f"{lvl.replace('zlib','').strip('-') or 'O2'}={z[lvl]['searchable']}"
                       for lvl in order if lvl in z)
        inv = ", ".join(f"{lvl.replace('zlib','').strip('-') or 'O2'} N={z[lvl]['N']}"
                        for lvl in order if lvl in z)
        print(f"zlib searchable count by opt: {sc}")
        print(f"zlib inventory by opt       : {inv}")

    with open(os.path.join(base, 'CEILING_TABLE.csv'), 'w', newline='') as f:
        w = csv.writer(f)
        w.writerow(['library', 'build', 'N', 'CEIL_pct', 'baseline_recall_pct',
                    'baseline_f1_pct', 'searchable', 'magic_hits'])
        for n, r in main_libs + sorted(opt_libs):
            build = '-O2' if n not in OPT else '-' + n.split('-')[1]
            lib = 'zlib' if n in OPT else n
            w.writerow([lib, build, r['N'], f"{r['ceil']:.1f}",
                        f"{r['baseline_recall']:.1f}" if r['magic_hits'] else '',
                        f"{r['baseline_f1']:.1f}" if r['magic_hits'] else '',
                        r['searchable'], r['magic_hits']])
    print("\nwrote CEILING_TABLE.csv")

if __name__ == '__main__':
    main()
