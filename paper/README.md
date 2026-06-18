# APEX: Attributability Profiling of stripped EXecutables

**Measurement harness and reference implementation** for the paper:
*APEX: A Provenance-Controlled, Multi-Library Measurement of the Source-Attribution Ceiling for Stripped-Binary Functions*

![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)
![Python](https://img.shields.io/badge/python-3.12+-blue.svg)
![Libraries](https://img.shields.io/badge/corpus-30%20libraries-green.svg)
![Functions](https://img.shields.io/badge/functions-2566-green.svg)

---

## Overview

**APEX** measures how many functions in a stripped binary can be attributed back to their source file *at all*, before any particular matching method is applied. It is a measurement study, not a tool: rather than proposing yet another matcher, it puts a **method-independent upper bound** on the recall of any lexical-feature retrieval method and shows how far that bound sits above what is actually attributable once feature uniqueness is taken into account.

The headline metric is **CEIL** (Ceiling Estimation for Inferred Lineage): the fraction of a binary's functions that clear an identifiability gate built from compilation-invariant signal:

* **Rare numeric constants** (after removing common and architectural values, above a magnitude threshold, plus a catalog of known magic constants)
* **Read-only data references** (a proxy for string and table use)
* **External calls** (resolved through the PLT)

A function clears the gate if it carries at least one such discriminator. CEIL is the fraction that clear it; the **attributable-in-principle** fraction tightens CEIL by intra-corpus feature uniqueness, and the gap between the two is the central finding.

The harness builds a provenance-controlled corpus from upstream sources, compiles it under controlled flags, runs the extractor, and reproduces every number in the paper, including a fully independent second extractor that cross-checks the first.

---

## Key Results (as measured in this repo)

Measured on **30 real C libraries** compiled with **gcc 13.3.0 `-O2`** (2566 functions; zlib additionally built at `-O0/-O3/-Os`):

| Quantity | Value |
|---|---|
| CEIL range (`-O2`) | 0.0% (base64) to 84.0% (qrcodegen) |
| CEIL at `-O3` (zlib) | 72.4% |
| Median CEIL | **32.5%** (20 of 30 libraries below 40%) |
| Median attributable-in-principle | **21.2%** |
| Ceiling-vs-attributable gap (difference of medians) | **11.4 points** |
| Searchable functions that are file-unique | 63% (526 / 831) |
| Robustness: static linking | CEIL −5.5 points (32.5% → 27.0%) |
| Robustness: clang vs gcc | CEIL +12.0 points (32.5% → 44.5%), Spearman ρ = 0.83 |
| Cross-extractor agreement | exact on all 2566 functions (mean abs. diff 0.00) |

* **A diagnostic baseline.** A magic-constant lookup (near-100% precision) recovers most searchable signal where it is constant-dominated (xxHash, 81% of the ceiling) but little otherwise (zlib, 11%); it marks where a discriminating method has room.
* **A worked example at the floor.** A tiered retrieval-and-verification pipeline (the Source Recovery Tool) on a separate zlib-1.2.11 binary attributes 9 of 107 functions (precision 28.1%, recall 8.4%, F1 12.9%), below both bounds and the baseline.

Per-library numbers are in `evalkit/CEILING_TABLE.csv` and `evalkit/ATTRIBUTABILITY.csv`; library provenance is in `evalkit/corpus_manifest.csv`.

---

## Repository Structure

```
apex/
├── README.md                          # This file
├── LICENSE                            # MIT (harness); corpus libraries keep their own licenses
├── requirements.txt                   # Python dependencies
├── reproduce.sh                       # One-command end-to-end reproduction
│
├── paper/                             # The paper (IEEEtran, camera-ready, 6 pages)
│   ├── main.tex                       # Source
│   ├── references.bib                 # Bibliography (24 references)
│   ├── IEEEtran.cls                   # Document class (for a standalone build)
│   ├── IEEEtran.bst                   # Bibliography style
│   └── apex_paper.pdf                 # Rendered paper
│
└── evalkit/                           # Measurement harness
    ├── bin_features.py                # Primary extractor (objdump + nm): per-function features and the gate
    ├── summarize.py                   #  -> CEILING_TABLE.csv        (CEIL per library/build)
    ├── attributability.py             #  -> ATTRIBUTABILITY.csv      (intra-corpus feature uniqueness)
    ├── signal_decomposition.py        #  -> results/SIGNAL_DECOMPOSITION.csv (constant/data/call marginals)
    ├── component_detection.py         #  -> results/COMPONENT_DETECTION.csv  (presence detectability)
    ├── ceil_sensitivity.py            #  -> SENSITIVITY.csv          (gate-threshold sensitivity)
    ├── robustness.py                  # Static-linking and gcc-vs-clang axes (+ Spearman rho)
    ├── validate_capstone.py           # Independent second extractor (Capstone + pyelftools); cross-check
    ├── apex_stats.py                  # Aggregate statistics reported in the paper
    │
    ├── build_all.sh                   # Clone + gcc-build 15 original libraries (+ zlib opt sweep) -> corpus/
    ├── build_ext.sh                   # Clone + gcc-build the external library set -> corpus_ext/
    ├── build_new.sh                   # Add 6 new libraries and promote 9 external into corpus/
    ├── build_clang.sh                 # Clang mirror of all 30 libraries -> corpus_clang/
    │
    ├── corpus_manifest.csv            # library, type, source repo, ref, and measured CEIL/attributable
    ├── CEILING_TABLE.csv              # Committed results (CEIL per library/build)
    ├── ATTRIBUTABILITY.csv            # Committed results (attributable-in-principle)
    ├── SENSITIVITY.csv                # Committed results (gate sensitivity)
    └── results/
        ├── COMPONENT_DETECTION.csv    # Committed results (presence detectability)
        └── SIGNAL_DECOMPOSITION.csv   # Committed results (signal marginals)
```

Cloned sources (`evalkit/src/`, `ext_src/`, `new_src/`) and compiled corpora (`corpus/`, `corpus_ext/`, `corpus_clang/`) are git-ignored: the build scripts fetch and rebuild them, and nothing third-party is vendored. The committed CSVs let you inspect every reported number without rebuilding.

---

## Setup

### Prerequisites

* **Python 3.12** (the harness uses only the standard library plus the two packages below)
* **gcc 13.3.0**: corpus ground-truth builds
* **clang 18.1.3**: compiler-axis / robustness builds
* **binutils 2.42**: provides `objdump` and `nm`, the primary extractor
* **git**: shallow clones of the corpus libraries

The exact toolchain versions above are the ones the paper was measured with. The primary extractor depends only on `objdump` and `nm`; the independent cross-check uses Capstone and pyelftools.

### Install

```bash
python -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

`requirements.txt` pulls `capstone` and `pyelftools` (used by the second extractor). The compilers and binutils are system tools; install them via your package manager rather than pip.

---

## Quick Start

### 1) Inspect the measured results (no build, instant)

Every number in the paper is already committed as a CSV, so you can read the results without compiling anything:

```bash
cat evalkit/CEILING_TABLE.csv          # CEIL per library and build
cat evalkit/ATTRIBUTABILITY.csv        # attributable-in-principle per library
cat evalkit/corpus_manifest.csv        # source repo + pinned ref + measured values
```

### 2) Full reproduction (fetches and compiles ~30 libraries)

```bash
pip install -r requirements.txt
./reproduce.sh
```

`reproduce.sh` clones and builds the gcc and clang corpora, then runs every analysis script, regenerating all CSVs in `evalkit/` and `evalkit/results/`. Runtime is dominated by cloning and compiling the corpus.

### 3) Step-by-step (from `evalkit/`)

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
python3 robustness.py           # static-linking and gcc-vs-clang axes, Spearman rho
python3 validate_capstone.py    # cross-extractor agreement
python3 apex_stats.py           # aggregate statistics
```

The build scripts use shallow clones and record per-library provenance (commit, flags, file list) under `corpus/<lib>/provenance.json`. `build_clang.sh` reuses the sources cloned by the gcc scripts, so run those first.

### 4) Build the paper

```bash
cd paper
pdflatex main.tex
bibtex main
pdflatex main.tex
pdflatex main.tex
```

---

## Reproduction Methodology

The repository is self-reproducing: starting from a clean clone with no sources or build outputs, the four build scripts fetch every library from upstream and the analysis scripts regenerate every committed result.

| Stage | What it checks | Result |
|---|---|---|
| **1. Inspect committed CSVs** | Read every reported number without building | 5 result CSVs, 30 libraries + 3 zlib variants |
| **2. Clean-room rebuild** (`reproduce.sh`) | Fetch and compile all 30 libraries from scratch, re-run all analyses | All 5 CSVs regenerate **byte-identical** to the committed copies |
| **3. Cross-extractor check** (`validate_capstone.py`) | A second extractor (Capstone + pyelftools) sharing only the gate | Agrees with objdump on all 2566 functions (mean abs. diff 0.00) |

Headline numbers emitted by the scripts (`apex_stats.py` and `robustness.py`):

```
Corpus:                     30 libraries, gcc 13.3.0 -O2, 2566 functions
Median CEIL:                32.5%   (20 of 30 below 40%)
Median attributable:        21.2%
Difference of medians:      11.4 points
Per-library gap (median):   8.0 points
File-unique fraction:       526 / 831 = 63% of searchable functions
Static-linking axis:        CEIL -5.5 points (32.5% -> 27.0%)
Compiler axis (clang):      CEIL +12.0 points (32.5% -> 44.5%), Spearman rho = 0.83
Cross-extractor agreement:  mean |objdump - capstone| = 0.00 points over 2566 functions
```

The 15 original libraries are cloned at pinned release tags and reproduce exactly. The 9 external and 6 new libraries are cloned at their default branch; they reproduce today but can be pinned to the commits in their `provenance.json` files for indefinite reproducibility.

---

## Included Outputs

The committed results under `evalkit/` are the exact artifacts the paper reports:

* `CEILING_TABLE.csv`: CEIL, function count, searchable count, magic-constant hits, and baseline recall/F1 per library and build (33 rows: 30 libraries + 3 zlib optimization variants)
* `ATTRIBUTABILITY.csv`: attributable-in-principle per library under both a 15-library and the full 30-library reference set
* `SENSITIVITY.csv`: how the median ceiling moves as the gate threshold, call filter, and data-reference rule vary
* `results/COMPONENT_DETECTION.csv`: presence detectability per library on a full link
* `results/SIGNAL_DECOMPOSITION.csv`: marginal contribution of constants, data references, and calls
* `corpus_manifest.csv`: per-library type, upstream repository, pinned ref, and the measured CEIL and attributable fraction

Build outputs (`corpus/`, `corpus_clang/`) and cloned sources are git-ignored and regenerated on demand.

---

## Known Limitations

These are stated plainly so reviewers can calibrate expectations:

* **The bound is on lexical-feature retrieval.** CEIL upper-bounds methods keyed on constants, strings, and call names. A method keyed on the call graph or on deeper structure can attribute a feature-less function from confirmed neighbors and so sits below this line, still under true attributability.
* **CEIL is an upper bound, and the gap can only widen.** Attributability is measured within a controlled corpus. Against all public code the file-uniqueness gap can only grow, not shrink, by an amount this study does not measure.
* **The realizable rung is future work.** The reported band runs from a measured upper bound to a single disclaimed worked example, with nothing measured between. A controlled retrieve-and-verify experiment over a fixed candidate set (separating retrieval-limited from verification-limited loss) is the natural next measurement.
* **The extractor is deliberately conservative.** The objdump-based extractor only counts references it can resolve and only treats read-only data as a string/table signal. base64's ceiling of 0.0%, for example, reflects an alphabet table declared mutable, so it lands in writable `.data` that the read-only proxy excludes. Conservative misses push the measured fraction down, never up.
* **Default-branch clones for 15 libraries.** The 9 external and 6 new libraries clone at their default branch rather than a pinned tag. They reproduce today; pin them to their recorded commits before relying on the artifact long-term.

---

## Citation

```bibtex
@inproceedings{apex,
  author    = {Syem Shibly Ador and Siam Shibly Antar},
  title     = {{APEX}: A Provenance-Controlled, Multi-Library Measurement of the
               Source-Attribution Ceiling for Stripped-Binary Functions},
  booktitle = {TODO: venue},
  year      = {2026}
}
```

---

## License

The harness, scripts, and paper in this repository are released under the **MIT License** (see `LICENSE`). The corpus libraries are fetched from their upstream repositories at build time and remain under their own permissive licenses (zlib, MIT, BSD, public-domain, and similar); none is redistributed here.

---

> **Note:** the citation block above still lists `TODO: venue` for the `booktitle`; fill it once the paper is placed. The artifact lives at https://github.com/syemador/apex, and each tagged GitHub release is a citable snapshot of the harness, results, and paper.
