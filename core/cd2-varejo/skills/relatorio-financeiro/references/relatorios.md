# Financeiro: mapeamento, relatórios e consultas-modelo

Conteúdo:
1. Mapeamento
2. O que medir
3. Relatórios (3.1 a 3.7)

Consultas em SQL Server com marcadores `<assim>`; **[modelo]** até passarem na prova nos dados da pessoa. A consulta de aging (3.1) foi exercitada em SQLite sobre um arquivo de exemplo, na versão convertida pela tabela de `references/regras-sqlite.md`. Sem conexão, adapte a consulta com essa tabela e troque os marcadores pelos nomes de coluna do perfil do arquivo. Cada relatório termina com **Para exportar**: o que pedir ao ERP quando não há conexão.

## 1. Mapeamento

| Domínio | Para quê | Termos de busca | O que confirmar |
|---|---|---|---|
| Títulos a pagar | Aging, fluxo | `titulo_pagar`, `contas_pagar`, `cap`, `pagar`, `duplicata`, `obrigacao`, `payable` | Valor original, saldo, emissão, vencimento, pagamento, situação, fornecedor, espécie |
| Títulos a receber | Aging, inadimplência | `titulo_receber`, `contas_receber`, `car`, `receber`, `crediario`, `convenio`, `receivable` | Idem; portador, forma de cobrança |
| Baixas | Realizado, prazos | `baixa`, `liquidacao`, `pagamento`, `recebimento`, `quitacao` | Tipo da baixa (dinheiro ou não), data, juros, desconto, conta bancária |
| Movimento bancário e caixa | Fluxo realizado, saldos | `movimentacao_bancaria`, `mov_banco`, `extrato`, `tesouraria`, `caixa`, `conta_corrente` | Saldo inicial, sentido, conciliado ou não |
| Plano financeiro | Quebra do fluxo | `plano_financeiro`, `natureza`, `categoria`, `centro_custo`, `historico` | Grupos de entrada e saída |
| Cartões | Conciliação | `cartao`, `adquirente`, `bandeira`, `tef`, `nsu`, `autorizacao`, `taxa`, `antecipacao`, `lote_cartao` | Venda bruta, taxa, líquido, previsão e data de crédito |
| Parceiro | Quebras | `cliente`, `fornecedor`, `pessoa` | Tipo (PF ou PJ), limite de crédito, situação |

Uma tabela única de títulos com indicador de pagar ou receber é comum: confirme o indicador antes de somar.

## 2. O que medir

- Títulos por situação e por espécie: contagem, valor original e saldo.
- Vencimentos: menor e maior data; títulos em aberto com vencimento muito antigo (provável sujeira).
- Baixas por tipo; % de baixas com conta bancária.
- Movimento bancário: período, contas, % conciliado.
- Indicador de pagar ou receber: liste os valores distintos. Código fora do par esperado (um terceiro valor, por exemplo) não entra em nenhum dos lados até a pessoa dizer o que é.
- Data de pagamento: % preenchido nos títulos quitados. Quitado sem data de quitação é comum em carga e migração, e inviabiliza prazo praticado e fluxo realizado por título: diga isso em vez de usar outra data no lugar.
- Tabelas vazias: o financeiro pode rodar em outro sistema. Se títulos e movimento estiverem vazios, diga isso e pare.

Com arquivo, estas medidas saem do perfil de `scripts/dados_arquivo.py`. O que não estiver no arquivo não tem como ser medido: diga isso nas premissas.

## 3. Relatórios

### 3.1 Contas a pagar por vencimento

**Colunas (sintético):** faixa, títulos, valor em aberto, % do total. **Por fornecedor:** os 20 maiores, com vencido e a vencer. **Agenda:** por dia nos próximos 30 dias.

As faixas são exclusivas e cobrem todos os valores: vencido há mais de 90 dias, de 61 a 90, de 31 a 60, de 1 a 30; a vencer de 0 a 7, de 8 a 15, de 16 a 30, de 31 a 60 e acima de 60. Um título vence na data de referência com zero dia e entra na faixa de 0 a 7.

```sql
SELECT x.faixa, COUNT(*) titulos, CAST(SUM(x.saldo) AS float) valor,
       CAST(100.0 * SUM(x.saldo) / NULLIF(SUM(SUM(x.saldo)) OVER (), 0) AS float) part_pct
FROM (SELECT d.saldo,
             CASE WHEN d.dias < -90 THEN '1 vencido > 90'
                  WHEN d.dias < -60 THEN '2 vencido 61-90'
                  WHEN d.dias < -30 THEN '3 vencido 31-60'
                  WHEN d.dias <   0 THEN '4 vencido 1-30'
                  WHEN d.dias <=  7 THEN '5 a vencer 0-7'
                  WHEN d.dias <= 15 THEN '6 a vencer 8-15'
                  WHEN d.dias <= 30 THEN '7 a vencer 16-30'
                  WHEN d.dias <= 60 THEN '8 a vencer 31-60'
                  ELSE '9 a vencer > 60' END faixa
      FROM (SELECT t.<saldo> saldo, DATEDIFF(day, <data_referencia>, t.<vencimento>) dias
            FROM <titulo_pagar> t
            WHERE <em_aberto> AND t.<saldo> > 0
              AND t.<empresa> = COALESCE(NULLIF(<empresa>, 0), t.<empresa>)) d) x
GROUP BY x.faixa
ORDER BY x.faixa OFFSET 0 ROWS
```

