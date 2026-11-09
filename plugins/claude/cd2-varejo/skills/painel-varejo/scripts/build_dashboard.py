#!/usr/bin/env python3
"""Monta o HTML do painel de varejo a partir de um config JSON e do template.

Uso:
  python3 build_dashboard.py config.json saida.html

Valida a estrutura do config antes de gerar, para que erros de formato
aparecam aqui e nao como uma secao vazia na pagina entregue.

O campo `origem` e obrigatorio (banco, outro-mcp, arquivo ou digitado) e
decide o texto do rodape e a linha de fonte: um painel feito de arquivo nunca
diz que foi conferido no banco. Arquivo e digitado so tem modo snapshot.
"""
import datetime
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import brand  # noqa: E402  (kit de marca, vem de core/<plugin>/shared/scripts)

TEMPLATE = Path(__file__).resolve().parent.parent / "assets" / "dashboard-template.html"
TIPOS = {"kpis", "score", "linha", "barras", "heatmap", "tabela"}
FORMATOS = {None, "moeda", "inteiro", "decimal", "pct", "dias"}
COM_CONEXAO = ("banco", "outro-mcp")


def erro(msgs, texto):
    msgs.append(texto)


def validar(cfg):
    msgs = []
    modo = cfg.get("modo")
    origem = cfg.get("origem")
    if modo not in ("snapshot", "live"):
        erro(msgs, "modo deve ser 'snapshot' ou 'live'")
    if not origem:
        erro(msgs, f"falta origem: use {', '.join(brand.ORIGENS)}")
    elif not isinstance(origem, str) or origem not in brand.ORIGENS:
        erro(msgs, f"origem '{origem}' invalida: use {', '.join(brand.ORIGENS)}")
        origem = None
    if origem and origem not in COM_CONEXAO:
        if modo == "live":
            erro(msgs, f"modo ao vivo exige conexão com o banco (origem banco ou outro-mcp); com origem '{origem}' entregue só o snapshot")
        if not (cfg.get("fonte") or {}).get("nome"):
            erro(msgs, "fonte.nome e obrigatorio quando a origem e arquivo ou digitado (nome do arquivo ou 'dados informados')")
    elif origem and not all((cfg.get("fonte") or {}).get(k) for k in ("banco", "engine", "conector")):
        erro(msgs, "fonte precisa de banco, engine e conector quando a origem e banco ou outro-mcp")
    if not cfg.get("titulo"):
        erro(msgs, "titulo e obrigatorio")
    if cfg.get("veredito") is not None:
        if not (cfg["veredito"] or {}).get("titulo"):
            erro(msgs, "veredito precisa de titulo")
        if modo == "live":
            erro(msgs, "veredito e texto fixo: no modo ao vivo ele ficaria defasado, retire do config")
    if modo == "live":
        live = cfg.get("live") or {}
        for k in ("server", "tool"):
            if not live.get(k):
                erro(msgs, f"live.{k} e obrigatorio no modo ao vivo")
    ids = set()
    for i, sec in enumerate(cfg.get("secoes") or []):
        nome = sec.get("id") or f"secoes[{i}]"
        if not sec.get("id"):
            erro(msgs, f"{nome}: falta id")
        elif sec["id"] in ids:
            erro(msgs, f"{nome}: id repetido")
        ids.add(sec.get("id"))
        if sec.get("tipo") not in TIPOS:
            erro(msgs, f"{nome}: tipo '{sec.get('tipo')}' invalido ({', '.join(sorted(TIPOS))})")
        if sec.get("formato") not in FORMATOS:
            erro(msgs, f"{nome}: formato '{sec.get('formato')}' invalido")
        if modo == "live" and not sec.get("sql"):
            erro(msgs, f"{nome}: modo ao vivo exige sql em toda secao")
        if modo == "snapshot" and not isinstance(sec.get("dados"), list):
            erro(msgs, f"{nome}: modo snapshot exige dados (lista de linhas)")
        if modo == "live" and sec.get("dados"):
            erro(msgs, f"{nome}: no modo ao vivo nao embuta dados; a pagina busca no banco")
        if sec.get("tipo") == "score":
            comps = sec.get("componentes") or []
            if not comps:
                erro(msgs, f"{nome}: score sem componentes")
            for c in comps:
                if not all(k in c for k in ("campo", "rotulo", "peso", "ruim", "bom")):
                    erro(msgs, f"{nome}: componente sem campo/rotulo/peso/ruim/bom: {c}")
                elif c["ruim"] == c["bom"]:
                    erro(msgs, f"{nome}: componente {c['campo']} com ruim == bom")
        if sec.get("tipo") == "kpis" and not sec.get("cards"):
            erro(msgs, f"{nome}: kpis sem cards")
        if sec.get("tipo") == "tabela" and not sec.get("colunas"):
            erro(msgs, f"{nome}: tabela sem colunas")
    for nivel in [x.get("nivel") for x in cfg.get("leitura") or []]:
        if nivel not in ("critico", "atencao", "bom", "info"):
            erro(msgs, f"leitura com nivel invalido: {nivel}")
    return msgs


