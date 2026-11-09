#!/usr/bin/env python3
"""Sincroniza a fonte única (core/) com os pacotes de cada plataforma.

As skills são escritas uma vez em core/<plugin>/ e copiadas para cada
plataforma declarada em harnesses.json. As cópias não devem ser editadas à mão:
edite core/ e rode este script.

Uso:
    python3 scripts/sync_plugins.py                  # gera as cópias no repositório
    python3 scripts/sync_plugins.py --check          # só confere; sai com 1 se houver problema (CI)
    python3 scripts/sync_plugins.py --out-root PASTA # gera (ou confere) em outra pasta, para testes

Layouts (campo "layout" em harnesses.json, padrão "plugin"):

- "plugin" (Claude, Codex): skills/<skill>/ copiado do core, com o que está em
  shared/ e nos kits do tipo da skill dentro de cada skill (shared/scripts/brand.py
  em scripts/, references/* em references/ e shared/assets/brand/ em assets/brand/).
  Cada skill fica autocontida. LICENSE, NOTICE e COMMERCIAL.md vão na raiz do pacote.
- "flat-skills" (DeepSeek Harness): o mesmo conteúdo por skill, mais LICENSE,
  NOTICE e COMMERCIAL.md dentro de cada skills/<skill>/, porque o harness lê
  cada skill solta, sem raiz de plugin.
- "gpt" (GPT Store): gpts/<skill>/instructions.md (preâmbulo mais as instruções
  do GPT da skill), gpts/<skill>/gpt.json e gpts/<skill>/knowledge/ com a skill
  autocontida, menos o SKILL.md.

Kits: shared/ vai para todas as skills (a marca). Os kits em kits/<kit>/ vão só
para as skills do tipo que os usa. O campo "tipo" de cada item do skills.json
(calculadora, relatorio, painel, ficha) escolhe os kits pela tabela "kits" do
plugin em harnesses.json. Toda skill de core/ precisa estar no skills.json com
"tipo" e "gpt". Só as skills com "gpt": true viram pacote de GPT.

Em todo arquivo de texto copiado (.md, .py, .html, .json), o placeholder de UTM
vira o utm_source da plataforma. O script também gera a tabela de skills do
README.md e os cards do docs/index.html, entre os marcadores
<!-- skills:start --> e <!-- skills:end -->, a partir do skills.json.

O --check falha quando: alguma cópia difere; um instructions.md de GPT passa de
8.000 caracteres; o name do frontmatter difere da pasta; um manifesto tem nome,
versão ou licença diferente do core e de CC-BY-NC-ND-4.0; o name ou a description
do frontmatter quebram o YAML (': ' ou caractere especial no início, sem aspas);
uma referência entre
crases aponta para arquivo inexistente; ou sobra placeholder de UTM nas cópias.
Um arquivo de shared/ ou de um kit com o mesmo caminho de um arquivo da skill
(ou de outro kit) também é erro: o compartilhado nunca sobrescreve nada. Kit
inexistente em uso por uma skill registrada também é acusado.
"""

from __future__ import annotations

import argparse
import filecmp
import html
import json
import re
import shutil
import sys
import tempfile
from pathlib import Path
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parent.parent
CONFIG = ROOT / "harnesses.json"
SKILLS_JSON = ROOT / "skills.json"
LICENSE_ID = "CC-BY-NC-ND-4.0"
LICENSE_FILES = ("LICENSE", "NOTICE", "COMMERCIAL.md")
PLACEHOLDER = "{{" + "UTM_SOURCE" + "}}"
SKILL_PLACEHOLDER = "{{" + "SKILL" + "}}"
TEXT_SUFFIXES = {".md", ".py", ".html", ".json"}
GPT_LIMIT = 8000
JUNK_DIRS = {"__pycache__"}
JUNK_FILES = {".DS_Store"}
IGNORED = shutil.ignore_patterns("__pycache__", "*.pyc", ".DS_Store")
# Caracteres que não podem abrir um valor de YAML sem aspas.
YAML_INDICATORS = "!&*[]{}#|>%@`,'\""
# Caminho relativo entre crases apontando para um arquivo da skill.
REF_PATTERN = re.compile(r"`((?:\.\./|references/|assets/|scripts/)[^`\s]+\.(?:md|py|html|json))`")
LAYOUTS = ("plugin", "flat-skills", "gpt")
TIPOS = ("calculadora", "relatorio", "painel", "ficha")
MARK_START, MARK_END = "<!-- skills:start -->", "<!-- skills:end -->"


