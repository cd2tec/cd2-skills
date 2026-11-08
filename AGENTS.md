# Instruções para agentes neste repositório

Este repositório publica o plugin `cd2-varejo`, da CD2 Tech, para mais de uma plataforma: Claude Code e Claude Cowork, Codex e ChatGPT Work, DeepSeek Harness e GPT Store. Cada skill leva para dentro do assistente a conta de uma calculadora gratuita da CD2.

Nomes fixos: repositório `cd2tec/cd2-skills`, marketplace `cd2-skills`, plugin `cd2-varejo`. A titular é só a CD2 Tech, em todos os arquivos.

## Regra principal

**Edite só `core/`.** As pastas `plugins/<plataforma>/cd2-varejo/skills/`, `gpts/<skill>/` e as cópias de `LICENSE`, `NOTICE` e `COMMERCIAL.md` dentro dos pacotes são geradas. Depois de qualquer mudança em `core/`, em `skills.json` ou nos arquivos de licença, rode:

```
python3 scripts/sync_plugins.py
python3 scripts/sync_plugins.py --check
python3 -m unittest discover -s tests -v
```

O CI roda o `--check` e os testes. O `--check` falha se uma cópia divergir de `core/`, se um manifesto tiver nome, versão ou licença diferente do core, se uma referência entre crases apontar para arquivo que não existe, se sobrar placeholder de UTM nas cópias ou se um `instructions.md` de GPT passar de 8.000 caracteres.

## Onde fica cada coisa

| Caminho | O que é | Edita à mão? |
|---|---|---|
| `core/cd2-varejo/skills/<skill>/` | Fonte única de cada skill: `SKILL.md`, `references/`, `scripts/`, `assets/` | Sim |
| `core/cd2-varejo/shared/` | O que vai para dentro de toda skill: `scripts/brand.py`, `references/fluxo-conversa.md`, `references/marca.md` e as logos em `assets/brand/` | Sim |
| `core/cd2-varejo/gpts/` | `_preamble.md` comum e, por skill, `instructions.md` e `gpt.json` do GPT | Sim |
| `core/cd2-varejo/plugin.core.json` | Nome e versão de referência do plugin | Sim |
| `skills.json` | Lista das skills (nome, título, resumo, site, regra e status). Gera a tabela do README e os cards do site | Sim |
| `harnesses.json` | Plataformas do plugin, caminho, manifesto, layout e `utm_source` de cada uma | Sim |
| `plugins/<plataforma>/cd2-varejo/` (manifesto, `README.md` e, no DSH, `install.py`) | Empacotamento próprio da plataforma | Sim |
| `plugins/<plataforma>/cd2-varejo/skills/` e `gpts/<skill>/` | Cópias geradas | **Não** |
| `gpts/README.md` | Passo a passo para publicar os GPTs | Sim |
| `.claude-plugin/marketplace.json` e `.agents/plugins/marketplace.json` | Marketplaces do Claude Code e do Codex | Sim |
| `README.md` e `docs/index.html` | Vitrine do plugin. O trecho entre `<!-- skills:start -->` e `<!-- skills:end -->` é gerado | Sim, fora dos marcadores |
| `docs/assets/` | Logos, símbolo, ícone e a fonte Manrope do site | Sim, copiando de `core/cd2-varejo/shared/assets/brand/` |
| `LICENSE`, `NOTICE`, `COMMERCIAL.md` | Licença CC BY-NC-ND 4.0, atribuição e licença comercial | Sim, com cuidado: valem para todos os pacotes |

## Layouts de plataforma

O campo `layout` de cada entrada em `harnesses.json` diz como o sync monta o pacote:

- **`plugin`** (padrão; Claude e Codex): `skills/<skill>/` copiado do core, com o conteúdo de `shared/` somado no mesmo caminho relativo dentro de cada skill (`shared/scripts/brand.py` vai para `scripts/`, `shared/references/` para `references/` e `shared/assets/brand/` para `assets/brand/`). Cada skill fica autocontida. `LICENSE`, `NOTICE` e `COMMERCIAL.md` vão na raiz do pacote.
- **`flat-skills`** (DeepSeek Harness): o mesmo conteúdo por skill, mais `LICENSE`, `NOTICE` e `COMMERCIAL.md` dentro de cada `skills/<skill>/`, porque o DSH lê cada skill solta, sem raiz de plugin. O `install.py` do pacote copia as skills para o diretório que o DSH lê.
- **`gpt`** (GPT Store): `gpts/<skill>/instructions.md` (o `_preamble.md` mais as instruções do GPT da skill), `gpts/<skill>/gpt.json` e `gpts/<skill>/knowledge/` com a skill autocontida, menos o `SKILL.md`. O ChatGPT achata o upload numa pasta só, então nenhum arquivo do conhecimento pode repetir nome, e os scripts acham os vizinhos nos dois layouts.

