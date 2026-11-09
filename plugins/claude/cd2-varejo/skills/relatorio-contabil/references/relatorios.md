# Contábil: mapeamento, relatórios e consultas-modelo

Conteúdo:
1. Mapeamento
2. O que medir
3. Relatórios (3.1 a 3.7)

Consultas em SQL Server com marcadores `<assim>`; **[modelo]** até passarem na prova nos dados da pessoa. A consulta do balancete (3.1) foi exercitada em SQLite sobre um arquivo de exemplo, na versão convertida pela tabela de `references/regras-sqlite.md`. Elas estão escritas para o formato "uma linha por conta, com indicador D ou C"; adapte para os outros formatos (SKILL.md, item 1). Sem conexão, troque os marcadores pelos nomes de coluna do perfil do arquivo. Cada relatório termina com **Para exportar**: o que pedir ao ERP quando não há conexão.

Todo relatório desta skill é conferência gerencial e não substitui a escrituração contábil oficial.

## 1. Mapeamento

| Domínio | Para quê | Termos de busca | O que confirmar |
|---|---|---|---|
| Lançamento | Tudo | `lancamento`, `lancto`, `lcto`, `partida`, `movimento_contabil`, `ctb`, `razao`, `journal` | Formato da partida, data de competência, valor, histórico, lote, origem, situação |
| Plano de contas | Hierarquia, natureza | `plano_conta`, `conta_contabil`, `conta`, `pc`, `chart` | Código, código reduzido, descrição, analítica ou sintética, natureza, conta pai ou máscara |
| Saldo | Saldo anterior | `saldo_conta`, `saldo_mensal`, `saldo_contabil`, `fechamento` | Período de cada saldo, se é acumulado |
| Centro de custo | Quebra | `centro_custo`, `ccusto`, `cc`, `centro_resultado` | % dos lançamentos de resultado preenchidos |
| Histórico padrão | Leitura | `historico`, `hist_padrao` | Código e complemento |
| Origem e lote | Integração | `lote`, `origem`, `modulo`, `integracao`, `documento` | Quais módulos integram e com que frequência |
| LALUR | Adições e exclusões | `lalur`, `lacs`, `adicao`, `exclusao`, `parte_a`, `parte_b`, `prejuizo_fiscal` | Se existe e está em uso (tabela vazia é o caso mais comum) |

## 2. O que medir

- Lançamentos por mês e por origem; primeira e última data; por situação.
- Débitos e créditos totais por mês (já mostra onde não fecha).
- Contas analíticas com movimento, contas sem movimento no exercício, lançamentos em conta sintética.
- Identificação dos lançamentos de encerramento e de abertura.

Com arquivo, estas medidas saem do perfil de `scripts/dados_arquivo.py`. O que não estiver no arquivo não tem como ser medido: diga isso nas premissas.

## 3. Relatórios

### 3.1 Balancete de verificação

**Colunas:** código, descrição, saldo anterior (D ou C), débitos, créditos, saldo atual (D ou C). Contas sintéticas totalizando as filhas, no nível pedido.

```sql
SELECT pc.<codigo>, pc.<descricao>, pc.<natureza>,
       CAST(SUM(CASE WHEN l.<data> <  '2025-07-01' THEN <deb> - <cre> ELSE 0 END) AS float) saldo_anterior,
       CAST(SUM(CASE WHEN l.<data> >= '2025-07-01' THEN <deb> ELSE 0 END) AS float) debitos,
       CAST(SUM(CASE WHEN l.<data> >= '2025-07-01' THEN <cre> ELSE 0 END) AS float) creditos,
       CAST(SUM(<deb> - <cre>) AS float) saldo_atual
FROM <lancamento> l
JOIN <plano_contas> pc ON pc.<conta> = l.<conta>
WHERE l.<empresa> = <empresa> AND <lancamento_efetivado>
  AND l.<data> >= '2025-01-01' AND l.<data> < '2025-08-01'
GROUP BY pc.<codigo>, pc.<descricao>, pc.<natureza>
HAVING SUM(<deb>) <> 0 OR SUM(<cre>) <> 0
ORDER BY pc.<codigo> OFFSET 0 ROWS
```

