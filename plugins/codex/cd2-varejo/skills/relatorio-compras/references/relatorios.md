# Compras e abastecimento: mapeamento, relatórios e consultas-modelo

Conteúdo:
1. Mapeamento
2. O que medir
3. Relatórios (3.1 a 3.7)

Consultas em SQL Server com marcadores `<assim>`; **[modelo]** até passarem na prova nos dados da pessoa. O padrão de participação e acumulado por janela é **[validado]** pelo conector. Sem conexão, adapte a consulta com a tabela de `references/regras-sqlite.md` e troque os marcadores pelos nomes de coluna do perfil do arquivo. Cada relatório termina com **Para exportar**: o que pedir ao ERP quando não há conexão.

## 1. Mapeamento

Saldo, movimento, produto e venda por item: `references/mapeamento-erp.md`, seção 1. Acrescente:

| Domínio | Para quê | Termos de busca | O que confirmar |
|---|---|---|---|
| Pedido de compra | Pendentes, nível de serviço | `pedido_compra`, `ped_compra`, `ordem_compra`, `oc`, `purchase` | Cabeçalho e itens; datas de emissão e de entrega prevista; situação; quantidade pedida, recebida e cancelada |
| Entrada (recebimento) | Custo, prazo, pedido x nota | `nota_entrada`, `nf_entrada`, `recebimento`, `entrada`, `compra` | Data de emissão x data de entrada; tipo de operação (compra, bonificação, devolução, transferência); vínculo com o pedido |
| Fornecedor | Quebras | `fornecedor`, `parceiro`, `pessoa` | Chave, situação, comprador responsável |
| Produto x fornecedor | Embalagem, prazo | `prod_fornec`, `fornecedor_produto`, `embalagem`, `fator`, `lead_time`, `prazo_entrega` | Fator de conversão, múltiplo de compra, fornecedor principal |
| Parâmetros de reposição | Sugestão | `estoque_minimo`, `estoque_maximo`, `ponto_pedido`, `dias_cobertura`, `frequencia` | Se estão preenchidos de verdade (mínimo zerado em tudo = não usado) |
| Custo | Variação | `custo`, `custo_ultima_entrada`, `custo_medio`, `preco_compra` | Composição do custo e histórico de alteração |

## 2. O que medir

- Pedidos: por situação, período, % com data de entrega prevista, % de itens com quantidade recebida preenchida.
- Entradas: por tipo de operação, % com vínculo ao pedido, diferença entre data de emissão e de entrada.
- Parâmetros de reposição: % de itens ativos com mínimo, máximo, prazo e embalagem preenchidos.

Com arquivo, estas medidas saem do perfil de `scripts/dados_arquivo.py`. O que não estiver no arquivo não tem como ser medido: diga isso nas premissas.

## 3. Relatórios

### 3.1 ABC de abastecimento

**Colunas:** posição, código, descrição, fornecedor principal, quantidade vendida, venda a custo (ou quantidade, conforme a dimensão), participação %, acumulado %, classe, saldo atual, dias de cobertura, pendente de recebimento, alerta.

**Alertas do cruzamento:**
| Classe | Cobertura | Alerta |
|---|---|---|
| A | Menos de 7 dias e sem pedido pendente | Risco de ruptura em item crítico |
| A | Saldo <= 0 | Ruptura em item crítico |
| C | Mais de 90 dias | Excesso em item de baixa relevância |
| Qualquer | Saldo > 0 e sem venda | Parado (fica fora da curva, que só tem item vendido; saem da posição de estoque) |

A curva usa a medida `SUM(quantidade * custo)` (ou `SUM(quantidade)`), a classe pelo acumulado **antes** do item (A até 80%, B até 95%, C o restante) e, em cima dela, `LEFT JOIN` no saldo e no pendente por produto:

