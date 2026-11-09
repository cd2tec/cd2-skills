#!/usr/bin/env python3
"""Compara a venda acumulada do mês com a meta proporcional aos dias corridos.

Meta até a data = meta do mês x dias corridos até a data de referência / dias do mês.

Uso:
  python3 meta_proporcional.py --input metas.json --data AAAA-MM-DD

Entrada: lista de objetos com loja, mes (AAAA-MM), meta e acumulado.
Saída: a mesma lista, com meta_ate_a_data, diferenca, atingimento_pct e situacao (ok ou sem_meta).
Loja sem meta nunca vira meta zero: sai com situacao sem_meta e sem números.
Erro: código de saída 2 e {"errors": [...]} em português.
"""
import argparse
import calendar
import json
import sys
from datetime import date


def meta_ate_a_data(meta_mes: float, data_ref: date) -> float:
    dias_do_mes = calendar.monthrange(data_ref.year, data_ref.month)[1]
    return round(meta_mes * data_ref.day / dias_do_mes, 2)


def _numero(valor) -> bool:
    return isinstance(valor, (int, float)) and not isinstance(valor, bool)


def _comparar_linha(linha: dict, data_ref: date) -> dict:
    loja = linha.get("loja", "sem nome")
    if linha.get("mes") != data_ref.strftime("%Y-%m"):
        raise ValueError(f"{loja}: a meta é do mês {linha.get('mes')} e a data de referência é {data_ref.isoformat()}.")
    meta, acumulado = linha.get("meta"), linha.get("acumulado")
    if not _numero(acumulado):
        raise ValueError(f"{loja}: 'acumulado' precisa ser número.")
    if meta in (None, ""):
        meta = 0
    if not _numero(meta):
        raise ValueError(f"{loja}: 'meta' precisa ser número.")
    if meta <= 0:
        return {**linha, "meta_ate_a_data": None, "diferenca": None, "atingimento_pct": None, "situacao": "sem_meta"}
    proporcional = meta_ate_a_data(meta, data_ref)
    return {
        **linha,
        "meta_ate_a_data": proporcional,
        "diferenca": round(acumulado - proporcional, 2),
        "atingimento_pct": round(acumulado / proporcional * 100, 1),
        "situacao": "ok",
    }


def comparar(linhas: list[dict], data_ref: date) -> list[dict]:
    return [_comparar_linha(linha, data_ref) for linha in linhas]


def _falha(mensagem: str) -> int:
    print(json.dumps({"errors": [mensagem]}, ensure_ascii=False))
    return 2


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Meta proporcional aos dias corridos.")
    parser.add_argument("--input", required=True, help="JSON com loja, mes, meta e acumulado")
    parser.add_argument("--data", required=True, help="Data de referência, AAAA-MM-DD")
    args = parser.parse_args(argv)
    try:
        with open(args.input, encoding="utf-8") as fh:
            linhas = json.load(fh)
        data_ref = date.fromisoformat(args.data)
    except (OSError, ValueError) as exc:
        return _falha(f"Não consegui ler a entrada: {exc}")
    if not isinstance(linhas, list) or not all(isinstance(l, dict) for l in linhas):
        return _falha("A entrada precisa ser uma lista de objetos.")
    try:
        resultado = comparar(linhas, data_ref)
    except ValueError as exc:
        return _falha(str(exc))
    print(json.dumps(resultado, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
