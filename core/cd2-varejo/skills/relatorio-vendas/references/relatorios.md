# Vendas: mapeamento, relatórios e consultas-modelo

Conteúdo:
1. Mapeamento
2. O que medir
3. Relatórios (3.1 a 3.6)

Consultas em SQL Server com marcadores `<assim>`; **[modelo]** até passarem na prova nos dados da pessoa. O padrão de participação e acumulado por janela é **[validado]** pelo conector. Sem conexão, adapte a consulta com a tabela de `references/regras-sqlite.md` e troque os marcadores pelos nomes de coluna do perfil do arquivo. Cada relatório termina com **Para exportar**: o que pedir ao ERP quando não há conexão.

## 1. Mapeamento

Venda por cupom, itens, produto, departamento, loja e custo: `references/indicadores-varejo.md`, seção 1. Pedido e faturamento, cliente, segmento e canal, vendedor, devolução e composição: `references/mapeamento-erp.md`, seção 2.

## 2. O que medir

- Venda: período com dado, linhas por tipo de operação e por situação, % com cliente identificado, % com segmento e vendedor.
- Bonificação, remessa, transferência e venda para consumo interno costumam estar na mesma tabela: separe pelo tipo de operação ou CFOP (Código Fiscal de Operações e Prestações) antes de somar.
- Devolução: volume, período, % com vínculo à venda original e % com motivo.
- Composição: quantos produtos têm ficha, quantos componentes por ficha, fichas com componente inativo.

Com arquivo, estas medidas saem do perfil de `scripts/dados_arquivo.py`. O que não estiver no arquivo não tem como ser medido: diga isso nas premissas.

## 3. Relatórios

### 3.1 ABC de venda

**Colunas:** posição, código, descrição (produto, cliente, segmento ou vendedor), quantidade, venda líquida, participação %, acumulado %, classe; com custo confiável, margem em valor e %.
**Quadro de classes:** classe, itens, % dos itens, venda, % da venda.
**Parâmetros naturais:** período, loja, departamento ou segmento, dimensão, medida.

```sql
SELECT y.codigo, y.descricao, CAST(y.qtd AS float) qtd, CAST(y.valor AS float) valor,
       CAST(100.0 * y.valor / NULLIF(y.total, 0) AS float) part_pct,
       CAST(100.0 * y.acum / NULLIF(y.total, 0) AS float) acum_pct,
       CASE WHEN 100.0 * (y.acum - y.valor) / NULLIF(y.total, 0) < 80 THEN 'A'
            WHEN 100.0 * (y.acum - y.valor) / NULLIF(y.total, 0) < 95 THEN 'B' ELSE 'C' END classe
FROM (SELECT x.codigo, x.descricao, x.qtd, x.valor,
             SUM(x.valor) OVER () total,
             SUM(x.valor) OVER (ORDER BY x.valor DESC, x.codigo ROWS UNBOUNDED PRECEDING) acum
      FROM (SELECT i.<cod_produto> codigo, MAX(p.<descricao>) descricao,
                   SUM(i.<quantidade>) qtd, SUM(i.<valor_liquido>) valor
            FROM <itens_venda> i
            LEFT JOIN <produto> p ON p.<cod_produto> = i.<cod_produto> /* e loja, se o cadastro for por loja */
            WHERE <filtro_validos>
              AND i.<data> >= '2025-07-01' AND i.<data> < '2025-10-01'
            GROUP BY i.<cod_produto>
            HAVING SUM(i.<valor_liquido>) > 0) x) y
ORDER BY y.valor DESC, y.codigo OFFSET 0 ROWS
```

Notas:
- A classe usa o acumulado **antes** do item (`acum - valor`), para o item que cruza os 80% ainda ser A. É a convenção mais comum; declare.
- Itens com venda líquida zero ou negativa (devolução maior que a venda) ficam fora da curva e são contados à parte.
- A lista completa costuma passar de 30 linhas: quadro de classes e os 30 primeiros na conversa, o restante em planilha.
- ABC por margem: troque `valor` pela margem em valor e trate margem negativa à parte (ela distorce o acumulado).
- Com arquivo, a descrição costuma vir na mesma linha: use `MAX(i.<descricao>)` no lugar do join com o cadastro.

**Prova:** soma de `valor` = venda líquida total do período pelos mesmos filtros; último `acum_pct` = 100.
**Leituras típicas:** quantos itens fazem a classe A e se estão com estoque (cruze com o relatório de estoque, cobertura), cauda C longa com custo de manter em linha, item A com margem baixa, dependência de poucos clientes.

**Para exportar:** peça o relatório de venda por item do período, em CSV ou Excel, com uma linha por produto (melhor ainda, por produto e dia). Colunas mínimas: código do produto, descrição, quantidade, valor líquido.

