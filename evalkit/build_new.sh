#!/usr/bin/env bash
# Build the six additional diverse libraries that, together with build_all.sh (15)
# and the nine promoted from build_ext.sh, make up the thirty-library corpus.
set -u
NS=new_src
mkdir -p "$NS"
cl(){ [ -d "$NS/$1" ] || git clone --depth 1 -q "https://github.com/$2" "$NS/$1"; }
cl picohttpparser h2o/picohttpparser
cl tinyexpr       codeplea/tinyexpr
cl tinyregex      kokke/tiny-regex-c
cl qrcodegen      nayuki/QR-Code-generator
cl microtar       rxi/microtar
cl monocypher     LoupVaillant/Monocypher
bld(){ lib="$1"; inc="$2"; src="$3"; mkdir -p "corpus/$lib/obj"
  gcc -O2 -w $inc -c "$src" -o "corpus/$lib/obj/$(basename ${src%.c}).o" 2>/dev/null; }
bld picohttpparser "-I$NS/picohttpparser"  $NS/picohttpparser/picohttpparser.c
bld tinyexpr       "-I$NS/tinyexpr"          $NS/tinyexpr/tinyexpr.c
bld tinyregex      "-I$NS/tinyregex"         $NS/tinyregex/re.c
bld qrcodegen      "-I$NS/qrcodegen/c"       $NS/qrcodegen/c/qrcodegen.c
bld microtar       "-I$NS/microtar/src"      $NS/microtar/src/microtar.c
bld monocypher     "-I$NS/monocypher/src"    $NS/monocypher/src/monocypher.c
# promote nine diverse libraries built by build_ext.sh into the measured corpus
for lib in base64 heatshrink jsmn klib logc miniz mpack sha2 stb; do
  [ -d "corpus_ext/$lib/obj" ] && { rm -rf "corpus/$lib"; mkdir -p "corpus/$lib"; cp -r "corpus_ext/$lib/obj" "corpus/$lib/obj"; }
done
echo "corpus now: $(ls -d corpus/*/ | grep -vc 'zlib-O') distinct libraries (+ zlib opt variants)"