def load_json(path: Path):
    with path.open(encoding="utf-8") as fh:
        return json.load(fh)


def is_junk(rel: Path) -> bool:
    return bool(JUNK_DIRS & set(rel.parts)) or rel.name in JUNK_FILES or rel.suffix == ".pyc"


def files_of(tree: Path) -> dict[str, Path]:
    """Arquivos de `tree`, relativos e sem lixo de sistema."""
    out: dict[str, Path] = {}
    for path in sorted(tree.rglob("*")):
        rel = path.relative_to(tree)
        if path.is_file() and not is_junk(rel):
            out[rel.as_posix()] = path
    return out


def shown(path: Path, base: Path) -> str:
    try:
        return path.relative_to(base).as_posix()
    except ValueError:
        return path.as_posix()


# ------------------------------------------------------------------ montagem

def skill_dirs(core: Path) -> list[Path]:
    return sorted(p.parent for p in (core / "skills").glob("*/SKILL.md"))


def kits_da_skill(core: Path, spec: dict, skills: list[dict], nome: str) -> list[Path]:
    """Fontes compartilhadas da skill `nome`: shared/ e os kits do seu tipo.

    O tipo vem do skills.json e a lista de kits do tipo vem de spec["kits"].
    Levanta ValueError se a skill não está no skills.json, não tem tipo ou o
    tipo não está na tabela de kits.
    """
    entry = next((s for s in skills if s.get("name") == nome), None)
    if entry is None:
        raise ValueError(f"skill {nome} está em core mas não está no skills.json")
    tipo = entry.get("tipo")
    if not tipo:
        raise ValueError(f"skill {nome} sem 'tipo' no skills.json")
    kits = spec.get("kits", {})
    if tipo not in kits:
        raise ValueError(f"skill {nome}: tipo '{tipo}' sem entrada em 'kits' do harnesses.json")
    return [core / spec.get("shared", "shared")] + [core / "kits" / kit for kit in kits[tipo]]


def assemble_skill(skill: Path, fontes: list[Path], dest: Path) -> list[str]:
    """Copia `skill` para `dest` e soma o conteúdo de cada fonte no mesmo caminho relativo.

    shared/scripts/brand.py vai para scripts/brand.py, kits/x/references/y.md
    para references/y.md e assim por diante. Colisão entre a skill e uma fonte,
    ou entre duas fontes, é reportada e o primeiro arquivo fica.
    """
    problems: list[str] = []
    shutil.copytree(skill, dest, ignore=IGNORED)
    donos: dict[str, str] = {}
    for fonte in fontes:
        if not fonte.is_dir():
            problems.append(f"fonte compartilhada inexistente: {fonte.as_posix()} (usada por skills/{skill.name})")
            continue
        for rel, path in files_of(fonte).items():
            target = dest / rel
            if target.exists():
                dono = donos.get(rel, f"skills/{skill.name}")
                problems.append(
                    f"colisão: {rel} de {fonte.name}/ já existe em {dono} (skill {skill.name}); "
                    f"renomeie um dos dois"
                )
                continue
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(path, target)
            donos[rel] = f"{fonte.name}/"
    return problems


def copy_license(dest: Path) -> None:
    for name in LICENSE_FILES:
        shutil.copy2(ROOT / name, dest / name)


def fontes_ou_problema(core: Path, spec: dict, skills: list[dict], nome: str, problems: list[str]):
    try:
        return kits_da_skill(core, spec, skills, nome)
    except ValueError as err:
        problems.append(str(err))
        return None


def build_skills(core: Path, spec: dict, skills: list[dict], work: Path) -> list[str]:
    problems: list[str] = []
    for skill in skill_dirs(core):
        fontes = fontes_ou_problema(core, spec, skills, skill.name, problems)
        if fontes is not None:
            problems += assemble_skill(skill, fontes, work / "skills" / skill.name)
    return problems


