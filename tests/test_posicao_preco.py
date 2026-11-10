"""Conta do radar de concorrência: índice de preço por item, categoria e concorrente."""
import importlib.util
import json
import subprocess
import sys
import tempfile
import unittest
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SCRIPT = ROOT / "core/cd2-super/skills/radar-de-concorrencia/scripts/posicao_preco.py"
HOJE = date(2026, 11, 9)


def carregar():
    spec = importlib.util.spec_from_file_location("posicao_preco", SCRIPT)
    modulo = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(modulo)
    return modulo


def preco(nome, valor, data="2026-11-08", tipo="regular"):
    return {"concorrente": nome, "preco": valor, "data": data, "tipo": tipo}


COLETA = [
    {"produto": "A", "categoria": "Mercearia", "preco": 10.0, "venda": 1000.0,
     "coleta": [preco("X", 9.5), preco("Y", 10.5, "2026-11-07")]},
    {"produto": "B", "categoria": "Mercearia", "preco": 12.0, "venda": 3000.0, "coleta": [preco("X", 10.0)]},
    {"produto": "C", "categoria": "Limpeza", "preco": 5.0, "venda": 500.0, "coleta": [preco("X", 5.5)]},
    {"produto": "D", "categoria": "Limpeza", "preco": 8.0, "venda": 200.0, "coleta": [preco("X", 8.0, "2026-10-01")]},
    {"produto": "E", "categoria": "Limpeza", "preco": 4.0, "preco_oferta": 3.0, "venda": 100.0, "coleta": [preco("X", 2.5, tipo="oferta")]},
]


