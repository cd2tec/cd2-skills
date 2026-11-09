# Estoque: mapeamento, relatórios e consultas-modelo

Conteúdo:
1. Mapeamento
2. O que medir
3. Relatórios (3.1 a 3.8)

Consultas em SQL Server com marcadores `<assim>`; **[modelo]** até passarem na prova nos dados da pessoa. O padrão de janela para acumulado é **[validado]** pelo conector. Sem conexão, adapte a consulta com a tabela de `references/regras-sqlite.md` e troque os marcadores pelos nomes de coluna do perfil do arquivo. Cada relatório termina com **Para exportar**: o que pedir ao ERP quando não há conexão.

## 1. Mapeamento

Saldo, movimento, tipo de operação, inventário, produto, mercadológico, fornecedor, custo e venda por item: `references/mapeamento-erp.md`, seção 1. Os termos de itens vendidos estão em `references/indicadores-varejo.md`, seção 1.

## 2. O que medir

- Saldo: linhas, itens com saldo > 0, = 0 e < 0, soma de quantidade, data mais recente de atualização.
- Movimento: linhas, primeira e última data, tabela por tipo de operação com contagem e soma de quantidade.
- Inventário: lotes por situação, data do último, itens por lote.
- Produto: ativos, inativos, sem departamento, sem custo.

```sql
SELECT m.<tipo_operacao>, COUNT(*) linhas,
       CAST(SUM(m.<quantidade>) AS float) qtd,
       CONVERT(varchar(10), MIN(m.<data>), 23) primeira, CONVERT(varchar(10), MAX(m.<data>), 23) ultima
FROM <movimento> m
GROUP BY m.<tipo_operacao>
ORDER BY COUNT(*) DESC OFFSET 0 ROWS
```

A partir dessa tabela e do cadastro de tipos, defina `<sinal>`: `CASE WHEN m.<tipo_operacao> IN (<entradas>) THEN 1 WHEN m.<tipo_operacao> IN (<saidas>) THEN -1 ELSE 0 END`. Tipo sem classificação segura: pergunte.

Com arquivo, estas medidas saem do perfil de `scripts/dados_arquivo.py`. O que não estiver no arquivo não tem como ser medido: diga isso nas premissas.

## 3. Relatórios

### 3.1 Estoque geral

**Pergunta:** quanto tenho, onde e quanto vale.

**Colunas (analítico):** loja, departamento, código, descrição, unidade, saldo, custo unitário, valor a custo, preço de venda, valor a venda, margem potencial %, data da última entrada e da última venda quando houver.
**Sintético:** por departamento (ou loja, fornecedor, segmento): itens com saldo, saldo, valor a custo, valor a venda, participação % no valor, itens negativos, itens zerados.

**Parâmetros naturais:** loja, departamento, fornecedor, situação do produto, só com saldo.

```sql
SELECT x.<cod_departamento>, d.<descricao> departamento,
       x.itens, x.itens_negativos, x.itens_zerados,
       CAST(x.valor_custo AS float) valor_custo, CAST(x.valor_venda AS float) valor_venda,
       CAST(100.0 * x.valor_custo / NULLIF(SUM(x.valor_custo) OVER (), 0) AS float) part_pct
FROM (SELECT p.<cod_departamento>,
             SUM(CASE WHEN s.<saldo> > 0 THEN 1 ELSE 0 END) itens,
             SUM(CASE WHEN s.<saldo> < 0 THEN 1 ELSE 0 END) itens_negativos,
             SUM(CASE WHEN s.<saldo> = 0 THEN 1 ELSE 0 END) itens_zerados,
             SUM(CASE WHEN s.<saldo> > 0 THEN s.<saldo> * COALESCE(s.<custo>, 0) ELSE 0 END) valor_custo,
             SUM(CASE WHEN s.<saldo> > 0 THEN s.<saldo> * COALESCE(s.<preco>, 0) ELSE 0 END) valor_venda
      FROM <saldo_estoque> s
      JOIN <produto> p ON p.<cod_produto> = s.<cod_produto> /* e loja, se o cadastro for por loja */
      WHERE s.<cod_loja> = COALESCE(NULLIF(<loja>, 0), s.<cod_loja>)
        AND p.<controla_estoque> = <sim>
      GROUP BY p.<cod_departamento>) x
LEFT JOIN <departamento> d ON d.<cod_departamento> = x.<cod_departamento>
ORDER BY x.valor_custo DESC OFFSET 0 ROWS
```

Com arquivo, o departamento costuma vir na mesma linha do saldo: agrupe por ele e tire o join com o cadastro.