def build_gpts(core: Path, spec: dict, skills: list[dict], work: Path) -> list[str]:
    problems: list[str] = []
    gpt_src = core / "gpts"
    preamble_path = gpt_src / "_preamble.md"
    if not preamble_path.is_file():
        return [f"preâmbulo ausente: {shown(preamble_path, ROOT)}"]
    preamble = preamble_path.read_text(encoding="utf-8").strip()
    com_gpt = {s["name"] for s in skills if s.get("gpt") is True}
    for skill in skill_dirs(core):
        if skill.name not in com_gpt:
            continue
        src = gpt_src / skill.name
        missing = [n for n in ("instructions.md", "gpt.json") if not (src / n).is_file()]
        if missing:
            problems.append(f"GPT da skill {skill.name} sem {', '.join(missing)} em {shown(src, ROOT)}")
            continue
        fontes = fontes_ou_problema(core, spec, skills, skill.name, problems)
        if fontes is None:
            continue
        base = work / skill.name
        knowledge = base / "knowledge"
        problems += assemble_skill(skill, fontes, knowledge)
        (knowledge / "SKILL.md").unlink()
        body = (src / "instructions.md").read_text(encoding="utf-8").strip()
        text = preamble.replace(SKILL_PLACEHOLDER, skill.name) + "\n\n" + body + "\n"
        (base / "instructions.md").write_text(text, encoding="utf-8")
        shutil.copy2(src / "gpt.json", base / "gpt.json")
    if gpt_src.is_dir():
        stray = sorted(
            p.name for p in gpt_src.iterdir()
            if p.is_dir() and not is_junk(Path(p.name)) and p.name not in com_gpt
        )
        problems += [f"core/gpts/{name} não corresponde a nenhuma skill com \"gpt\": true" for name in stray]
    return problems


def build_harness(core: Path, spec: dict, skills: list[dict], layout: str, work: Path) -> list[str]:
    work.mkdir(parents=True)
    if layout == "plugin":
        problems = build_skills(core, spec, skills, work)
    elif layout == "flat-skills":
        problems = build_skills(core, spec, skills, work)
        for skill in (work / "skills").iterdir():
            copy_license(skill)
    elif layout == "gpt":
        problems = build_gpts(core, spec, skills, work)
    else:
        return [f"layout desconhecido '{layout}' (use um de: {', '.join(LAYOUTS)})"]
    copy_license(work)
    return problems


def replace_utm(tree: Path, source: str) -> None:
    for rel, path in files_of(tree).items():
        if path.suffix in TEXT_SUFFIXES:
            text = path.read_text(encoding="utf-8")
            if PLACEHOLDER in text:
                path.write_text(text.replace(PLACEHOLDER, source), encoding="utf-8")


# ------------------------------------------------------------------ conferências

def check_frontmatter(core: Path) -> list[str]:
    problems: list[str] = []
    for skill_md in sorted((core / "skills").glob("*/SKILL.md")):
        folder = skill_md.parent.name
        text = skill_md.read_text(encoding="utf-8")
        match = re.match(r"^---\n(.*?)\n---\n", text, re.S)
        if not match:
            problems.append(f"{shown(skill_md, ROOT)}: sem frontmatter")
            continue
        front = match.group(1)
        name = re.search(r"^name:\s*(.+)$", front, re.M)
        if not name or name.group(1).strip() != folder:
            problems.append(f"{shown(skill_md, ROOT)}: name diferente da pasta '{folder}'")
        if not re.search(r"^description:\s*\S", front, re.M):
            problems.append(f"{shown(skill_md, ROOT)}: sem description")
        for campo in ("name", "description"):
            found = re.search(rf"^{campo}:\s*(.+)$", front, re.M)
            motivo = yaml_scalar_problem(found.group(1).strip()) if found else None
            if motivo:
                problems.append(f"{shown(skill_md, ROOT)}: {campo} {motivo}")
    return problems


def yaml_scalar_problem(value: str) -> str | None:
    """Por que um valor de frontmatter sem aspas quebra num leitor de YAML. Só biblioteca padrão, sem parser."""
    if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
        return None
    if ": " in value or value.endswith(":"):
        return "tem ': ' sem aspas, o YAML recusa"
    if value[0] in YAML_INDICATORS or value[:2] in ("- ", "? "):
        return f"começa com '{value[0]}' sem aspas, o YAML recusa"
    return None


