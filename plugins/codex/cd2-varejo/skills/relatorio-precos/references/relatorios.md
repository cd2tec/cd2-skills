# Preço, margem e promoção: mapeamento, relatórios e consultas-modelo

Conteúdo:
1. Mapeamento
2. O que medir
3. Relatórios (3.1 a 3.6)

Consultas em SQL Server com marcadores `<assim>`; **[modelo]** até passarem na prova nos dados da pessoa. Sem conexão, adapte a consulta com a tabela de `references/regras-sqlite.md` e troque os marcadores pelos nomes de coluna do perfil do arquivo. Cada relatório termina com **Para exportar**: o que pedir ao ERP quando não há conexão.

## 1. Mapeamento

Itens vendidos, produto, departamento e custo: `references/indicadores-varejo.md`, seção 1. Acrescente:

| Domínio | Para quê | Termos de busca | O que confirmar |
|---|---|---|---|
| Preço vigente | Margem de cadastro, conferência | `preco`, `preco_venda`, `tabela_preco`, `prc`, `vlr_venda` | Chave (produto + loja + embalagem?), vigência, preço de atacado |
| Histórico de preço | Alterações | `historico_preco`, `alteracao_preco`, `log_preco`, `auditoria` | Data, preço anterior e novo, usuário, motivo |
| Promoção | Resultado de oferta | `promocao`, `oferta`, `encarte`, `campanha`, `preco_oferta`, `desconto_item` | Vigência, lojas, preço promocional, tipo; marca no item vendido |
| Custo no item vendido | Margem do período | `custo`, `cmv`, `vlr_custo` na tabela de itens | Se é gravado na venda (custo da época) |
| Impostos por item | Margem de contribuição | `icms`, `pis`, `cofins`, `aliquota`, `tributacao` | Valor por item ou só alíquota no cadastro |

## 2. O que medir

- Teste do custo (cobertura, dispersão, época do custo): SKILL.md, "Antes de qualquer margem".
- Preço: quantos preços por produto (lojas, embalagens, tabelas), % de itens ativos sem preço.
- Histórico de preço: existe? Desde quando? Guarda usuário e motivo?
- Promoção: quantas no período, com vigência e lojas; % dos itens vendidos marcados como promoção.
- Item vendido: o valor unitário é antes ou depois do desconto? Há coluna de desconto por item?

Com arquivo, estas medidas saem do perfil de `scripts/dados_arquivo.py`. O que não estiver no arquivo não tem como ser medido: diga isso nas premissas.

## 3. Relatórios

### 3.1 Margem

**Colunas (sintético por departamento):** departamento, venda líquida, custo, contribuição em valor, margem %, participação na venda %, participação na contribuição %, variação da margem em pontos percentuais contra o período anterior.
**Analítico:** produto, quantidade, preço médio praticado, custo médio unitário, margem %, contribuição.

```sql
SELECT x.d, MAX(dp.<descricao>) departamento,
       CAST(x.venda AS float) venda, CAST(x.custo AS float) custo,
       CAST(x.venda - x.custo AS float) contribuicao,
       CAST(100.0 * (x.venda - x.custo) / NULLIF(x.venda, 0) AS float) margem_pct,
       CAST(100.0 * x.venda / NULLIF(SUM(x.venda) OVER (), 0) AS float) part_venda_pct,
       CAST(100.0 * (x.venda - x.custo) / NULLIF(SUM(x.venda - x.custo) OVER (), 0) AS float) part_contrib_pct
FROM (SELECT i.<cod_departamento> d, SUM(i.<valor_liquido>) venda,
             SUM(COALESCE(i.<custo_unitario>, 0) * i.<quantidade>) custo
      FROM <itens_venda> i
      WHERE <filtro_validos> AND i.<data> >= '2025-07-01' AND i.<data> < '2025-08-01'
        AND COALESCE(i.<custo_unitario>, 0) > 0
      GROUP BY i.<cod_departamento>) x
LEFT JOIN <departamento> dp ON dp.<cod_departamento> = x.d
GROUP BY x.d, x.venda, x.custo
ORDER BY x.venda - x.custo DESC OFFSET 0 ROWS
```

Confirme se a coluna de custo do item é unitária ou total da linha antes de multiplicar pela quantidade. O filtro `custo > 0` restringe o relatório à parcela coberta: informe a venda que ficou de fora.
Com arquivo, o departamento costuma vir na mesma linha do item: agrupe por ele e tire o join com o cadastro.
**Prova:** venda do relatório + venda sem custo = venda total do período.
**Leituras típicas:** departamento que pesa mais na venda que na contribuição (gerador de tráfego), queda de margem por mix ou por preço (decomponha: mesma cesta a preços e custos atuais), itens de alto giro com margem abaixo da média do departamento.

