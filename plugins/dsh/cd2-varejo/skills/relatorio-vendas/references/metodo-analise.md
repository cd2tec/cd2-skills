# Método comum das skills de relatório

Todas as skills `relatorio-*` do plugin seguem este método, com o banco conectado ou com um arquivo exportado. A conversa está em `references/fluxo-dados.md`. Cada skill acrescenta o catálogo de relatórios, as colunas para exportar e as provas do seu domínio em `relatorios.md`.

Conteúdo:
1. Princípios
2. Fluxo
3. Regras de consulta
4. Formato da entrega
5. Volume e exportação
6. Dados pessoais
7. Depois do relatório: ferramenta ou painel
8. Checklist

## 1. Princípios

- **O dado decide, não o manual.** Os nomes de relatório vêm do vocabulário dos ERPs de varejo, mas tabelas, colunas e regras saem da exploração do banco conectado ou do perfil do arquivo. Nenhum nome de tabela nas consultas-modelo é real: são marcadores `<assim>`.
- **Relatório sem prova não sai.** Cada relatório do catálogo tem uma prova de reconciliação (saldo inicial + movimento = saldo final, débito = crédito, soma das partes = total). Prova que não fecha vira o primeiro item da entrega, não uma nota de rodapé.
- **Dado ruim aparece.** Campo nunca preenchido, custo zerado, posição desatualizada e base sem movimento são achados. Diga o que faltou e o que isso impede de concluir.
- **Só leitura.** Toda consulta usa as ferramentas somente leitura do conector, ou o modo só leitura de `scripts/dados_arquivo.py`. Nada é gravado no ERP.
- **Não é documento oficial.** Relatórios fiscais e contábeis daqui servem para conferência e gestão. Livros, obrigações acessórias e apurações oficiais saem do ERP ou do sistema fiscal, com responsável técnico.

## 2. Fluxo

### 2.1 Identifique de onde vêm os dados

Procure as ferramentas `db_*` do Archeo MCP Creator da CD2 (`db_connection_status`, `db_list_tables`, `db_search_columns`, `db_describe_table`, `db_sample_table`, `db_read_only_query`, às vezes em nomes como `mcp__<conector>__db_<banco>_<engine>_<id>__<ação>`) e outros MCPs de dados da sessão, inclusive os deferidos (carregue tudo em uma chamada só). Com vários bancos, pergunte qual.

- **Banco pelo Archeo MCP Creator:** rode `db_connection_status`, anote engine e versão e leia `references/regras-sql.md` (seções 1, 3 e 4) antes da primeira consulta. Origem `banco`.
- **Outro MCP que leia os dados:** veja 2.8. Origem `outro-mcp`.
- **Nenhuma conexão:** não pare. Siga o texto de `references/fluxo-dados.md`, etapa 2, e continue com 2.7. Origem `arquivo` ou `digitado`.

### 2.2 Feche o escopo

Todo relatório tem quatro eixos. Use o padrão da skill quando a pessoa não disser, e declare o recorte na entrega.

| Eixo | Pergunta | Padrão geral |
|---|---|---|
| Unidade | Qual empresa, loja ou depósito? | Todas, com quebra por loja quando houver mais de uma |
| Tempo | Período de movimento ou data de posição? | Últimos 30 dias até a **última data com movimento** (não até hoje: réplicas e bases de laboratório param de receber dado) |
| Recorte | Departamento, fornecedor, cliente, conta? | Sem filtro |
| Nível | Sintético ou analítico? | Sintético, com o analítico dos 20 maiores |

Pergunte só o que muda o resultado. Um pedido vago ("me dá o estoque") recebe o relatório padrão da skill com o recorte declarado, não uma entrevista.

### 2.3 Mapeie o domínio

Use a tabela de mapeamento da skill: termos de busca por domínio, em português, inglês e abreviações de legado (`vlr`, `dta`, `cod`, `qtd`, `flg`, `sld`). Prefira views de resumo do próprio sistema. Se `db_describe_table` falhar, consulte o catálogo (`INFORMATION_SCHEMA.COLUMNS`, ou `ALL_TAB_COLUMNS` em Oracle) filtrando a tabela e padrões de coluna, nunca sem `WHERE`.

### 2.4 Meça antes de calcular

Para cada tabela que entra no relatório: `COUNT(*)`, `MIN` e `MAX` da data, percentual de nulos nas colunas de valor e valores distintos das colunas de status, tipo e flag. É aqui que aparecem:

- tabela vazia ou parada no tempo (o módulo não é usado, ou o dado vive em outro lugar);
- tipos de movimento e de documento que precisam virar filtro fixo ou sinal (entrada, saída, estorno);
- registros cancelados, estornados, de teste ou excluídos logicamente;
- cadastros com uma linha por loja, que multiplicam o join.

Quando o significado de um código não for inferível com segurança (qual tipo é devolução, qual situação é "em aberto"), **pergunte à pessoa** e registre a decisão nas premissas.

### 2.5 Calcule e prove

