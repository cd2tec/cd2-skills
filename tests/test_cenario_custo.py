"""Conta do cenário de custo: margem e preço com e sem repasse."""
import importlib.util
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SCRIPT = ROOT / "core/cd2-super/skills/cenario-de-custo/scripts/cenario_custo.py"


def carregar():
    spec = importlib.util.spec_from_file_location("cenario_custo", SCRIPT)
    modulo = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(modulo)
    return modulo


BASE = {"produto": "Arroz 5 kg", "quantidade": 100, "preco": 10.0, "custo": 7.0}


class Cenarios(unittest.TestCase):
    def setUp(self):
        self.m = carregar()

    def um_item(self, variacao=10.0, **extra):
        return self.m.simular([{**BASE, **extra}], variacao)

    def test_custo_novo_e_margem_atual(self):
        item = self.um_item()["itens"][0]
        self.assertEqual(item["custo_novo"], 7.7)
        self.assertEqual(item["margem_atual_pct"], 30.0)
        self.assertEqual(item["situacao"], "ok")

    def test_sem_repasse_mantem_o_preco_e_perde_margem(self):
        c = self.um_item()["itens"][0]["cenarios"]["sem_repasse"]
        self.assertEqual(c["preco"], 10.0)
        self.assertEqual(c["margem_pct"], 23.0)
        self.assertEqual(c["contribuicao"], 230.0)

    def test_repasse_do_valor_mantem_os_reais(self):
        c = self.um_item()["itens"][0]["cenarios"]["repasse_valor"]
        self.assertEqual(c["preco"], 10.7)
        self.assertEqual(c["contribuicao"], 300.0)
        self.assertEqual(c["margem_pct"], 28.04)

    def test_manter_a_margem_recompoe_o_percentual(self):
        c = self.um_item()["itens"][0]["cenarios"]["mantem_margem"]
        self.assertEqual(c["preco"], 11.0)
        self.assertEqual(c["margem_pct"], 30.0)
        self.assertEqual(c["contribuicao"], 330.0)

    def test_posicao_frente_ao_concorrente_em_cada_cenario(self):
        c = self.um_item(concorrente=10.5)["itens"][0]["cenarios"]
        self.assertEqual(c["sem_repasse"]["dif_concorrente_pct"], -4.76)
        self.assertEqual(c["repasse_valor"]["dif_concorrente_pct"], 1.9)
        self.assertEqual(c["mantem_margem"]["dif_concorrente_pct"], 4.76)

    def test_sem_concorrente_nao_inventa_posicao(self):
        c = self.um_item()["itens"][0]["cenarios"]["sem_repasse"]
        self.assertIsNone(c["dif_concorrente_pct"])

    def test_total_soma_as_linhas_e_mostra_a_perda(self):
        linhas = [BASE, {"produto": "Feijão 1 kg", "quantidade": 50, "preco": 8.0, "custo": 6.0}]
        total = self.m.simular(linhas, 10.0)["total"]
        self.assertEqual(total["atual"]["venda"], 1400.0)
        self.assertEqual(total["atual"]["contribuicao"], 400.0)
        self.assertEqual(total["atual"]["margem_pct"], 28.57)
        self.assertEqual(total["sem_repasse"]["contribuicao"], 300.0)
        self.assertEqual(total["sem_repasse"]["variacao_contribuicao"], -100.0)
        self.assertEqual(total["itens_com_base"], 2)

    def test_item_sem_base_fica_de_fora_e_e_contado(self):
        linhas = [BASE, {"produto": "Sem custo", "quantidade": 10, "preco": 5.0, "custo": 0}]
        r = self.m.simular(linhas, 10.0)
        self.assertEqual(r["itens"][1]["situacao"], "sem_base")
        self.assertNotIn("cenarios", r["itens"][1])
        self.assertEqual(r["total"]["itens_sem_base"], 1)
        self.assertEqual(r["total"]["atual"]["venda"], 1000.0)

    def test_nenhum_item_com_base_nao_divide_por_zero(self):
        r = self.m.simular([{"produto": "X", "quantidade": 0, "preco": 5.0, "custo": 3.0}], 10.0)
        self.assertEqual(r["total"]["itens_com_base"], 0)
        self.assertIsNone(r["total"]["atual"])

    def test_venda_tao_pequena_que_arredonda_para_zero_fica_sem_base(self):
        r = self.m.simular([{"produto": "X", "quantidade": 0.001, "preco": 1.0, "custo": 0.5}], 10.0)
        self.assertEqual(r["itens"][0]["situacao"], "sem_base")
        self.assertIsNone(r["total"]["atual"])

    def test_concorrente_zero_e_o_mesmo_que_nao_ter(self):
        c = self.um_item(concorrente=0)["itens"][0]["cenarios"]["sem_repasse"]
        self.assertIsNone(c["dif_concorrente_pct"])

    def test_rotulo_que_nao_e_texto_e_erro_em_portugues(self):
        with self.assertRaises(ValueError):
            self.m.simular([{**BASE, "loja": ["1"]}], 10.0)

    def test_venda_menos_custo_fecha_com_a_contribuicao(self):
        linhas = [{"produto": f"P{i}", "quantidade": 3.37 + i, "preco": 1.99 + i * 0.13, "custo": 1.41 + i * 0.07} for i in range(25)]
        r = self.m.simular(linhas, 7.3)
        for item in r["itens"]:
            self.assertEqual(round(item["venda"] - item["custo_total"], 2), item["contribuicao"])
        atual = r["total"]["atual"]
        self.assertEqual(round(atual["venda"] - atual["custo"], 2), atual["contribuicao"])

    def test_queda_de_custo_tambem_funciona(self):
        item = self.um_item(variacao=-10.0)["itens"][0]
        self.assertEqual(item["custo_novo"], 6.3)
        self.assertEqual(item["cenarios"]["sem_repasse"]["margem_pct"], 37.0)

    def test_recusa_entrada_invalida(self):
        for linhas, variacao in (
            ([], 10.0),
            ([{**BASE, "preco": float("nan")}], 10.0),
            ([{**BASE, "custo": True}], 10.0),
            ([BASE], -100.0),
            ([BASE], float("inf")),
        ):
            with self.assertRaises(ValueError):
                self.m.simular(linhas, variacao)

    def test_produto_repetido_na_mesma_loja_e_erro(self):
        with self.assertRaises(ValueError):
            self.m.simular([BASE, BASE], 10.0)

    def test_mesmo_produto_em_lojas_diferentes_e_aceito(self):
        r = self.m.simular([{**BASE, "loja": "1"}, {**BASE, "loja": "2"}], 10.0)
        self.assertEqual(r["total"]["itens_com_base"], 2)


class LinhaDeComando(unittest.TestCase):
    def rodar(self, entrada, *args):
        with tempfile.TemporaryDirectory() as pasta:
            caminho = Path(pasta) / "itens.json"
            caminho.write_text(entrada, encoding="utf-8")
            return subprocess.run(
                [sys.executable, str(SCRIPT), "--input", str(caminho), *args], capture_output=True, text=True
            )

    def test_saida_em_json(self):
        r = self.rodar(json.dumps([BASE]), "--variacao-pct", "10")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(json.loads(r.stdout)["variacao_pct"], 10.0)

    def test_erro_sai_com_codigo_2_em_portugues(self):
        r = self.rodar("[]", "--variacao-pct", "10")
        self.assertEqual(r.returncode, 2)
        self.assertIn("errors", json.loads(r.stdout))

    def test_json_quebrado_sai_com_codigo_2(self):
        r = self.rodar("{", "--variacao-pct", "10")
        self.assertEqual(r.returncode, 2)


if __name__ == "__main__":
    unittest.main()
