# Perdas: mapeamento, relatórios e consultas-modelo

Conteúdo:
1. Mapeamento
2. O que medir
3. Relatórios (3.1 a 3.6)

Consultas em SQL Server com marcadores `<assim>`; **[modelo]** até passarem na prova nos dados da pessoa. O padrão de participação por janela é **[validado]** pelo conector. Sem conexão, adapte a consulta com a tabela de `references/regras-sqlite.md` e troque os marcadores pelos nomes de coluna do perfil do arquivo. Cada relatório termina com **Para exportar**: o que pedir ao ERP quando não há conexão.

## 1. Mapeamento

Movimento, tipo de operação, inventário, produto e custo: `references/mapeamento-erp.md`, seção 1. Venda por cupom e operador: `references/indicadores-varejo.md`, seção 1. Acrescente:

| Domínio | Para quê | Termos de busca | O que confirmar |
|---|---|---|---|
| Quebra | Perda identificada | `quebra`, `perda`, `avaria`, `baixa`, `descarte`, `sinistro` | Se é tabela própria, tipo de movimento ou nota de baixa; quantidade, custo, motivo |
| Motivo | Classificação | `motivo`, `causa`, `justificativa`, `tipo_quebra` | Distribuição real dos motivos e % em motivo genérico |
| Validade e lote | Vencidos | `validade`, `vencimento`, `lote`, `dta_validade`, `shelf` | Se o saldo é controlado por lote ou só a entrada tem validade |
| Ajuste | Ajustes manuais | tipo de movimento de `ajuste`, `acerto`, `correcao`; `usuario`, `observacao` | Quem lança, se exige motivo e aprovação |
| Cancelamento e desconto no caixa | Exceções | `cancelado`, `item_cancelado`, `desconto`, `supervisor`, `autorizacao` | Cancelamento de item x de cupom; desconto de promoção x manual; quem autorizou |

## 2. O que medir

- Onde a quebra está gravada (tabela própria, tipo de movimento, nota de baixa) e o total de cada fonte no mesmo mês, para escolher uma e não duplicar.
- Motivos: distribuição por ocorrências e por valor; % em motivo genérico ou vazio.
- Inventários: lotes encerrados no período, por loja e departamento.
- Cancelamentos e descontos: existem no nível do item e do cupom? Há operador, supervisor e hora?
- Validade: saldo por lote existe e está em uso?

Com arquivo, estas medidas saem do perfil de `scripts/dados_arquivo.py`. O que não estiver no arquivo não tem como ser medido: diga isso nas premissas.

## 3. Relatórios

### 3.1 Quebra por motivo e departamento

**Colunas:** departamento, motivo, ocorrências, quantidade, valor a custo, % do total de quebras, % sobre a venda do departamento.
**Analítico:** os 30 produtos de maior quebra em valor, com motivo predominante e % sobre a própria venda.

```sql
SELECT p.<cod_departamento>, COALESCE(q.<motivo>, '(sem motivo)') motivo, COUNT(*) ocorrencias,
       CAST(SUM(q.<quantidade>) AS float) qtd,
       CAST(SUM(q.<quantidade> * COALESCE(q.<custo>, 0)) AS float) valor_custo,
       CAST(100.0 * SUM(q.<quantidade> * COALESCE(q.<custo>, 0))
            / NULLIF(SUM(SUM(q.<quantidade> * COALESCE(q.<custo>, 0))) OVER (), 0) AS float) part_pct
FROM <quebra> q
JOIN <produto> p ON p.<cod_produto> = q.<cod_produto>
WHERE q.<cod_loja> = COALESCE(NULLIF(<loja>, 0), q.<cod_loja>)
  AND q.<data> >= '2025-07-01' AND q.<data> < '2025-08-01'
GROUP BY p.<cod_departamento>, COALESCE(q.<motivo>, '(sem motivo)')
ORDER BY valor_custo DESC, p.<cod_departamento>, motivo OFFSET 0 ROWS
```

Calcule o % sobre a venda com a venda do mesmo departamento, loja e período, em consulta separada, e junte no resultado. Referências de mercado para índice de perda variam por formato e por pesquisa: não cite um número de referência sem fonte; compare a operação com ela mesma (lojas entre si, período contra período).
Com arquivo, o departamento costuma vir na mesma linha da quebra: agrupe por ele e tire o join com o cadastro.
**Prova:** total por motivo = total por departamento = total de quebras do período.
**Leituras típicas:** perecíveis concentrando a quebra (esperado; o que importa é a tendência e a loja fora da curva), vencimento em item com excesso de cobertura (problema de compra, cruze com a cobertura de estoque), motivo genérico dominante.

**Para exportar:** peça o relatório de quebras ou perdas do período, em CSV ou Excel, uma linha por lançamento. Colunas mínimas: data, código do produto, quantidade, motivo. Recomendadas: custo, departamento, loja.

