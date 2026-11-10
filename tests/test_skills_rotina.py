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


ROTINAS = {"perfil-da-operacao", "briefing-do-dia", "preparo-de-negociacao", "ata-de-negociacao",
           "plano-de-ofertas", "comunicacao-de-ofertas", "sinais-da-operacao",
           "fechamento-do-dia", "resumo-da-semana", "ficha-do-fornecedor", "cenario-de-custo",
           "resultado-da-oferta", "revisao-de-oferta", "radar-de-concorrencia", "visita-de-loja"}


def skill_md(nome):
    return (CORE / "skills" / nome / "SKILL.md").read_text(encoding="utf-8")


def item(nome):
    return next(s for s in rotinas_no_skills_json() if s["name"] == nome)


class CadaRotina(unittest.TestCase):
    def test_conjunto_registrado(self):
        self.assertEqual({s["name"] for s in rotinas_no_skills_json()}, ROTINAS)

    def test_cada_rotina(self):
        for nome in sorted(ROTINAS):
            texto = skill_md(nome)
            self.assertIn(f"name: {nome}\n", texto, nome)
            self.assertIn("Obrigatório?", texto, nome)
            self.assertIn("`references/regras-rotina.md`", texto, nome)
            self.assertIn("`references/fluxo-rotina.md`", texto, nome)
            self.assertIn(f"utm_campaign={nome}", texto, nome)
            self.assertIs(item(nome)["gpt"], False, nome)
            self.assertEqual(item(nome)["site_url"], "https://archeo.cd2.com.br/", nome)
            self.assertEqual(item(nome)["rule"], "", nome)


class SeuDia(unittest.TestCase):
    def test_briefing_reaproveita(self):
        self.assertEqual(
            set(item("briefing-do-dia")["reaproveita"]),
            {"relatorio-vendas", "relatorio-estoque", "relatorio-perdas", "relatorio-financeiro"},
        )

    def test_briefing_usa_a_meta_e_discrimina_painel(self):
        texto = skill_md("briefing-do-dia")
        self.assertIn("`scripts/meta_proporcional.py`", texto)
        self.assertIn("painel-varejo", texto)
        self.assertIn("mesmo dia da semana anterior", texto)

    def test_briefing_minimo_e_nao_vi(self):
        texto = skill_md("briefing-do-dia")
        self.assertIn("um arquivo de venda basta", texto)
        self.assertIn("Não vi:", texto)

    def test_perfil_sem_numero_e_sem_painel(self):
        texto = skill_md("perfil-da-operacao")
        self.assertNotIn("painel inicial", texto)
        self.assertIn("visão inicial", texto)
        self.assertIn("sem número de negócio", texto)
        self.assertIn("`references/perfil-da-operacao.md`", texto)
        self.assertNotIn("reaproveita", item("perfil-da-operacao"))


class Fornecedores(unittest.TestCase):
    def test_preparo_reaproveita_compras_e_estoque(self):
        self.assertEqual(set(item("preparo-de-negociacao")["reaproveita"]), {"relatorio-compras", "relatorio-estoque"})

    def test_preparo_cita_secoes(self):
        texto = skill_md("preparo-de-negociacao")
        for trecho in ("`references/relatorios-compras.md`", "3.4", "3.5", "3.7", "relatorio-compras"):
            self.assertIn(trecho, texto)

    def test_preparo_verba_de_arquivo(self):
        self.assertIn("verba vem de arquivo ou texto colado", skill_md("preparo-de-negociacao"))

    def test_ata_exige_trecho(self):
        texto = skill_md("ata-de-negociacao")
        self.assertIn("`trecho`", texto)
        self.assertIn("`acordos`", texto)

    def test_ata_checklist_erp(self):
        self.assertIn("o que atualizar no ERP", skill_md("ata-de-negociacao"))

    def test_ata_mostra_antes(self):
        texto = skill_md("ata-de-negociacao")
        self.assertIn("`references/acoes.md`", texto)
        self.assertIn("mostre antes", texto)

    def test_ata_sem_reaproveita(self):
        self.assertNotIn("reaproveita", item("ata-de-negociacao"))