Onde `<deb>` = `CASE WHEN l.<dc> = 'D' THEN l.<valor> ELSE 0 END` e `<cre>` o equivalente para crédito. Saldo positivo = devedor, negativo = credor; converta para D ou C na apresentação.

- O exemplo acumula do início do exercício. Para contas patrimoniais, o saldo anterior correto vem de **toda** a história ou da tabela de saldos: prefira a tabela de saldos e some o movimento do período.
- **Nível sintético:** com máscara no código, agrupe por `LEFT(codigo, n)` do nível desejado e traga a descrição da conta sintética; com coluna de conta pai, suba um nível por junção (uma junção por nível, sem CTE recursiva).
- Conta com saldo invertido à natureza (caixa credor, fornecedor devedor) é achado: liste.

**Prova:** o total de débitos e o de créditos do período, somados direto nos lançamentos por D e C (não pelas colunas do balancete), são iguais; a soma dos saldos com sinal é zero; e ativo = passivo + patrimônio líquido + resultado do exercício.

**Para exportar:** peça o relatório de lançamentos contábeis do exercício, uma linha por conta do lançamento, e o plano de contas. Colunas mínimas dos lançamentos: número do lançamento, data (competência), conta, indicador D ou C (ou valor com sinal), valor. Recomendadas: situação (efetivado ou rascunho), histórico, origem. Do plano: código, descrição e natureza.

- Se o ERP só entrega o balancete pronto: a página mostra o que veio, e a prova de débito = crédito usa os totais do próprio relatório. O selo é "Conferido só contra o arquivo", e a entrega diz que os lançamentos não foram vistos.
- Sem a situação: rascunho e pendente entram na soma. Peça a coluna ou só os efetivados.
- Sem o saldo anterior (exportação só do mês): peça o balancete do mês anterior ou o exercício inteiro; sem isso, o saldo sai como movimento do período.
- Sem a natureza no plano: o D ou C do saldo sai pelo sinal, sem a leitura de saldo invertido.

### 3.2 Razão

**Colunas:** data, lote ou número do lançamento, histórico, contrapartida, débito, crédito, saldo após o lançamento (D ou C). Linha inicial com o saldo anterior.

```sql
SELECT CONVERT(varchar(10), r.dia, 23) data, r.num, r.historico,
       CAST(r.deb AS float) debito, CAST(r.cre AS float) credito,
       CAST(r.saldo_anterior + SUM(r.deb - r.cre) OVER (ORDER BY r.dia, r.num, r.seq ROWS UNBOUNDED PRECEDING) AS float) saldo
FROM (SELECT l.<data> dia, l.<num_lancamento> num, l.<sequencia> seq, l.<historico> historico,
             <deb> deb, <cre> cre,
             (SELECT COALESCE(SUM(<deb_a> - <cre_a>), 0) FROM <lancamento> a
              WHERE a.<empresa> = l.<empresa> AND a.<conta> = l.<conta> AND a.<data> < '2025-07-01') saldo_anterior
      FROM <lancamento> l
      WHERE l.<empresa> = <empresa> AND l.<conta> = <conta> AND <lancamento_efetivado>
        AND l.<data> >= '2025-07-01' AND l.<data> < '2025-08-01') r
ORDER BY r.dia, r.num, r.seq OFFSET 0 ROWS
```

Contrapartida: no formato de uma linha por conta, é a outra conta do mesmo lançamento; com várias, mostre "diversas". Razão é por conta: sem conta informada, mostre as 20 contas com maior movimento para a pessoa escolher.
**Prova:** saldo anterior + débitos - créditos = saldo final = saldo da conta no balancete da mesma data, que vem de outro relatório.

**Para exportar:** peça o razão da conta no período, ou os lançamentos que passam por ela. Colunas mínimas: data, número do lançamento, débito, crédito. Recomendadas: histórico, contrapartida, saldo anterior.

- Sem o saldo anterior: o saldo corrido parte de zero e a prova contra o balancete não existe. Peça o saldo ou o balancete da data.
- Sem a contrapartida: ela não sai; só o formato "uma linha por conta" permite achá-la, e isso exige os lançamentos de todas as contas.
- Sem a ordem do lançamento no dia: o saldo corrido pode sair em ordem diferente da do sistema, e o saldo final continua certo.
- Sem o balancete da mesma data: a prova fica "Conferido só contra o arquivo".