O prefixo numérico na faixa garante a ordem. Em Oracle, `TRUNC(t.<vencimento>) - <data_referencia>` no lugar do `DATEDIFF`. Quando não houver coluna de saldo, use `valor nominal - COALESCE(valor pago, 0)` e confira numa amostra.
A pagar vencido há muito tempo raramente é dívida real: costuma ser título pago por fora e não baixado, ou em disputa. Destaque como item a sanear.
**Prova:** soma das faixas = total em aberto, e esse total vem de outra conta: valor original menos baixas, título a título, somado direto no cadastro de títulos sem passar pela coluna de saldo nem pelas faixas. Para 5 títulos, original - baixas = saldo, conferido na origem; diga que é conferência de amostra ("5 de 5 itens conferidos na origem, conferência de amostra").

**Para exportar:** peça o relatório de contas a pagar em aberto, com a data de referência, em CSV ou Excel, uma linha por título. Colunas mínimas: fornecedor (nome ou código), vencimento, saldo em aberto. Recomendadas: número do título, emissão, valor original, valor baixado, situação, empresa ou filial, espécie.

- Sem o saldo: peça valor original e valor baixado, e o saldo sai da diferença. Sem nenhum dos dois, não há valor em aberto.
- Sem a situação: se a exportação já vem só com os abertos, diga isso na premissa; se vier tudo misturado, liquidado e cancelado entram na soma. Peça a coluna.
- Sem valor original e baixado, a prova de saldo por título fica de fora e a entrega fica marcada como "Conferido só contra o arquivo".
- Sem a empresa ou filial: a rede sai somada, e a entrega diz isso.
- Sem a data de referência: pergunte à pessoa a data da exportação.

### 3.2 Contas a receber e inadimplência

Mesmo aging de 3.1, sobre os títulos a receber, mais:

| Indicador | Fórmula | Declare |
|---|---|---|
| Inadimplência % | Vencido há mais de N dias / carteira total (aberto + vencido) | N (default 30) e o denominador |
| Inadimplência sobre faturamento | Vencido do que foi emitido no período / emitido no período | Safra analisada |
| Atraso médio | Média de dias de atraso ponderada pelo saldo | |
| Concentração | Participação dos 10 maiores devedores no vencido | |

**Por cliente:** saldo vencido, a vencer, maior atraso, limite de crédito e % utilizado, última compra.
**Por safra (opcional):** para cada mês de emissão, % ainda em aberto hoje: mostra se a inadimplência está piorando nas vendas recentes, o que o aging sozinho esconde.
Separe por espécie: crediário próprio, boleto, convênio, cheque e cartão têm comportamento e risco diferentes; cartão não é inadimplência do cliente.
Cliente pessoa física: código e nome, CPF mascarado, sem telefone nem endereço, e só para quem tem finalidade de cobrança ou crédito (`references/metodo-analise.md`, seção 6).
**Prova:** soma das faixas = total em aberto, somado direto dos títulos como em 3.1, e carteira = vencido + a vencer.

**Para exportar:** peça o relatório de contas a receber em aberto, uma linha por título. Colunas mínimas: cliente (nome ou código), vencimento, saldo em aberto. Recomendadas: emissão, valor original, valor baixado, espécie, limite de crédito, data da última compra.

- Sem a espécie: cartão, boleto e crediário se misturam, e a inadimplência fica inflada ou confusa. Peça a coluna.
- Sem a emissão: sem a safra e sem a inadimplência sobre faturamento.
- Sem o limite de crédito: sem o % utilizado. Sem a última compra: sem a coluna de última compra.
- Sem o cliente identificado (só o total por faixa): sai o aging, não a lista de devedores.
- Atraso médio ponderado precisa do vencimento de cada título; sem ele, não sai.

### 3.3 Fluxo de caixa

**Realizado:** por dia ou semana: saldo inicial, entradas por grupo, saídas por grupo, saldo final.
**Projetado:** saldo atual + títulos a receber por vencimento - títulos a pagar por vencimento, por dia ou semana, com saldo acumulado e a primeira data de saldo negativo.