```sql
SELECT z.codigo, z.descricao, z.qtd, z.valor, z.part_pct, z.acum_pct, z.classe,
       z.saldo, z.dias_cobertura, z.pendente,
       CASE WHEN z.classe = 'A' AND z.saldo <= 0 THEN 'Ruptura em item crítico'
            WHEN z.classe = 'A' AND z.dias_cobertura < 7 AND z.pendente = 0 THEN 'Risco de ruptura em item crítico'
            WHEN z.classe = 'C' AND z.dias_cobertura > 90 THEN 'Excesso em item de baixa relevância'
            ELSE '' END alerta
FROM (SELECT y.codigo, y.descricao, CAST(y.qtd AS float) qtd, CAST(y.valor AS float) valor,
             CAST(y.part_pct AS float) part_pct, CAST(y.acum_pct AS float) acum_pct, y.classe,
             CAST(COALESCE(s.<saldo>, 0) AS float) saldo,
             CAST(COALESCE(s.<saldo>, 0) / NULLIF(y.qtd / 90.0, 0) AS float) dias_cobertura,
             CAST(COALESCE(pe.pendente, 0) AS float) pendente
      FROM (SELECT w.codigo, w.descricao, w.qtd, w.valor,
                   100.0 * w.valor / NULLIF(w.total, 0) part_pct,
                   100.0 * w.acum / NULLIF(w.total, 0) acum_pct,
                   CASE WHEN 100.0 * (w.acum - w.valor) / NULLIF(w.total, 0) < 80 THEN 'A'
                        WHEN 100.0 * (w.acum - w.valor) / NULLIF(w.total, 0) < 95 THEN 'B' ELSE 'C' END classe
            FROM (SELECT x.codigo, x.descricao, x.qtd, x.valor,
                         SUM(x.valor) OVER () total,
                         SUM(x.valor) OVER (ORDER BY x.valor DESC, x.codigo ROWS UNBOUNDED PRECEDING) acum
                  FROM (SELECT i.<cod_produto> codigo, MAX(p.<descricao>) descricao,
                               SUM(i.<quantidade>) qtd, SUM(i.<quantidade> * COALESCE(i.<custo_unitario>, 0)) valor
                        FROM <itens_venda> i
                        LEFT JOIN <produto> p ON p.<cod_produto> = i.<cod_produto> /* e loja, se o cadastro for por loja */
                        WHERE <filtro_validos> AND i.<cod_loja> = <loja>
                          AND i.<data> >= '2025-07-01' AND i.<data> < '2025-09-29'
                        GROUP BY i.<cod_produto>
                        HAVING SUM(i.<quantidade> * COALESCE(i.<custo_unitario>, 0)) > 0) x) w) y
      LEFT JOIN <saldo_estoque> s ON s.<cod_produto> = y.codigo AND s.<cod_loja> = <loja>
      LEFT JOIN (SELECT pi.<cod_produto>,
                        SUM(pi.<qtd_pedida> - COALESCE(pi.<qtd_recebida>, 0) - COALESCE(pi.<qtd_cancelada>, 0)) pendente
                 FROM <pedido_compra_item> pi
                 JOIN <pedido_compra> pc ON pc.<num_pedido> = pi.<num_pedido>
                 WHERE pc.<cod_loja> = <loja> AND pc.<situacao> IN (<abertos>)
                 GROUP BY pi.<cod_produto>) pe ON pe.<cod_produto> = y.codigo) z
ORDER BY z.valor DESC, z.codigo OFFSET 0 ROWS
```

Notas:
- O divisor `90.0` é o número de dias do período de demanda: troque junto com as datas.
- Itens com valor zero ou negativo ficam fora da curva e são contados à parte.
- Limites de cobertura são defaults: ajuste por departamento quando a pessoa indicar.
- Com arquivo, a descrição costuma vir na mesma linha: use `MAX(i.<descricao>)` no lugar do join com o cadastro, e o saldo e o pendente vêm de outro arquivo, ligado pelo código.
- A lista completa costuma passar de 30 linhas: quadro de classes e os 30 primeiros na conversa, o restante em planilha.

**Por quantidade ou por valor:** por valor responde "onde está o capital"; por quantidade responde "o que mais movimenta doca e gôndola". Itens A nas duas são o núcleo do abastecimento.
**Prova:** soma da medida = total do período; número de itens antes e depois do cruzamento é o mesmo (join com saldo não pode multiplicar nem descartar linhas).

**Para exportar:** peça a venda por item do período (de 90 dias, se der), com o custo, e a posição de estoque na data mais recente. Colunas mínimas da venda: código do produto, descrição, quantidade vendida, custo unitário (ou o valor a custo da linha). Da posição: código e saldo.

- Sem custo: a curva sai só por quantidade, não por valor a custo, e isso fica dito.
- Sem a posição de estoque: sai a curva, mas sem cobertura e sem alertas.
- Sem os pedidos pendentes (relatório de pedidos em aberto, 3.3): o alerta de risco de ruptura ignora o pedido a caminho e pode apontar item que já vai chegar. Avise.
- Sem data na venda: o período vale o que a pessoa informar, e o divisor de dias da cobertura é esse número.
- Sem fornecedor: sem a coluna de fornecedor principal.
- Sem loja: a curva e a cobertura são da rede inteira.