### 3.3 Diário

**Colunas:** data, número do lançamento, conta, descrição, histórico, débito, crédito; total por lançamento e por dia.
Volume alto por natureza: exija período curto (até um mês) e empresa, entregue em planilha, e traga na conversa só os totais por dia e os lançamentos acima de um valor de corte.
**Prova:** débito = crédito em cada lançamento e no dia; o total do mês confere com o do balancete.

**Para exportar:** peça o diário do período, uma linha por conta do lançamento. Colunas mínimas: data, número do lançamento, conta, débito, crédito (ou D ou C e valor). Recomendadas: descrição da conta, histórico, situação.

- Período longo demais: peça por mês.
- Sem o número do lançamento: não dá para fechar débito e crédito por lançamento, só por dia.
- Sem a situação: rascunhos entram.

### 3.4 Resultado gerencial

Estrutura a partir dos grupos do plano: receita bruta, deduções, receita líquida, custo da mercadoria vendida, lucro bruto, despesas por grupo, resultado operacional, resultado financeiro, resultado antes dos impostos.
**Colunas:** linha, mês, mês anterior, acumulado do exercício, % sobre a receita líquida (análise vertical), variação % (horizontal).
- O mapeamento conta para linha vem do plano (grupos de resultado). Se a estrutura não for evidente, mostre os grupos encontrados e confirme com a pessoa antes de montar.
- Exclua os lançamentos de encerramento.
- Chame de **gerencial**: a demonstração oficial tem regras de apresentação próprias.
- Por loja ou centro de custo só se o preenchimento for alto; informe a parcela sem centro.

**Prova:** resultado = soma das contas de resultado no balancete do mesmo período, que vem de outro relatório.

**Para exportar:** o balancete do mês e do mês anterior, ou os lançamentos das contas de resultado. Colunas mínimas: código e descrição da conta, débitos, créditos (ou saldo), período. Recomendadas: o plano com os grupos, centro de custo.

- Sem a estrutura dos grupos no plano: a pessoa diz qual conta vai em qual linha, e a entrega mostra o mapeamento usado.
- Sem o mês anterior: sem a variação horizontal.
- Sem o lançamento de encerramento identificado: o resultado do mês de encerramento sai distorcido, e a entrega avisa.
- Sem centro de custo: sem a quebra por loja.

### 3.5 Integridade dos lançamentos

Exceções, cada uma com contagem, valor e amostra:
- lançamento ou lote em que débito diferente de crédito;
- dia ou mês que não fecha (mostre o primeiro período em que a diferença aparece);
- lançamento em conta sintética ou em conta inativa;
- conta de resultado sem centro de custo, quando a empresa usa;
- lançamento sem histórico, ou com histórico genérico;
- lançamentos manuais (origem diferente de integração) em contas que deveriam ser só integradas (estoque, fornecedores, clientes);
- valores redondos altos, lançamentos em fim de semana ou no último dia do mês com estorno no primeiro dia do seguinte;
- lançamentos duplicados (mesma data, contas, valor e histórico).

```sql
SELECT l.<num_lancamento>, CONVERT(varchar(10), MIN(l.<data>), 23) data,
       CAST(SUM(<deb>) AS float) debitos, CAST(SUM(<cre>) AS float) creditos,
       CAST(SUM(<deb> - <cre>) AS float) diferenca
FROM <lancamento> l
WHERE l.<empresa> = <empresa> AND l.<data> >= '2025-07-01' AND l.<data> < '2025-08-01'
GROUP BY l.<num_lancamento>
HAVING ABS(SUM(<deb> - <cre>)) > 0.005
ORDER BY ABS(SUM(<deb> - <cre>)) DESC OFFSET 0 ROWS
```

São indícios para revisão, não conclusões: lançamento manual de ajuste no fechamento pode ser legítimo.
**Prova:** lançamentos analisados = contagem direta de lançamentos do período = os que fecham + os que não fecham. Uma amostra de 5 itens de cada lista é conferida na origem e dita como conferência de amostra.