**Decisões a declarar:** saldo negativo fica fora do valor (somado à parte como inconsistência); qual custo foi usado; se saldo reservado ou em trânsito entrou.
**Prova:** soma de `valor_custo` do relatório = `SUM(saldo * custo)` dos saldos positivos, direto na tabela de saldo com os mesmos filtros, sem join.
**Leituras típicas:** concentração do valor em poucos departamentos, itens negativos (saldo sem confiança), valor parado em itens inativos ou fora de linha, itens sem custo.

**Para exportar:** peça o relatório de posição de estoque (saldo por produto) na data de hoje, em CSV ou Excel, com uma linha por produto, ou por produto e loja. Colunas mínimas: código do produto, descrição, saldo.

- Sem custo unitário: sai a quantidade, mas não o valor a custo nem a cobertura de custo.
- Sem preço de venda: sem valor a venda e sem margem potencial.
- Sem departamento: sai o total e a lista de itens, mas não o sintético por departamento.
- Sem loja: sai a rede inteira somada; se a exportação traz várias lojas misturadas sem a coluna, a conta fica sem sentido por loja.
- Sem data da posição: pergunte a data da exportação e registre nas premissas; saldo sem data não vale como posição de outro dia.
- Sem situação do produto: não dá para separar item inativo ou fora de linha com saldo.

### 3.2 Kardex

**Pergunta:** como o produto chegou ao saldo atual.

**Colunas:** data, tipo de operação, documento, parceiro (fornecedor ou cliente), entrada, saída, saldo após o movimento, custo unitário, valor do movimento. Linha inicial com o saldo anterior ao período.

**Parâmetros naturais:** produto (obrigatório), loja, data inicial, data final.

```sql
SELECT CONVERT(varchar(10), k.dia, 23) data, k.tipo, k.documento, k.parceiro,
       CAST(k.entrada AS float) entrada, CAST(k.saida AS float) saida,
       CAST(k.saldo_anterior
            + SUM(k.entrada - k.saida) OVER (ORDER BY k.dia, k.seq ROWS UNBOUNDED PRECEDING) AS float) saldo,
       CAST(k.custo AS float) custo_unitario
FROM (SELECT m.<data> dia, m.<sequencial> seq, t.<descricao> tipo, m.<documento> documento, m.<parceiro> parceiro,
             CASE WHEN <sinal> =  1 THEN m.<quantidade> ELSE 0 END entrada,
             CASE WHEN <sinal> = -1 THEN m.<quantidade> ELSE 0 END saida,
             m.<custo> custo,
             (SELECT COALESCE(SUM(<sinal_a> * a.<quantidade>), 0)
              FROM <movimento> a
              WHERE a.<cod_produto> = m.<cod_produto> AND a.<cod_loja> = m.<cod_loja>
                AND a.<data> < '2025-07-01') saldo_anterior
      FROM <movimento> m
      LEFT JOIN <tipo_operacao> t ON t.<cod_tipo> = m.<tipo_operacao>
      WHERE m.<cod_produto> = <produto> AND m.<cod_loja> = <loja>
        AND m.<data> >= '2025-07-01' AND m.<data> < '2025-08-01') k
ORDER BY k.dia, k.seq OFFSET 0 ROWS
```

Notas:
- `seq` desempata movimentos do mesmo dia; sem uma coluna sequencial, use hora ou a chave da tabela. Sem desempate, o saldo linha a linha muda entre execuções.
- Se a tabela de movimento já grava o saldo após o movimento, use-o e confira contra o acumulado calculado: divergência entre os dois é achado.
- O saldo anterior recomposto desde o primeiro movimento só vale se o histórico estiver completo. Base com expurgo ou implantação com saldo inicial lançado direto: ancore no saldo atual e volte no tempo (3.8).
- Mais de uma loja: um Kardex por loja, ou consolidado com transferências internas somando zero.

**Prova:** saldo anterior + entradas - saídas = último saldo da lista; quando o período vai até a última data, último saldo = saldo atual da tabela de saldo.
**Leituras típicas:** ajustes manuais recorrentes, saída sem entrada que deixa o saldo negativo, entrada com custo muito fora da média, longos intervalos sem movimento.

**Para exportar:** peça o Kardex ou a movimentação de estoque do produto no período, em CSV ou Excel, de preferência de todos os movimentos de uma vez (o relatório por produto serve se for um produto só). Colunas mínimas: produto, data, tipo de operação, quantidade. Se o ERP já separa em colunas de entrada e saída, melhor: o sentido do movimento fica sem dúvida.