Monte a consulta a partir do modelo da skill, rode e aplique a prova do relatório. Diferença acima da tolerância indicada (2% quando não houver outra) pede investigação antes de entregar: join que multiplica, filtro fixo faltando, sinal invertido, unidade de medida diferente.

### 2.6 Leia

De 3 a 5 achados, do mais urgente ao menos, cada um com o número que o sustenta e o que fazer com ele. Leitura de negócio, não descrição da tabela. Inclua sempre um item sobre qualidade do dado quando 2.4 ou 2.5 mostraram algo.

### 2.7 Sem conexão

A sequência é a mesma: medir, filtrar, agregar, provar. Muda onde a conta roda.

1. Peça a exportação pela linha **Para exportar** do relatório. Mais de um arquivo pode entrar na mesma base (vendas e cadastro, por exemplo).
2. Carregue com `scripts/dados_arquivo.py`, nas regras de `references/regras-sqlite.md`. Rode os comandos a partir da pasta de trabalho, com o caminho completo do script.
3. O perfil substitui a medição de 2.4. Leia os avisos antes de qualquer conta: coluna de peso lida como decimal, CPF mascarado, linhas de total separadas.
4. Traduza a consulta-modelo com a tabela de `references/regras-sqlite.md` e troque os marcadores pelos nomes de coluna do perfil. Some a tabela principal; `<tabela>__totais` é só para conferir, senão conta duas vezes.
5. A prova é a mesma do relatório, e fecha só contra o arquivo. Some como conferências o total do ERP, quando a pessoa tiver, e as linhas de `<tabela>__totais`.
6. No JSON, use `"origem": "arquivo"` (`"digitado"` para números da conversa) e `"fonte": {"nome": "<nome do arquivo>"}`. O selo sai "Conferido só contra o arquivo", mesmo com o total do ERP igual.
7. Terminou, rode `apagar` na base temporária.

O arquivo mostra só o que foi exportado. Cancelados, devoluções e registros de teste podem ter ficado de fora sem aviso: diga nas premissas o que você não tem como saber, e não conclua sobre o que o arquivo não traz.

### 2.8 Outro MCP

Mesmo método e mesmo selo do banco, porque a conta foi feita na origem. A exigência é esta: **o total e as partes vêm de consultas separadas, feitas na origem.** Traduza o SQL para o que o MCP aceitar, diga qual MCP usou e preencha `fonte` com `banco`, `engine` e `conector`.

Se o MCP só devolver uma listagem e a soma sair daqui, a conta não foi feita na origem: carregue a listagem como arquivo e use a origem `arquivo`.

## 3. Regras de consulta

Valem as de `references/regras-sql.md` e as de `references/indicadores-varejo.md`, seção 2. No SQLite do arquivo, valem as de `references/regras-sqlite.md`. As que mais pesam em relatório:

- **Sem CTE no conector**: use tabelas derivadas (`FROM (SELECT ...) x`).
- **`ORDER BY` com `OFFSET 0 ROWS`** no SQL Server; teste nas outras engines. No SQLite, sem `OFFSET 0 ROWS`.
- **`CAST(... AS float)`** em valores quando o conector devolver decimal codificado.
- **Funções de janela funcionam** pelo conector em SQL Server (**[validado]**: `SUM(...) OVER ()` para participação e `SUM(...) OVER (ORDER BY ... ROWS UNBOUNDED PRECEDING)` para acumulado, dentro de tabela derivada) e no SQLite. Use para saldo acumulado, participação e classes ABC. Sempre desempate a ordenação com a chave, senão o acumulado muda entre execuções.
- **Datas com fim exclusivo**, sem função sobre a coluna filtrada.
- **Agregue na origem.** Não traga milhares de linhas para somar na conversa.
- **Sinal explícito.** Movimentos costumam guardar quantidade sempre positiva e o sentido em uma coluna de tipo. Converta com `CASE` e nunca presuma o sinal.

As consultas-modelo das skills estão em SQL Server. Marcação: **[validado]** quando o padrão rodou pelo conector em banco real; **[modelo]** quando é o desenho de referência, que só vale depois do passo 2.5 nos dados da pessoa.

## 4. Formato da entrega

Todo relatório sai como página, pelo renderizador comum. Você não escreve o HTML à mão e não declara se a prova fechou: o script decide, a partir dos números e da origem.

1. Grave `relatorio.json` na pasta de trabalho da pessoa, no formato de `formato-relatorio.md`. O título do veredito é o achado principal, com o número. A leitura é a do passo 2.6. Os campos `origem`, `skill` e `fonte` são obrigatórios.
2. Gere a página, rodando a partir da pasta de trabalho e chamando o script pelo caminho completo, para a entrega não cair dentro da pasta do plugin:

   ```bash
   python3 <pasta da skill>/scripts/render_relatorio.py --input relatorio.json --format html --output relatorio.html --platform "<Nome da plataforma>"
   ```

   Troque `<Nome da plataforma>` pelo nome real da plataforma em que você está: Claude, Codex, ChatGPT ou DeepSeek.