def fonte_texto(cfg):
    """Linha de fonte do painel. Arquivo e digitado dizem que a conferencia e so contra o que a pessoa informou."""
    fonte = cfg.get("fonte") or {}
    if cfg["origem"] == "arquivo":
        return f"Fonte: arquivo {fonte['nome']}. Conferido só contra o arquivo, não contra o sistema de origem."
    if cfg["origem"] == "digitado":
        return f"Fonte: {fonte['nome']}. Conferido só contra o que foi informado, não contra o sistema de origem."
    banco = ", ".join(x for x in (fonte["banco"], fonte["engine"], "via " + fonte["conector"]) if x)
    return f"Fonte: {banco}. Consultas somente leitura."


def data_do_rodape(cfg):
    """Snapshot: a data de geracao. Ao vivo: o texto fixo diz que vale a cada abertura da pagina."""
    if cfg["modo"] == "live":
        return "cada abertura da página"
    gerado = str(cfg.get("geradoEm") or "")[:10]
    return brand.data_br(gerado) if gerado else brand.data_br(datetime.date.today().isoformat())


def main():
    if len(sys.argv) != 3:
        print(__doc__)
        sys.exit(2)
    cfg = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
    msgs = validar(cfg)
    if msgs:
        print("Config invalido:")
        for m in msgs:
            print(" -", m)
        sys.exit(1)
    html = TEMPLATE.read_text(encoding="utf-8")
    titulo = (cfg.get("titulo") or "Painel do varejo").replace("<", "").replace(">", "")
    if cfg["modo"] == "snapshot":
        ini, fim = html.find("/*LIVE-START*/"), html.find("/*LIVE-END*/")
        if ini < 0 or fim < 0:
            print("Template sem marcadores LIVE-START/LIVE-END")
            sys.exit(1)
        html = html[:ini] + html[fim + len("/*LIVE-END*/"):]
    payload = json.dumps({**cfg, "fonteTexto": fonte_texto(cfg)}, ensure_ascii=False).replace("</", "<\\/")
    valores = {"__FONT_FACE__": brand.font_face(), "__TOKENS_CSS__": brand.tokens_css(),
               "__LOGO__": brand.logo_html(),
               "__FOOTER__": brand.footer_dados_html(cfg["origem"], data_do_rodape(cfg)),
               "__DASH_TITLE__": titulo, "__DASH_CONFIG__": payload}
    # Uma passada so: texto vindo do config (titulo, rede, rotulos) nunca vira marcador.
    html = re.sub("|".join(valores), lambda m: valores[m.group(0)], html)
    Path(sys.argv[2]).write_text(html, encoding="utf-8")
    n = len(cfg.get("secoes") or [])
    print(f"OK: {sys.argv[2]} ({n} secoes, modo {cfg['modo']}, origem {cfg['origem']}, {len(html)//1024} KB)")


if __name__ == "__main__":
    main()
