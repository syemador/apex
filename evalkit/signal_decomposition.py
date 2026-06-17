#!/usr/bin/env python3
"""Decompose the ceiling into the marginal contribution of each signal.

CEIL gates on three signals: a rare constant, a distinctive data reference
(string/named table/anonymous table), or a distinctive external call. This script
reports, per library, the share of functions searchable through each signal and the
marginal contribution of each, the drop in CEIL if that signal alone were removed (a
function survives the removal if any other signal still fires). The marginal
separates a signal that is the sole discriminator for a function from one that merely
co-occurs with others. Writes results/SIGNAL_DECOMPOSITION.csv.
"""
import glob, os, csv, statistics
import bin_features as bf

OPT = {'zlib-O0', 'zlib-O3', 'zlib-Os'}
SIGNALS = ('const', 'data', 'call')

def fires(f):
    return {'const': f['c'] >= 1, 'data': f['s'] >= 1, 'call': f['e'] >= 1}

def main():
    base = os.path.dirname(os.path.abspath(__file__))
    libs = [d for d in sorted(glob.glob(os.path.join(base, 'corpus', '*', 'obj')))
            if os.path.basename(os.path.dirname(d)) not in OPT]
    print(f"{'library':12s} {'CEIL':>6s} | "
          + ' '.join(s.rjust(6) for s in SIGNALS) + " | "
          + ' '.join(('-' + s).rjust(7) for s in SIGNALS))
    agg = {s: [] for s in SIGNALS}; marg = {s: [] for s in SIGNALS}
    out = []
    for d in libs:
        lib = os.path.basename(os.path.dirname(d))
        r = bf.measure_library(d); pf = r['per_func']; N = r['N']
        base_ceil = 100.0 * r['searchable'] / N
        share = {s: 100.0 * sum(1 for f in pf if fires(f)[s]) / N for s in SIGNALS}
        drop = {}
        for s in SIGNALS:
            kept = sum(1 for f in pf if any(fires(f)[o] for o in SIGNALS if o != s))
            drop[s] = base_ceil - 100.0 * kept / N
        for s in SIGNALS:
            agg[s].append(share[s]); marg[s].append(drop[s])
        print(f"{lib:12s} {base_ceil:5.1f}% | "
              + ' '.join(f'{share[s]:5.1f}%' for s in SIGNALS) + " | "
              + ' '.join(f'{drop[s]:6.1f}p' for s in SIGNALS))
        out.append([lib, round(base_ceil, 1)]
                   + [round(share[s], 1) for s in SIGNALS]
                   + [round(drop[s], 1) for s in SIGNALS])
    print()
    for s in SIGNALS:
        print(f"median share via {s:5s} = {statistics.median(agg[s]):5.1f}%   "
              f"median marginal = {statistics.median(marg[s]):4.1f} pts")
    os.makedirs(os.path.join(base, 'results'), exist_ok=True)
    hdr = (['library', 'CEIL'] + [f'share_{s}' for s in SIGNALS]
           + [f'marginal_{s}' for s in SIGNALS])
    with open(os.path.join(base, 'results', 'SIGNAL_DECOMPOSITION.csv'), 'w', newline='') as fh:
        w = csv.writer(fh); w.writerow(hdr); w.writerows(out)

if __name__ == '__main__':
    main()