**Para exportar:** peça o relatório de venda por item do período, em CSV ou Excel, com o custo de cada item. Colunas mínimas: código do produto, quantidade, valor líquido, custo unitário (ou o custo total da linha). Recomendadas: departamento, data, situação do item.

- Sem o custo na venda: peça o custo atual do cadastro de produtos (código e custo). A margem sai aproximada, com o custo de hoje sobre a venda de antes, e isso entra nas premissas.
- Sem custo de nenhuma fonte: não existe margem. Sai só a venda.
- Com custo mas quase todo igual em percentual da venda: custo estimado por percentual fixo (teste da dispersão); a margem sai, mas sem ranking.
- Sem departamento: a margem sai por produto, sem o sintético por departamento.
- Sem o período anterior: sem a variação da margem em pontos percentuais.
- Sem situação do item: não dá para tirar os cancelados. Peça a exportação só com vendas válidas e registre isso nas premissas.
- Sem impostos por item: a margem é bruta, e a entrega diz o que ficou de fora.

### 3.2 Margem negativa

Duas listas diferentes, que não devem ser misturadas:
- **Praticada:** itens cuja venda no período ficou abaixo do custo (preço médio praticado < custo). Colunas: produto, quantidade, preço médio, custo, prejuízo em valor, % das vendas do item em promoção.
- **De cadastro:** itens ativos com preço vigente <= custo atual, vendidos ou não.

Ordene pelo prejuízo em valor. Antes de alarmar, descarte os falsos positivos: custo com erro de embalagem (custo da caixa contra preço da unidade), item em promoção com verba do fornecedor, item de combo com preço rateado.
**Prova:** cada item listado confere com o preço e o custo da fonte (cadastro, ou item vendido na lista praticada).

**Para exportar:** para a lista praticada, o mesmo relatório do 3.1: venda por item com código, quantidade, valor líquido e custo unitário. Para a lista de cadastro, o cadastro de produtos ativos com preço vigente e custo atual.

- Sem custo na venda: a lista praticada sai com o custo atual do cadastro e fica aproximada.
- Sem o cadastro de preços e custos: sai só a lista praticada, não a de cadastro.
- Sem marca de promoção no item: sem o percentual das vendas em promoção, e o falso positivo de promoção com verba do fornecedor não se descarta sozinho. Pergunte à pessoa.
- Sem a unidade de custo e de venda: o erro de embalagem (caixa contra unidade) pode aparecer como prejuízo. Avise.

### 3.3 Custo sem repasse

Itens com aumento de custo nas últimas entradas e preço de venda inalterado.
**Colunas:** produto, custo anterior, custo atual, variação %, data da entrada, preço atual, data da última alteração de preço, margem anterior e atual, preço para recompor a margem anterior (custo atual / (1 - margem anterior)).
Custos por entrada: `references/mapeamento-erp.md`, seção 3. O preço de recomposição é referência de cálculo, não recomendação: elasticidade e concorrência não estão no dado.
**Prova:** cada item listado confere com o custo das duas últimas entradas e com o preço atual do cadastro.

**Para exportar:** peça duas coisas: as notas de entrada por item (produto, data de entrada, custo unitário, quantidade, tipo de operação), com pelo menos duas entradas por produto, e os preços de venda atuais (produto, preço).

- Sem a data da última alteração de preço (ou o histórico, 3.4): não dá para dizer se o preço ficou parado desde o aumento do custo. Avise que "sem repasse" é só o preço atual contra o custo.
- Sem tipo de operação: bonificação com custo zero parece queda e transferência vira entrada. Peça só notas de compra.
- Sem embalagem: troca de caixa pode parecer aumento (falso aumento).
- Sem o preço de venda atual: sai a variação de custo, mas não a margem nem o preço de recomposição.

### 3.4 Alterações de preço

**Colunas:** data, produto, loja, preço anterior, novo, variação %, usuário, motivo.
**Sintético:** alterações por dia, aumentos x reduções, variação média, itens alterados mais de 3 vezes no período.
Sem tabela de histórico, o ERP não permite este relatório. Não infira alterações a partir do preço praticado na venda (desconto e promoção confundem): diga que o dado não existe.
Usuário é dado pessoal de colaborador: mostre só quando a pergunta for de auditoria.
**Prova:** alterações listadas e somadas por dia = linhas do histórico no período, mesmos filtros.

**Para exportar:** peça o relatório de histórico ou auditoria de alteração de preço do período. Colunas mínimas: data, produto, preço anterior, preço novo.