Um arquivo de `shared/` com o mesmo caminho de um arquivo da skill é erro: o compartilhado nunca sobrescreve o da skill.

## Somar uma calculadora nova

Cada calculadora gratuita nova da CD2 ganha uma skill aqui. Em ordem:

1. **Crie `core/cd2-varejo/skills/<nome>/`** com:
   - `SKILL.md`, com frontmatter `name` igual ao nome da pasta e `description` com as palavras que a pessoa usaria;
   - `references/metodologia.md`, com as fórmulas em português e os valores de conferência;
   - `references/legal-params.json` e `references/assumptions.json`, copiados da calculadora com versão, data de conferência e fontes;
   - `scripts/calc.py` e `scripts/render.py`, só com biblioteca padrão do Python 3.10+, portando a conta do `core/calculator.ts` da calculadora;
   - `assets/template.html` e `assets/fonts/` (Manrope e `OFL.txt`).
2. **Escreva os testes** em `tests/test_calc_<apelido>.py` e `tests/test_render_<apelido>.py`, como os de hoje (`test_calc_6x1.py`, `test_render_vrva.py`): os valores de exemplo da metodologia e os casos do `calculator.test.ts` do site viram testes. Some o nome da skill nos testes que listam as skills (`tests/test_repo.py` e `tests/test_sync.py`).
3. **Crie o GPT** em `core/cd2-varejo/gpts/<nome>/`: `instructions.md` (com o preâmbulo, até 8.000 caracteres) e `gpt.json` (nome, descrição, conversation starters, capacidades e `profile_picture`). Atualize a tabela do `gpts/README.md`.
4. **Registre no `skills.json`** com nome, título, resumo, `site_url` (com barra no fim), regra e status.
5. **Atualize as descrições e as palavras-chave** dos manifestos (`plugins/*/cd2-varejo/` e os dois marketplaces) e dos READMEs dos pacotes, que citam as skills pelo nome.
6. **Escreva a ponte** com as outras skills, quando fizer sentido: uma frase no fechamento, nunca um desvio da conversa.
7. **Some um exemplo de conversa** no `README.md` e no `docs/index.html`, fora dos marcadores.
8. **Rode o sync**, o `--check` e os testes. A tabela do README, os cards do site, os pacotes e os GPTs saem daí.
9. **Suba a versão** (minor) e escreva a entrada no `CHANGELOG.md`, como em [Versão e release](#versão-e-release).

## Sincronia com os sites

As calculadoras ficam em repositórios privados da organização `cd2tec` no GitHub e nunca são citadas como fonte para quem usa a skill. A sincronia é manual, sem job no CI, para não exigir segredo num repositório público.

| Skill | Site |
|---|---|
| `fim-escala-6x1` | https://calc-fim-escala6x1.cd2.com.br/ |
| `custo-vrva` | https://calc-vrva.cd2.com.br/ |

Quando o `legal-params.json` ou o `assumptions.json` de uma calculadora mudar:

1. Copie os arquivos novos para `core/cd2-varejo/skills/<skill>/references/`, mantendo versão, data de conferência e fontes.
2. Se a conta mudou no `core/calculator.ts`, porte a mudança para `scripts/calc.py`.
3. Porte os testes novos do `calculator.test.ts` para o `tests/test_calc_<apelido>.py` da skill e confira os valores de conferência da `metodologia.md`.
4. Atualize a `metodologia.md`, o `SKILL.md` e as instruções do GPT quando citarem um valor ou uma data que mudou.
5. Rode o sync, o `--check` e os testes.
6. Suba a versão (patch, ou minor se a conta mudou) e escreva no `CHANGELOG.md` o que mudou na regra e a nova data de conferência.

Cada skill mostra a data de conferência dos parâmetros, e a pergunta sobre novidades (etapa 3 da conversa) cobre o intervalo entre uma atualização e outra.

## Versão e release

- A versão segue `MAJOR.MINOR.PATCH` e mora em `core/cd2-varejo/plugin.core.json`. Repita a mesma versão nos manifestos `plugins/claude/cd2-varejo/.claude-plugin/plugin.json`, `plugins/codex/cd2-varejo/plugin.json` e `plugins/dsh/cd2-varejo/plugin.json`. O `--check` confere nome, versão e licença de cada um.
- Não declare `version` nas entradas dos marketplaces: as plataformas usam a do manifesto, e a duplicação só abre espaço para divergência.
- Escreva a entrada no `CHANGELOG.md` com o título exato `## <versão>`, da mais recente para a mais antiga. O workflow de release copia essa seção para as notas da release.
- Quando o `plugin.core.json` muda na `main`, o workflow de release cria a tag `cd2-varejo-v<versão>` com os ZIPs gerados por `scripts/package_plugins.py`: `cd2-varejo-<pacote>-<versão>.zip` e a cópia sem versão `cd2-varejo-<pacote>.zip`, para `claude`, `codex`, `dsh` e `gpts`. Release de versão que já existe não é recriada: suba a versão.
- Depois da release, republique os GPTs pelo passo a passo do `gpts/README.md`.
- Nunca faça commit de `dist/` nem de `.superpowers/`.

## Links e UTM

- Todo link para `cd2.com.br`, `archeo.cd2.com.br` e os sites das calculadoras leva `utm_source=<origem>&utm_medium=skill&utm_campaign=<campanha>`.
  - Nas skills e nas referências, escreva `utm_source={{UTM_SOURCE}}`. O sync troca o placeholder pelo `utm_source` da plataforma em `harnesses.json`: `claude`, `codex`, `deepseek` e `gpt-store`.
  - No `README.md`, `utm_source=github`. No `docs/index.html`, `utm_source=site-skills`.
  - A campanha é o nome da skill no link da calculadora e `cd2-varejo` nos links gerais para `cd2.com.br` e o Archeo.
- Os sites das calculadoras sempre com barra no fim: `https://calc-vrva.cd2.com.br/`.
- WhatsApp comercial: `https://wa.me/5519982355172`, com mensagem preenchida que diz a origem. Nas skills: `Oi, vim pela skill {nome_humano} no {plataforma_humana} e quero falar sobre uso na minha empresa.` No README, "vim pelo GitHub das skills da CD2"; no site, "vim pelo site das skills da CD2".
- Nenhum número digitado pela pessoa entra em URL, nem na do WhatsApp.

## Texto e marca

- Português do Brasil, frases curtas, "você" para quem lê e "nós" para a CD2. Títulos em caixa normal, só a primeira letra em maiúscula.
- Sem emoji e sem travessão (os caracteres U+2014 e U+2013). Use ponto, vírgula, dois-pontos ou parênteses. Os testes conferem isso no README, no site e nestes guias.
- Nenhum arquivo cita pessoa física como autora ou titular: a titular é a CD2 Tech.
- O tom do convite comercial é convite, não ameaça. Quem não é cliente está avaliando.
- Design system da CD2 Tech: as cores de `brand.TOKENS` em `core/cd2-varejo/shared/scripts/brand.py`, fonte Manrope com fallback `system-ui`, raios de 6, 12, 24 e 999px, marca plana (sem sombra em card), sem degradê decorativo e sem card com borda lateral de destaque. Nunca use texto `blue-sky`, `gray-solution` ou `yellow-like` sobre fundo claro.
- Escreva as skills de forma neutra quanto à plataforma. Quando um passo depender de recurso exclusivo (artefato no Claude, busca na web, rodar código), diga isso na skill e traga a alternativa.

## Site do GitHub Pages

- `docs/index.html` é uma página só, autocontida: CSS e JS no próprio arquivo, assets em `docs/assets/` com caminho relativo. Link absoluto só para `cd2.com.br` e subdomínios, `wa.me` e `github.com`.
- As abas da instalação funcionam sem JS como lista: nenhum painel nasce com `hidden` no HTML.
- Confira o site no navegador em desktop, em 375px de largura e no tema escuro, sem rolagem horizontal.
- O `index.html` da raiz só redireciona para `docs/`, para o caso de o Pages publicar a partir da raiz do branch.