- Sem o tipo de operação e sem colunas de entrada e saída: não dá para saber o sentido de cada linha, e o relatório não sai.
- Sem o saldo anterior ao período: peça o saldo inicial, ou o período desde o primeiro movimento. Sem isso o Kardex começa em zero e o saldo linha a linha fica deslocado; diga isso.
- Sem o saldo atual (relatório de posição à parte): a prova com o saldo atual não existe, e o fechamento fica só em saldo anterior + entradas - saídas = último saldo.
- Sem documento ou parceiro: sai o saldo, mas não a origem de cada movimento.
- Sem custo no movimento: sem o valor do movimento e sem a leitura de entrada com custo fora da média.
- Sem sequencial nem hora, com vários movimentos no mesmo dia: o saldo linha a linha pode mudar de ordem; avise.

### 3.3 Análise de lote de inventário

**Pergunta:** o que o balanço encontrou e quanto isso custa.

**Colunas (analítico):** código, descrição, departamento, quantidade congelada, quantidade contada, divergência (contada - congelada), custo unitário, divergência em valor, situação (sobra, falta, sem divergência, não contado).
**Sintético:** por departamento e total: itens no lote, contados, não contados, com divergência, sobras em valor, faltas em valor, divergência líquida, divergência absoluta, acuracidade em itens % e acuracidade em valor %.

**Parâmetros naturais:** lote (ou loja + data), departamento, só divergentes.

```sql
SELECT p.<cod_departamento>,
       COUNT(*) itens,
       SUM(CASE WHEN i.<qtd_contada> IS NULL THEN 1 ELSE 0 END) nao_contados,
       SUM(CASE WHEN i.<qtd_contada> <> i.<qtd_congelada> THEN 1 ELSE 0 END) divergentes,
       CAST(SUM(CASE WHEN i.<qtd_contada> > i.<qtd_congelada> THEN (i.<qtd_contada> - i.<qtd_congelada>) * COALESCE(i.<custo>, 0) ELSE 0 END) AS float) sobra_valor,
       CAST(SUM(CASE WHEN i.<qtd_contada> < i.<qtd_congelada> THEN (i.<qtd_congelada> - i.<qtd_contada>) * COALESCE(i.<custo>, 0) ELSE 0 END) AS float) falta_valor,
       CAST(SUM(i.<qtd_congelada> * COALESCE(i.<custo>, 0)) AS float) valor_congelado,
       CAST(100.0 * SUM(CASE WHEN i.<qtd_contada> = i.<qtd_congelada> THEN 1 ELSE 0 END) / NULLIF(SUM(CASE WHEN i.<qtd_contada> IS NOT NULL THEN 1 ELSE 0 END), 0) AS float) acuracidade_itens_pct
FROM <inventario_item> i
JOIN <produto> p ON p.<cod_produto> = i.<cod_produto>
WHERE i.<cod_lote> = <lote>
GROUP BY p.<cod_departamento>
ORDER BY falta_valor DESC OFFSET 0 ROWS
```

Definições (declare na entrega):
- **Acuracidade em itens** = itens contados sem divergência / itens contados.
- **Acuracidade em valor** = 1 - (sobras + faltas em valor) / valor congelado. Usa a divergência **absoluta**: sobra e falta não se compensam.
- **Divergência líquida** = sobras - faltas. É o que ajusta o resultado; a absoluta mede a qualidade do processo.
- **Não contado** é diferente de contado zero. Se o sistema grava zero nos dois casos, diga que não dá para separar.

**Prova:** itens do lote = contados + não contados; total em valor = soma do analítico.
**Leituras típicas:** falta concentrada em poucos itens de alto valor (furto, erro de recebimento), sobra e falta em itens parecidos (troca de código na contagem ou no caixa), muitos não contados (balanço incompleto), divergência em pesáveis (tara, quebra operacional).

**Para exportar:** peça o relatório de resultado do balanço ou do lote de inventário, com uma linha por produto. Colunas mínimas: código do produto, quantidade congelada (a do sistema na hora do balanço), quantidade contada.

- Sem custo unitário: sai a divergência em quantidade, mas não em valor, nem sobras e faltas em valor, nem a acuracidade em valor.
- Sem departamento: sai o total e a lista, mas não o sintético por departamento.
- Sem situação do lote: não dá para saber se a contagem terminou. Pergunte, porque lote ainda em contagem mostra falta que é só item não contado.
- Se o ERP grava zero tanto para contado zero quanto para não contado: não dá para separar os dois. Diga isso e trate os zeros com a pessoa.
- Sem a data do balanço: registre a data informada pela pessoa nas premissas.

