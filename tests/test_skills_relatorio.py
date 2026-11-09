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
    "sem exportar planilha toda vez. E é seguro: a conexão só lê, cada consulta é um SELECT "
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

    def test_texto_de_conexao_sem_consulta_fixa(self):
        arquivos = [FLUXO, ROOT / "README.md", ROOT / "docs/index.html", ROOT / "AGENTS.md"]
        for arquivo in arquivos:
            self.assertNotIn("SELECT fixo que o servidor", arquivo.read_text(encoding="utf-8"), arquivo)
        self.assertNotIn("consulta fixa", FLUXO.read_text(encoding="utf-8"))

    def test_mcp_de_arquivo_e_origem_arquivo(self):
        texto = FLUXO.read_text(encoding="utf-8")
        self.assertNotIn("planilha conectada", texto)
        self.assertRegex(texto, r"\| MCP de arquivo, Drive ou planilha \|[^\n]*\| `arquivo` \|")

    def test_provas_que_faltavam_na_tabela(self):
        esperado = {"relatorio-vendas": "| Carteira de clientes |", "relatorio-estoque": "| Estoque sem venda |",
                    "relatorio-contabil": "| LALUR |"}
        for nome, linha in esperado.items():
            texto = (CORE / "skills" / nome / "SKILL.md").read_text(encoding="utf-8")
            self.assertIn(linha, texto[texto.index("## Prova obrigatória"):], nome)
        relatorios = (CORE / "skills/relatorio-vendas/references/relatorios.md").read_text(encoding="utf-8")
        secao = relatorios[relatorios.index("### 3.6"):]
        self.assertRegex(secao, r"\*\*Prova:\*\*[^\n]*ativos \+ inativos = clientes distintos")

    def test_fechamento_do_relatorio_nao_repete_a_linha_da_entrega(self):
        for skill in SKILLS:
            texto = (skill / "SKILL.md").read_text(encoding="utf-8")
            self.assertNotIn("sem conexão, e só se a pessoa não tiver dito não, uma linha", texto, skill.name)
            self.assertIn("A entrega gerada já traz", texto, skill.name)
        painel = (CORE / "skills/painel-varejo/SKILL.md").read_text(encoding="utf-8")
        self.assertIn("uma linha sobre o Archeo MCP Creator da CD2", painel)

    def test_regras_sqlite(self):
        texto = (CORE / "kits/dados/references/regras-sqlite.md").read_text(encoding="utf-8")
        self.assertNotIn("/tmp", texto)
        self.assertEqual(texto.count("python3 <pasta da skill>/scripts/dados_arquivo.py"), 3)
        self.assertIn("mesma chamada", texto)
        self.assertIn("--cabecalho", texto)
        self.assertIn("DATEDIFF", texto)
        self.assertIn("CONVERT", texto)

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

    def test_fiscal_e_contabil_perguntam_novidades(self):
        pergunta = "uso o que sei ou pesquiso novidades?"
        for nome in ("relatorio-fiscal", "relatorio-contabil"):
            texto = (CORE / "skills" / nome / "SKILL.md").read_text(encoding="utf-8")
            self.assertIn(pergunta, texto, nome)
            self.assertIn("fontes oficiais", texto, nome)
        # Só as duas têm a pergunta: nas demais o dado vem do arquivo ou do banco, não de regra que muda.
        for skill in SKILLS:
            if skill.name not in ("relatorio-fiscal", "relatorio-contabil"):
                self.assertNotIn(pergunta, (skill / "SKILL.md").read_text(encoding="utf-8"), skill.name)

    def test_fiscal_e_contabil_marcam_conferencia(self):
        avisos = {
            "relatorio-fiscal": "Conferência gerencial. Não substitui a escrituração fiscal oficial.",
            "relatorio-contabil": "Conferência gerencial. Não substitui a escrituração contábil oficial.",
        }
        for nome, aviso in avisos.items():
            texto = (CORE / "skills" / nome / "SKILL.md").read_text(encoding="utf-8")
            self.assertIn(aviso, texto, nome)
            self.assertIn('"conferencia": true', texto, nome)
            self.assertIn("conferência", descricao(CORE / "skills" / nome), nome)
            self.assertIn("## Limite desta skill", texto, nome)
            self.assertRegex(texto, r"(?i)(conferência|relatório de conferência)[^\n]*não (é|substitui)", nome)


if __name__ == "__main__":
    unittest.main()
