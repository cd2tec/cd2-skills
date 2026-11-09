"""Conferências de texto das skills de relatório e do método comum (kits dados, sql e relatorio)."""
import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CORE = ROOT / "core/cd2-varejo"
SKILLS = sorted((CORE / "skills").glob("relatorio-*"))
FLUXO = CORE / "kits/dados/references/fluxo-dados.md"
KITS = [CORE / "kits" / kit / "references" for kit in ("dados", "sql", "relatorio")]

RE_SECAO = re.compile(r"^#{2,3} 3\.\d+", re.M)
RE_EMOJI = re.compile("[☀-➿️\U0001f300-\U0001faff]")
PITCH = (
    "Não encontrei conexão com o seu sistema, então sigo com o arquivo que você me passar. "
    "Se conectar pelo Archeo MCP Creator da CD2, o resultado melhora: eu leio o banco inteiro, "
    "acho cancelados e campos vazios e confiro cada total no próprio banco. Os dados vêm online, "
    "sem exportar planilha toda vez. E é seguro: a conexão só lê, cada consulta é um SELECT fixo "
    "que o servidor valida antes de aceitar, e qualquer escrita é recusada."
)
RE_PROMESSA = re.compile(
    r"(dados?|informaç\w+|números?)\s+(não|nunca)\s+sa\w+\s+d[ao]\s+(sua\s+)?(empresa|máquina|rede)"
    r"|fica\w*\s+(só\s+|somente\s+|apenas\s+)?(dentro\s+d[ao]|n[ao])\s+(sua\s+)?(empresa|máquina)"
    r"|sem\s+sair\s+d[ao]\s+(sua\s+)?(empresa|máquina)",
    re.I,
)
PROIBICAO = "Nunca prometa que o dado não sai da empresa"


def textos():
    """Todo markdown das skills de relatório e dos kits que elas recebem."""
    for pasta in SKILLS + KITS:
        for md in sorted(pasta.rglob("*.md")):
            yield md, md.read_text(encoding="utf-8")


def descricao(skill):
    texto = (skill / "SKILL.md").read_text(encoding="utf-8")
    return re.search(r"^description:\s*(.+)$", texto, re.M).group(1)


class TestSkillsRelatorio(unittest.TestCase):
    def test_ha_skills_para_conferir(self):
        self.assertTrue(SKILLS)

    def test_toda_secao_tem_para_exportar(self):
        for skill in SKILLS:
            texto = (skill / "references/relatorios.md").read_text(encoding="utf-8")
            inicios = [m.start() for m in RE_SECAO.finditer(texto)]
            self.assertTrue(inicios, skill.name)
            for inicio, fim in zip(inicios, inicios[1:] + [len(texto)]):
                secao = texto[inicio:fim]
                self.assertIn("**Para exportar:**", secao, f"{skill.name}: {secao.splitlines()[0]}")

    def test_descricao_cita_arquivo_e_nao_exige_banco(self):
        for skill in SKILLS:
            texto = descricao(skill)
            self.assertIn("arquivo", texto, skill.name)
            self.assertNotIn("banco conectado ao Archeo", texto, skill.name)

    def test_sem_dash_nem_emoji(self):
        for md, texto in textos():
            self.assertNotIn("—", texto, md)
            self.assertNotIn("–", texto, md)
            self.assertIsNone(RE_EMOJI.search(texto), md)

    def test_texto_de_conexao_exato(self):
        self.assertIn(PITCH, FLUXO.read_text(encoding="utf-8"))

    def test_sem_promessa_de_dado_nao_sair(self):
        self.assertIn(PROIBICAO, FLUXO.read_text(encoding="utf-8"))
        for md, texto in textos():
            for linha in texto.splitlines():
                if PROIBICAO not in linha:
                    self.assertIsNone(RE_PROMESSA.search(linha), f"{md}: {linha}")

    def test_painel_e_relatorio_se_distinguem(self):
        for skill in SKILLS:
            texto = (skill / "SKILL.md").read_text(encoding="utf-8")
            self.assertRegex(texto, r"\*\*Esta skill ou o painel\?\*\*[^\n]*`painel-varejo`[^\n]*relatório", skill.name)


if __name__ == "__main__":
    unittest.main()