def check_skills_json(skills: list[dict]) -> list[str]:
    problems: list[str] = []
    for s in skills:
        if s.get("tipo") not in TIPOS:
            problems.append(f"skills.json: '{s.get('name')}' com tipo '{s.get('tipo')}' (use um de: {', '.join(TIPOS)})")
        if not isinstance(s.get("gpt"), bool):
            problems.append(f"skills.json: '{s.get('name')}' sem 'gpt' true ou false")
    return problems


def check_refs(skill_root: Path, docs: list[Path], label) -> list[str]:
    """Toda referência entre crases em `docs` resolve a partir do documento ou da raiz da skill."""
    problems: list[str] = []
    for doc in docs:
        for ref in REF_PATTERN.findall(doc.read_text(encoding="utf-8")):
            if not any((base / ref).resolve().is_file() for base in (doc.parent, skill_root)):
                problems.append(f"{label(doc)}: referência quebrada '{ref}'")
    return problems


def check_tree(tree: Path, layout: str, label) -> list[str]:
    """Conferências sobre uma árvore gerada (a esperada ou a que está no disco)."""
    problems: list[str] = []
    for rel, path in files_of(tree).items():
        if path.suffix in TEXT_SUFFIXES | {".txt", ".svg"} and PLACEHOLDER in path.read_text(encoding="utf-8"):
            problems.append(f"{label(path)}: sobrou o placeholder {PLACEHOLDER}")
    if layout == "gpt":
        for base in sorted(p for p in tree.iterdir() if p.is_dir()):
            knowledge = base / "knowledge"
            instructions = base / "instructions.md"
            if instructions.is_file():
                text = instructions.read_text(encoding="utf-8")
                if len(text) > GPT_LIMIT:
                    problems.append(f"{label(instructions)}: {len(text)} caracteres, passa de 8.000")
                leftovers = sorted(set(re.findall(r"\{\{[^}]*\}\}", text)))
                if leftovers:
                    problems.append(f"{label(instructions)}: placeholder sem troca {', '.join(leftovers)}")
            if knowledge.is_dir():
                docs = sorted(knowledge.rglob("*.md")) + ([instructions] if instructions.is_file() else [])
                problems += check_refs(knowledge, docs, label)
    else:
        for skill in sorted(p for p in (tree / "skills").glob("*") if p.is_dir()):
            problems += check_refs(skill, sorted(skill.rglob("*.md")), label)
    return problems


def diff_entry(expected: Path, actual: Path, label) -> list[str]:
    if not actual.exists():
        return [f"faltando: {label(actual)}"]
    if expected.is_file():
        if not actual.is_file() or not filecmp.cmp(expected, actual, shallow=False):
            return [f"diferente: {label(actual)}"]
        return []
    if not actual.is_dir():
        return [f"diferente: {label(actual)} deveria ser pasta"]
    want, have = files_of(expected), files_of(actual)
    problems = [f"faltando: {label(actual / rel)}" for rel in sorted(set(want) - set(have))]
    problems += [f"sobrando: {label(actual / rel)}" for rel in sorted(set(have) - set(want))]
    problems += [
        f"diferente: {label(actual / rel)}"
        for rel in sorted(set(want) & set(have))
        if not filecmp.cmp(want[rel], have[rel], shallow=False)
    ]
    return problems


def check_manifest(path: Path, core_meta: dict, label) -> list[str]:
    if not path.is_file():
        return [f"manifesto ausente: {label(path)}"]
    manifest = load_json(path)
    problems: list[str] = []
    for key in ("name", "version"):
        if manifest.get(key) != core_meta[key]:
            problems.append(f"{label(path)}: {key} '{manifest.get(key)}' diferente do core '{core_meta[key]}'")
    if manifest.get("license") != LICENSE_ID:
        problems.append(f"{label(path)}: license '{manifest.get('license')}' diferente de '{LICENSE_ID}'")
    return problems