```sql
SELECT CONVERT(varchar(10), x.dia, 23) dia,
       CAST(x.entradas AS float) entradas, CAST(x.saidas AS float) saidas,
       CAST(<saldo_atual> + SUM(x.entradas - x.saidas) OVER (ORDER BY x.dia ROWS UNBOUNDED PRECEDING) AS float) saldo_projetado
FROM (SELECT u.dia, SUM(u.entra) entradas, SUM(u.sai) saidas
      FROM (SELECT CAST(r.<vencimento> AS date) dia, r.<saldo> entra, 0 sai
            FROM <titulo_receber> r
            WHERE <em_aberto_r> AND r.<vencimento> >= <data_referencia> AND r.<vencimento> < DATEADD(day, 30, <data_referencia>)
            UNION ALL
            SELECT CAST(p.<vencimento> AS date), 0, p.<saldo>
            FROM <titulo_pagar> p
            WHERE <em_aberto_p> AND p.<vencimento> >= <data_referencia> AND p.<vencimento> < DATEADD(day, 30, <data_referencia>)) u
      GROUP BY u.dia) x
ORDER BY x.dia OFFSET 0 ROWS
```

**Premissas que precisam estar na entrega:**
- Vencidos a receber: fora da projeção por default (ou em linha própria "vencido, recebimento incerto"). Somar vencido como entrada do dia infla o caixa.
- Vencidos a pagar: entram no primeiro dia, em linha própria.
- Cartão: pela data prevista de crédito, líquido de taxa, se o dado existir.
- **Não incluído:** vendas futuras à vista, folha, impostos, aluguel, compras ainda não faturadas, investimentos. A projeção é o que já está contratado em título; liste o que ficou de fora.

Ofereça cenário quando fizer sentido: recebimento com o atraso médio histórico aplicado (3.2) contra recebimento no vencimento.
**Prova (realizado):** saldo inicial + entradas - saídas = saldo final, por conta, com o saldo final lido do extrato e não calculado.
**Prova (projetado):** soma das entradas e das saídas da janela = soma dos títulos a receber e a pagar com vencimento na janela, nos totais de 3.1 e 3.2.

**Para exportar:** o fluxo tem duas metades. Do projetado: os títulos a pagar e a receber em aberto (3.1 e 3.2) e o saldo atual das contas. Do realizado: o extrato ou movimento de caixa e bancos do período, uma linha por lançamento.

- Colunas mínimas do movimento: data, conta, valor, sentido (entrada ou saída) ou valor com sinal. Recomendadas: grupo ou natureza financeira e o saldo inicial de cada conta.
- Sem o saldo inicial da conta: o realizado sai como variação do período, não como saldo, e a prova de saldo final não existe. Diga isso.
- Sem o grupo ou natureza: entradas e saídas saem sem a quebra.
- Sem o saldo atual das contas: a projeção sai como variação acumulada, sem o saldo.
- Sem o movimento bancário (só os títulos): só o projetado sai, e o realizado fica de fora.

### 3.4 Prazos médios e ciclo

| Indicador | Fórmula |
|---|---|
| PMR, prazo médio de recebimento | Contas a receber médio / venda a prazo do período x dias; ou média de (vencimento - emissão) ponderada pelo valor |
| PMP, prazo médio de pagamento | Fornecedores médio / compras do período x dias; ou média ponderada de (vencimento - emissão) |
| PME, prazo médio de estoque | Estoque médio a custo / custo da mercadoria vendida x dias |
| Ciclo operacional | PME + PMR |
| Ciclo financeiro | PME + PMR - PMP |

Mostre o prazo **contratado** (emissão ao vencimento) e o **praticado** (emissão ao pagamento) lado a lado: a diferença é o atraso real, dos dois lados.
No varejo alimentar o ciclo financeiro costuma ser curto ou negativo (vende à vista, paga a prazo). Diga o que o número significa para a necessidade de capital de giro, sem comparar com referência externa sem fonte.
**Prova:** as vendas e as compras usadas na conta = totais da fonte de vendas e da fonte de compras no período, somados direto nelas.

**Para exportar:** peça os títulos a receber e a pagar do período com as datas, e os totais de venda a prazo e de compras do mesmo período. Colunas mínimas dos títulos: emissão, vencimento, valor. Recomendadas: data de pagamento ou recebimento. Para o prazo de estoque: o estoque médio a custo e o custo da mercadoria vendida.

- Sem a data de pagamento: sai o prazo contratado, não o praticado. Quitado sem data é comum em carga de ERP; diga isso em vez de usar outra data.
- Sem o estoque médio e o custo vendido: sai PMR e PMP, sem PME e sem o ciclo completo.
- Sem o total de vendas e de compras do período: a prova não fecha; peça os totais à pessoa.
- Sem a emissão: só vale o método pelo saldo médio, e a entrega diz qual usou.