class Posicao(unittest.TestCase):
    def setUp(self):
        self.m = carregar()
        self.r = self.m.posicionar(COLETA, HOJE)

    def item(self, nome):
        return next(i for i in self.r["itens"] if i["produto"] == nome)

    def categoria(self, nome):
        return next(c for c in self.r["categorias"] if c["categoria"] == nome)

    def concorrente(self, nome):
        return next(c for c in self.r["concorrentes"] if c["concorrente"] == nome)

    def test_indice_do_item_usa_a_media_dos_concorrentes(self):
        self.assertEqual(self.item("A")["media_concorrentes"], 10.0)
        self.assertEqual(self.item("A")["indice"], 100.0)
        self.assertEqual(self.item("A")["posicao"], "igual")

    def test_menor_preco_e_quem_cobra(self):
        self.assertEqual(self.item("A")["menor_preco"], 9.5)
        self.assertEqual(self.item("A")["menor_concorrente"], "X")

    def test_posicao_acima_e_abaixo(self):
        self.assertEqual(self.item("B")["indice"], 120.0)
        self.assertEqual(self.item("B")["posicao"], "acima")
        self.assertEqual(self.item("C")["indice"], 90.91)
        self.assertEqual(self.item("C")["posicao"], "abaixo")

    def test_coleta_antiga_fica_de_fora_e_diz_o_motivo(self):
        self.assertEqual(self.item("D")["situacao"], "coleta_antiga")
        self.assertIsNone(self.item("D")["indice"])

    def test_oferta_nao_se_compara_com_preco_regular(self):
        self.assertEqual(self.item("E")["situacao"], "sem_coleta_do_tipo")

    def test_comparar_so_oferta_quando_pedido(self):
        r = self.m.posicionar(COLETA, HOJE, tipo="oferta")
        item = next(i for i in r["itens"] if i["produto"] == "E")
        self.assertEqual(item["indice"], 120.0)
        self.assertEqual(r["total"]["itens_comparados"], 1)

    def test_oferta_nunca_usa_o_preco_regular_da_loja(self):
        r = self.m.posicionar(COLETA, HOJE, tipo="oferta")
        self.assertEqual(next(i for i in r["itens"] if i["produto"] == "A")["situacao"], "sem_preco")

    def test_coleta_sem_data_fica_de_fora_e_e_contada(self):
        sem_data = {"concorrente": "X", "preco": 9.0, "tipo": "regular"}
        r = self.m.posicionar([{**COLETA[1], "coleta": [sem_data]}], HOJE)
        self.assertEqual(r["itens"][0]["situacao"], "sem_data")
        self.assertEqual(r["total"]["itens_fora"], 1)

    def test_rotulo_que_nao_e_texto_e_erro_em_portugues(self):
        for coleta in ([{**COLETA[0], "loja": ["1"]}], [{**COLETA[0], "categoria": ["a"]}],
                       [{**COLETA[0], "coleta": [preco(["X"], 9.0)]}]):
            with self.assertRaises(ValueError):
                self.m.posicionar(coleta, HOJE)

    def test_categoria_pondera_pela_venda(self):
        self.assertEqual(self.categoria("Mercearia")["indice"], 115.0)
        self.assertEqual(self.categoria("Mercearia")["venda"], 4000.0)
        self.assertEqual(self.categoria("Limpeza")["indice"], 90.91)
        self.assertEqual(self.categoria("Limpeza")["itens"], 1)

    def test_indice_por_concorrente(self):
        self.assertEqual(self.concorrente("X")["indice"], 113.49)
        self.assertEqual(self.concorrente("X")["itens"], 3)
        self.assertEqual(self.concorrente("Y")["indice"], 95.24)

    def test_total_fecha_com_a_coleta(self):
        t = self.r["total"]
        self.assertEqual(t["itens_coletados"], 5)
        self.assertEqual(t["itens_comparados"], 3)
        self.assertEqual(t["itens_fora"], 2)
        self.assertEqual(t["venda_comparada"], 4500.0)
        self.assertEqual(t["venda_total"], 4800.0)
        self.assertEqual(t["cobertura_venda_pct"], 93.75)
        self.assertEqual(t["indice"], 112.32)
        self.assertEqual((t["acima"], t["igual"], t["abaixo"]), (1, 1, 1))

    def test_validade_pode_ser_mudada(self):
        r = self.m.posicionar(COLETA, HOJE, validade_dias=60)
        self.assertEqual(next(i for i in r["itens"] if i["produto"] == "D")["situacao"], "ok")

    def test_item_sem_venda_nao_pesa(self):
        r = self.m.posicionar([{**COLETA[0], "venda": 0}], HOJE)
        self.assertEqual(r["itens"][0]["situacao"], "sem_venda")
        self.assertIsNone(r["total"]["indice"])

    def test_item_sem_preco_nosso_fica_de_fora(self):
        r = self.m.posicionar([{**COLETA[0], "preco": 0}], HOJE)
        self.assertEqual(r["itens"][0]["situacao"], "sem_preco")

    def test_recusa_entrada_invalida(self):
        for coleta in (
            [],
            [{**COLETA[0], "venda": float("nan")}],
            [{**COLETA[0], "coleta": [preco("X", -1)]}],
            [{**COLETA[0], "coleta": [preco("X", 9.0, "ontem")]}],
            [{**COLETA[0], "coleta": [preco("X", 9.0, "2026-11-10")]}],
            [{**COLETA[0], "coleta": [preco("X", 9.0, tipo="promo")]}],
            [COLETA[0], COLETA[0]],
        ):
            with self.assertRaises(ValueError):
                self.m.posicionar(coleta, HOJE)


class LinhaDeComando(unittest.TestCase):
    def rodar(self, entrada, *args):
        with tempfile.TemporaryDirectory() as pasta:
            caminho = Path(pasta) / "coleta.json"
            caminho.write_text(entrada, encoding="utf-8")
            return subprocess.run(
                [sys.executable, str(SCRIPT), "--input", str(caminho), *args], capture_output=True, text=True
            )

    def test_saida_em_json(self):
        r = self.rodar(json.dumps(COLETA), "--data", "2026-11-09")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(json.loads(r.stdout)["total"]["itens_comparados"], 3)

    def test_erro_sai_com_codigo_2(self):
        r = self.rodar("[]", "--data", "2026-11-09")
        self.assertEqual(r.returncode, 2)
        self.assertIn("errors", json.loads(r.stdout))


if __name__ == "__main__":
    unittest.main()
