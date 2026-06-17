#!/usr/bin/env python3
"""Component-level detectability, reconciled with the per-function ceiling.

Per-function attribution needs every function to be attributable; library *presence*
detection needs only one. From the per-function attributable-in-principle set we
compute, with no new measurement, the probability that a present library is
detectable as a function of how many of its functions the binary actually links.

For a library with N functions of which A are file-attributable (carry a feature
distinctive to a single source file across the corpus), and a binary that links k of
them (uniformly, a stand-in for dead-code elimination), presence is detectable iff at
least one linked function is attributable:

    P(detect | k) = 1 - C(N-A, k) / C(N, k)        (hypergeometric, >=1 success)

P(detect | k=1) is the per-function attributable fraction (the gloomy number);
P(detect | k=N) is 1 whenever A>=1. Writes results/COMPONENT_DETECTION.csv.
"""
import glob, os, csv, statistics
from math import comb
import attributability as A

OPT = {'zlib-O0', 'zlib-O3', 'zlib-Os'}
K_REPORT = (1, 2, 5, 10)

def p_detect(N, a, k):
    if a <= 0:
        return 0.0
    if a >= N or k >= N:
        return 1.0
    return 1.0 - comb(N - a, k) / comb(N, k)

def main():
    base = os.path.dirname(os.path.abspath(__file__))
    objdirs = [d for d in sorted(glob.glob(os.path.join(base, 'corpus', '*', 'obj')))
               if os.path.basename(os.path.dirname(d)) not in OPT]
    per, files = A.index_files(objdirs)
    distinctive = {f for f, s in files.items() if len(s) == 1}

    rows = []
    for lib, funcs in per.items():
        N = len(funcs)
        a = sum(1 for _, _, fe, s in funcs if s and (fe & distinctive))
        rows.append((lib, N, a, [p_detect(N, a, k) for k in K_REPORT]))
    rows.sort(key=lambda r: r[2] / r[1])

    hdr = ['library', 'N', 'attributable'] + [f'P_detect_k{k}' for k in K_REPORT] + ['full_link']
    print(f"{'library':12s} {'N':>4s} {'A':>4s} {'per-func':>9s} "
          + ' '.join(f'P(k={k})'.rjust(8) for k in K_REPORT) + f"{'full':>6s}")
    out = []
    for lib, N, a, ps in rows:
        full = 1.0 if a >= 1 else 0.0
        print(f"{lib:12s} {N:4d} {a:4d} {a/N*100:8.1f}% "
              + ' '.join(f'{p*100:7.1f}%' for p in ps) + f"{full*100:5.0f}%")
        out.append([lib, N, a] + [round(p, 4) for p in ps] + [round(full, 4)])

    pf = [r[2] / r[1] for r in rows]
    pk10 = [p_detect(r[1], r[2], 10) for r in rows]
    nfull = sum(1 for r in rows if r[2] >= 1)
    print(f"\nmedian per-function attributability     = {statistics.median(pf)*100:.1f}%")
    print(f"median P(presence | 10 functions linked) = {statistics.median(pk10)*100:.1f}%")
    print(f"presence certain on full link (A>=1)     = {nfull}/{len(rows)} libraries")
    undet = [r[0] for r in rows if r[2] == 0]
    print(f"undetectable even fully linked           = {undet or 'none'}")

    os.makedirs(os.path.join(base, 'results'), exist_ok=True)
    with open(os.path.join(base, 'results', 'COMPONENT_DETECTION.csv'), 'w', newline='') as fh:
        w = csv.writer(fh); w.writerow(hdr); w.writerows(out)

if __name__ == '__main__':
    main()
