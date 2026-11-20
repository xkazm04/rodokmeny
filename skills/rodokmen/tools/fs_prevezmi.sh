#!/bin/bash
# fs_prevezmi.sh <soubor ve Stažených> <cíl.jpg> [--ark 3:1:…]  -- přesune snímek stažený v prohlížeči (fs.stahni, tlačítko Download) do projektu
# Bere jen soubor s přesně tímto názvem (nikdy „nejnovější ve Stažených“), počká, až prohlížeč dostahuje (.tmp, .crdownload),
# ověří, že je to JPEG, a s --ark ho uloží i do sdílené mezipaměti (tools/cache.py), ať se příště nestahuje znovu.
# Na síť nesahá. Složku Stažené jde nastavit proměnnou STAZENE (výchozí ~/Downloads).
if [ "$1" = -h ] || [ "$1" = --help ] || [ $# -lt 2 ]; then sed -n '2,5p' "$0" | sed 's/^# \{0,1\}//'; exit 2; fi   # nápověda
PY=python3; $PY -c "" 2>/dev/null || PY=python; $PY -c "" 2>/dev/null || PY="py -3"
jmeno=$1; cil=$2; ark=""
[ "$3" = --ark ] && ark=$4
case "$jmeno" in */*|*\\*|..*) echo "Zadej jen název souboru ve Stažených, ne cestu: $jmeno" >&2; exit 2;; esac
dir=${STAZENE:-$HOME/Downloads}
src="$dir/$jmeno"
for i in $(seq 1 30); do   # prohlížeč může soubor ještě dopisovat
  [ -s "$src" ] && [ ! -e "$src.crdownload" ] && [ ! -e "$src.tmp" ] && [ ! -e "$src.part" ] && break
  sleep 2
done
if [ ! -s "$src" ]; then
  echo "Ve Stažených ($dir) není $jmeno. Ať uživatel snímek stáhne (nebo zkontroluj název); jiný soubor nepřebírej." >&2
  exit 1
fi
if [ "$(head -c 3 "$src" | od -An -tx1 | tr -d ' \n')" != "ffd8ff" ]; then
  echo "$jmeno není JPEG (HTML stránka „Pardon Our Interruption“?) – nepřebírám. Skonči a zapiš:" >&2
  echo "  python3 -I tools/slusne.py zastav familysearch.org \"Pardon Our Interruption\"" >&2
  exit 1
fi
mkdir -p "$(dirname "$cil")" && mv "$src" "$cil" || exit 1
echo "$cil"
if [ -n "$ark" ]; then
  $PY -I -X utf8 - "$(dirname "$0")" "$cil" "$ark" <<'EOF'
import os, re, sys
sys.path.insert(0, sys.argv[1])
import cache
ark = sys.argv[3]
if not re.fullmatch(r"3:1:[A-Za-z0-9-]+", ark):
    sys.exit(f"ARK {ark} nemá tvar 3:1:… – do mezipaměti neukládám")
data = open(sys.argv[2], "rb").read()
klic = f"familysearch/{ark.replace(':', '_')}.jpg"
print("v mezipaměti:", klic if cache.cely(data) and cache.uloz(klic, data) else "neuloženo (neúplný obrázek?)")
EOF
fi