### 3.2 Sugestão de compra

**Fórmula (por produto e local):**

```
demanda_dia    = quantidade vendida no período / dias considerados
dias_alvo      = lead time + intervalo entre pedidos + dias de segurança
necessidade    = demanda_dia x dias_alvo
sugestão bruta = necessidade - saldo disponível - pendente de recebimento
sugestão       = arredonda para cima no múltiplo da embalagem de compra (zero se negativa)
```

**Colunas:** código, descrição, embalagem, demanda diária, saldo, pendente, cobertura atual em dias, dias alvo, necessidade, sugestão em unidades e em embalagens, custo unitário, valor da sugestão, observação.

```sql
SELECT p.<cod_produto>, p.<descricao>,
       CAST(COALESCE(v.qtd, 0) / 90.0 AS float) demanda_dia,
       CAST(COALESCE(s.<saldo>, 0) AS float) saldo,
       CAST(COALESCE(pe.pendente, 0) AS float) pendente,
       CAST(COALESCE(v.qtd, 0) / 90.0 * <dias_alvo>
            - COALESCE(s.<saldo>, 0) - COALESCE(pe.pendente, 0) AS float) sugestao_bruta,
       CAST(pf.<fator_embalagem> AS float) embalagem, CAST(p.<custo> AS float) custo
FROM <produto> p
JOIN <produto_fornecedor> pf ON pf.<cod_produto> = p.<cod_produto> AND pf.<cod_fornecedor> = <fornecedor>
LEFT JOIN <saldo_estoque> s ON s.<cod_produto> = p.<cod_produto> AND s.<cod_loja> = <loja>
LEFT JOIN (SELECT i.<cod_produto>, SUM(i.<quantidade>) qtd
           FROM <itens_venda> i
           WHERE <filtro_validos> AND i.<cod_loja> = <loja>
             AND i.<data> >= '2025-07-01' AND i.<data> < '2025-09-29'
           GROUP BY i.<cod_produto>) v ON v.<cod_produto> = p.<cod_produto>
LEFT JOIN (SELECT pi.<cod_produto>,
                  SUM(pi.<qtd_pedida> - COALESCE(pi.<qtd_recebida>, 0) - COALESCE(pi.<qtd_cancelada>, 0)) pendente
           FROM <pedido_compra_item> pi
           JOIN <pedido_compra> pc ON pc.<num_pedido> = pi.<num_pedido>
           WHERE pc.<cod_loja> = <loja> AND pc.<situacao> IN (<abertos>)
           GROUP BY pi.<cod_produto>) pe ON pe.<cod_produto> = p.<cod_produto>
WHERE p.<ativo> = <sim>
```

Faça o arredondamento por embalagem e o corte em zero no resultado (ou com `CEILING` na consulta), e marque na coluna de observação:
- item com ruptura no período (demanda subestimada);
- item novo, com menos de 30 dias de venda (demanda instável);
- item com promoção no período (demanda superestimada);
- saldo negativo (tratado como zero; corrija o estoque antes);
- item sem embalagem ou sem custo.

**Premissas a declarar sempre:** de onde vieram lead time, intervalo e segurança (cadastro, observado ou default informado pela pessoa). Sem nenhuma dessas fontes, pergunte os três números em uma pergunta só.
**Limite:** média simples não trata sazonalidade nem tendência. Para datas sazonais (Páscoa, Natal, volta às aulas), compare com o mesmo período do ano anterior e diga que a sugestão não captura o pico.
**Prova:** para 5 itens da amostra, confira demanda, saldo e pendente contra as fontes; valor total = soma das linhas.

**Para exportar:** peça três relatórios, ligados pelo código do produto: a venda por item do período (código, quantidade, data), a posição de estoque (código, saldo) e os pedidos de compra em aberto (produto, quantidade pedida, recebida e cancelada). Recomendados: o cadastro de produto por fornecedor (embalagem, fornecedor) e o custo.

- Sem os pedidos em aberto: a sugestão pode pedir de novo o que já está a caminho. Avise e deixe a coluna de pendente à mão para a pessoa preencher.
- Sem a embalagem de compra: a sugestão sai em unidades, sem arredondar para caixa.
- Sem o custo: sai a quantidade, mas não o valor da sugestão.
- Sem o fornecedor de cada produto: sai a lista da loja inteira, sem o filtro por fornecedor.
- Sem lead time, intervalo e segurança: a pessoa informa os três números (ou aceita os do prazo observado nas entradas, se enviar o arquivo de entradas).
- Sem data na venda: os dias do período vêm da pessoa.