- Sem data: não dá para conferir o período nem recortar 90 dias. O relatório vale pelo período que a pessoa informar, e isso entra nas premissas.
- Sem loja: sai só a curva da rede inteira.
- Sem departamento: sai a curva, mas não o sintético por departamento.
- Sem custo: sem coluna de margem e sem ABC por margem.
- Sem situação do item: não dá para tirar os cancelados. Peça a exportação só com vendas válidas e registre isso nas premissas.
- Sem valor líquido: use o bruto só se a pessoa confirmar e diga na entrega que devolução e desconto não foram abatidos.

### 3.2 Venda por cliente e segmento

**Colunas (sintético por segmento):** segmento, clientes ativos, pedidos ou cupons, venda líquida, participação %, ticket médio, margem % (se confiável), variação contra o período anterior.
**Analítico por cliente:** cliente, segmento, vendedor, pedidos, venda, ticket, itens distintos comprados, última compra, margem %.
**Opcional:** cliente x departamento (mix), para ver o que cada cliente não compra.

```sql
SELECT c.<segmento>, COUNT(DISTINCT v.<cod_cliente>) clientes, COUNT(*) documentos,
       CAST(SUM(v.<valor_liquido>) AS float) venda,
       CAST(SUM(v.<valor_liquido>) / NULLIF(COUNT(*), 0) AS float) ticket
FROM <venda> v
LEFT JOIN <cliente> c ON c.<cod_cliente> = v.<cod_cliente>
WHERE <filtro_validos> AND v.<data> >= '2025-07-01' AND v.<data> < '2025-08-01'
GROUP BY c.<segmento>
ORDER BY SUM(v.<valor_liquido>) DESC OFFSET 0 ROWS
```

Mantenha a linha de "sem cliente" e a de "sem segmento": elas são o tamanho do que o relatório não enxerga.
**Prova:** soma das linhas = venda total; venda identificada + não identificada = total.
**Leituras típicas:** concentração (os 10 maiores clientes fazem quanto), segmento com ticket alto e margem baixa, clientes com mix estreito.

**Para exportar:** peça o relatório de venda por cliente ou por documento do período. Colunas mínimas: cliente (código ou nome), documento, data, valor líquido. Traga também as vendas sem cliente, ou peça o total de venda do período: sem isso, a parte "não identificada" da prova não existe.

- Sem segmento: sai só a lista por cliente.
- Sem vendedor: sem quebra por vendedor.
- Sem item vendido: sem itens distintos comprados e sem o mix por departamento.
- Sem custo: sem margem.
- Sem o período anterior: sem a variação.

### 3.3 Produto final x componentes

**Pergunta:** quanto rendeu o produto composto e o que os componentes custaram.

Três casos, com tabelas diferentes:
| Caso | Exemplo | O que comparar |
|---|---|---|
| Kit ou cesta | Cesta de Natal | Receita do kit x soma dos componentes a preço e a custo |
| Receita ou produção | Pão, prato pronto | Custo da ficha técnica x custo real dos insumos baixados; rendimento previsto x obtido |
| Desmontagem | Carcaça em cortes | Peso de entrada x soma dos cortes; perda; custo rateado por corte |

**Colunas:** produto final, quantidade vendida ou produzida, receita, componente, quantidade prevista (ficha x quantidade do pai), quantidade real baixada (se houver apontamento), custo do componente, custo total, rendimento % (obtido / previsto), margem do produto final.

```sql
SELECT f.<cod_produto_final>, f.<cod_componente>, MAX(pc.<descricao>) componente,
       CAST(SUM(v.qtd * f.<qtd_por_unidade>) AS float) qtd_prevista,
       CAST(SUM(v.qtd * f.<qtd_por_unidade> * COALESCE(pc.<custo>, 0)) AS float) custo_previsto
FROM (SELECT i.<cod_produto> cod, SUM(i.<quantidade>) qtd
      FROM <itens_venda> i
      WHERE <filtro_validos> AND i.<data> >= '2025-07-01' AND i.<data> < '2025-08-01'
      GROUP BY i.<cod_produto>) v
JOIN <composicao> f ON f.<cod_produto_final> = v.cod
JOIN <produto> pc ON pc.<cod_produto> = f.<cod_componente>
GROUP BY f.<cod_produto_final>, f.<cod_componente>
ORDER BY f.<cod_produto_final>, custo_previsto DESC OFFSET 0 ROWS
```

Atenção: ficha com vários níveis (componente que também é composto) exige explodir nível a nível; sem CTE recursiva pelo conector, limite a dois ou três níveis com joins encadeados e diga quando houver nível não explodido.
**Prova:** custo previsto dos componentes / quantidade vendida = custo unitário do produto final no cadastro, ou a diferença é explicada (ficha desatualizada, perda).
**Leituras típicas:** produto final vendido abaixo do custo dos componentes, ficha desatualizada, rendimento real abaixo do previsto.

**Para exportar:** são dois arquivos na mesma base. O de venda por item do período (código do produto, quantidade, valor líquido) e o da ficha técnica ou composição (produto final, componente, quantidade por unidade, custo do componente).

