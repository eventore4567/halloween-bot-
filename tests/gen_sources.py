"""Génère _sources.luau : les fichiers du hub embarqués en chaînes Luau (le CLI Luau n'a pas d'io)."""
import pathlib
import sys

root = pathlib.Path(__file__).resolve().parent.parent
files = [root / "loader.lua"] + sorted((root / "src").glob("*.lua"))
out = ["-- Fichier généré par gen_sources.py, ne pas modifier.", "return {"]
for f in files:
    text = f.read_text(encoding="utf-8")
    level = 1
    while ("]" + "=" * level + "]") in text:
        level += 1
    eq = "=" * level
    rel = f.relative_to(root).as_posix()
    out.append(f'\t["{rel}"] = [{eq}[\n{text}]{eq}],')
out.append("}")
sys.stdout.write("\n".join(out) + "\n")