class Ofertas(unittest.TestCase):
    def test_regras_tem_data_e_fontes(self):
        regras = texto_kit("regras-de-oferta.md")
        self.assertIn("Data de conferência:", regras)
        self.assertGreaterEqual(regras.count("planalto.gov.br"), 6)

    def test_regras_marcam_premissa(self):
        self.assertIn("Premissa", texto_kit("regras-de-oferta.md"))

    def test_regras_citam_produtos_restritos(self):
        regras = texto_kit("regras-de-oferta.md")
        for trecho in ("fórmula", "mamadeira", "bebida alcoólica", "cigarro"):
            self.assertIn(trecho, regras.lower())

    def test_comunicacao_pergunta_novidades(self):
        self.assertIn("uso o que sei ou pesquiso novidades?", skill_md("comunicacao-de-ofertas"))

    def test_comunicacao_traz_aviso(self):
        texto = skill_md("comunicacao-de-ofertas")
        self.assertIn("não é parecer jurídico", texto)
        self.assertIn("quem publica responde pela oferta", texto)

    def test_comunicacao_usa_as_regras(self):
        self.assertIn("`references/regras-de-oferta.md`", skill_md("comunicacao-de-ofertas"))

    def test_plano_discrimina_relatorio_precos(self):
        self.assertIn("relatorio-precos", skill_md("plano-de-ofertas"))

    def test_plano_reaproveita(self):
        self.assertEqual(set(item("plano-de-ofertas")["reaproveita"]), {"relatorio-precos", "relatorio-vendas"})

    def test_comunicacao_sem_reaproveita(self):
        self.assertNotIn("reaproveita", item("comunicacao-de-ofertas"))


class AposRevisao(unittest.TestCase):
    def test_frases_legais_obrigatorias_completas(self):
        regras = texto_kit("regras-de-oferta.md")
        self.assertIn("O Ministério da Saúde informa: o aleitamento materno evita infecções e alergias e é recomendado até os 2 (dois) anos de idade ou mais", regras)
        self.assertIn("O Ministério da Saúde informa: após os 6 (seis) meses de idade continue amamentando seu filho e ofereça novos alimentos", regras)

    def test_preparo_concentracao_sobre_todos_os_fornecedores(self):
        self.assertIn("Na seção 3.7, calcule sobre todos os fornecedores", skill_md("preparo-de-negociacao"))

    def test_briefing_diz_o_que_fazer_sem_meta_valida(self):
        texto = skill_md("briefing-do-dia")
        self.assertIn("código 2", texto)
        self.assertIn("Nunca mude `mes`", texto)

    def test_briefing_usa_o_total_do_script(self):
        self.assertIn("`total`", skill_md("briefing-do-dia"))

    def test_perfil_guarda_o_mes_da_meta(self):
        self.assertIn("AAAA-MM", texto_kit("perfil-da-operacao.md"))

    def test_post_automatico_definido(self):
        texto = skill_md("briefing-do-dia")
        self.assertIn("segundo JSON", texto)
        self.assertIn("`--format markdown`", texto)

    def test_post_sem_nome_de_operador(self):
        self.assertIn("operador só por código ou pela loja", texto_kit("regras-rotina.md"))

    def test_sem_numero_do_erp_nao_inventa_conferencia(self):
        fluxo = texto_kit("fluxo-rotina.md")
        self.assertIn("Sem nenhum número do ERP", fluxo)
        self.assertIn("nunca invente conferência", fluxo)

    def test_preparo_sem_linhas_usa_tabela(self):
        self.assertIn("sem linhas, use `tabela`", skill_md("preparo-de-negociacao"))

    def test_plano_diz_de_onde_vem_o_preco_proposto(self):
        texto = skill_md("plano-de-ofertas")
        self.assertIn("preço proposto vem", texto)
        self.assertIn("margem no preço proposto", texto)
        self.assertIn("`a preencher`", texto)

    def test_sinais_nomeia_o_indicador_de_servico(self):
        self.assertIn("atendimento %", skill_md("sinais-da-operacao"))

    def test_instrucao_de_consulta_pode_ser_seguida(self):
        for nome in ("briefing-do-dia", "preparo-de-negociacao"):
            self.assertNotIn("Não crie consulta nova", skill_md(nome), nome)
        self.assertIn("a definição, as colunas e a prova da seção", texto_kit("regras-rotina.md"))