**Para exportar:** peça os lançamentos do período, uma linha por conta do lançamento. Colunas mínimas: número do lançamento, data, conta, débito, crédito. Recomendadas: histórico, origem (manual ou integração), usuário, centro de custo, situação.

- Sem a origem: sem a exceção de lançamento manual em conta integrada.
- Sem o histórico: sem as exceções de histórico vazio ou genérico.
- Sem o centro de custo: sem a exceção de resultado sem centro.
- Sem o usuário: sem a leitura por quem lançou. Usuário é dado pessoal de colaborador: mostre só quando a pergunta for de auditoria.
- Exportação só de uma conta: o lançamento chega pela metade e todo ele parece não fechar. Peça todas as contas do lançamento.

### 3.6 Conciliação módulo x contábil

| Módulo | Posição do módulo | Conta contábil |
|---|---|---|
| Estoque | Valor do estoque a custo na data | Estoques de mercadorias |
| Contas a receber | Títulos em aberto na data | Clientes, cartões a receber |
| Contas a pagar | Títulos em aberto na data | Fornecedores |
| Bancos | Saldo das contas correntes | Bancos conta movimento |

**Colunas:** módulo, posição do módulo, saldo contábil, diferença, % e explicação.
A posição do módulo precisa ser **na mesma data** do saldo contábil: estoque em data passada se recompõe pelo Kardex (saldo atual menos os movimentos posteriores à data); títulos em aberto em data passada são os emitidos até a data e baixados depois dela. Comparar a posição de hoje com o saldo do fechamento é o erro que mais gera diferença falsa.
Peça à pessoa quais contas correspondem a cada módulo se o plano não deixar claro.
**Prova:** diferença total = explicada item a item + não explicada, e a diferença é conta de dois totais de origens diferentes (o do módulo e o do balancete). Diferença sem explicação é apresentada como não explicada.

**Para exportar:** peça dois relatórios, ambos na mesma data de fechamento: o balancete (3.1) com as contas correspondentes e a posição do módulo. Do módulo, colunas mínimas: data da posição e valor total (estoque a custo, títulos em aberto a pagar ou a receber, saldo de bancos). Recomendadas: o detalhe por item ou título, para explicar a diferença.

- Posição do módulo em data diferente do saldo contábil: a entrega diz que a comparação não vale e pede a posição na data certa.
- Sem o detalhe do módulo: a diferença sai total, sem explicação item a item.
- Sem a indicação de quais contas do plano correspondem a cada módulo: a pessoa informa, e a entrega mostra as contas usadas.
- Estoque em data passada sem os movimentos: não se recompõe; a conciliação do estoque fica só na data da exportação.

### 3.7 Posição do LALUR

Só existe se o ERP controlar a Parte A (adições, exclusões e compensações ao lucro líquido) e a Parte B (saldos a controlar para exercícios futuros: prejuízos fiscais, diferenças temporárias).
**Colunas, Parte A:** período, lucro líquido antes dos tributos, adições por natureza, exclusões por natureza, lucro real antes da compensação, compensação de prejuízo, lucro real.
**Parte B:** conta, saldo inicial, movimentação, saldo final.
Na maioria dos ERPs de varejo isso fica no sistema fiscal ou do escritório contábil e as tabelas estão vazias: diga isso e pare, sem tentar reconstruir o LALUR a partir dos lançamentos. Classificar o que é adição ou exclusão é juízo tributário, não consulta.
**Prova:** Parte B: saldo inicial + movimentação = saldo final, por conta, com o saldo final do relatório do sistema que escritura o livro. Parte A: lucro líquido antes dos tributos = resultado do balancete do período.

**Para exportar:** peça o relatório do LALUR (Parte A e Parte B) do sistema que o escritura, que pode ser o do escritório contábil. Colunas mínimas: período, natureza da adição ou exclusão, valor; na Parte B, conta e saldo inicial, movimentação e final.

- Sem o relatório: não se reconstrói o LALUR a partir dos lançamentos. Diga isso e pare.
- Sem o balancete do período: a Parte A sai sem a prova do lucro líquido.
- Este relatório só mostra a posição; apuração e enquadramento ficam com o contador.
