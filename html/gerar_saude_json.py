#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
gerar_saude_json.py

Lê as notas de saúde da pasta "07. Saúde" do Segundo Cérebro (os ficheiros
"MOC - Saúde <Pessoa>.md" e o cardápio "Dieta - Perda de Peso ....md") e gera
um único ficheiro saude.json, pronto para ser publicado no repositório do site
e consumido pela página saude.html.

A página saude.html faz fetch('saude.json') da mesma pasta e desenha tudo a
partir daí — por isso, sempre que editar as notas no Obsidian, corra este
script (ou use o gerar_saude.html no navegador) e faça commit do saude.json.

USO:
    # usa os caminhos-padrão (pasta 07. Saúde -> ./saude.json)
    python3 gerar_saude_json.py

    # ou indique a pasta de origem e o destino
    python3 gerar_saude_json.py \
        --pasta "/caminho/para/07. Saúde" \
        --saida "/caminho/para/pessoal/html/saude.json"
"""

import argparse
import json
import re
import sys
import unicodedata
from datetime import date
from pathlib import Path

# ---- Caminhos-padrão (ajuste se mudar a estrutura de pastas) ----
PASTA_SAUDE_PADRAO = Path(
    "/Users/marcio.andrio/pCloud/Projetos/Obsidian/MA Brain/07. Saúde"
)
SAIDA_PADRAO = Path(__file__).resolve().parent / "saude.json"

# ---- Metadados por pessoa (emoji + ordem). Fallback para quem não estiver aqui. ----
META_PESSOAS = {
    "marcio":  {"emoji": "👨", "ordem": 0, "titular": True},
    "helen":   {"emoji": "👩", "ordem": 1, "titular": False},
    "victor":  {"emoji": "🧒", "ordem": 2, "titular": False},
    "dominic": {"emoji": "🧒", "ordem": 3, "titular": False},
    "desiree": {"emoji": "👶", "ordem": 4, "titular": False},
}


def slug(texto: str) -> str:
    """primeiro nome, sem acentos, minúsculo — usado como id da pessoa."""
    t = unicodedata.normalize("NFD", texto or "")
    t = "".join(c for c in t if unicodedata.category(c) != "Mn")
    t = re.sub(r"[^a-zA-Z0-9]+", " ", t).strip().lower()
    return t.split(" ")[0] if t else ""


def sem_front_matter(texto: str) -> str:
    """Remove o bloco YAML --- ... --- do topo, se existir."""
    if texto.lstrip().startswith("---"):
        m = re.match(r"^\s*---\s*\n.*?\n---\s*\n", texto, re.DOTALL)
        if m:
            return texto[m.end():]
    return texto


def limpar_corpo(texto: str) -> str:
    """Tira front matter, o H1 (# ...) e o blockquote de introdução que vem logo
    a seguir (> Mapa consolidado... / > Ligado a [[...]]), deixando só o conteúdo."""
    t = sem_front_matter(texto).lstrip("\n")
    linhas = t.split("\n")
    out = []
    i = 0
    # salta o primeiro H1
    if i < len(linhas) and linhas[i].startswith("# "):
        i += 1
    # salta linhas em branco + blockquote de introdução + primeiro ---
    while i < len(linhas):
        s = linhas[i].strip()
        if s == "" or s.startswith(">") or re.fullmatch(r"-{3,}", s):
            i += 1
            continue
        break
    out = linhas[i:]
    # remove wikilinks [[Nome]] -> Nome
    corpo = "\n".join(out)
    corpo = re.sub(r"\[\[([^\]]+?)\]\]", lambda m: m.group(1).split("|")[0], corpo)
    return corpo.strip()


def extrair_nome(texto: str, fallback: str) -> str:
    """Procura '| **Nome** | valor |'; senão usa o título/ficheiro."""
    m = re.search(r"\|\s*\*\*Nome\*\*\s*\|\s*([^|]+?)\s*\|", texto)
    if m:
        return m.group(1).strip()
    m = re.search(r"^#\s+.*?Saúde\s+(.+)$", texto, re.MULTILINE)
    if m:
        return m.group(1).strip()
    return fallback


def extrair_idade(texto: str) -> str:
    """Extrai '(X anos)' / '(X meses)' do campo Data de Nascimento, se houver."""
    m = re.search(r"Data de Nascimento\*\*\s*\|\s*[^|(]*\(([^)]+)\)", texto)
    if m:
        return m.group(1).strip()
    return ""


def extrair_titulo_dieta(texto: str) -> str:
    m = re.search(r"^#\s+(.+)$", sem_front_matter(texto), re.MULTILINE)
    return m.group(1).strip().lstrip("🥗 ").strip() if m else "Dieta"


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--pasta", type=Path, default=PASTA_SAUDE_PADRAO,
                    help="Pasta 07. Saúde (com subpastas por pessoa)")
    ap.add_argument("--saida", type=Path, default=SAIDA_PADRAO,
                    help="Ficheiro saude.json de saída")
    args = ap.parse_args()

    if not args.pasta.exists():
        print(f"❌ Pasta não encontrada: {args.pasta}", file=sys.stderr)
        sys.exit(1)

    # No macOS os nomes vêm em NFD; comparamos de forma tolerante a acentos.
    def norm(s: str) -> str:
        return unicodedata.normalize("NFC", s).lower()

    todos_md = [f for f in args.pasta.rglob("*.md")]
    mocs = sorted(f for f in todos_md if norm(f.name).startswith("moc - sa"))
    dietas = sorted(f for f in todos_md if norm(f.name).startswith("dieta"))

    if not mocs:
        print(f"❌ Nenhum ficheiro 'MOC - Saúde *.md' encontrado em {args.pasta}",
              file=sys.stderr)
        sys.exit(1)

    pessoas = []
    for f in mocs:
        texto = f.read_text(encoding="utf-8")
        nome = extrair_nome(texto, f.stem.replace("MOC - Saúde ", ""))
        pid = slug(nome) or slug(f.stem.replace("MOC - Saúde ", ""))
        meta = META_PESSOAS.get(pid, {"emoji": "👤", "ordem": 99, "titular": False})
        pessoas.append({
            "id": pid,
            "nome": nome,
            "primeiro_nome": nome.split(" ")[0],
            "emoji": meta["emoji"],
            "idade": extrair_idade(texto),
            "titular": meta["titular"],
            "ordem": meta["ordem"],
            "markdown": limpar_corpo(texto),
        })

    pessoas.sort(key=lambda p: (p["ordem"], p["nome"]))

    # Dieta (a mais recente pelo nome do ficheiro) — anexa ao titular
    dieta = None
    if dietas:
        f = dietas[-1]
        texto = f.read_text(encoding="utf-8")
        dieta = {
            "titulo": extrair_titulo_dieta(texto),
            "ficheiro": f.name,
            "markdown": limpar_corpo(texto),
        }

    dados = {
        "gerado_em": date.today().isoformat(),
        "pessoas": pessoas,
        "dieta": dieta,
    }

    args.saida.parent.mkdir(parents=True, exist_ok=True)
    args.saida.write_text(json.dumps(dados, ensure_ascii=False, indent=2),
                          encoding="utf-8")

    print(f"✅ saude.json gerado: {args.saida}")
    print(f"   Pessoas: {', '.join(p['nome'] for p in pessoas)}")
    print(f"   Dieta:   {dieta['ficheiro'] if dieta else '— (nenhuma encontrada)'}")
    print()
    print("Agora faça commit + push do saude.json (e do saude.html na 1ª vez) para o site.")


if __name__ == "__main__":
    main()