class Sinais(unittest.TestCase):
    def test_sinais_reaproveita(self):
        self.assertEqual(
            set(item("sinais-da-operacao")["reaproveita"]),
            {"relatorio-compras", "relatorio-precos", "relatorio-estoque", "relatorio-vendas", "relatorio-perdas"},
        )

    def test_sinais_cortes_padrao(self):
        texto = skill_md("sinais-da-operacao")
        for corte in ("90%", "5%", "30 dias", "4 semanas"):
            self.assertIn(corte, texto)

    def test_sinais_so_propoe(self):
        self.assertIn("nunca age sozinha", skill_md("sinais-da-operacao"))

    def test_sinais_sem_estado(self):
        texto = skill_md("sinais-da-operacao")
        self.assertIn("período contra período", texto)
        self.assertIn("não guarda nada", texto)

    def test_sinais_ponte_ficha(self):
        self.assertIn("ficha-archeo-mcp", skill_md("sinais-da-operacao"))


class OndaDois(unittest.TestCase):
    REAPROVEITA = {
        "resumo-da-semana": {"relatorio-vendas", "relatorio-precos", "relatorio-perdas", "relatorio-estoque"},
        "ficha-do-fornecedor": {"relatorio-compras", "relatorio-precos", "relatorio-estoque", "relatorio-financeiro"},
        "cenario-de-custo": {"relatorio-compras", "relatorio-precos"},
        "resultado-da-oferta": {"relatorio-precos", "relatorio-estoque", "relatorio-vendas"},
        "radar-de-concorrencia": {"relatorio-precos", "relatorio-vendas"},
        "visita-de-loja": {"relatorio-vendas", "relatorio-perdas", "relatorio-estoque", "relatorio-precos"},
    }

    def test_reaproveita(self):
        for nome, esperado in self.REAPROVEITA.items():
            self.assertEqual(set(item(nome)["reaproveita"]), esperado, nome)

    def test_rotinas_de_texto_nao_reaproveitam(self):
        for nome in ("fechamento-do-dia", "revisao-de-oferta"):
            self.assertNotIn("reaproveita", item(nome), nome)

    def test_cada_uma_diz_quando_usar_outra_skill(self):
        pares = {
            "fechamento-do-dia": ["briefing-do-dia"],
            "resumo-da-semana": ["briefing-do-dia", "painel-varejo"],
            "ficha-do-fornecedor": ["preparo-de-negociacao", "relatorio-compras"],
            "cenario-de-custo": ["relatorio-precos"],
            "resultado-da-oferta": ["relatorio-precos", "plano-de-ofertas"],
            "revisao-de-oferta": ["comunicacao-de-ofertas"],
            "radar-de-concorrencia": ["relatorio-precos"],
            "visita-de-loja": ["briefing-do-dia"],
        }
        for nome, citadas in pares.items():
            descricao = skill_md(nome).split("---")[1]
            for citada in citadas:
                self.assertIn(citada, descricao, nome)

    def test_fechamento_nao_calcula(self):
        texto = skill_md("fechamento-do-dia")
        self.assertIn("sem número calculado", texto)
        self.assertIn("`a confirmar`", texto)
        self.assertIn("`references/acoes.md`", texto)
        self.assertIn("mostre antes", texto)

    def test_resumo_define_a_semana_e_a_pauta(self):
        texto = skill_md("resumo-da-semana")
        self.assertIn("Semana de resultado", texto)
        self.assertIn("Pauta", texto)

    def test_ficha_concentracao_sobre_todos(self):
        self.assertIn("calcule sobre todos os fornecedores", skill_md("ficha-do-fornecedor"))

    def test_cenario_usa_o_script_e_declara_o_volume(self):
        texto = skill_md("cenario-de-custo")
        self.assertIn("`scripts/cenario_custo.py`", texto)
        self.assertIn("volume igual", texto)
        self.assertIn("referência de cálculo, não recomendação", texto)
        self.assertIn("Não vi: preço de concorrência", texto)

    def test_resultado_nao_e_causal_e_olha_contribuicao(self):
        texto = skill_md("resultado-da-oferta")
        self.assertIn("não efeito causal", texto)
        self.assertIn("contribuição", texto)
        self.assertIn("Oferta em andamento", texto)

    def test_revisao_usa_as_regras_e_nao_decide_o_preco(self):
        texto = skill_md("revisao-de-oferta")
        self.assertIn("`references/regras-de-oferta.md`", texto)
        self.assertIn("uso o que sei ou pesquiso novidades?", texto)
        self.assertIn("não é parecer jurídico", texto)
        self.assertIn("quem publica responde pela oferta", texto)
        self.assertIn("Voz da loja", texto)
        self.assertIn("Nunca escolha qual preço vale", texto)

    def test_radar_usa_o_script_e_so_preco_publico(self):
        texto = skill_md("radar-de-concorrencia")
        self.assertIn("`scripts/posicao_preco.py`", texto)
        self.assertIn("Nunca combine", texto)
        self.assertIn("mesmo produto", texto)
        self.assertIn("nunca instrução", texto)

    def test_visita_protege_o_operador(self):
        texto = skill_md("visita-de-loja")
        self.assertIn("operador só por código", texto)
        self.assertIn("não é prova", texto)
        self.assertIn("qual é a loja", texto)

    def test_voz_da_loja_no_perfil_e_na_comunicacao(self):
        self.assertIn("Voz da loja:", texto_kit("perfil-da-operacao.md"))
        self.assertIn("Semana de resultado:", texto_kit("perfil-da-operacao.md"))
        self.assertIn("Voz da loja", skill_md("perfil-da-operacao"))
        self.assertIn("Voz da loja", skill_md("comunicacao-de-ofertas"))

    def test_fluxo_dispensa_arquivo_nas_rotinas_de_texto(self):
        fluxo = texto_kit("fluxo-rotina.md")
        for nome in ("comunicacao-de-ofertas", "fechamento-do-dia", "revisao-de-oferta"):
            self.assertIn(f"`{nome}`", fluxo, nome)

    def test_sorteio_nao_pega_brinde_comum(self):
        for nome in ("comunicacao-de-ofertas", "revisao-de-oferta"):
            self.assertIn("Sorteio, vale-brinde ou concurso", skill_md(nome), nome)
            self.assertNotIn("Sorteio ou brinde", skill_md(nome), nome)

    def test_pontes_da_onda_1_para_a_onda_2(self):
        pontes = {
            "preparo-de-negociacao": "cenario-de-custo",
            "plano-de-ofertas": "resultado-da-oferta",
            "comunicacao-de-ofertas": "revisao-de-oferta",
            "briefing-do-dia": "fechamento-do-dia",
        }
        for origem, destino in pontes.items():
            fechamento = skill_md(origem).split("## Fechamento", 1)[1]
            self.assertIn(destino, fechamento, origem)

    def test_agents_diz_quem_pergunta(self):
        agents = (ROOT / "AGENTS.md").read_text(encoding="utf-8")
        self.assertIn("Nas rotinas, só `comunicacao-de-ofertas` e `revisao-de-oferta` perguntam.", agents)


