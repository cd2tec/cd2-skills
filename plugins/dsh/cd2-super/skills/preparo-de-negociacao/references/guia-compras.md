Regras do relatório compras, reaproveitadas aqui: valem para conta, recorte e prova. Entrega e fechamento são os desta skill.


# Relatório de compras

Esta skill é da CD2 Tech. Ela responde às perguntas do comprador: o que comprar, quanto, de quem, a que custo e o quanto dá para confiar no fornecedor, do dado até um relatório com veredito, leitura e prova.

Os caminhos entre crases abaixo são relativos à pasta desta skill. Rode os comandos sempre a partir da pasta de trabalho da pessoa (a pasta da conversa ou do projeto), chamando os scripts pelo caminho completo, como em python3 <pasta da skill>/scripts/render_relatorio.py. Assim a entrada e as entregas ficam na pasta de trabalho, nunca dentro da pasta do plugin.

Siga o roteiro de conversa em `references/fluxo-dados.md` e o método em `references/metodo-analise.md`. Mapeamento, colunas, consultas-modelo, provas e o que exportar de cada relatório estão em `references/relatorios-compras.md`. Saldo de estoque e venda por item são mapeados em `references/mapeamento-erp.md`, seção 1.

**Esta skill ou o painel?** Painel para acompanhar a operação (cards, linha do tempo, mapa de calor) é `painel-varejo`. Aqui o resultado é um relatório analítico, com linhas e prova, para decidir o que comprar, de quem e a que custo.

## Relatórios

| A pessoa pede | Relatório | Seção |
|---|---|---|
| "curva ABC de abastecimento", "ABC de compras" | ABC de abastecimento | 3.1 |
| "o que comprar", "sugestão de pedido", "reposição" | Sugestão de compra | 3.2 |
| "pedidos em aberto", "o que está para chegar", "atrasados" | Pedidos pendentes | 3.3 |
| "desempenho do fornecedor", "quem atrasa", "entrega incompleta" | Nível de serviço do fornecedor | 3.4 |
| "o que subiu de custo", "variação de custo" | Variação de custo de compra | 3.5 |
| "pedido bate com a nota?", "divergência no recebimento" | Pedido x nota | 3.6 |
| "dependência de fornecedor" | Concentração de fornecedores | 3.7 |

Pedido genérico ("análise de compras") recebe a **ABC de abastecimento por valor cruzada com cobertura**, que é onde aparecem os dois erros caros: item A sem estoque e item C com estoque demais.

## Padrões de recorte

- **Período de demanda:** 90 dias até a última data com venda (30 dias para perecíveis, se a pessoa indicar).
- **Dimensão da ABC:** produto, por valor de venda a custo (o que consome capital de giro). Por quantidade quando a pessoa pedir: muda a ordem e a decisão logística.
- **Sugestão de compra:** por fornecedor ou por comprador, uma loja ou centro de distribuição por vez.
- **Pedidos pendentes:** todos os em aberto na data de referência.

## O que compras tem de particular

1. **Demanda não é venda.** Venda de item que ficou em ruptura subestima a demanda; venda em promoção superestima. Para a sugestão, use venda média dos **dias com saldo** quando der para saber, e sinalize itens que tiveram promoção no período.
2. **Embalagem de compra.** Pede-se em caixa, fardo ou palete, vende-se em unidade. Converta pelo fator de embalagem do fornecedor e arredonde a sugestão para cima no múltiplo.
3. **Prazo e frequência.** Sugestão sem lead time (prazo de entrega) e frequência de visita é chute. Se o ERP não guarda, calcule o prazo observado (data do recebimento - data do pedido) e declare.
4. **Custo de compra tem camadas.** Preço de tabela, descontos, bonificação, IPI (Imposto sobre Produtos Industrializados), ST (Substituição Tributária), frete, verba. Diga qual custo está na coluna usada. Bonificação entra com valor zero ou simbólico e derruba o custo médio aparente.
5. **Situação do pedido.** Aberto, parcial, atendido, cancelado, com saldo eliminado. "Pendente" = quantidade pedida - recebida - cancelada, e não a situação do cabeçalho.
6. **Abastecimento por CD (centro de distribuição).** Em rede com CD, a loja "compra" por transferência. Separe compra de fornecedor de transferência interna.

## Prova obrigatória por relatório

| Relatório | Prova |
|---|---|
| ABC de abastecimento | Soma das classes = total do período; cruzamento com estoque mantém o mesmo número de itens |
| Sugestão de compra | Cada parcela do cálculo (demanda, saldo, pendente) confere com sua fonte para uma amostra de 5 itens |
| Pedidos pendentes | Pedido = recebido + cancelado + pendente, por item |
| Nível de serviço | Recebimentos considerados = notas de entrada de compra do período |
| Variação de custo | Soma do valor comprado por produto = total das entradas de compra do período |
| Pedido x nota | Valor da nota = soma dos itens conferidos |
| Concentração de fornecedores | Soma dos fornecedores = total comprado no período |

Sem ela, o script recusa. Origem `arquivo` ou `digitado` nunca vira "Prova fechada": o selo é "Conferido só contra o arquivo", mesmo com o total do ERP igual. Quem decide se a prova fechou é o script: não ajuste número para fechar.

## Sem conexão

Siga `references/metodo-analise.md`, seção 2.7. Antes de pedir o arquivo, leia a linha **Para exportar** do relatório: ela diz o que pedir ao ERP, as colunas mínimas e o que fica de fora sem cada coluna opcional. Diga isso à pessoa em uma frase, sem listar a tabela inteira. Coluna que falta não se inventa: diga qual é e o que deixa de sair.

