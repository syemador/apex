#!/usr/bin/env bash
# Build the APEX measurement corpus: clone each library at a pinned ref and
# compile its core C sources with gcc -O2 into corpus/<lib>/obj/*.o.
# zlib is additionally built at -O0/-O3/-Os. Provenance (commit, files, flags)
# is recorded per library in corpus/<lib>/provenance.json.
set -u
cd "$(dirname "$0")"
mkdir -p src corpus
GCC_VER=$(gcc -dumpfullversion)

clone () {  # $1=dir $2=url $3=ref(tag/branch)
  d="src/$1"
  if [ -d "$d/.git" ]; then echo "  (have $1)"; return; fi
  git clone -q --depth 1 --branch "$3" "$2" "$d" 2>/dev/null \
    || git clone -q --depth 1 "$2" "$d" 2>/dev/null
}

# name | srcsubdir | include-dir(s, space sep, rel to repo) | extra cflags | list of .c (rel to srcsubdir)
build () {
  name="$1"; sub="$2"; incs="$3"; xtra="$4"; shift 4
  repo="src/$name"; src="$repo"; [ -n "$sub" ] && src="$repo/$sub"
  out="corpus/$name/obj"; rm -rf "corpus/$name"; mkdir -p "$out"
  iflags=""; for i in $incs; do iflags="$iflags -I$repo/$i"; done
  ok=0; fail=0; files=""
  for c in "$@"; do
    base=$(basename "$c" .c)
    if gcc -O2 $iflags $xtra -c "$src/$c" -o "$out/$base.o" 2>>"corpus/$name/build.err"; then
      ok=$((ok+1)); files="$files $c"
    else
      fail=$((fail+1)); echo "    FAIL $name/$c"
    fi
  done
  commit=$(git -C "$repo" rev-parse HEAD 2>/dev/null)
  n=$(nm "$out"/*.o 2>/dev/null | grep -E ' [Tt] ' | wc -l)
  printf '{"library":"%s","commit":"%s","gcc":"%s","flags":"-O2","objs":%d,"funcsyms":%d,"files":[%s]}\n' \
    "$name" "$commit" "$GCC_VER" "$ok" "$n" \
    "$(echo $files | tr ' ' '\n' | sed 's/.*/"&"/' | paste -sd,)" > "corpus/$name/provenance.json"
  printf '%-14s objs=%-3d fail=%-2d funcsyms=%d\n' "$name" "$ok" "$fail" "$n"
}

echo "=== cloning (pinned refs; falls back to default branch if tag missing) ==="
clone zlib        https://github.com/madler/zlib.git              v1.3.1
clone xxHash      https://github.com/Cyan4973/xxHash.git          v0.8.2
clone cJSON       https://github.com/DaveGamble/cJSON.git         v1.7.18
clone lz4         https://github.com/lz4/lz4.git                  v1.9.4
clone yyjson      https://github.com/ibireme/yyjson.git           0.10.0
clone parson      https://github.com/kgabis/parson.git            master
clone tomlc99     https://github.com/cktan/tomlc99.git            master
clone md4c        https://github.com/mity/md4c.git                release-0.5.2
clone http_parser https://github.com/nodejs/http-parser.git       v2.9.4
clone inih        https://github.com/benhoyt/inih.git             r58
clone utf8proc    https://github.com/JuliaStrings/utf8proc.git    v2.9.0
clone sds         https://github.com/antirez/sds.git              master
clone cwalk       https://github.com/likle/cwalk.git              v1.2.9
clone mongoose    https://github.com/cesanta/mongoose.git         7.14
clone lua         https://github.com/lua/lua.git                  v5.4.7

echo "=== building (gcc $GCC_VER, -O2) ==="
build zlib        ""    "."          "" adler32.c compress.c crc32.c deflate.c gzclose.c gzlib.c gzread.c gzwrite.c infback.c inffast.c inflate.c inftrees.c trees.c uncompr.c zutil.c
build xxHash      ""    "."          "" xxhash.c
build cJSON       ""    "."          "" cJSON.c
build lz4         "lib" "lib"        "" lz4.c lz4hc.c lz4frame.c xxhash.c lz4file.c
build yyjson      "src" "src"        "" yyjson.c
build parson      ""    "."          "" parson.c
build tomlc99     ""    "."          "" toml.c
build md4c        "src" "src"        "" md4c.c md4c-html.c entity.c
build http_parser ""    "."          "" http_parser.c
build inih        ""    "."          "" ini.c
build utf8proc    ""    "."          "" utf8proc.c
build sds         ""    "."          "" sds.c
build cwalk       "src" "include"    "" cwalk.c
build mongoose    ""    "."          "" mongoose.c
# Lua: core VM/base sources. The lua/lua repo keeps .c at the top level (no src/ dir).
LUA_CORE="lapi lcode lctype ldebug ldo ldump lfunc lgc llex lmem lobject lopcodes lparser lstate lstring ltable ltm lundump lvm lzio"
build lua         ""    "."          "" $(for f in $LUA_CORE; do echo $f.c; done)

echo "=== zlib optimization sweep (-O0/-O3/-Os) ==="
for OPT in O0 O3 Os; do
  out="corpus/zlib-$OPT/obj"; rm -rf "corpus/zlib-$OPT"; mkdir -p "$out"
  for c in adler32 compress crc32 deflate gzclose gzlib gzread gzwrite infback inffast inflate inftrees trees uncompr zutil; do
    gcc -$OPT -I src/zlib -c "src/zlib/$c.c" -o "$out/$c.o" 2>/dev/null
  done
  n=$(nm "$out"/*.o 2>/dev/null | grep -E ' [Tt] ' | wc -l)
  printf 'zlib-%-9s funcsyms=%d\n' "$OPT" "$n"
done
echo "=== done ==="