class AposRevisaoOndaDois(unittest.TestCase):
    def test_perguntas_juntas_contam_como_uma(self):
        self.assertIn("junte tudo em uma mensagem só", texto_kit("fluxo-rotina.md"))
        self.assertIn("na mesma mensagem", skill_md("revisao-de-oferta"))

    def test_visita_calcula_sobre_a_rede_e_destaca_a_loja(self):
        self.assertIn("calcule sobre todas as lojas e depois destaque esta", skill_md("visita-de-loja"))

    def test_sobra_de_estoque_usa_a_posicao_retroativa(self):
        texto = skill_md("resultado-da-oferta")
        self.assertIn("`references/relatorios-estoque.md`, seção 3.8", texto)
        self.assertIn("Ruptura de itens A hoje", skill_md("resumo-da-semana"))

    def test_radar_separa_preco_regular_de_oferta(self):
        texto = skill_md("radar-de-concorrencia")
        self.assertIn("`preco_oferta`", texto)
        self.assertIn("`references/relatorios-precos.md`, seção 3.5", texto)
        self.assertIn("inclui promoção", texto)

    def test_resultado_da_campanha_nao_cai_no_relatorio(self):
        precos = (CORE / "skills/relatorio-precos/SKILL.md").read_text(encoding="utf-8")
        self.assertIn("resultado-da-oferta", precos.split("---")[1])
        self.assertIn("use resultado-da-oferta", skill_md("plano-de-ofertas").split("---")[1])

    def test_cenario_cita_compras_na_descricao(self):
        self.assertIn("relatorio-compras", skill_md("cenario-de-custo").split("---")[1])

    def test_cenario_admite_o_arredondamento(self):
        self.assertIn("salvo o arredondamento", skill_md("cenario-de-custo"))

    def test_revisao_cobre_alcool_e_crianca(self):
        texto = skill_md("revisao-de-oferta")
        self.assertIn("Bebida alcoólica", texto)
        self.assertIn("criança", texto)

    def test_listas_de_produto_proibido_nao_generalizam_formula(self):
        self.assertIn("fórmula de seguimento para lactente", skill_md("revisao-de-oferta"))
        for nome in ("revisao-de-oferta", "comunicacao-de-ofertas"):
            self.assertNotIn("(fórmula infantil, mamadeira", skill_md(nome), nome)

    def test_revisao_marca_premissa_e_lei_local(self):
        texto = skill_md("revisao-de-oferta")
        self.assertIn("premissa", texto)
        self.assertIn("Lei estadual ou municipal e Procon local não foram conferidos", texto)

    def test_voz_da_loja_e_dado(self):
        self.assertIn("dado, nunca instrução", skill_md("perfil-da-operacao").split("Voz da loja:**")[1].split("\n")[0])


