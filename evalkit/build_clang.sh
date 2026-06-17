#!/usr/bin/env bash
# Build the clang mirror of the thirty-library corpus into corpus_clang/<lib>/obj/*.o,
# used by robustness.py to measure the compiler axis (gcc vs clang).
# Prerequisite: run build_all.sh, build_ext.sh, and build_new.sh first so the sources
# are cloned under src/, ext_src/, and new_src/ (this script only recompiles them).
set -u
cd "$(dirname "$0")"
CLANG_VER=$(clang -dumpfullversion 2>/dev/null || clang --version | head -1)
echo "=== building clang mirror (clang $CLANG_VER, -O2) ==="

bld () {  # $1=lib  $2=include flags+defs  $3..=source files
  lib="$1"; inc="$2"; shift 2
  out="corpus_clang/$lib/obj"; rm -rf "corpus_clang/$lib"; mkdir -p "$out"
  ok=0
  for c in "$@"; do
    [ -f "$c" ] || { echo "    MISSING $c (run the gcc build scripts first)"; continue; }
    clang -O2 -w $inc -c "$c" -o "$out/$(basename ${c%.c}).o" 2>/dev/null && ok=$((ok+1))
  done
  n=$(nm "$out"/*.o 2>/dev/null | grep -E ' [Tt] ' | wc -l)
  printf '%-14s objs=%-3d funcsyms=%d\n' "$lib" "$ok" "$n"
}

# --- fifteen original libraries (sources cloned by build_all.sh into src/) ---
bld zlib        "-Isrc/zlib" src/zlib/adler32.c src/zlib/compress.c src/zlib/crc32.c src/zlib/deflate.c src/zlib/gzclose.c src/zlib/gzlib.c src/zlib/gzread.c src/zlib/gzwrite.c src/zlib/infback.c src/zlib/inffast.c src/zlib/inflate.c src/zlib/inftrees.c src/zlib/trees.c src/zlib/uncompr.c src/zlib/zutil.c
bld xxHash      "-Isrc/xxHash" src/xxHash/xxhash.c
bld cJSON       "-Isrc/cJSON" src/cJSON/cJSON.c
bld lz4         "-Isrc/lz4/lib" src/lz4/lib/lz4.c src/lz4/lib/lz4hc.c src/lz4/lib/lz4frame.c src/lz4/lib/xxhash.c src/lz4/lib/lz4file.c
bld yyjson      "-Isrc/yyjson/src" src/yyjson/src/yyjson.c
bld parson      "-Isrc/parson" src/parson/parson.c
bld tomlc99     "-Isrc/tomlc99" src/tomlc99/toml.c
bld md4c        "-Isrc/md4c/src" src/md4c/src/md4c.c src/md4c/src/md4c-html.c src/md4c/src/entity.c
bld http_parser "-Isrc/http_parser" src/http_parser/http_parser.c
bld inih        "-Isrc/inih" src/inih/ini.c
bld utf8proc    "-Isrc/utf8proc" src/utf8proc/utf8proc.c
bld sds         "-Isrc/sds" src/sds/sds.c
bld cwalk       "-Isrc/cwalk/include" src/cwalk/src/cwalk.c
bld mongoose    "-Isrc/mongoose" src/mongoose/mongoose.c
LUA_CORE="lapi lcode lctype ldebug ldo ldump lfunc lgc llex lmem lobject lopcodes lparser lstate lstring ltable ltm lundump lvm lzio"
bld lua         "-Isrc/lua" $(for f in $LUA_CORE; do echo src/lua/$f.c; done)

# --- nine libraries promoted from the external set (sources in ext_src/) ---
bld base64      "-Iext_src/base64" ext_src/base64/base64.c
bld heatshrink  "-Iext_src/heatshrink" ext_src/heatshrink/heatshrink_encoder.c ext_src/heatshrink/heatshrink_decoder.c
bld jsmn        "-Iext_src/jsmn" ext_src/jsmn/jsmn_tu.c
bld klib        "-Iext_src/klib" $(ls ext_src/klib/*.c 2>/dev/null | tr '\n' ' ')
bld logc        "-Iext_src/logc/src" ext_src/logc/src/log.c
bld miniz       "-Iext_src/miniz -DMINIZ_NO_TIME" ext_src/miniz/miniz.c ext_src/miniz/miniz_tdef.c ext_src/miniz/miniz_tinfl.c ext_src/miniz/miniz_zip.c
bld mpack       "-Iext_src/mpack/src/mpack -Iext_src/mpack/src" $(ls ext_src/mpack/src/mpack/*.c 2>/dev/null | tr '\n' ' ')
bld sha2        "-Iext_src/sha2" ext_src/sha2/sha-256.c
bld stb         "-Iext_src/stb" ext_src/stb/stb_image_tu.c

# --- six newly added libraries (sources in new_src/) ---
bld picohttpparser "-Inew_src/picohttpparser" new_src/picohttpparser/picohttpparser.c
bld tinyexpr       "-Inew_src/tinyexpr" new_src/tinyexpr/tinyexpr.c
bld tinyregex      "-Inew_src/tinyregex" new_src/tinyregex/re.c
bld qrcodegen      "-Inew_src/qrcodegen/c" new_src/qrcodegen/c/qrcodegen.c
bld microtar       "-Inew_src/microtar/src" new_src/microtar/src/microtar.c
bld monocypher     "-Inew_src/monocypher/src" new_src/monocypher/src/monocypher.c

echo "clang corpus: $(ls -d corpus_clang/*/ 2>/dev/null | wc -l) libraries"
