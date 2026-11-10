#!/usr/bin/env python3
"""Simula uma variação de custo: margem e preço com e sem repasse.

Três cenários, sempre com o volume igual ao do período, porque a elasticidade não está no dado:
  sem_repasse    o preço não muda
  repasse_valor  o preço sobe o mesmo valor em reais que o custo
  mantem_margem  o preço sobe até recompor a margem percentual atual

Uso:
  python3 cenario_custo.py --input itens.json --variacao-pct 8

Entrada: lista de objetos com produto, quantidade, preco e custo, e, se houver, loja e concorrente.
Saída: {"variacao_pct": ..., "itens": [...], "total": {...}}. Item sem quantidade, preço ou custo positivos
sai com situacao sem_base, fica fora do total e é contado. O total soma as linhas já arredondadas.
Erro: código de saída 2 e {"errors": [...]} em português.
"""
import argparse
import json
import math
import sys

CENARIOS = ("sem_repasse", "repasse_valor", "mantem_margem")


def _numero(valor) -> bool:
    return isinstance(valor, (int, float)) and not isinstance(valor, bool) and math.isfinite(valor)


def _validar_rotulo(linha: dict, campo: str) -> None:
    valor = linha.get(campo)
    if valor is not None and (isinstance(valor, bool) or not isinstance(valor, (str, int, float))):
        raise ValueError(f"'{campo}' precisa ser texto.")


def _campo(linha: dict, campo: str, nome: str) -> float:
    valor = linha.get(campo)
    if valor in (None, ""):
        return 0
    if not _numero(valor):
        raise ValueError(f"{nome}: '{campo}' precisa ser número.")
    return valor


def _margem(preco: float, custo: float) -> float:
    return round((preco - custo) / preco * 100, 2)


def _diferenca(preco: float, concorrente):
    return None if concorrente is None else round((preco - concorrente) / concorrente * 100, 2)


def _cenario(preco: float, custo: float, quantidade: float, concorrente) -> dict:
    venda = round(preco * quantidade, 2)
    return {
        "preco": preco,
        "venda": venda,
        "contribuicao": round(venda - round(custo * quantidade, 2), 2),
        "margem_pct": _margem(preco, custo),
        "dif_concorrente_pct": _diferenca(preco, concorrente),
    }


def _simular_linha(linha: dict, fator: float) -> dict:
    nome = linha["produto"]
    quantidade, preco, custo = (_campo(linha, c, nome) for c in ("quantidade", "preco", "custo"))
    concorrente = linha.get("concorrente")
    if concorrente in (None, "", 0):
        concorrente = None
    elif not _numero(concorrente) or concorrente <= 0:
        raise ValueError(f"{nome}: 'concorrente' precisa ser um preço maior que zero.")
    sem_base = {**linha, "situacao": "sem_base"}
    if quantidade <= 0 or preco <= 0 or custo <= 0:
        return sem_base
    custo_novo = round(custo * fator, 4)
    margem = (preco - custo) / preco
    precos = {
        "sem_repasse": preco,
        "repasse_valor": round(preco + custo_novo - custo, 2),
        "mantem_margem": round(custo_novo / (1 - margem), 2),
    }
    if any(p <= 0 or round(p * quantidade, 2) <= 0 for p in precos.values()):
        return sem_base
    venda, custo_total = round(preco * quantidade, 2), round(custo * quantidade, 2)
    return {
        **linha,
        "situacao": "ok",
        "custo_novo": custo_novo,
        "venda": venda,
        "custo_total": custo_total,
        "contribuicao": round(venda - custo_total, 2),
        "margem_atual_pct": _margem(preco, custo),
        "dif_concorrente_atual_pct": _diferenca(preco, concorrente),
        "cenarios": {nome_c: _cenario(p, custo_novo, quantidade, concorrente) for nome_c, p in precos.items()},
    }


def _total(itens: list[dict]) -> dict:
    ok = [i for i in itens if i["situacao"] == "ok"]
    total = {"itens_com_base": len(ok), "itens_sem_base": len(itens) - len(ok), "atual": None}
    total.update({c: None for c in CENARIOS})
    if not ok:
        return total
    venda = round(sum(i["venda"] for i in ok), 2)
    contribuicao = round(sum(i["contribuicao"] for i in ok), 2)
    total["atual"] = {
        "venda": venda,
        "custo": round(sum(i["custo_total"] for i in ok), 2),
        "contribuicao": contribuicao,
        "margem_pct": round(contribuicao / venda * 100, 2),
    }
    for nome in CENARIOS:
        venda_c = round(sum(i["cenarios"][nome]["venda"] for i in ok), 2)
        contribuicao_c = round(sum(i["cenarios"][nome]["contribuicao"] for i in ok), 2)
        total[nome] = {
            "venda": venda_c,
            "contribuicao": contribuicao_c,
            "margem_pct": round(contribuicao_c / venda_c * 100, 2),
            "variacao_contribuicao": round(contribuicao_c - contribuicao, 2),
        }
    return total


def simular(linhas: list[dict], variacao_pct: float) -> dict:
    if not _numero(variacao_pct) or variacao_pct <= -100:
        raise ValueError("A variação precisa ser um número maior que -100.")
    if not linhas:
        raise ValueError("A lista de itens está vazia.")
    vistos = set()
    for linha in linhas:
        if not isinstance(linha, dict) or not str(linha.get("produto") or "").strip():
            raise ValueError("Todo item precisa ter 'produto'.")
        _validar_rotulo(linha, "produto")
        _validar_rotulo(linha, "loja")
        chave = (linha["produto"], linha.get("loja"))
        if chave in vistos:
            raise ValueError(f"{linha['produto']}: item repetido na mesma loja.")
        vistos.add(chave)
    itens = [_simular_linha(linha, 1 + variacao_pct / 100) for linha in linhas]
    return {"variacao_pct": variacao_pct, "itens": itens, "total": _total(itens)}


def _falha(mensagem: str) -> int:
    print(json.dumps({"errors": [mensagem]}, ensure_ascii=False))
    return 2


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Simula uma variação de custo, com e sem repasse.")
    parser.add_argument("--input", required=True, help="JSON com produto, quantidade, preco e custo")
    parser.add_argument("--variacao-pct", required=True, type=float, help="Variação do custo em %%, como 8")
    args = parser.parse_args(argv)
    try:
        with open(args.input, encoding="utf-8") as fh:
            linhas = json.load(fh)
    except (OSError, ValueError) as exc:
        return _falha(f"Não consegui ler a entrada: {exc}")
    if not isinstance(linhas, list):
        return _falha("A entrada precisa ser uma lista de objetos.")
    try:
        resultado = simular(linhas, args.variacao_pct)
    except ValueError as exc:
        return _falha(str(exc))
    print(json.dumps(resultado, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