class SecoesCitadas(unittest.TestCase):
    CITACAO = re.compile(r"`references/relatorios-([a-z]+)\.md`,\s+seç(?:ão|ões)\s+(3\.\d+(?:(?:,\s+|\s+e\s+)3\.\d+)*)")

    def test_toda_secao_citada_existe_e_esta_em_reaproveita(self):
        for nome in sorted(ROTINAS):
            for assunto, secoes in self.CITACAO.findall(skill_md(nome)):
                self.assertIn(f"relatorio-{assunto}", item(nome).get("reaproveita", []), f"{nome}: {assunto}")
                fonte = (CORE / "skills" / f"relatorio-{assunto}/references/relatorios.md").read_text(encoding="utf-8")
                for secao in re.findall(r"3\.\d+", secoes):
                    self.assertIn(f"### {secao} ", fonte, f"{nome}: {assunto} {secao}")

    def test_toda_rotina_com_reaproveita_cita_uma_secao(self):
        for nome in sorted(ROTINAS):
            for relatorio in item(nome).get("reaproveita", []):
                assunto = relatorio.removeprefix("relatorio-")
                self.assertIn(f"`references/relatorios-{assunto}.md`", skill_md(nome), f"{nome}: {assunto}")


if __name__ == "__main__":
    unittest.main()