def check_marketplaces(plugin: str, spec: dict) -> list[str]:
    problems: list[str] = []
    harnesses = spec["harnesses"]
    checks = (
        ("claude", ROOT / ".claude-plugin" / "marketplace.json", lambda e: e.get("source")),
        ("codex", ROOT / ".agents" / "plugins" / "marketplace.json", lambda e: (e.get("source") or {}).get("path")),
    )
    for harness, path, source_of in checks:
        if harness not in harnesses:
            continue
        if not path.is_file():
            problems.append(f"marketplace ausente: {shown(path, ROOT)}")
            continue
        entries = [e for e in load_json(path).get("plugins", []) if e.get("name") == plugin]
        if not entries:
            problems.append(f"{shown(path, ROOT)}: sem a entrada do plugin '{plugin}'")
            continue
        entry = entries[0]
        expected = "./" + harnesses[harness]["path"]
        if source_of(entry) != expected:
            problems.append(f"{shown(path, ROOT)}: source '{source_of(entry)}' diferente de '{expected}'")
        if harness == "claude":
            if "version" in entry:
                problems.append(f"{shown(path, ROOT)}: não declare version na entrada do plugin (vale a do plugin.json)")
            if entry.get("license") != LICENSE_ID:
                problems.append(f"{shown(path, ROOT)}: license '{entry.get('license')}' diferente de '{LICENSE_ID}'")
    return problems


# ------------------------------------------------------------------ README e site

def utm_url(url: str, source: str, campaign: str) -> str:
    sep = "&" if "?" in url else "?"
    return f"{url}{sep}utm_source={source}&utm_medium=skill&utm_campaign={campaign}"


def link_label(skill: dict) -> str:
    return "Abrir a calculadora gratuita" if skill["tipo"] == "calculadora" else "Conecte seu ERP"


def readme_block(skills: list[dict]) -> str:
    lines = [
        "| Skill | O que faz | Regra | Site | Status |",
        "| --- | --- | --- | --- | --- |",
    ]
    for s in skills:
        host = urlparse(s["site_url"]).netloc
        url = utm_url(s["site_url"], "github", s["name"])
        rule = s["rule"] or "Não se aplica"
        lines.append(
            f"| **{s['title']}** (`{s['name']}`) | {s['summary']} | {rule} | [{host}]({url}) | {s['status']} |"
        )
    return "\n".join(lines)


def site_block(skills: list[dict]) -> str:
    cards = []
    for s in skills:
        url = html.escape(utm_url(s["site_url"], "site-skills", s["name"]), quote=True)
        rule = f'    <p class="skill-rule">Base: {html.escape(s["rule"])}</p>\n' if s["rule"] else ""
        cards.append(
            f'  <article class="skill-card" id="skill-{html.escape(s["name"])}">\n'
            f'    <p class="skill-status">{html.escape(s["status"])}</p>\n'
            f"    <h3>{html.escape(s['title'])}</h3>\n"
            f"    <p>{html.escape(s['summary'])}</p>\n"
            f"{rule}"
            f'    <a class="skill-link" href="{url}">{link_label(s)}</a>\n'
            "  </article>"
        )
    return '<div class="skills-grid">\n' + "\n".join(cards) + "\n</div>"


def fill_block(text: str, block: str) -> str | None:
    start, end = text.find(MARK_START), text.find(MARK_END)
    if start < 0 or end < start:
        return None
    return text[: start + len(MARK_START)] + "\n" + block + "\n" + text[end:]


def sync_blocks(out: Path, check: bool, skills: list[dict]) -> list[str]:
    problems: list[str] = []
    for rel, block in (("README.md", readme_block(skills)), ("docs/index.html", site_block(skills))):
        dst = out / rel
        src = dst if dst.is_file() else ROOT / rel
        if not src.is_file():
            problems.append(f"{rel} não existe (crie com os marcadores {MARK_START} e {MARK_END})")
            continue
        current = src.read_text(encoding="utf-8")
        new = fill_block(current, block)
        if new is None:
            problems.append(f"{rel}: faltam os marcadores {MARK_START} e {MARK_END}")
        elif check:
            if not dst.is_file() or dst.read_text(encoding="utf-8") != new:
                problems.append(f"diferente: {rel} (bloco de skills desatualizado)")
        elif not dst.is_file() or current != new or src != dst:
            dst.parent.mkdir(parents=True, exist_ok=True)
            dst.write_text(new, encoding="utf-8")
            print(f"{rel}: bloco de skills atualizado")
    return problems


