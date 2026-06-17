# APEX: the source-attribution ceiling for stripped-binary functions

APEX (**A**ttributability **P**rofiling of stripped **EX**ecutables) is a
provenance-controlled measurement of how many functions in a stripped binary
can be attributed back to their source file *at all* — before any particular
matching method is applied. It is a measurement study, not a tool: it puts an
**upper bound** on the recall of any lexical-feature retrieval method and shows
how far that bound sits above what is actually attributable once feature
uniqueness is taken into account.

The headline metric is **CEIL** (Ceiling Estimation for Inferred Lineage): the
fraction of a binary's functions that clear an identifiability gate built from
compilation-invariant signal (rare constants, read-only string/table
references, and external calls).

## Headline results

Measured on **30 real C libraries** compiled with **gcc 13.3.0 `-O2`**
(2566 functions; zlib additionally built at `-O0/-O3/-Os`):

| Quantity | Value |
| --- | --- |
| CEIL range (`-O2`) | 0.0% (base64) to 84.0% (qrcodegen) |
| CEIL at `-O3` (zlib) | 72.4% |
| Median CEIL | **32.5%** (20 of 30 libraries below 40%) |
| Median attributable-in-principle | **21.2%** |
| Ceiling-vs-attributable gap (difference of medians) | **11.4 points** |
| Searchable functions that are file-unique | 63% |
| Robustness: static linking | CEIL −5.5 points (32.5% to 27.0%) |
| Robustness: clang vs gcc | CEIL +12.0 points (32.5% to 44.5%), Spearman rho = 0.84 |
| Cross-extractor agreement | exact on all 2566 functions (mean abs. diff 0.00) |

A magic-constant lookup baseline (near-100% precision) recovers most searchable
signal where it is constant-dominated (xxHash, 81% of the ceiling) but little
otherwise (zlib, 11%). A worked retrieval-and-verification example on a separate
zlib-1.2.11 binary attributes 9 of 107 functions (precision 28.1%, recall 8.4%,
F1 12.9%), below both bounds and the baseline.

Per-library numbers are in [`evalkit/CEILING_TABLE.csv`](evalkit/CEILING_TABLE.csv)
and [`evalkit/ATTRIBUTABILITY.csv`](evalkit/ATTRIBUTABILITY.csv); library
provenance is in [`evalkit/corpus_manifest.csv`](evalkit/corpus_manifest.csv).

## Repository layout

```
apex/
  README.md                 this file
  LICENSE                   MIT (harness); corpus libraries keep their own licenses
  requirements.txt          Python dependencies
  reproduce.sh              one-command end-to-end reproduction
  paper/
    main.tex                the paper (IEEEtran, camera-ready, 6 pages)
    references.bib          bibliography
    IEEEtran.cls/.bst       class and bibliography style (for a standalone build)
    apex_paper.pdf          rendered paper
  evalkit/
    bin_features.py         primary extractor (objdump + nm): per-function features and the gate
    summarize.py            -> CEILING_TABLE.csv      (CEIL per library/build)
    attributability.py      -> ATTRIBUTABILITY.csv    (intra-corpus feature uniqueness)
    signal_decomposition.py -> results/SIGNAL_DECOMPOSITION.csv (constant/data/call marginals)
    component_detection.py  -> results/COMPONENT_DETECTION.csv  (presence detectability)
    ceil_sensitivity.py     -> SENSITIVITY.csv        (gate-threshold sensitivity)
    robustness.py           static-linking and gcc-vs-clang axes
    validate_capstone.py    second extractor (Capstone + pyelftools); cross-extractor check
    apex_stats.py           aggregate statistics reported in the paper
    build_all.sh            clone + gcc-build 15 original libraries (+ zlib opt sweep) -> corpus/
    build_ext.sh            clone + gcc-build the external library set -> corpus_ext/
    build_new.sh            add 6 new libraries and promote 9 external into corpus/
    build_clang.sh          clang mirror of all 30 libraries -> corpus_clang/
    corpus_manifest.csv     library, type, source repo, ref, and measured CEIL/attributable
    *.csv, results/*.csv    the measured results (committed)
```

Cloned sources (`evalkit/src/`, `ext_src/`, `new_src/`) and compiled corpora
(`corpus/`, `corpus_ext/`, `corpus_clang/`) are git-ignored: they are fetched
and rebuilt by the scripts and are not vendored. The committed CSVs let you
inspect every reported number without rebuilding.

## Toolchain

The measurements were produced with gcc 13.3.0, clang 18.1.3, binutils 2.42
(`objdump`, `nm`), Python 3.12, capstone 5.0.7, and pyelftools. The primary
extractor depends only on `objdump` and `nm`; the independent cross-check uses
capstone and pyelftools.

## Reproduce

```bash
pip install -r requirements.txt
./reproduce.sh
```

Or step by step (from `evalkit/`):

```bash
bash build_all.sh      # 15 original libraries (gcc -O2) + zlib -O0/-O3/-Os -> corpus/
bash build_ext.sh      # external library set (gcc -O2)                     -> corpus_ext/
bash build_new.sh      # 6 new libraries + promote 9 external               -> corpus/
bash build_clang.sh    # clang mirror of all 30 (needs the clones above)    -> corpus_clang/

python3 summarize.py            # CEILING_TABLE.csv
python3 attributability.py      # ATTRIBUTABILITY.csv
python3 signal_decomposition.py # results/SIGNAL_DECOMPOSITION.csv
python3 component_detection.py  # results/COMPONENT_DETECTION.csv
python3 ceil_sensitivity.py     # SENSITIVITY.csv
python3 robustness.py           # static-linking and gcc-vs-clang axes
python3 validate_capstone.py    # cross-extractor agreement
python3 apex_stats.py           # aggregate statistics
```

The build scripts use shallow clones and record per-library provenance
(commit, flags, file list) under `corpus/<lib>/provenance.json`. `build_clang.sh`
reuses the sources cloned by the gcc scripts, so run those first.

## Build the paper

```bash
cd paper
pdflatex main.tex
bibtex main
pdflatex main.tex
pdflatex main.tex
```

## Citation

> S. S. Ador and S. S. Antar, "APEX: A Provenance-Controlled, Multi-Library
> Measurement of the Source-Attribution Ceiling for Stripped-Binary Functions."

```bibtex
@inproceedings{apex,
  author    = {Syem Shibly Ador and Siam Shibly Antar},
  title     = {{APEX}: A Provenance-Controlled, Multi-Library Measurement of the
               Source-Attribution Ceiling for Stripped-Binary Functions},
  booktitle = {TODO: venue},
  year      = {2026}
}
```

## License

The harness, scripts, and paper in this repository are released under the MIT
License (see `LICENSE`). The corpus libraries are fetched from their upstream
repositories at build time and remain under their own permissive licenses; none
is redistributed here.

---

**Before publishing this repository:** the paper's reproducibility section
(`paper/main.tex`) and the citation block above still contain `TODO`/`REPLACE-ME`
placeholders for the public repository URL and the archival DOI. Fill the repo
URL once this repository is pushed, and mint a DOI by linking the repository to
Zenodo and cutting a tagged release (Zenodo archives the release and issues a
version DOI; cite that DOI for the submitted version).