- Se o ERP não guarda o histórico de preço, este relatório não sai por arquivo nenhum. Diga isso e não tente reconstruir pela venda.
- Sem o preço anterior: aparece o preço novo, mas não a variação nem aumentos x reduções.
- Sem loja: as alterações saem da rede inteira, sem separar loja.
- Sem usuário e motivo: o relatório sai sem a parte de auditoria.

### 3.5 Resultado de promoção

**Janelas:** antes (mesma duração, imediatamente anterior), durante e depois (mesma duração).
**Colunas por item promovido:** preço normal, preço promocional, desconto %, quantidade por dia nas três janelas, aumento de volume % (durante / antes), venda, contribuição nas três janelas, variação da contribuição.

```sql
SELECT i.<cod_produto>,
       CAST(SUM(CASE WHEN i.<data> <  '2025-07-08' THEN i.<quantidade> ELSE 0 END) / 7.0 AS float) qtd_dia_antes,
       CAST(SUM(CASE WHEN i.<data> >= '2025-07-08' AND i.<data> < '2025-07-15' THEN i.<quantidade> ELSE 0 END) / 7.0 AS float) qtd_dia_durante,
       CAST(SUM(CASE WHEN i.<data> >= '2025-07-15' THEN i.<quantidade> ELSE 0 END) / 7.0 AS float) qtd_dia_depois,
       CAST(SUM(CASE WHEN i.<data> >= '2025-07-08' AND i.<data> < '2025-07-15'
                     THEN i.<valor_liquido> - COALESCE(i.<custo_unitario>, 0) * i.<quantidade> ELSE 0 END) AS float) contrib_durante
FROM <itens_venda> i
WHERE <filtro_validos> AND i.<cod_produto> IN (<itens_da_promocao>)
  AND i.<data> >= '2025-07-01' AND i.<data> < '2025-07-22'
GROUP BY i.<cod_produto>
```

**O que dizer e o que não dizer:**
- O aumento de volume é uma **comparação antes e depois**, não efeito causal: sazonalidade, dia de pagamento, clima e ruptura anterior entram junto. Se houver lojas fora da promoção, use-as como controle e diga isso.
- A queda no "depois" indica antecipação de compra (o cliente estocou).
- Canibalização: mostre a venda dos demais itens da mesma categoria nas três janelas.
- A conta que importa é a contribuição: volume maior com contribuição menor só se justifica por tráfego, e tráfego se mede em cupons, não no item.

**Prova:** venda dos itens promovidos nas três janelas = venda desses itens na fonte geral, no mesmo intervalo.

**Para exportar:** peça a venda por item e por dia dos itens da promoção, de um período que cubra as três janelas (antes, durante e depois). Colunas mínimas: data, código do produto, quantidade, valor líquido. A pessoa informa a vigência da promoção (início e fim) e a lista dos itens, ou você a lê de um relatório de promoções com o preço promocional.

- Sem a data em cada linha: não dá para separar as janelas, e o relatório não sai.
- Sem custo: sai o volume e a venda, mas não a contribuição, que é a conta que importa.
- Sem loja: sem lojas de controle, e a leitura do aumento fica mais fraca. Avise.
- Sem os demais itens da categoria na exportação: sem a canibalização.
- Sem o preço normal e o promocional: o desconto % sai do preço médio praticado, e isso fica dito.
- Sem cupom ou documento: o tráfego não se mede.

### 3.6 Preço de cadastro x praticado

**Colunas:** produto, loja, preço vigente na data, preço unitário do item vendido, diferença, quantidade de ocorrências, operador ou PDV quando a pergunta for de auditoria.
Compare com o preço **vigente na data da venda** (histórico), não com o de hoje. Classifique: desconto registrado, promoção vigente, preço de atacado por quantidade, alteração manual, sem explicação. Só o último grupo é divergência.
**Prova:** amostra de 5 divergências conferida no detalhe do item vendido.

**Para exportar:** peça a venda por item do período com o preço unitário do item (código, data, quantidade, preço unitário) e o cadastro de preços de venda. Se tiver o histórico de preço (3.4), melhor: compara-se com o preço da data.

- Sem o histórico de preço: a comparação é com o preço de hoje e só vale para venda recente. Diga isso, porque preço que mudou depois da venda aparece como divergência.
- Sem o desconto registrado e a marca de promoção no item: a classificação das diferenças não separa desconto e promoção de alteração manual. Avise que parte da lista pode ser explicável.
- Sem operador ou PDV: sai a divergência por produto, sem a leitura de auditoria.
- Sem loja: o preço de cadastro vale como único para a rede, o que é raro.