### 3.5 Cartões

**Colunas por adquirente e bandeira, por modalidade (débito, crédito à vista, parcelado, voucher):** transações, venda bruta, taxa em valor, taxa efetiva %, líquido previsto, líquido creditado, diferença, prazo médio de crédito, valor antecipado e custo da antecipação.

**Conferências:**
1. Venda em cartão no caixa (finalizadoras) = recebíveis gerados no mesmo período. Diferença aponta venda não integrada ou forma de pagamento trocada no caixa.
2. Taxa efetiva (taxa / bruto) por modalidade contra a taxa cadastrada ou contratada, se a pessoa informar.
3. Recebíveis com data prevista vencida e sem crédito: liste por adquirente e data.
4. Chargebacks e cancelamentos.

Sem módulo de cartão, só a conferência 1 no nível agregado é possível: diga isso. A conciliação transação a transação com o extrato da adquirente depende de um arquivo que não está no ERP.
**Prova:** venda em cartão no caixa, somada nas finalizadoras da venda, = recebíveis brutos gerados no período, somados no módulo de cartão ou no extrato da adquirente. São dois totais de origens diferentes; a diferença é explicada ou apresentada como não explicada.

**Para exportar:** peça dois relatórios do mesmo período. Da venda: o total por forma de pagamento (finalizadora), com bandeira se houver. Do cartão: o relatório de recebíveis do ERP ou o extrato da adquirente, uma linha por venda ou por lote. Colunas mínimas do recebível: data da venda, bandeira ou adquirente, valor bruto. Recomendadas: modalidade, taxa, valor líquido, data prevista de crédito, data do crédito.

- Sem o relatório de recebíveis (só a venda no caixa): não há o que conciliar. Sai a venda por forma de pagamento e nada mais.
- Sem a taxa e o líquido: sai o bruto, mas não a taxa efetiva nem a diferença de líquido.
- Sem a data de crédito: sem prazo médio e sem os recebíveis vencidos e sem crédito.
- A conciliação transação a transação precisa do extrato da adquirente. Se a pessoa não tiver o arquivo, o relatório fica no agregado, e a entrega diz que não conferiu transação por transação.

### 3.6 Bancos e tesouraria

**Colunas:** conta, saldo inicial, entradas, saídas, saldo final, lançamentos não conciliados (quantidade e valor), data do último lançamento.
Fundo de troco, sangrias e depósitos por loja, quando houver tesouraria: diferença de caixa (sobra e falta) por loja e por operador, com a base de fechamentos.
**Prova:** saldo inicial + entradas - saídas = saldo final, por conta, com o saldo final lido do extrato ou do saldo informado pelo banco.

**Para exportar:** peça o extrato ou o movimento bancário do período por conta, uma linha por lançamento, e o saldo de cada conta no início e no fim. Colunas mínimas: conta, data, valor com sinal (ou valor e sentido). Recomendadas: histórico, situação de conciliação.

- Sem o saldo inicial e o final: sai a movimentação do período, não o saldo, e a prova não existe.
- Sem a situação de conciliação: sem a contagem de lançamentos não conciliados.
- Diferença de caixa por loja e operador vem do relatório de fechamento de caixa, que é outra exportação. Operador é pessoa: mostre só quando a pergunta for de auditoria.

### 3.7 Exceções

Cada uma com contagem, valor e amostra:
- títulos em duplicidade (mesmo parceiro, documento ou valor e vencimento);
- baixa com data anterior à emissão;
- baixa com desconto ou abatimento acima de um percentual (default 10%);
- títulos em aberto com vencimento há mais de um ano;
- pagamento a fornecedor sem nota de entrada vinculada;
- alteração de vencimento repetida no mesmo título;
- títulos a receber de cliente bloqueado com venda nova no período.

São itens para revisão; duplicidade aparente pode ser parcela legítima de mesmo valor.
**Prova:** títulos analisados = contagem direta de títulos do cadastro no período, e cada exceção sai com a lista dos títulos. Uma amostra de 5 itens de cada lista é conferida na origem e dita como conferência de amostra.

**Para exportar:** peça os títulos do período, a pagar e a receber, em todas as situações, uma linha por título. Colunas mínimas: número, parceiro, emissão, vencimento, valor, situação. Recomendadas: data de pagamento, desconto, valor baixado, nota de entrada vinculada, histórico de alteração de vencimento.

- Sem a data de pagamento: sem a baixa anterior à emissão.
- Sem desconto e valor baixado: sem a baixa com desconto alto.
- Sem a nota de entrada vinculada, sem o histórico de vencimento e sem o bloqueio do cliente: essas exceções não saem de um arquivo de títulos; elas dependem de outras tabelas do ERP. A entrega lista as que ficaram de fora.
- Só a lista dos abertos: sem exceções de baixa.