### 3.3 Pedidos pendentes

**Colunas:** pedido, fornecedor, emissão, entrega prevista, dias de atraso, produto, pedido, recebido, cancelado, pendente, valor pendente.
**Sintético por fornecedor:** pedidos, itens pendentes, valor pendente, valor atrasado, maior atraso.
**Faixas de atraso:** no prazo, 1 a 7, 8 a 15, 16 a 30, acima de 30 dias. Pedido muito antigo em aberto geralmente é sujeira (saldo que deveria ter sido eliminado): destaque em vez de somar ao que "vai chegar".
**Prova:** pedido = recebido + cancelado + pendente em cada item.

**Para exportar:** peça o relatório de pedidos de compra em aberto, um item por linha. Colunas mínimas: número do pedido, fornecedor, produto, quantidade pedida, quantidade recebida, data de entrega prevista.

- Sem a quantidade cancelada: o pendente sai inflado (pedido - recebido) e a prova de pedido = recebido + cancelado + pendente não fecha. Avise e peça a coluna.
- Sem a data de entrega prevista: não há atraso nem faixas, só o pendente.
- Sem a data de emissão: não dá para destacar o pedido antigo que é sujeira.
- Sem custo ou valor do item: sem valor pendente nem valor atrasado.
- Se a exportação traz só os pedidos ainda abertos pela situação do cabeçalho, pode perder item pendente em pedido marcado como atendido. Pergunte como o ERP fecha o pedido.

### 3.4 Nível de serviço do fornecedor

| Indicador | Fórmula |
|---|---|
| Atendimento em quantidade (fill rate) | Quantidade recebida / quantidade pedida, nos pedidos com entrega prevista no período |
| Pontualidade | Recebimentos até a data prevista / recebimentos |
| OTIF (On Time In Full; no prazo e completo) | Pedidos recebidos completos e no prazo / pedidos |
| Prazo médio observado | Média de (data de entrada - data do pedido), em dias |
| Variabilidade do prazo | Desvio padrão do prazo (é ela que define o estoque de segurança) |

**Colunas:** fornecedor, pedidos, valor comprado, atendimento %, pontualidade %, OTIF %, prazo médio, desvio do prazo.
Sem data de entrega prevista, não há pontualidade nem OTIF: entregue atendimento e prazo observado e diga o que faltou.
**Prova:** recebimentos considerados = entradas de compra do período com vínculo a pedido; informe o % de entradas sem pedido (compra fora do processo).

**Para exportar:** peça os pedidos de compra do período com o recebimento de cada item. Colunas mínimas: número do pedido, fornecedor, produto, quantidade pedida, quantidade recebida, data do pedido, data do recebimento.

- Sem a data de entrega prevista: sai o atendimento e o prazo observado, sem pontualidade nem OTIF.
- Sem a data do pedido: sem prazo médio nem variabilidade.
- Sem o vínculo da entrada com o pedido: pergunte se as notas trazem o número do pedido. Sem ele, o recebimento não se liga ao pedido e o relatório não sai.
- Sem as entradas de compra que não têm pedido: o percentual de compra fora do processo não sai.
- Sem valor: sem a coluna de valor comprado.

### 3.5 Variação de custo de compra

**Colunas:** produto, fornecedor, custo da penúltima entrada, custo da última entrada, variação %, data, quantidade comprada, valor comprado no período, impacto estimado (variação x quantidade vendida mensal), preço de venda atual, margem antes e depois.

Compare entradas de **compra** (sem bonificação, devolução ou transferência) do mesmo fornecedor e da mesma embalagem. Para pegar as duas últimas entradas por produto, numere as entradas com `ROW_NUMBER() OVER (PARTITION BY produto, fornecedor ORDER BY data DESC, chave DESC)` em tabela derivada. Numere todas as entradas do período, sem filtrar `rn <= 2`: a última (`rn = 1`) e a penúltima (`rn = 2`) dão o custo e a variação, e a soma de todas dá o valor comprado.

