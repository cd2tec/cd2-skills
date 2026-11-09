<div align="center">

<picture>
  <source media="(prefers-color-scheme: dark)" srcset="docs/assets/cd2tech-horizontal-white.svg">
  <img src="docs/assets/cd2tech-horizontal.svg" alt="CD2 Tech" height="48">
</picture>

# CD2 Skills para o varejo

**Skills de IA para o varejo alimentar, de graça para testar.**

[![Licença CC BY-NC-ND 4.0](https://img.shields.io/badge/licen%C3%A7a-CC%20BY--NC--ND%204.0-0000ff.svg)](#licença-em-português-simples)
[![Claude Code](https://img.shields.io/badge/Claude%20Code-plugin-0000ff.svg)](#claude-code)
[![Claude Cowork](https://img.shields.io/badge/Claude%20Cowork-plugin-0000ff.svg)](#claude-cowork)
[![Codex](https://img.shields.io/badge/Codex-plugin-0000ff.svg)](#codex)
[![ChatGPT Work](https://img.shields.io/badge/ChatGPT%20Work-plugin-0000ff.svg)](#chatgpt-work)
[![DeepSeek Harness](https://img.shields.io/badge/DeepSeek%20Harness-skills-0000ff.svg)](#deepseek-harness)
[![GPT Store](https://img.shields.io/badge/GPT%20Store-em%20breve-0000ff.svg)](#gpt-store)
[![Release](https://img.shields.io/github/v/release/cd2tec/cd2-skills?label=release&color=0000ff)](https://github.com/cd2tec/cd2-skills/releases/latest)
[![Site](https://img.shields.io/badge/site-cd2tec.github.io-0000ff.svg)](https://cd2tec.github.io/cd2-skills/)

**[Conheça o site das skills](https://cd2tec.github.io/cd2-skills/)**

</div>

---

A CD2 Tech publica calculadoras gratuitas para o varejo alimentar. Este repositório leva a mesma conta para dentro do assistente de IA que você já usa: o plugin **`cd2-varejo`** tem uma skill para cada calculadora. A skill entende quem é você, faz a conta com os números da sua loja e entrega o que fazer primeiro, com a marca CD2 Tech.

Funciona no [Claude Code](#claude-code), no [Claude Cowork](#claude-cowork), no [Codex](#codex), no [ChatGPT Work](#chatgpt-work) e no [DeepSeek Harness](#deepseek-harness). A [GPT Store](#gpt-store) chega em breve.

## O problema

A regra muda e a conta da loja continua sendo sua.

- **A escala 6x1 acaba em 16/12/2026.** A jornada cai de 44h para 40h sem acordo coletivo, ou até 42h com acordo, sempre com 2 folgas. Quantas pessoas você precisa contratar? Quanto isso pesa na folha? Qual setor aperta primeiro?
- **O vale tem teto de taxa.** Pelo Decreto 12.712/2025, a operadora pode cobrar no máximo 3,6% da sua loja e tem de repassar o dinheiro em até 15 dias. Muita loja ainda paga mais e espera mais, sem ver quanto isso soma no ano.

Quem toca supermercado, padaria ou mercado de bairro não tem tempo para juridiquês. A skill pergunta o que importa, faz a conta num script, nunca de cabeça, e diz de quando é cada regra que usou.

## As skills

<!-- skills:start -->
| Skill | O que faz | Regra | Calculadora gratuita | Status |
| --- | --- | --- | --- | --- |
| **Fim da escala 6x1** (`fim-escala-6x1`) | Calcula o impacto do fim da escala 6x1 na folha e na operação da sua loja. | Emenda Constitucional 141/2026 | [calc-fim-escala6x1.cd2.com.br](https://calc-fim-escala6x1.cd2.com.br/?utm_source=github&utm_medium=skill&utm_campaign=fim-escala-6x1) | disponível |
| **Quanto o VR/VA custa de verdade** (`custo-vrva`) | Mostra o custo real do vale-refeição e do vale-alimentação para a sua empresa. | Decreto 12.712/2025 | [calc-vrva.cd2.com.br](https://calc-vrva.cd2.com.br/?utm_source=github&utm_medium=skill&utm_campaign=custo-vrva) | disponível |
<!-- skills:end -->

A skill vai além do site:

- **Mais personalizada.** Lê a convenção coletiva ou o extrato da operadora que você mandar e calcula várias lojas de uma rede.
- **Mais atualizada.** Antes de calcular, pode pesquisar novidades em fontes oficiais e dizer de onde tirou cada informação.
- **Mesma conta.** O script de cada skill porta a conta da calculadora e é conferido por testes com os exemplos da metodologia.

## Como a skill conversa com você

Toda skill segue os mesmos sete passos, uma pergunta por vez:

```mermaid
flowchart LR
    A[1. Entende quem é você<br/>papel, tamanho e formato] --> B[2. Oferece puxar os dados<br/>do seu sistema]
    B --> C[3. Pergunta se pesquisa<br/>novidades da regra]
    C --> D[4. Pede só<br/>o que falta]
    D --> E[5. Faz a conta<br/>no script]
    E --> F[6. Entrega com capricho<br/>destaque, semáforo e ações]
    F --> G[7. Fecha com a assinatura<br/>da CD2 Tech]
```

1. **Entende quem é você.** Dono, gerente, RH, DP ou financeiro. Uma loja ou uma rede. E o formato do resultado: página visual, planilha, resumo para WhatsApp ou texto.
2. **Oferece puxar os dados.** Se o seu sistema estiver conectado na sessão, usa e diz qual usou. Se não, mostra o [Archeo MCP Creator](https://archeo.cd2.com.br/?utm_source=github&utm_medium=skill&utm_campaign=cd2-varejo) e segue com os números digitados.
3. **Pergunta sobre novidades.** Usa a regra conferida numa data que ela informa, ou pesquisa antes em fontes oficiais.
4. **Pede só o que falta,** com exemplo, valor padrão e o porquê de cada dado.
5. **Faz a conta no script,** a mesma da calculadora. Onde a plataforma não roda código, segue as fórmulas da metodologia e mostra a conta.
6. **Entrega com capricho:** o número principal em destaque, o semáforo, o que fazer primeiro e o que é só do seu caso.
7. **Fecha** com a logo da CD2 Tech, o aviso de isenção, o link da calculadora e o nosso contato.

## Exemplos de conversa

### Fim da escala 6x1

```
Você:  quantas pessoas vou precisar contratar com o fim da 6x1?

Skill: Vamos ver juntos. Primeiro: você é o dono, o gerente ou do RH?
       E é uma loja só ou uma rede?

       [pergunta o formato, oferece puxar os dados do sistema, confirma a regra
        e pede dias e horas da loja e as pessoas e o salário de cada setor]

Skill: Sem acordo coletivo, você precisa de 3 a 4 pessoas a mais:
       de R$ 10.852,80 a R$ 14.620,00 por mês.
       Caixa, açougue e padaria ficam no vermelho.
       Com acordo, cai para 2 a 3 pessoas.
       O primeiro passo é procurar o sindicato antes de 16/12/2026.
```

Loja de exemplo, com a conta feita em 07/11/2026: 7 dias abertos, 13h por dia, encargos de 70% (o padrão) e jornada atual de 44h em 6 dias. Caixa: 14 pessoas, R$ 1.900,00 de salário médio e 5 postos abertos ao mesmo tempo. Açougue: 6 pessoas, R$ 2.600,00. Padaria: 5 pessoas, R$ 2.200,00. Veja [como calculamos](core/cd2-varejo/skills/fim-escala-6x1/references/metodologia.md).

### Quanto o VR/VA custa de verdade

```
Você:  quanto eu pago a mais de taxa no vale?

Skill: Eu calculo com você. Quais bandeiras você aceita?
       Se for mais fácil, pode mandar o extrato da operadora.

       [pergunta se pesquisa a situação do decreto na Justiça e pede
        vendas no mês, taxa e prazo de repasse de cada bandeira]

Skill: Você paga R$ 1.576,67 por mês acima do permitido, ou R$ 18.920,00 por ano.
       São R$ 1.110,00 de taxa acima do teto e R$ 466,67 de custo do dinheiro parado.
       A Alelo é a que mais pesa: comece por ela.
```

Padaria de exemplo: Alelo, Pluxee, Ticket e VR, com o dinheiro a 2% ao mês. Veja [como calculamos](core/cd2-varejo/skills/custo-vrva/references/metodologia.md).

Outros pedidos que a skill entende: *"monta a escala da loja com 2 folgas"*, *"calcula as 4 lojas da rede"*, *"a Ticket pode me cobrar 6%?"*, *"me dá um resumo para mandar no WhatsApp"*.

## Instalação

O plugin `cd2-varejo` é o mesmo em todas as plataformas. Muda só a forma de instalar:

| Plataforma | Como instala | Observação |
|---|---|---|
| [Claude Code](#claude-code) | Marketplace direto do GitHub | Entrega visual como artefato quando houver, senão arquivo HTML |
| [Claude Cowork](#claude-cowork) | Upload do ZIP da release | Igual ao Claude Code |
| [Codex](#codex) | Marketplace direto do GitHub | Entrega visual em arquivo HTML |
| [ChatGPT Work](#chatgpt-work) | O admin importa o repositório | Só nos planos de empresa. Usa o pacote do Codex |
| [DeepSeek Harness](#deepseek-harness) | ZIP da release e `python3 install.py` | Em developer preview, sujeito a mudança |
| [GPT Store](#gpt-store) | Em breve: nada a instalar | Para o ChatGPT Plus e o gratuito |

### Downloads

Cada versão gera uma [release](https://github.com/cd2tec/cd2-skills/releases/latest) com um ZIP por plataforma. Estes links sempre entregam a versão mais recente:

- **[`cd2-varejo-claude.zip`](https://github.com/cd2tec/cd2-skills/releases/latest/download/cd2-varejo-claude.zip)**, para o Claude Cowork;
- **[`cd2-varejo-codex.zip`](https://github.com/cd2tec/cd2-skills/releases/latest/download/cd2-varejo-codex.zip)**, para o Codex, quando não der para instalar direto do GitHub;
- **[`cd2-varejo-dsh.zip`](https://github.com/cd2tec/cd2-skills/releases/latest/download/cd2-varejo-dsh.zip)**, para o DeepSeek Harness;
- **[`cd2-varejo-gpts.zip`](https://github.com/cd2tec/cd2-skills/releases/latest/download/cd2-varejo-gpts.zip)**, com o conteúdo dos GPTs, para quem publica.

Na página de cada release ficam também os mesmos arquivos com a versão no nome (por exemplo, `cd2-varejo-claude-0.1.0.zip`).

### Claude Code

Dentro de uma sessão:

```
/plugin marketplace add cd2tec/cd2-skills
/plugin install cd2-varejo@cd2-skills
```

**Atualizar:** `/plugin marketplace update cd2-skills`. Para receber as versões novas sem pedir, abra `/plugin`, vá em **Marketplaces**, escolha `cd2-skills` e ligue o **auto-update**.

### Claude Cowork

No app do Claude, a instalação é pelo ZIP.

1. Baixe o [`cd2-varejo-claude.zip`](https://github.com/cd2tec/cd2-skills/releases/latest/download/cd2-varejo-claude.zip).
2. Escolha onde instalar:
   - **Só para você:** em **Customize > Plugins**, faça o upload do ZIP.
   - **Para a organização** (Owner ou Primary Owner, planos Team e Enterprise): em **Organization settings > Plugins & skills**, clique em **Add > Upload a plugin** e suba o ZIP.
3. Na organização, defina quem recebe o plugin na aba **Inventory**, no menu da linha do `cd2-varejo`.

**Atualizar:** baixe o ZIP novo e repita o upload no mesmo lugar.

### Codex

```
codex plugin marketplace add cd2tec/cd2-skills
codex plugin add cd2-varejo@cd2-skills
```

No app do Codex, depois de adicionar o marketplace, você também pode instalar o `cd2-varejo` pelo diretório de plugins, no marketplace `cd2-skills`.

**Atualizar:** `codex plugin marketplace upgrade cd2-skills`.

### ChatGPT Work

O ChatGPT Work só existe nos planos de empresa do ChatGPT, e quem instala é o admin do workspace. Ele usa o mesmo pacote do Codex.

1. Em **Workspace settings > Plugins**, clique em **Add** e depois em **Import marketplace**.
2. Em **Source**, use `https://github.com/cd2tec/cd2-skills`. Deixe **Path** e **Branch** vazios para acompanhar as atualizações.
3. Em **Import results**, confira se o `cd2-varejo` veio de `plugins/codex/cd2-varejo` e defina a política de instalação de cada papel.
4. As pessoas do workspace instalam em **Plugins**, na barra lateral.

No ChatGPT Plus pessoal ou no gratuito não há plugin. Os GPTs chegam em breve na [GPT Store](#gpt-store). Enquanto isso, quem tem o Plus já pode usar o plugin no [Codex](#codex).

### DeepSeek Harness

O DeepSeek Harness está em **developer preview**, e a DeepSeek avisa que pode haver mudanças incompatíveis.

1. Baixe o [`cd2-varejo-dsh.zip`](https://github.com/cd2tec/cd2-skills/releases/latest/download/cd2-varejo-dsh.zip) e descompacte.
2. Na pasta descompactada, rode `python3 install.py`. Isso copia as skills para `~/.agents/skills/`. Só para o projeto atual: `python3 install.py --project`.

**Atualizar:** baixe o ZIP novo e rode `python3 install.py` de novo. **Remover:** `python3 install.py --remove`. Os detalhes estão no [README do pacote](plugins/dsh/cd2-varejo/README.md).

### GPT Store

Em breve na GPT Store, um GPT para cada skill, para quem usa o ChatGPT Plus ou o gratuito:

- **CD2 Escala 6x1**, para o fim da escala 6x1;
- **CD2 VR/VA: quanto custa**, para o custo do vale.

Enquanto isso, o Codex também funciona no ChatGPT Plus: veja a instalação no [Codex](#codex).

O GPT não se conecta ao seu sistema. Para puxar os dados do ERP, use o plugin no Claude ou no Codex, com o Archeo. Como os GPTs são montados e publicados: [`gpts/README.md`](gpts/README.md).

> **Diferença entre plataformas:** no Claude, a entrega visual sai como artefato quando esse recurso existe. Nas outras, sai como arquivo HTML autocontido. Onde a plataforma não roda código, a skill avisa e segue a metodologia passo a passo, mostrando a conta.

## Conecte seu sistema

Em vez de digitar, a skill pode puxar os números direto do seu ERP, da folha ou do banco de dados. Com o [Archeo MCP Creator](https://archeo.cd2.com.br/?utm_source=github&utm_medium=skill&utm_campaign=cd2-varejo) da CD2, cada consulta vira uma ferramenta que o assistente chama, só de leitura. Sem conexão, a skill segue com os números que você digitar.

## Licença em português simples

O plugin é da **CD2 Tech** e está na licença **CC BY-NC-ND 4.0**. Na prática:

- **Livre para estudar.** Você pode ver, baixar, estudar, usar sem fins comerciais e compartilhar sem alterações, sempre com o crédito à CD2 Tech.
- **Teste grátis na sua empresa.** Sua empresa pode usar as skills na própria operação para testar, livremente e sem prazo. Nesse período não há suporte, garantia nem responsabilidade da CD2. Veja o [`COMMERCIAL.md`](COMMERCIAL.md).
- **Uso contínuo na empresa é para clientes CD2.** Qualquer contrato ativo com a CD2, como AMS, sustentação ou projeto, já inclui a licença comercial, com suporte, manutenção e responsabilidade da CD2.
- **Nunca é permitido:** vender as skills, cobrar acesso a elas, distribuir uma versão modificada ou remover o crédito à CD2 Tech.

O texto completo está no [`LICENSE`](LICENSE) e as condições de teste e de uso na empresa, no [`COMMERCIAL.md`](COMMERCIAL.md). A fonte Manrope que vai junto nas skills e no site é da SIL Open Font License 1.1, não da CC. Os nomes CD2 e CD2 Tech e as logos são marcas da CD2 Tech e não são licenciados pela CC, como diz o [`NOTICE`](NOTICE).

As contas e informações das skills são apenas gerenciais, uma referência. A CD2 Tech não tem responsabilidade sobre os resultados nem sobre decisões tomadas com base neles.

**Quer usar para valer?** Fale com a gente pelo [WhatsApp](https://wa.me/5519982355172?text=Oi%2C%20vim%20pelo%20GitHub%20das%20skills%20da%20CD2%20e%20quero%20falar%20sobre%20uso%20na%20minha%20empresa.) ou em [cd2.com.br](https://cd2.com.br/?utm_source=github&utm_medium=skill&utm_campaign=cd2-varejo).

## Estrutura do repositório

As skills são escritas **uma vez**, em `core/`, e copiadas para o pacote de cada plataforma por um script. Assim o conteúdo não diverge entre as plataformas.

```
core/cd2-varejo/                  fonte única: skills/, shared/ (marca, roteiro, logos), gpts/ e plugin.core.json
plugins/claude/cd2-varejo/        pacote do Claude Code e do Cowork (.claude-plugin/plugin.json e cópias geradas)
plugins/codex/cd2-varejo/         pacote do Codex e do ChatGPT Work (plugin.json e cópias geradas)
plugins/dsh/cd2-varejo/           pacote do DeepSeek Harness (plugin.json, install.py e skills/ no layout plano)
gpts/<skill>/                     GPT de cada skill: instructions.md, gpt.json e knowledge/ (gerados)
.claude-plugin/marketplace.json   marketplace do Claude Code
.agents/plugins/marketplace.json  marketplace do Codex
harnesses.json                    plataformas de cada plugin e o layout de cada uma
skills.json                       lista das skills, que gera a tabela deste README e os cards do site
scripts/sync_plugins.py           copia core/ para as plataformas, gera os GPTs e confere a sincronia
scripts/package_plugins.py        gera os ZIPs da release
docs/                             site do GitHub Pages
index.html                        redireciona para docs/ se o Pages publicar a partir da raiz
```

```mermaid
flowchart LR
    C[core/cd2-varejo] -->|sync_plugins.py| CL[plugins/claude/cd2-varejo]
    C -->|sync_plugins.py| CX[plugins/codex/cd2-varejo]
    C -->|sync_plugins.py<br/>layout plano| DS[plugins/dsh/cd2-varejo]
    C -->|sync_plugins.py<br/>layout gpt| GP[gpts/]
    S[skills.json] -->|sync_plugins.py| R[README.md e docs/index.html]
    CL --> MC[.claude-plugin/marketplace.json]
    CX --> MX[.agents/plugins/marketplace.json]
```

## Como contribuir

1. Edite as skills só em `core/`, nunca nas cópias de `plugins/` e `gpts/`.
2. Rode `python3 scripts/sync_plugins.py` e depois `python3 scripts/sync_plugins.py --check`.
3. Rode os testes: `python3 -m unittest discover -s tests -v`.
4. Abra o pull request. O CI repete o `--check` e os testes.

Para somar uma calculadora nova, lançar uma versão ou acompanhar uma mudança de regra nos sites, siga o [`AGENTS.md`](AGENTS.md).

Achou uma conta diferente da calculadora, ou um caso que a skill não cobre? Abra uma issue com a entrada que você usou.