- Sem o arquivo da ficha técnica, não dá para fazer só com arquivo, porque a venda não traz a composição. Nesse caso, diga isso e ofereça a ABC do produto final.
- Sem quantidade real baixada: sai o custo previsto, mas não o rendimento obtido.
- Sem custo do componente: sai a quantidade prevista, mas não o custo nem a margem.
- Desmontagem: peça também o peso de entrada e o peso de cada corte. Sem eles, não sai a perda.

### 3.4 Comparativo de períodos

**Colunas:** dimensão (loja, departamento, segmento), venda atual, venda anterior, variação em valor e %, contribuição para a variação total em pontos percentuais.
- Período anterior: imediatamente anterior de mesma duração, ou mesmo período do ano anterior alinhado por dia da semana (364 dias atrás) quando houver histórico.
- **Mesmas lojas:** só lojas com venda nos dois períodos.
- Decomposição simples da variação, quando houver cupons: efeito fluxo (cupons) e efeito ticket.
- Use a regra de base comparável de `references/indicadores-varejo.md`, seção 3 (menos de 30 documentos ou menos de 10% do outro período: sem comparação).

**Prova:** total = mesmas lojas + novas + encerradas, nos dois períodos.

**Para exportar:** peça o relatório de venda dos dois períodos, em um arquivo com a data em cada linha ou em dois arquivos, um por período. Colunas mínimas: data e valor líquido. Recomendadas: loja e a dimensão que será comparada (departamento ou segmento).

- Sem data em cada linha e com um arquivo só: não dá para separar os períodos.
- Sem loja: não dá para isolar mesmas lojas. Sai a comparação do total, a prova vira soma das linhas = total, e isso fica dito na entrega.
- Sem departamento ou segmento: a comparação sai só por loja ou no total.
- Sem documento (cupom ou nota): sem a decomposição em fluxo e ticket e sem a regra de base comparável. Avise que a comparação pode estar sobre base pequena.

### 3.5 Devoluções e cancelamentos

**Colunas:** motivo, ocorrências, valor, % sobre a venda bruta; por produto, cliente, vendedor ou operador nos 20 maiores.
**Indicadores:** taxa de devolução (devolução / venda bruta), prazo médio entre venda e devolução (com vínculo), % sem motivo.
Separe cancelamento (antes de faturar ou no caixa) de devolução (depois da venda concluída) e de troca (devolução com nova venda).
**Prova:** soma por motivo = devolução total do período.
**Leituras típicas:** produto com devolução acima da média (qualidade, cadastro, entrega), concentração em um operador ou vendedor, motivo "outros" dominante (o campo não informa nada).

**Para exportar:** o relatório comum de venda quase nunca traz cancelados e devoluções. Peça o relatório específico de devoluções e cancelamentos do período. Colunas mínimas: tipo (cancelamento, devolução ou troca), data, valor.

- Sem motivo: sai o total por tipo, mas não a prova por motivo. Vira soma das linhas = total.
- Sem a venda bruta do período: sai o valor, mas não a taxa de devolução.
- Sem vínculo com a venda original: sem o prazo médio entre venda e devolução.
- Sem produto, cliente, vendedor ou operador: sem o ranking dos 20 maiores naquela dimensão.

### 3.6 Carteira de clientes

**Positivação:** clientes com compra no período / clientes ativos da carteira (por vendedor ou segmento).
**RFV (Recência, Frequência e Valor; em inglês RFM, Recency, Frequency, Monetary):** dias desde a última compra, número de compras e valor em 12 meses, por cliente.
**Inativos:** compraram entre 90 e 365 dias atrás e não nos últimos 90 (limites ajustáveis), ordenados pelo valor que compravam.

```sql
SELECT v.<cod_cliente>, COUNT(*) compras, CAST(SUM(v.<valor_liquido>) AS float) valor,
       CONVERT(varchar(10), MAX(v.<data>), 23) ultima_compra,
       DATEDIFF(day, MAX(v.<data>), <data_referencia>) dias_sem_compra
FROM <venda> v
WHERE <filtro_validos> AND v.<cod_cliente> IS NOT NULL
  AND v.<data> >= DATEADD(day, -365, <data_referencia>)
GROUP BY v.<cod_cliente>
HAVING MAX(v.<data>) < DATEADD(day, -90, <data_referencia>)
ORDER BY SUM(v.<valor_liquido>) DESC OFFSET 0 ROWS
```

`<data_referencia>` é a última data com venda, não a data de hoje.
**Limite:** vale para a parcela identificada da venda; informe a cobertura. Sem contato nem endereço na saída (`references/metodo-analise.md`, seção 6).

**Para exportar:** peça a venda por cliente e documento dos últimos 12 meses. Colunas mínimas: cliente (código ou nome), data, valor líquido.

- Não dá para fazer só com arquivo porque a carteira depende de saber quem comprou, quando a exportação não traz o cliente em cada venda.
- Com menos de 12 meses: a frequência e o valor ficam curtos, e quem comprou antes do início do arquivo pode aparecer como cliente novo. Diga até onde o arquivo vai.
- Sem o cadastro de clientes ativos: sem positivação. Saem RFV e inativos.
- Sem vendedor ou segmento: sem as quebras por vendedor e segmento.