```sql
SELECT e.<cod_produto>, e.<cod_fornecedor>,
       CAST(MAX(CASE WHEN e.rn = 1 THEN e.custo END) AS float) custo_ultima,
       CAST(MAX(CASE WHEN e.rn = 2 THEN e.custo END) AS float) custo_penultima,
       CAST(100.0 * MAX(CASE WHEN e.rn = 1 THEN e.custo END)
            / NULLIF(MAX(CASE WHEN e.rn = 2 THEN e.custo END), 0) - 100.0 AS float) variacao_pct,
       CAST(SUM(e.qtd * e.custo) AS float) valor_comprado
FROM (SELECT ni.<cod_produto>, n.<cod_fornecedor>, ni.<custo_unitario> custo, ni.<quantidade> qtd,
             ROW_NUMBER() OVER (PARTITION BY ni.<cod_produto>, n.<cod_fornecedor>
                                ORDER BY n.<data_entrada> DESC, n.<chave> DESC) rn
      FROM <nota_entrada> n
      JOIN <nota_entrada_item> ni ON ni.<chave> = n.<chave>
      WHERE <so_compra> AND n.<data_entrada> >= '2025-04-01' AND n.<data_entrada> < '2025-10-01') e
GROUP BY e.<cod_produto>, e.<cod_fornecedor>
ORDER BY ABS(variacao_pct) DESC OFFSET 0 ROWS
```

Produto com uma só entrada no período fica na lista com a variação vazia: ele não tem comparação, mas o valor comprado dele entra na prova.
**Leituras típicas:** aumento ainda não repassado ao preço (margem comprimida, cruze com a margem do período), variação grande por mudança de embalagem ou de composição de imposto (falso aumento), queda de custo não aproveitada.
**Prova:** soma de `valor_comprado` de todas as linhas = soma de quantidade x custo de todas as entradas de compra do período, direto na tabela de entradas, sem o ranking. Informe também quantos produtos ficaram sem variação por terem uma entrada só.

**Para exportar:** peça o relatório de notas de entrada por item, de um período longo o bastante para cada produto ter pelo menos duas entradas. Colunas mínimas: produto, fornecedor, data de entrada, custo unitário, quantidade.

- Sem tipo de operação: não dá para separar compra de bonificação, devolução e transferência, e o custo zerado de uma bonificação parece queda. Peça a exportação só com notas de compra e registre isso nas premissas.
- Sem embalagem: a troca de caixa com 12 por caixa com 24 parece variação de custo. Avise que pode haver falso aumento.
- Sem venda mensal por produto: sai a variação, mas não o impacto estimado.
- Sem preço de venda atual: sai a variação, mas não a margem antes e depois.
- Sem o total das entradas do período por outra fonte: a prova fecha só contra o arquivo, entre as linhas e o total das notas exportadas.

### 3.6 Pedido x nota

**Colunas:** pedido, nota, produto, quantidade pedida x faturada, custo pedido x faturado, diferença em valor, tipo de divergência (preço maior, quantidade maior, item sem pedido, item não entregue).
**Tolerância default:** 1% no preço e na quantidade, ajustável. Declare.
**Prova:** valor da nota = soma dos itens conferidos + itens sem pedido.

**Para exportar:** peça os itens do pedido de compra e os itens da nota de entrada, ligados pelo número do pedido. Colunas mínimas: do pedido, número, produto, quantidade e custo pedidos; da nota, número da nota, número do pedido, produto, quantidade e custo faturados.

- Sem o número do pedido na nota: não dá para ligar nota e pedido, e o relatório não sai só com arquivo. Pergunte se existe outro campo de vínculo.
- Sem o item sem pedido na exportação da nota (só os itens com pedido): a prova do valor da nota não fecha. Peça a nota completa.
- Sem o valor total da nota: a prova fecha só contra a soma das linhas exportadas.
- Sem custo no pedido: sai a divergência de quantidade, não a de preço.

### 3.7 Concentração de fornecedores

ABC de fornecedores por valor comprado; participação do maior, dos 5 e dos 10 maiores; por departamento, itens da classe A de venda com fornecedor único. Leitura de risco de dependência, não de desempenho.
**Prova:** soma do valor dos fornecedores = total comprado no período, nas mesmas notas de compra.

**Para exportar:** peça o relatório de compras por fornecedor do período. Colunas mínimas: fornecedor, valor comprado.

- Sem tipo de operação: bonificação, devolução e transferência entram na soma e distorcem a participação. Peça só notas de compra.
- Sem departamento: sai a concentração geral, sem a quebra por departamento.
- Itens da classe A com fornecedor único: precisam da venda por item e do fornecedor de cada produto; sem eles, essa leitura fica de fora.
