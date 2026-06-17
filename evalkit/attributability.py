#!/usr/bin/env python3
"""From searchable to attributable: the intra-corpus uniqueness rung.

CEIL counts functions that carry any discriminator (searchable). But a
discriminator only enables *attribution* if it is globally distinctive: a
moderately rare constant or a generic string that recurs across many source
files cannot pin a function to its origin. This script measures, across the
fifteen libraries, the fraction of searchable functions whose identifiable
features (rare constant values, named const-table symbols, distinctive external
callees) are distinctive enough to identify a single source file.

A feature is *distinctive* if, across the entire corpus, every function carrying
it belongs to one source file (by basename; vendored copies of the same file
count as that file). A function is *attributable-in-principle* if it carries at
least one distinctive feature. This is a strict lower bound on attributability:
functions identifiable only through anonymous read-only data (whose content this
objdump-level extractor does not resolve) are conservatively excluded.

Result: searchable (CEIL) >= attributable-in-principle, a measured band.
"""
import os, glob, csv, subprocess, statistics
from collections import defaultdict
import bin_features as bf

OPT = {'zlib-O0', 'zlib-O3', 'zlib-Os'}

def library_functions(objdir, T=4096):
    """Yield (source_file_basename, func_name, feature_set) per function, canonical settings."""
    objs = sorted(glob.glob(os.path.join(objdir, '*.o')))
    defined = set()
    for line in subprocess.run(['nm'] + objs, capture_output=True, text=True).stdout.splitlines():
        p = line.split()
        if len(p) >= 3 and p[-2] in ('T', 't'):
            defined.add(p[-1])
    for obj in objs:
        src = os.path.basename(obj)[:-2] + '.c'           # object -> source file
        for fn, fe in bf.analyze_object(obj, defined, T, True, want_data=True).items():
            searchable = bool(fe['c'] or fe['s'] or fe['anon'] or fe['e'])
            feats = ({('const', v) for v in fe['c']} |
                     {('call', c) for c in fe['e']} |
                     {('table', t) for t in fe['tables']} |
                     {('data', d) for d in fe['data']})
            yield src, fn, feats, searchable

def index_files(objdirs):
    """feature -> set of source-file basenames carrying it, across the given dirs."""
    from collections import defaultdict
    ff = defaultdict(set)
    per_lib = {}
    for d in objdirs:
        lib = os.path.basename(os.path.dirname(d))
        funcs = list(library_functions(d))
        per_lib[lib] = funcs
        for src, fn, feats, _ in funcs:
            for f in feats:
                ff[f].add(src)
    return per_lib, ff

ORIG15 = {'parson', 'cJSON', 'cwalk', 'tomlc99', 'inih', 'sds', 'yyjson', 'lua',
          'mongoose', 'lz4', 'md4c', 'xxHash', 'http_parser', 'zlib', 'utf8proc'}

def main():
    base = os.path.dirname(os.path.abspath(__file__))
    objdirs = [d for d in sorted(glob.glob(os.path.join(base, 'corpus', '*', 'obj')))
               if os.path.basename(os.path.dirname(d)) not in OPT]
    orig_dirs = [d for d in objdirs if os.path.basename(os.path.dirname(d)) in ORIG15]

    # reference index over the full corpus, and over the original 15-library sub-reference
    per_lib, ff_full = index_files(objdirs)
    _, ff15 = index_files(orig_dirs)

    dist_full = {f for f, files in ff_full.items() if len(files) == 1}
    dist15 = {f for f, files in ff15.items() if len(files) == 1}

    rows = []
    for lib, funcs in per_lib.items():
        N = len(funcs)
        searchable = sum(1 for *_, s in funcs if s)
        a_full = sum(1 for _, _, fe, s in funcs if s and (fe & dist_full))
        a15 = sum(1 for _, _, fe, s in funcs if s and (fe & dist15))
        rows.append((lib, N, 100.0 * searchable / N, 100.0 * a_full / N, 100.0 * a15 / N,
                     searchable, a_full, a15))
    rows.sort(key=lambda r: r[2])

    head = f"{'library':14s} {'N':>5s} {'CEIL':>7s} {'attr(corpus)':>13s}"
    print(head); print('-' * len(head))
    for lib, N, ceil, a_full, a15, *_ in rows:
        print(f"{lib:14s} {N:5d} {ceil:6.1f}% {a_full:12.1f}%")
    print('-' * len(head))
    ceils = [r[2] for r in rows]; afulls = [r[3] for r in rows]
    print(f"median  CEIL={statistics.median(ceils):.1f}%  attributable(full {len(rows)}-lib corpus)"
          f"={statistics.median(afulls):.1f}%  gap={statistics.median(ceils)-statistics.median(afulls):.1f} pts")
    ts = sum(r[5] for r in rows)
    print(f"corpus searchable->attributable: {sum(r[6] for r in rows)}/{ts} = {100*sum(r[6] for r in rows)/ts:.0f}% file-unique")
    # tightening: same original-15 libraries, judged against a 15-lib vs the full corpus reference
    o15 = [r for r in rows if r[0] in ORIG15]
    m15 = statistics.median([r[4] for r in o15]); mfull = statistics.median([r[3] for r in o15])
    print(f"\nTIGHTENING (the original 15 libraries):")
    print(f"  attributable vs 15-lib reference  = {m15:.1f}% (median)")
    print(f"  attributable vs {len(rows)}-lib reference  = {mfull:.1f}% (median)")
    print(f"  doubling the reference lowers it by {m15-mfull:.1f} points; the smaller reference over-counts")
    print(f"  distinctiveness, so the attributable fraction is an upper bound that tightens as the reference grows.")

    with open(os.path.join(base, 'ATTRIBUTABILITY.csv'), 'w', newline='') as f:
        w = csv.writer(f)
        w.writerow(['library', 'N', 'CEIL_searchable_pct', 'attributable_corpus_pct',
                    'attributable_15lib_ref_pct'])
        for lib, N, ceil, a_full, a15, *_ in rows:
            w.writerow([lib, N, f"{ceil:.1f}", f"{a_full:.1f}", f"{a15:.1f}"])
    print("\nwrote ATTRIBUTABILITY.csv")

if __name__ == '__main__':
    main()