3. Se o script sair com código 2, ele devolve `{"errors": [...]}`. Corrija o JSON e rode de novo. Relatório sem prova não gera página.
4. Entregue conforme a plataforma:
   - **Claude com artefatos:** publique o `relatorio.html` com ícone `chart` e título com o relatório e a rede. O artefato é privado por padrão e traz dado do cliente: não sugira compartilhar sem a pessoa pedir.
   - **Outras plataformas que rodam código (Codex, DeepSeek Harness):** deixe o `relatorio.html` na pasta de trabalho e diga o caminho completo.
   - **Sem execução de código:** avise em uma linha e escreva a entrega no formato de texto abaixo, com os limites de `references/fluxo-dados.md`, "Casos especiais".
5. Na conversa, sempre: o achado principal, o selo da prova, o recorte e o link ou caminho da página.

Se a pessoa pedir outro formato, rode com `--format markdown`, `whatsapp` ou `csv`. O formato de texto é este:

```
**<Nome do relatório>**
Fonte: <banco e engine, via conector; ou nome do arquivo>
Recorte: <unidade> | <período ou data de posição> | <filtros> | <nível>

**Resumo**
3 a 6 totais em uma linha ou tabela curta.

**Relatório**
Tabela com as colunas do catálogo. Até 30 linhas na conversa; o restante vai em arquivo (seção 5).

**Leitura**
1. ... (número, o que significa, o que fazer)

**Prova**
O que foi reconciliado, o resultado e a diferença. Com arquivo ou números digitados: "Conferido só contra o arquivo".

**Premissas e qualidade do dado**
Filtros fixos aplicados, significados assumidos, campos indisponíveis, relatórios pedidos que não puderam ser gerados e por quê.
```

Números em formato brasileiro (`1.234,56`), moeda com `R$`, percentual com uma casa. Datas `dd/mm/aaaa`. Código e descrição lado a lado sempre que houver cadastro.

## 5. Volume e exportação

- **Sintético na conversa e na página, analítico em arquivo.** A página mostra até 30 linhas por tabela. Acima disso, entregue planilha (`.xlsx` ou `.csv`) com uma aba de dados, uma de resumo e uma de premissas. Use a skill de planilha da sessão, se houver.
- **Analítico grande não se pagina pela conversa.** Um Kardex de todos os produtos ou um razão de todas as contas tem centenas de milhares de linhas. Entregue o sintético, o analítico dos maiores e, com conexão, ofereça a ferramenta parametrizada (seção 7) para a pessoa consultar item a item.
- O conector limita linhas por chamada. Para exportar algo entre o limite e ~20 mil linhas, pagine por faixa de chave (`WHERE chave > <última>` com `TOP`), nunca por `OFFSET` crescente, e confira a contagem final contra `COUNT(*)`.
- No arquivo, `consultar` corta em 500 linhas por padrão e avisa. Agregue antes de aumentar `--limite`.

## 6. Dados pessoais

Relatórios por cliente, fornecedor pessoa física, operador ou vendedor trazem dado pessoal (LGPD, Lei Geral de Proteção de Dados). Vale igual para banco e para arquivo. Por padrão:

- agregue ou use o código interno; mostre nome só quando o relatório precisar dele para ser útil;
- mascare CPF (`***.123.456-**`); CNPJ pode aparecer;
- não exporte cadastro (endereço, telefone, e-mail) junto com relatório de venda ou de cobrança, a menos que a pessoa peça com finalidade clara.

## 7. Depois do relatório: ferramenta ou painel

Um relatório que a pessoa vai pedir de novo deve virar ativo, não conversa:

- **Ferramenta no MCP Creator:** cada relatório do catálogo lista os parâmetros naturais. Com conexão, ofereça `ficha-archeo-mcp` para gerar a ficha com o SQL já validado nesta sessão. Sem conexão, não ofereça: a ficha valida a consulta contra o banco.
- **Painel:** indicadores recorrentes cabem em `painel-varejo`.

Ofereça em uma linha no fim da entrega, sem insistir.

## 8. Checklist

- [ ] Fonte, origem e recorte declarados.
- [ ] Página gerada por `render_relatorio.py`, com a prova avaliada por ele.
- [ ] Tabelas medidas (volume, período, flags) ou perfil do arquivo lido antes do cálculo.
- [ ] Filtros fixos de cancelamento, estorno e exclusão lógica aplicados e listados.
- [ ] Prova do relatório executada, com a diferença informada.
- [ ] Joins com cadastro por loja conferidos (soma com join = soma sem join).
- [ ] Posição de estoque, saldo ou título com a data de referência explícita.
- [ ] Leitura com número e ação, incluindo qualidade do dado.
- [ ] Dado pessoal agregado ou mascarado.
- [ ] Relatório fiscal ou contábil marcado como conferência.
- [ ] Indisponíveis listados com o motivo.
- [ ] Com arquivo: `<tabela>__totais` fora da soma, nenhuma frase de "Prova fechada" e base temporária apagada.
