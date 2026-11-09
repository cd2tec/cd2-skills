"""Conta da meta proporcional aos dias corridos, do briefing do dia."""
import csv
import importlib.util
import io
import json
import tempfile
import unittest
from contextlib import redirect_stdout
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SKILL = ROOT / "core/cd2-super/skills/briefing-do-dia"
_spec = importlib.util.spec_from_file_location("meta_proporcional", SKILL / "scripts/meta_proporcional.py")
mp = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(mp)

NOV8 = date(2026, 11, 8)


def linha(**extra):
    return {"loja": "Loja 1", "mes": "2026-11", "meta": 300000, "acumulado": 76000, **extra}


def cli(linhas, data="2026-11-08"):
    with tempfile.TemporaryDirectory() as tmp:
        entrada = Path(tmp) / "e.json"
        entrada.write_text(json.dumps(linhas), encoding="utf-8")
        saida = io.StringIO()
        with redirect_stdout(saida):
            codigo = mp.main(["--input", str(entrada), "--data", data])
    return codigo, saida.getvalue()


class MetaProporcional(unittest.TestCase):
    def test_proporcional_novembro(self):
        self.assertEqual(mp.meta_ate_a_data(300000, NOV8), 80000.0)

    def test_fevereiro_bissexto(self):
        self.assertEqual(mp.meta_ate_a_data(290000, date(2028, 2, 29)), 290000.0)

    def test_comparar(self):
        r = mp.comparar([linha()], NOV8)[0]
        self.assertEqual(r["meta_ate_a_data"], 80000.0)
        self.assertEqual(r["diferenca"], -4000.0)
        self.assertEqual(r["atingimento_pct"], 95.0)
        self.assertEqual(r["situacao"], "ok")

    def test_meta_zero(self):
        r = mp.comparar([linha(meta=0)], NOV8)[0]
        self.assertIsNone(r["atingimento_pct"])
        self.assertEqual(r["situacao"], "sem_meta")

    def test_meta_ausente(self):
        for vazio in (None, ""):
            r = mp.comparar([linha(meta=vazio)], NOV8)[0]
            self.assertEqual(r["situacao"], "sem_meta", vazio)
            self.assertIsNone(r["meta_ate_a_data"], vazio)
            self.assertIsNone(r["diferenca"], vazio)

    def test_data_fora_do_mes(self):
        codigo, saida = cli([linha(mes="2026-10", loja="Loja Centro")])
        self.assertEqual(codigo, 2)
        self.assertIn("Loja Centro", json.loads(saida)["errors"][0])

    def test_meta_que_nao_e_numero_recusa(self):
        codigo, saida = cli([linha(meta="muita")])
        self.assertEqual(codigo, 2)
        self.assertIn("Loja 1", saida)

    def test_cli_devolve_json(self):
        codigo, saida = cli([linha()])
        self.assertEqual(codigo, 0)
        self.assertEqual(json.loads(saida)["lojas"][0]["atingimento_pct"], 95.0)

    def test_loja_sem_meta_e_sem_mes_nao_derruba_as_outras(self):
        codigo, saida = cli([linha(), {"loja": "L9", "acumulado": 10}])
        self.assertEqual(codigo, 0)
        lojas = json.loads(saida)["lojas"]
        self.assertEqual(lojas[0]["situacao"], "ok")
        self.assertEqual(lojas[1]["situacao"], "sem_meta")

    def test_total_da_rede_deixa_fora_quem_nao_tem_meta(self):
        linhas = [linha(), linha(loja="Loja 2", meta=150000, acumulado=44000), linha(loja="Loja 3", meta=None, acumulado=9000)]
        total = mp.total_da_rede(mp.comparar(linhas, NOV8))
        self.assertEqual(total["acumulado"], 120000.0)
        self.assertEqual(total["meta_ate_a_data"], 120000.0)
        self.assertEqual(total["diferenca"], 0.0)
        self.assertEqual(total["atingimento_pct"], 100.0)
        self.assertEqual(total["lojas_com_meta"], 2)
        self.assertEqual(total["lojas_sem_meta"], 1)

    def test_total_sem_nenhuma_meta(self):
        total = mp.total_da_rede(mp.comparar([linha(meta=None)], NOV8))
        self.assertIsNone(total["atingimento_pct"])
        self.assertEqual(total["lojas_com_meta"], 0)

    def test_modelo_metas_tem_colunas(self):
        with (SKILL / "assets/modelo-metas.csv").open(encoding="utf-8") as fh:
            self.assertEqual(next(csv.reader(fh)), ["loja", "mes", "meta_venda"])


if __name__ == "__main__":
    unittest.main()