- Sem custo: sai a quantidade por motivo, mas não o valor a custo nem os percentuais em valor.
- Sem motivo: sem a quebra por motivo; a prova vira soma por departamento = total.
- Sem departamento: peça o cadastro de produtos (código e departamento) para ligar pelo código; sem ele, sai por motivo e por produto, sem o departamento.
- Sem a venda do departamento no período: sem o % sobre a venda. Peça a venda do mesmo período por departamento e loja.
- Quebra em mais de uma fonte no ERP (tabela de perdas, tipo de movimento e nota de baixa): peça só uma e diga qual, porque somar duas duplica.

### 3.2 Perda total: identificada e não identificada

**Colunas por departamento:** venda líquida, quebra identificada, falta de inventário, sobra de inventário, perda não identificada (falta - sobra), perda total, índice %, data do último inventário.

Monte em três consultas (quebras do período, divergência dos lotes de inventário encerrados no período, venda) e junte por departamento.

A divergência de cada lote vem item a item, só dos itens contados: `(contada - congelada) x custo`. Negativa é falta, positiva é sobra; item não contado fica fora, e contado zero não é não contado. A perda não identificada do departamento é a soma das faltas menos a soma das sobras, em valor a custo. A divergência líquida é a que ajustou o saldo; a absoluta (faltas + sobras) mede a qualidade do processo e vai ao lado. Lote ainda em contagem ou sem contagem lançada não entra.

Cuidados:
- O período da perda não identificada é o intervalo **entre inventários**, não o mês do balanço. Um inventário anual concentra 12 meses de perda no mês em que ocorre: diga isso em vez de mostrar um pico falso.
- Quebra lançada entre o congelamento e a contagem pode estar nos dois lados.
- Liste os lotes considerados e os departamentos sem inventário.
- **Contado zero x não contado:** se o sistema grava zero tanto para o item contado sem saldo quanto para o não contado, não dá para separar os dois, e o item não contado vira falta total. Isso infla a perda não identificada sem avisar: pergunte como o ERP grava, e diga na entrega que o número pode estar inflado.

**Prova:** perda não identificada = divergência líquida dos lotes considerados, e a lista dos lotes e dos departamentos sem inventário vai na entrega.

**Para exportar:** peça três relatórios do período: as quebras (3.1), o resultado dos balanços ou lotes de inventário e a venda por departamento. Do inventário, colunas mínimas: lote ou data, departamento, quantidade congelada, quantidade contada, custo (ou a divergência em valor já pronta).

- Sem o resultado dos inventários: sai só a perda identificada, e a entrega diz que a não identificada é desconhecida, não zero.
- Sem custo no inventário: sem divergência em valor, e a soma com a quebra não fecha em reais. Peça o custo.
- Sem a data do último inventário por departamento: não dá para dizer o intervalo entre inventários. Pergunte à pessoa.
- Sem a venda por departamento: sai a perda em reais, mas não o índice %.
- Sem a situação do lote: pergunte se os lotes foram encerrados. Contagem em andamento mostra falta que é só item não contado.

### 3.3 Validade

**Vencidos em estoque:** produto, lote, validade, saldo do lote, valor a custo, dias vencido.
**A vencer:** faixas de 7, 15 e 30 dias, mais "vence depois de 30 dias" para o saldo restante, com saldo, venda média diária e a quantidade que não deve vender até o vencimento (saldo - venda média x dias restantes, se positiva): essa é a lista de ação (remarcar, transferir, doar).
Só é possível com saldo por lote. Com validade apenas na nota de entrada, entregue uma estimativa por entrada mais recente e marque como estimativa; sem validade em lugar nenhum, diga que o ERP não controla.
**Prova:** saldo vencido + saldo de cada faixa a vencer (até 7, 15 e 30 dias) + saldo que vence depois de 30 dias = saldo dos lotes na fonte de saldo, somado direto. Lote sem validade informada vai à parte e entra na soma.

**Para exportar:** peça o relatório de posição de estoque por lote, com validade. Colunas mínimas: produto, lote, validade, saldo. Recomendadas: custo e a venda por item dos últimos 30 dias (para a venda média diária).

- Sem saldo por lote, com validade só na nota de entrada: a estimativa sai por entrada mais recente e fica marcada como estimativa. Peça as notas de entrada com a validade.
- Sem validade em nenhum arquivo: não dá para fazer. Diga que o ERP não controla.
- Sem custo: sai a quantidade, mas não o valor vencido.
- Sem a venda por item: sai o que vence, mas não a quantidade que não vai vender até o vencimento.

### 3.4 Ajustes manuais