# ------------------------------------------------------------------ principal

def copy_handwritten(src: Path, dst: Path, generated: set[str]) -> None:
    """Leva para `dst` o que é escrito à mão no pacote (manifesto, README, install.py)."""
    if not src.is_dir() or src.resolve() == dst.resolve():
        return
    dst.mkdir(parents=True, exist_ok=True)
    for entry in src.iterdir():
        if entry.name in generated or is_junk(Path(entry.name)):
            continue
        if entry.is_dir():
            shutil.copytree(entry, dst / entry.name, ignore=IGNORED, dirs_exist_ok=True)
        else:
            shutil.copy2(entry, dst / entry.name)


def sync_harness(harness: str, target: dict, work: Path, out: Path, check: bool, build_ok: bool) -> list[str]:
    dst = out / target["path"]
    layout = target.get("layout", "plugin")
    label = lambda p: shown(p, out)  # noqa: E731
    generated = {e.name for e in work.iterdir()}
    problems: list[str] = []
    if not check and build_ok:
        copy_handwritten(ROOT / target["path"], dst, generated)
        dst.mkdir(parents=True, exist_ok=True)
        for name in sorted(generated):
            path = dst / name
            if path.is_dir() and not path.is_symlink():
                shutil.rmtree(path)
            elif path.exists():
                path.unlink()
            if (work / name).is_dir():
                shutil.copytree(work / name, path)
            else:
                shutil.copy2(work / name, path)
        print(f"[{harness}] {', '.join(sorted(generated))} sincronizado em {label(dst)}")
    if check:
        for name in sorted(generated):
            problems += diff_entry(work / name, dst / name, label)
        if dst.is_dir():
            problems += check_tree(dst, layout, label)
    if layout == "gpt" and dst.is_dir():
        stray = sorted(p.name for p in dst.iterdir() if p.is_dir() and p.name not in generated)
        problems += [f"sobrando: {label(dst / name)} (não há skill com esse nome)" for name in stray]
    return problems


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--check", action="store_true", help="só confere, não escreve")
    parser.add_argument("--out-root", help="pasta onde gerar ou conferir (padrão: a raiz do repositório)")
    args = parser.parse_args()

    out = Path(args.out_root).expanduser().resolve() if args.out_root else ROOT
    config = load_json(CONFIG)
    skills = load_json(SKILLS_JSON)
    problems: list[str] = []

    with tempfile.TemporaryDirectory(prefix="cd2-sync-") as tmp:
        for plugin, spec in config["plugins"].items():
            core = ROOT / spec["core"]
            core_meta = load_json(core / "plugin.core.json")
            problems += check_frontmatter(core)
            names = {p.name for p in skill_dirs(core)}
            problems += [f"skills.json cita '{s['name']}', que não existe em {spec['core']}/skills"
                         for s in skills if s["name"] not in names]
            problems += check_skills_json(skills)
            problems += check_marketplaces(plugin, spec)

            for harness, target in spec["harnesses"].items():
                layout = target.get("layout", "plugin")
                work = Path(tmp) / plugin / harness
                build_problems = build_harness(core, spec, skills, layout, work)
                replace_utm(work, target["utm_source"])
                tree_problems = check_tree(work, layout, lambda p, w=work, d=target["path"]: f"{d}/{shown(p, w)}")
                problems += [f"[{harness}] {p}" for p in build_problems + tree_problems]
                build_ok = not build_problems and not tree_problems
                problems += [f"[{harness}] {p}" for p in sync_harness(harness, target, work, out, args.check, build_ok)]
                if "manifest" in target:
                    manifest = out / target["path"] / target["manifest"]
                    problems += [f"[{harness}] {p}" for p in check_manifest(manifest, core_meta, lambda p: shown(p, out))]

    problems += sync_blocks(out, args.check, skills)

    if problems:
        print("\nProblemas encontrados:", file=sys.stderr)
        for p in problems:
            print(f"  - {p}", file=sys.stderr)
        if args.check:
            print("\nEdite core/ e rode: python3 scripts/sync_plugins.py", file=sys.stderr)
        return 1

    print("OK: core e plataformas consistentes." if args.check else "OK: sincronização concluída.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
