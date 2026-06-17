#!/usr/bin/env bash
# End-to-end reproduction of the APEX measurement.
# Builds the gcc and clang corpora from upstream sources, then runs every
# analysis script. Regenerates all CSVs in evalkit/ and evalkit/results/.
#
# Requirements: gcc, clang, binutils (objdump/nm), git, python3, and
#   pip install -r requirements.txt
#
# Runtime is dominated by cloning and compiling ~30 libraries.
set -e
cd "$(dirname "$0")/evalkit"

echo "########## 1/4  building gcc corpus (15 original libraries + zlib opt sweep)"
bash build_all.sh
echo "########## 2/4  building external library set"
bash build_ext.sh
echo "########## 3/4  adding 6 new libraries and promoting 9 external into the corpus"
bash build_new.sh
echo "########## 4/4  building clang mirror (compiler-axis / robustness)"
bash build_clang.sh

echo "########## analysis"
python3 summarize.py            # -> CEILING_TABLE.csv
python3 attributability.py      # -> ATTRIBUTABILITY.csv
python3 signal_decomposition.py # -> results/SIGNAL_DECOMPOSITION.csv
python3 component_detection.py  # -> results/COMPONENT_DETECTION.csv
python3 ceil_sensitivity.py     # -> SENSITIVITY.csv
python3 robustness.py           # static-linking and gcc-vs-clang axes
python3 validate_capstone.py    # cross-extractor agreement (Capstone+pyelftools)
python3 apex_stats.py           # aggregate statistics reported in the paper

echo "########## done. results are in evalkit/*.csv and evalkit/results/*.csv"
