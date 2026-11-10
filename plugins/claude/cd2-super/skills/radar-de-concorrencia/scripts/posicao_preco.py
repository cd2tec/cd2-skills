#!/usr/bin/env python3
"""Calcula a posição de preço da loja frente aos concorrentes coletados.

Índice = preço da loja / preço do concorrente x 100. 100 é o mesmo preço, acima de 100 a loja está mais cara.
O índice do item usa a média dos concorrentes. Categoria, concorrente e total ponderam pela venda do item.
Só compara o mesmo tipo de preço e só coleta dentro da validade: o preço regular da loja está em preco,
o de oferta em preco_oferta.
Com mais de uma coleta do mesmo concorrente no item, vale a mais recente.

Uso:
  python3 posicao_preco.py --input coleta.json --data AAAA-MM-DD [--tipo regular] [--validade-dias 7]

Entrada: lista de objetos com produto, categoria, preco, venda, opcionalmente preco_oferta e loja, e coleta: uma lista
de objetos com concorrente, preco, data (AAAA-MM-DD) e tipo (regular ou oferta).
Saída: {"itens": [...], "categorias": [...], "concorrentes": [...], "total": {...}}.
Item fora da conta traz situacao sem_preco, sem_venda, sem_data, sem_coleta_do_tipo ou coleta_antiga.
Erro: código de saída 2 e {"errors": [...]} em português.
"""
import argparse
import json
import math
import sys
from datetime import date

TIPOS = ("regular", "oferta")
TOLERANCIA_IGUAL = 1.0


def _numero(valor) -> bool:
    return isinstance(valor, (int, float)) and not isinstance(valor, bool) and math.isfinite(valor)


def _validar_rotulo(linha: dict, campo: str) -> None:
    valor = linha.get(campo)
    if valor is not None and (isinstance(valor, bool) or not isinstance(valor, (str, int, float))):
        raise ValueError(f"'{campo}' precisa ser texto.")


def _valor(linha: dict, campo: str, nome: str) -> float:
    valor = linha.get(campo)
    if valor in (None, ""):
        return 0
    if not _numero(valor):
        raise ValueError(f"{nome}: '{campo}' precisa ser número.")
    return valor


def _ler_coleta(linha: dict, nome: str, data_ref: date) -> tuple[list[dict], int]:
    """Devolve os preços com data e quantos vieram sem data, que ficam fora da conta."""
    coleta = linha.get("coleta") or []
    if not isinstance(coleta, list):
        raise ValueError(f"{nome}: 'coleta' precisa ser uma lista.")
    lidos, sem_data = [], 0
    for preco in coleta:
        if not isinstance(preco, dict) or not str(preco.get("concorrente") or "").strip():
            raise ValueError(f"{nome}: todo preço coletado precisa ter 'concorrente'.")
        _validar_rotulo(preco, "concorrente")
        if not _numero(preco.get("preco")) or preco["preco"] <= 0:
            raise ValueError(f"{nome}: preço coletado de {preco['concorrente']} precisa ser maior que zero.")
        if preco.get("tipo") not in TIPOS:
            raise ValueError(f"{nome}: 'tipo' precisa ser regular ou oferta.")
        if preco.get("data") in (None, ""):
            sem_data += 1
            continue
        try:
            quando = date.fromisoformat(preco["data"])
        except (TypeError, ValueError):
            raise ValueError(f"{nome}: 'data' da coleta de {preco['concorrente']} precisa ser AAAA-MM-DD.") from None
        if quando > data_ref:
            raise ValueError(f"{nome}: a coleta de {preco['concorrente']} é posterior à data de referência.")
        lidos.append({**preco, "data": quando})
    return lidos, sem_data


def _mais_recentes(precos: list[dict]) -> dict:
    por_concorrente = {}
    for preco in sorted(precos, key=lambda p: p["data"]):
        por_concorrente[preco["concorrente"]] = preco["preco"]
    return por_concorrente


def _posicao(indice: float) -> str:
    if abs(indice - 100) <= TOLERANCIA_IGUAL:
        return "igual"
    return "acima" if indice > 100 else "abaixo"


def _fora(linha: dict, situacao: str) -> dict:
    vazios = ("indice", "media_concorrentes", "menor_preco", "menor_concorrente", "posicao")
    return {**{k: v for k, v in linha.items() if k != "coleta"}, "situacao": situacao, **{c: None for c in vazios}}


