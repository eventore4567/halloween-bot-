#!/usr/bin/env sh
# Lance les tests BloxHub hors Roblox : compilation Luau + exécution dans l'environnement simulé.
set -e
cd "$(dirname "$0")"
LUAU="${LUAU:-luau}"
LUAU_COMPILE="${LUAU_COMPILE:-luau-compile}"
for f in ../loader.lua ../src/*.lua; do
	"$LUAU_COMPILE" --null "$f" > /dev/null
done
echo "Syntaxe Luau : OK"
python3 gen_sources.py > _sources.luau
"$LUAU" run_tests.luau
