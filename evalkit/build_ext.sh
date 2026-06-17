#!/usr/bin/env bash
# Build the external reference corpus used to tighten the attributability bound.
# These eleven libraries are NOT part of the measured 15-library corpus; they only
# enlarge the reference set against which feature distinctiveness is judged, so that
# attributable-in-principle becomes a tighter upper bound. After running this,
# `python3 attributability.py` reports the enlarged column automatically.
set -u
ES=ext_src; OUT=corpus_ext
mkdir -p "$ES" "$OUT"
cl(){ [ -d "$ES/$1" ] || git clone --depth 1 -q "https://github.com/$2" "$ES/$1"; }
cl miniz richgel999/miniz
cl jsmn zserge/jsmn
cl frozen cesanta/frozen
cl logc rxi/log.c
cl sha2 amosnier/sha-2
cl mpack ludocode/mpack
cl stb nothings/stb
cl klib attractivechaos/klib
cl pdjson skeeto/pdjson
cl heatshrink atomicobject/heatshrink
cl base64 joedf/base64.c

# header-only translation units, and a stub for miniz's CMake-generated export header
printf '#include "jsmn.h"\n' > "$ES/jsmn/jsmn_tu.c"
printf '#define STB_IMAGE_IMPLEMENTATION\n#include "stb_image.h"\n' > "$ES/stb/stb_image_tu.c"
printf '#ifndef MINIZ_EXPORT\n#define MINIZ_EXPORT\n#endif\n' > "$ES/miniz/miniz_export.h"

bld(){ lib="$1"; inc="$2"; shift 2; mkdir -p "$OUT/$lib/obj"
  for c in "$@"; do gcc -O2 -w $inc -c "$c" -o "$OUT/$lib/obj/$(basename ${c%.c}).o" 2>/dev/null; done; }
bld miniz "-I$ES/miniz -DMINIZ_NO_TIME" $ES/miniz/miniz.c $ES/miniz/miniz_tdef.c $ES/miniz/miniz_tinfl.c $ES/miniz/miniz_zip.c
bld jsmn "-I$ES/jsmn" $ES/jsmn/jsmn_tu.c
bld frozen "-I$ES/frozen" $ES/frozen/frozen.c
bld logc "-I$ES/logc/src" $ES/logc/src/log.c
bld sha2 "-I$ES/sha2" $ES/sha2/sha-256.c
bld mpack "-I$ES/mpack/src/mpack -I$ES/mpack/src" $ES/mpack/src/mpack/*.c
bld stb "-I$ES/stb" $ES/stb/stb_image_tu.c
bld pdjson "-I$ES/pdjson" $ES/pdjson/pdjson.c
bld heatshrink "-I$ES/heatshrink" $ES/heatshrink/heatshrink_encoder.c $ES/heatshrink/heatshrink_decoder.c
bld base64 "-I$ES/base64" $ES/base64/base64.c
mkdir -p "$OUT/klib/obj"
for c in $ES/klib/*.c; do gcc -O2 -w -I$ES/klib -c "$c" -o "$OUT/klib/obj/$(basename ${c%.c}).o" 2>/dev/null; done

echo "external reference: $(find "$OUT" -name '*.o' | sed 's#/obj/.*##' | sort -u | wc -l) libraries, $(find "$OUT" -name '*.o' | wc -l) objects"