def _avaliar(linha, data_ref, tipo, validade_dias):
    """Devolve o item e os valores sem arredondar, que as somas ponderadas usam."""
    nome = linha["produto"]
    campo_preco = "preco" if tipo == "regular" else "preco_oferta"
    preco, venda = _valor(linha, campo_preco, nome), _valor(linha, "venda", nome)
    coleta, sem_data = _ler_coleta(linha, nome, data_ref)
    if preco <= 0:
        return _fora(linha, "sem_preco"), None
    if venda <= 0:
        return _fora(linha, "sem_venda"), None
    do_tipo = [c for c in coleta if c["tipo"] == tipo]
    if not do_tipo:
        return _fora(linha, "sem_data" if sem_data else "sem_coleta_do_tipo"), None
    validos = [c for c in do_tipo if (data_ref - c["data"]).days <= validade_dias]
    if not validos:
        return _fora(linha, "coleta_antiga"), None
    concorrentes = _mais_recentes(validos)
    media = sum(concorrentes.values()) / len(concorrentes)
    indice = preco / media * 100
    menor = min(concorrentes, key=concorrentes.get)
    item = {
        **{k: v for k, v in linha.items() if k != "coleta"},
        "situacao": "ok",
        "preco_comparado": preco,
        "indice": round(indice, 2),
        "media_concorrentes": round(media, 2),
        "menor_preco": concorrentes[menor],
        "menor_concorrente": menor,
        "posicao": _posicao(indice),
        "concorrentes": concorrentes,
    }
    return item, indice


def _ponderado(pares: list[tuple]) -> float | None:
    peso = sum(venda for _, venda in pares)
    return round(sum(indice * venda for indice, venda in pares) / peso, 2) if peso else None


def _contagem(itens: list[dict]) -> dict:
    return {p: sum(1 for i in itens if i["posicao"] == p) for p in ("acima", "igual", "abaixo")}


def _agrupar(comparados):
    grupos, por_concorrente = {}, {}
    for item, indice in comparados:
        grupos.setdefault(item.get("categoria") or "Sem categoria", []).append((item, indice))
        for nome, preco in item["concorrentes"].items():
            por_concorrente.setdefault(nome, []).append((item["preco_comparado"] / preco * 100, item["venda"]))
    categorias = [
        {
            "categoria": nome,
            "itens": len(lista),
            "venda": round(sum(i["venda"] for i, _ in lista), 2),
            "indice": _ponderado([(indice, i["venda"]) for i, indice in lista]),
            **_contagem([i for i, _ in lista]),
        }
        for nome, lista in grupos.items()
    ]
    concorrentes = [
        {"concorrente": nome, "itens": len(pares), "venda": round(sum(v for _, v in pares), 2), "indice": _ponderado(pares)}
        for nome, pares in por_concorrente.items()
    ]
    chave = lambda g: -g["venda"]
    return sorted(categorias, key=chave), sorted(concorrentes, key=chave)


def posicionar(coleta: list[dict], data_ref: date, tipo: str = "regular", validade_dias: int = 7) -> dict:
    if tipo not in TIPOS:
        raise ValueError("O tipo precisa ser regular ou oferta.")
    if not coleta:
        raise ValueError("A coleta está vazia.")
    vistos = set()
    for linha in coleta:
        if not isinstance(linha, dict) or not str(linha.get("produto") or "").strip():
            raise ValueError("Todo item precisa ter 'produto'.")
        for campo in ("produto", "loja", "categoria"):
            _validar_rotulo(linha, campo)
        chave = (linha["produto"], linha.get("loja"))
        if chave in vistos:
            raise ValueError(f"{linha['produto']}: item repetido na mesma loja.")
        vistos.add(chave)
    avaliados = [_avaliar(linha, data_ref, tipo, validade_dias) for linha in coleta]
    itens = [item for item, _ in avaliados]
    comparados = [(item, indice) for item, indice in avaliados if indice is not None]
    categorias, concorrentes = _agrupar(comparados)
    venda_comparada = round(sum(i["venda"] for i, _ in comparados), 2)
    venda_total = round(sum(max(_valor(l, "venda", l["produto"]), 0) for l in coleta), 2)
    total = {
        "itens_coletados": len(itens),
        "itens_comparados": len(comparados),
        "itens_fora": len(itens) - len(comparados),
        "venda_comparada": venda_comparada,
        "venda_total": venda_total,
        "cobertura_venda_pct": round(venda_comparada / venda_total * 100, 2) if venda_total else None,
        "indice": _ponderado([(indice, i["venda"]) for i, indice in comparados]),
        **_contagem([i for i, _ in comparados]),
    }
    return {"tipo": tipo, "itens": itens, "categorias": categorias, "concorrentes": concorrentes, "total": total}


def _falha(mensagem: str) -> int:
    print(json.dumps({"errors": [mensagem]}, ensure_ascii=False))
    return 2


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Posição de preço frente aos concorrentes coletados.")
    parser.add_argument("--input", required=True, help="JSON com os itens e a coleta de cada um")
    parser.add_argument("--data", required=True, help="Data de referência, AAAA-MM-DD")
    parser.add_argument("--tipo", default="regular", help="regular ou oferta")
    parser.add_argument("--validade-dias", type=int, default=7, help="Idade máxima da coleta, em dias")
    args = parser.parse_args(argv)
    try:
        with open(args.input, encoding="utf-8") as fh:
            coleta = json.load(fh)
        data_ref = date.fromisoformat(args.data)
    except (OSError, ValueError) as exc:
        return _falha(f"Não consegui ler a entrada: {exc}")
    if not isinstance(coleta, list):
        return _falha("A entrada precisa ser uma lista de objetos.")
    try:
        resultado = posicionar(coleta, data_ref, args.tipo, args.validade_dias)
    except ValueError as exc:
        return _falha(str(exc))
    print(json.dumps(resultado, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