### 3.4 Cobertura e ruptura

**Pergunta:** o que vai faltar, o que já faltou e o que está sobrando.

**Colunas:** código, descrição, departamento, saldo, venda média diária (quantidade vendida / dias com loja aberta no período), dias de cobertura (saldo / venda média diária), situação.

**Situações (limites default, ajustáveis):**
| Situação | Regra |
|---|---|
| Ruptura | Saldo <= 0, produto ativo e com venda nos últimos 30 dias |
| Risco | Cobertura abaixo de 3 dias |
| Saudável | De 3 a 45 dias |
| Excesso | Acima de 45 dias |
| Sem giro | Saldo > 0 e nenhuma venda no período (vai para 3.5) |

Perecíveis e itens de alto giro pedem limites menores: se a pessoa disser o departamento, ajuste e declare.

```sql
SELECT s.<cod_produto>, CAST(s.<saldo> AS float) saldo,
       CAST(COALESCE(v.qtd, 0) / 30.0 AS float) venda_dia,
       CAST(s.<saldo> / NULLIF(COALESCE(v.qtd, 0) / 30.0, 0) AS float) dias_cobertura
FROM <saldo_estoque> s
LEFT JOIN (SELECT i.<cod_produto>, SUM(i.<quantidade>) qtd
           FROM <itens_venda> i
           WHERE <filtro_validos> AND i.<cod_loja> = <loja>
             AND i.<data> >= '2025-07-01' AND i.<data> < '2025-07-31'
           GROUP BY i.<cod_produto>) v ON v.<cod_produto> = s.<cod_produto>
WHERE s.<cod_loja> = <loja>
```

**Indicador de ruptura** = itens em ruptura / itens ativos do sortimento com venda recente. Diga sempre o denominador: ruptura sobre o cadastro inteiro fica artificialmente baixa.
**Limite da análise:** ruptura medida pelo saldo do sistema é a ruptura **contábil**. Produto com saldo no sistema e gôndola vazia (ruptura operacional) não aparece, e saldo negativo ou errado esconde ruptura real. Diga isso quando houver muitos negativos.
**Venda perdida estimada** (opcional, marque como estimativa): dias sem saldo x venda média diária x preço.
**Prova:** soma da quantidade vendida usada = quantidade vendida no período pela fonte de vendas.

**Para exportar:** são dois relatórios na mesma data: a posição de estoque (código, saldo) e a venda por item do período (código, quantidade, data), ligados pelo código do produto.

- Sem a venda por item: não dá para fazer só com a posição, porque cobertura e ruptura dependem do ritmo de venda. Sai apenas a lista de saldo zerado e negativo, sem dizer se o item vende.
- Sem data na venda: peça os dias do período à pessoa para calcular a venda diária e registre nas premissas.
- Sem situação do produto: a ruptura sai sobre o cadastro inteiro e fica artificialmente baixa. Diga o denominador.
- Sem departamento: sem os limites por departamento (perecível x seco).
- Sem preço: sai a quantidade perdida, mas não a venda perdida estimada.
- Sem loja: cobertura da rede, sem ler loja a loja.

### 3.5 Estoque sem venda

**Colunas:** código, descrição, departamento, saldo, valor a custo, última venda, dias sem venda, última entrada.
**Faixas:** 30 a 60, 61 a 90, 91 a 180, acima de 180 dias, e nunca vendeu.
Separe item novo (entrada recente, ainda sem venda) de item parado: sem isso, lançamento vira encalhe.
**Resumo:** valor parado por faixa e participação no estoque total.
**Prova:** soma do valor por faixa, mais o valor dos itens com venda recente, = valor a custo da posição inteira.
**Leitura típica:** capital imobilizado, candidatos a remarcação, devolução ao fornecedor ou transferência entre lojas (parado em uma, vendendo em outra).

**Para exportar:** peça a posição de estoque (código, saldo) e a data da última venda de cada produto. Se o ERP não tiver a última venda, peça a venda por item dos últimos 180 dias (código, data, quantidade), da qual ela sai.

- Sem a última venda e sem a venda por item: não dá para fazer só com a posição, porque ela não diz o que vendeu.
- Sem a data da última entrada: não dá para separar item novo de item parado. Avise que lançamento recente pode aparecer como encalhe.
- Sem custo: sai o saldo parado, mas não o valor a custo nem a participação no capital.
- Sem loja: parado na rede inteira, sem o cruzamento "parado numa loja, vendendo em outra".