**Colunas:** data, produto, loja, tipo (entrada ou saída), quantidade, valor a custo, motivo ou observação, usuário.
**Sintético:** por tipo e por loja: ocorrências, valor de entradas, valor de saídas, líquido, % sem motivo.
**Sinais de atenção:** ajuste de entrada e de saída no mesmo item em dias próximos, ajuste logo antes ou depois de inventário, concentração em um usuário, valores redondos, ajuste em itens de alto valor e fácil revenda.
**Prova:** ajustes do relatório = movimentos dos tipos de ajuste no período.

**Para exportar:** peça a movimentação de estoque do período só com os tipos de ajuste, ou o relatório de ajustes manuais. Colunas mínimas: data, produto, tipo (entrada ou saída), quantidade.

- Sem custo: sai a quantidade, não o valor.
- Sem motivo ou observação: o % sem motivo é 100% e não diz nada sobre a causa. Avise.
- Sem usuário: sem a concentração em um usuário. Usuário é dado pessoal de colaborador: mostre só quando a pergunta for de auditoria.
- Sem a data dos inventários: o sinal "logo antes ou depois de inventário" fica de fora.
- Sem loja: ajustes da rede somados.

### 3.5 Exceções de frente de caixa

**Colunas por operador (ou PDV, ou loja):** cupons, venda, cupons cancelados e valor, itens cancelados e valor, descontos manuais e valor, taxa de cada um sobre a própria venda, média da loja, quantas vezes acima da média.

```sql
SELECT v.<cod_operador>, COUNT(*) cupons,
       CAST(SUM(CASE WHEN <cancelado> THEN 0 ELSE v.<valor_liquido> END) AS float) venda,
       SUM(CASE WHEN <cancelado> THEN 1 ELSE 0 END) cupons_cancelados,
       CAST(SUM(CASE WHEN <cancelado> THEN v.<valor_liquido> ELSE 0 END) AS float) valor_cancelado,
       CAST(SUM(CASE WHEN <cancelado> THEN 0 ELSE COALESCE(v.<desconto>, 0) END) AS float) descontos
FROM <venda> v
WHERE v.<cod_loja> = <loja> AND v.<data> >= '2025-07-01' AND v.<data> < '2025-08-01'
GROUP BY v.<cod_operador>
HAVING COUNT(*) >= 100
ORDER BY valor_cancelado DESC OFFSET 0 ROWS
```

- O piso de cupons (100 por default) evita taxa alta por base pequena.
- Separe desconto de promoção e de fidelidade (regra do sistema) do desconto manual (decisão do operador ou supervisor). Sem essa distinção no dado, diga que o desconto mostrado inclui promoção.
- Itens cancelados dependem de exportação no nível do item; com só o cupom, saem os cupons cancelados e os itens não.
- Itens cancelados depois do subtotal e cancelamento do cupom inteiro logo após o pagamento em dinheiro são os padrões clássicos de auditoria; só aponte se o dado tiver hora e forma de pagamento.

**Prova:** cancelado + válido = total registrado do período.

**Para exportar:** peça o relatório de vendas por cupom do período, com os cancelados incluídos. Colunas mínimas: operador, cupom, valor, situação (cancelado ou válido).

- Sem os cupons cancelados na exportação (só a venda válida): não dá para calcular a taxa de cancelamento, e a prova cancelado + válido = total não existe. Peça a exportação com os cancelados.
- Sem desconto por cupom ou por item: sem a coluna de descontos.
- Sem hora e sem forma de pagamento: sem os padrões clássicos de auditoria (cancelamento logo após o pagamento em dinheiro).
- Sem a data: o período vale o que a pessoa informar.
- Sem supervisor: sem a leitura de quem autorizou.
- Sem loja ou PDV: sai por operador, na rede.

### 3.6 Trocas e devoluções

**Colunas:** loja, operador ou atendente, devoluções, valor, % sobre a venda, % sem cupom de origem, % em dinheiro, prazo médio entre venda e devolução.
**Sinais de atenção:** devolução sem venda de origem, devolução no mesmo dia e mesmo operador da venda, itens de alto valor recorrentes, cliente com muitas devoluções.
Complementa a devolução geral (taxa por motivo, produto e cliente) com o olhar de auditoria.
**Prova:** soma das devoluções por operador = total de devoluções do período.

**Para exportar:** peça o relatório de devoluções e trocas do período. Colunas mínimas: data, operador ou atendente, valor.

- Sem o cupom ou a venda de origem: sem o % sem origem, sem o prazo médio e sem o sinal "devolução sem venda de origem".
- Sem a venda do operador no período: sai o valor devolvido, mas não o % sobre a venda.
- Sem a forma de devolução (dinheiro ou crédito): sem o % em dinheiro.
- Sem produto: sem os itens de alto valor recorrentes.
- Sem cliente: sem o sinal de cliente com muitas devoluções. Cliente pessoa física usa código e nome, sem CPF inteiro (`references/metodo-analise.md`, seção 6).
