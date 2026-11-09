"""Regras do tipo rotina: kit, escrita no ERP, conteúdo externo e o que cada rotina precisa declarar."""
import json
import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CORE = ROOT / "core/cd2-super"
KIT = CORE / "kits/rotina/references"
ESCRITA_SQL = re.compile(
    r"\b(INSERT\s+INTO|UPDATE\s+\w+\s+SET|DELETE\s+FROM|MERGE\s+INTO|DROP\s+TABLE|ALTER\s+TABLE)\b|atualizar no banco", re.I
)
ARQUIVOS_KIT = ("regras-rotina.md", "fluxo-rotina.md", "conectores.md", "perfil-da-operacao.md", "acoes.md")


def texto_kit(nome):
    return (KIT / nome).read_text(encoding="utf-8")


def rotinas_no_skills_json():
    return [s for s in json.loads((ROOT / "skills.json").read_text(encoding="utf-8")) if s["tipo"] == "rotina"]


def arquivos_proprios():
    pastas = [CORE / "kits/rotina"] + [CORE / "skills" / s["name"] for s in rotinas_no_skills_json()]
    return [p for pasta in pastas for p in sorted(pasta.rglob("*")) if p.suffix in (".md", ".py", ".csv")]


class KitRotina(unittest.TestCase):
    def test_kit_tem_os_arquivos(self):
        for nome in ARQUIVOS_KIT:
            self.assertGreater(len(texto_kit(nome)), 300, nome)

    def test_sem_escrita_no_erp(self):
        for path in arquivos_proprios():
            self.assertIsNone(ESCRITA_SQL.search(path.read_text(encoding="utf-8")), path)

    def test_sem_travessao_nem_emoji(self):
        emoji = re.compile("[\U0001F300-\U0001FAFF☀-➿]")
        for path in arquivos_proprios():
            conteudo = path.read_text(encoding="utf-8")
            self.assertNotIn("—", conteudo, path)
            self.assertNotIn("–", conteudo, path)
            self.assertIsNone(emoji.search(conteudo), path)

    def test_conteudo_externo_e_dado(self):
        self.assertIn("nunca instrução", texto_kit("regras-rotina.md"))

    def test_agendada_so_o_configurado(self):
        regras = texto_kit("regras-rotina.md")
        self.assertIn("só os blocos do ERP", regras)
        self.assertIn("não publique", regras)

    def test_acoes_erp_nunca(self):
        linha = next(l for l in texto_kit("acoes.md").splitlines() if l.startswith("| Escrita no ERP"))
        self.assertIn("Nunca", linha)

    def test_acoes_email_e_rascunho(self):
        self.assertIn("sempre rascunho", texto_kit("acoes.md"))

    def test_fluxo_limita_perguntas(self):
        fluxo = texto_kit("fluxo-rotina.md")
        self.assertIn("no máximo uma pergunta", fluxo)
        self.assertIn("`references/fluxo-dados.md`", fluxo)

    def test_perfil_nao_grava(self):
        self.assertIn("não grava nada", texto_kit("perfil-da-operacao.md"))


if __name__ == "__main__":
    unittest.main()
