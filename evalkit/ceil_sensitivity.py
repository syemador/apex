#!/usr/bin/env python3
"""Sensitivity of the attributability ceiling to the two main extractor knobs:
  (1) the rare-constant magnitude threshold T, and
  (2) whether ubiquitous libc/runtime calls are filtered from the external-call
      signal (the "distinctive external call" criterion).

Reports median CEIL across the 15 libraries for a grid of (T, filter) and the
per-knob spread, so the paper can state which bias dominates.
"""
import os, glob, csv, statistics
import bin_features as bf

OPT = {'zlib-O0', 'zlib-O3', 'zlib-Os'}
THRESHOLDS = [256, 1024, 4096, 16384, 65536]

def main():
    base = os.path.dirname(os.path.abspath(__file__))
    objdirs = [d for d in sorted(glob.glob(os.path.join(base, 'corpus', '*', 'obj')))
               if os.path.basename(os.path.dirname(d)) not in OPT]

    grid = {}   # key -> list of per-library CEIL
    for T in THRESHOLDS:
        grid[(T, 'unfiltered')] = [bf.measure_library(d, T=T, filter_libc=False)['ceil'] for d in objdirs]
        grid[(T, 'filtered')]   = [bf.measure_library(d, T=T, filter_libc=True)['ceil'] for d in objdirs]
        grid[(T, 'strict')]     = [bf.measure_library(d, T=T, filter_libc=True, strict_data=True)['ceil'] for d in objdirs]

    print(f"Corpus median CEIL over the sensitivity grid:\n")
    print(f"{'T (|const| >=)':>14s} {'unfiltered':>11s} {'filtered':>10s} {'+strict data':>13s}")
    print('-' * 52)
    rows = []
    for T in THRESHOLDS:
        mu = statistics.median(grid[(T, 'unfiltered')])
        mf = statistics.median(grid[(T, 'filtered')])
        ms = statistics.median(grid[(T, 'strict')])
        print(f"{T:14d} {mu:10.1f}% {mf:9.1f}% {ms:12.1f}%")
        rows.append((T, mu, mf, ms))

    med_f = [statistics.median(grid[(T, 'filtered')]) for T in THRESHOLDS]
    thr_spread = max(med_f) - min(med_f)
    call_delta = statistics.median(grid[(4096, 'unfiltered')]) - statistics.median(grid[(4096, 'filtered')])
    data_delta = statistics.median(grid[(4096, 'filtered')]) - statistics.median(grid[(4096, 'strict')])
    print('-' * 52)
    print(f"threshold spread (filtered, T 256..65536): {thr_spread:.1f} points")
    print(f"call-filter delta at T=4096               : {call_delta:.1f} points")
    print(f"data-ref delta at T=4096 (named-only)     : {data_delta:.1f} points")

    with open(os.path.join(base, 'SENSITIVITY.csv'), 'w', newline='') as f:
        w = csv.writer(f)
        w.writerow(['threshold', 'median_ceil_unfiltered', 'median_ceil_filtered',
                    'median_ceil_filtered_strictdata'])
        for T, mu, mf, ms in rows:
            w.writerow([T, f"{mu:.1f}", f"{mf:.1f}", f"{ms:.1f}"])
    print("\nwrote SENSITIVITY.csv")

if __name__ == '__main__':
    main()