### 3.6 Inconsistências de saldo

Lista de exceções, cada uma com contagem e os 20 maiores casos:
- saldo negativo;
- saldo positivo em produto inativo ou fora de linha;
- produto que controla estoque, com venda no período, e sem nenhum movimento de entrada;
- saldo com custo zero ou nulo;
- saldo diferente do Kardex recomposto (amostra dos itens de maior valor, não a base inteira);
- quantidade fracionada em item vendido por unidade.

**Prova:** para cada exceção, itens contados na fonte (com um `COUNT` direto, sem a lista) = itens listados + itens omitidos além dos 20 maiores, e a soma do valor por exceção bate com a soma direta na fonte. Dos 20 itens mostrados, confira 5 no detalhe da origem e diga "5 de 5 itens conferidos na origem": isso é conferência de amostra, não de total.

**Para exportar:** peça a posição de estoque com o cadastro do produto. Colunas mínimas: código, saldo. Cada exceção depende de uma coluna.

- Saldo negativo só pede o saldo.
- Saldo em produto inativo ou fora de linha pede a situação do produto.
- Saldo com custo zero pede o custo.
- Quantidade fracionada em item de unidade pede a unidade de medida.
- Produto com venda e sem nenhuma entrada, e saldo diferente do Kardex: não saem só com a posição, porque pedem a movimentação (3.2). Sem o arquivo de movimentação, essas duas listas ficam de fora e a entrega diz isso.

### 3.7 Giro e estoque médio

- **Giro** = custo da mercadoria vendida no período / estoque médio a custo.
- **Prazo médio de estoque (dias)** = dias do período / giro.
- **Estoque médio:** média das posições diárias ou mensais, se o ERP guardar fotografia; senão (posição inicial recomposta + posição final) / 2, dizendo que é aproximação de dois pontos.

Apresente por departamento, com o total. Giro calculado com venda a preço de venda sobre estoque a custo é erro comum: os dois lados a custo.

**Prova:** o custo da mercadoria vendida usado = total a custo da venda por item do período, somado direto na exportação ou tabela de vendas (`SUM(quantidade x custo)` com os mesmos filtros), e não a conta refeita a partir do mesmo cálculo.

**Para exportar:** peça a venda por item do período com o custo da mercadoria vendida (código, quantidade, custo unitário ou total a custo) e duas posições de estoque a custo, uma no início e outra no fim do período.

- Sem o custo na venda: não dá para fazer só com arquivo sem inventar custo, porque a venda a preço sobre estoque a custo é o erro que este relatório evita. Peça a venda com custo.
- Com uma posição só: o estoque médio é de um ponto e o giro sai aproximado. Diga isso.
- Sem departamento: sai o giro total, sem a quebra por departamento.
- Sem custo na posição: sem estoque a custo, e o giro não sai.

### 3.8 Posição retroativa

Saldo na data D = saldo atual - soma dos movimentos com sinal depois de D.

```sql
SELECT s.<cod_produto>,
       CAST(s.<saldo> - COALESCE(m.depois, 0) AS float) saldo_na_data
FROM <saldo_estoque> s
LEFT JOIN (SELECT a.<cod_produto>, SUM(<sinal_a> * a.<quantidade>) depois
           FROM <movimento> a
           WHERE a.<cod_loja> = <loja> AND a.<data> >= '2025-07-01'
           GROUP BY a.<cod_produto>) m ON m.<cod_produto> = s.<cod_produto>
WHERE s.<cod_loja> = <loja>
```

Prefira a fotografia do próprio ERP quando existir (tabela de posição diária ou de fechamento mensal). A valorização retroativa precisa do custo da época: com o custo atual, diga que a quantidade é da data e o custo é de hoje.
**Prova:** aplicar a mesma lógica com D = hoje devolve o saldo atual; e, para uma amostra, o resultado bate com o Kardex.

**Para exportar:** o caminho mais simples é pedir ao ERP o relatório de posição de estoque na data D, se ele gera posição em data passada (fotografia ou fechamento). Sem isso, peça a posição de hoje e a movimentação de estoque desde D até hoje, com data, tipo de operação e quantidade.

- Com a posição de hoje e a movimentação: a recomposição sai, com a prova de D = hoje.
- Sem o tipo de operação (ou colunas de entrada e saída): não dá para saber o sentido do movimento, e o relatório não sai.
- Se o ERP expurga movimento antigo, a recomposição fica incompleta. Diga até onde o histórico vai.
- Sem custo da época: a quantidade é da data D e o custo é o de hoje. Registre isso nas premissas.
