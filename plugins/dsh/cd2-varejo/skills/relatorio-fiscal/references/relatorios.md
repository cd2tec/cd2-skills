# Fiscal: mapeamento, relatórios e consultas-modelo

Conteúdo:
1. Mapeamento
2. O que medir
3. Relatórios (3.1 a 3.8)

Consultas em SQL Server com marcadores `<assim>`; **[modelo]** até passarem na prova nos dados da pessoa. A consulta do resumo por CFOP (3.1) foi exercitada em SQLite sobre um arquivo de exemplo, na versão convertida pela tabela de `references/regras-sqlite.md`. Sem conexão, adapte a consulta com essa tabela e troque os marcadores pelos nomes de coluna do perfil do arquivo. Cada relatório termina com **Para exportar**: o que pedir ao ERP quando não há conexão.

Todo relatório desta skill é conferência gerencial e não substitui a escrituração fiscal oficial.

## 1. Mapeamento

| Domínio | Para quê | Termos de busca | O que confirmar |
|---|---|---|---|
| Cabeçalho da nota | Totais, situação, numeração | `nota`, `nf`, `nfe`, `nota_header`, `documento_fiscal`, `docto`, `capa` | Chave completa (loja, número, série, modelo, tipo), datas de emissão e de entrada, situação, cancelamento |
| Itens da nota | CFOP, CST, tributos por item | `nota_item`, `nf_item`, `item_nota`, `det` | CFOP por item (pode diferir do cabeçalho), bases, alíquotas, valores |
| Cupom e NFC-e | Venda de caixa | `nfce`, `cupom`, `sat`, `ecf`, `reducao_z` | Se o detalhe está aqui ou só o resumo vai para as notas |
| Parceiro | Cliente e fornecedor do documento | `cliente`, `fornecedor`, `parceiro`, `cnpj`, `uf` | UF (operação interna ou interestadual) |
| CFOP e natureza | Descrição da operação | `cfop`, `natureza_operacao`, `codigo_fiscal` | Cadastro com descrição e se movimenta estoque e financeiro |
| Situação tributária | CST, CSOSN | `cst`, `csosn`, `sit_trib`, `situacao_tributaria` | Formato (2 ou 3 dígitos), por imposto |
| Tributos | Resumo | `icms`, `icms_st`, `subst`, `pis`, `cofins`, `ipi`, `iss`, `fcp`, `difal`, `ibs`, `cbs`, `_is` | Base, alíquota e valor de cada um, no item e no cabeçalho |
| Cadastro tributário do produto | Inconsistências | `ncm`, `cest`, `tributacao`, `figura_fiscal`, `aliquota` | Por produto, por UF ou por loja |
| Eventos e controle | Sequência, inutilização | `inutilizacao`, `evento`, `cancelamento`, `protocolo`, `chave_acesso` | Faixas inutilizadas, protocolo de autorização |

## 2. O que medir

- Notas por tipo (entrada, saída), modelo e situação: contagem e valor.
- Período com dado e volume por mês.
- % de itens com CFOP, CST, NCM, base e alíquota preenchidos.
- Colunas de tributo existentes mas zeradas em todo o histórico (não capturadas).

Com banco, para achar as colunas certas numa tabela de nota (costumam ter mais de cem), consulte o catálogo com filtro de nome em vez de descrever a tabela inteira:

```sql
SELECT COLUMN_NAME, DATA_TYPE FROM INFORMATION_SCHEMA.COLUMNS
WHERE TABLE_NAME = '<nota_item>'
  AND (COLUMN_NAME LIKE '%cfop%' OR COLUMN_NAME LIKE '%cst%' OR COLUMN_NAME LIKE '%icms%'
       OR COLUMN_NAME LIKE '%pis%' OR COLUMN_NAME LIKE '%cofins%' OR COLUMN_NAME LIKE '%val%' OR COLUMN_NAME LIKE '%vlr%')
```

Com arquivo, estas medidas saem do perfil de `scripts/dados_arquivo.py`. O que não estiver no arquivo não tem como ser medido: diga isso nas premissas.

## 3. Relatórios

### 3.1 Documentos fiscais: sintético

**Agrupamentos:** CFOP (default), CST, alíquota de ICMS, modelo, dia, UF, parceiro.
**Colunas:** chave do agrupamento com descrição, documentos, itens, valor contábil, base de ICMS, ICMS, base de ST, ICMS-ST, IPI, PIS, COFINS, isentas, outras, participação %.

```sql
SELECT x.cfop, x.itens, CAST(x.valor AS float) valor,
       CAST(x.icms AS float) icms, CAST(x.icms_st AS float) icms_st,
       CAST(100.0 * x.valor / NULLIF(SUM(x.valor) OVER (), 0) AS float) part_pct
FROM (SELECT i.<cfop> cfop, COUNT(*) itens,
             SUM(COALESCE(i.<valor_total>, 0)) valor,
             SUM(COALESCE(i.<valor_icms>, 0)) icms,
             SUM(COALESCE(i.<valor_icms_st>, 0)) icms_st
      FROM <nota_item> i
      JOIN <nota> h ON h.<cod_loja> = i.<cod_loja> AND h.<num_nota> = i.<num_nota>
                   AND h.<serie> = i.<serie> AND h.<modelo> = i.<modelo> /* + tipo */
      WHERE h.<situacao_autorizada> AND h.<cod_loja> = <loja>
        AND h.<data> >= '2025-07-01' AND h.<data> < '2025-08-01'
      GROUP BY i.<cfop>) x
ORDER BY x.valor DESC, x.cfop OFFSET 0 ROWS
```

A coluna do item usada em `<valor_total>` é o **valor do produto do item** (quantidade x preço menos o desconto do item). Se o item do ERP embute IPI, frete ou ST rateados, use a coluna de valor de produtos do item, ou o valor do item sai maior que o do cabeçalho e a prova acusa diferença que não existe. Declare a coluna usada.
"Isentas" e "outras" dependem do CST: só preencha essas colunas se o dado já as trouxer; não as derive por conta própria. A junção leva a série e o modelo: só por número, a mesma nota de séries diferentes se multiplica e o total passa do valor dos cabeçalhos.
**Prova:** soma por CFOP = valor de produtos dos cabeçalhos autorizados do período, somado direto no cabeçalho, sem a junção com os itens; itens do relatório = itens das notas autorizadas do período, contados direto na exportação de itens. Se não fechar, a diferença é o assunto do relatório 3.3, não um ajuste.

**Para exportar:** peça dois relatórios do mês e do estabelecimento: as notas (cabeçalho) e os itens das notas, em CSV ou Excel. Colunas mínimas do cabeçalho: número, série, modelo, data, situação, valor de produtos. Dos itens: número, série, modelo, CFOP, valor. Recomendadas: loja ou CNPJ, ICMS e ICMS-ST por item, tipo (entrada ou saída).

- Sem a série e o modelo: a junção entre cabeçalho e itens mistura notas de séries diferentes. Peça as duas colunas; sem elas, a entrega diz que a junção é só por número.
- Sem a situação: canceladas entram na soma. Peça a coluna ou só as autorizadas, e diga qual veio.
- Só o relatório sintético por CFOP que o próprio ERP gera: sai a tabela por CFOP como veio, mas a prova contra o cabeçalho e a conferência de série e de cancelada não existem. O selo é "Conferido só contra o arquivo".
- Sem os valores de imposto por item: sai o valor contábil por CFOP, sem ICMS nem ST.
- Sem a loja ou o CNPJ: a entrega diz que o arquivo pode misturar estabelecimentos.

### 3.2 Documentos fiscais: analítico

**Por produto:** código, descrição, NCM (Nomenclatura Comum do Mercosul), CFOP, CST, quantidade, valor, base, alíquota, ICMS, ST, PIS, COFINS; uma linha por produto, CFOP, CST e alíquota.
**Por nota (conferência):** data, número, série, modelo, parceiro, UF, CFOP, valor de produtos, desconto, frete, total, ICMS, ST, situação, chave de acesso.
Volume alto: o resumo e os 30 maiores na conversa, completo em planilha, com filtro obrigatório de período e loja (`references/metodo-analise.md`, seção 5).
**Leituras típicas:** mesmo produto com CST ou alíquota diferentes no período (mudança de cadastro ou erro), CFOP incompatível com a UF do parceiro (interno 5.xxx para outra UF), item tributado com base zero.
**Prova:** soma dos itens por nota = valor de produtos do cabeçalho, que vem de outra tabela.

**Para exportar:** peça o relatório de itens das notas do mês, uma linha por item, e o de cabeçalhos. Colunas mínimas dos itens: número, série, modelo, produto, CFOP, CST, quantidade, valor. Recomendadas: NCM, base, alíquota, ICMS, ST, PIS, COFINS, UF do parceiro.

- Sem o cabeçalho: sai o detalhe por produto, mas a prova contra o valor de produtos não existe.
- Sem o NCM: sai a leitura por CFOP e CST, sem a conferência de NCM.
- Sem a UF do parceiro: sem a leitura de CFOP incompatível com a UF.
- Sem base e alíquota: não dá para conferir `valor = base x alíquota`.
- Arquivo muito grande: filtre período e loja na exportação.

### 3.3 Cabeçalho x itens

```sql
SELECT COUNT(*) notas,
       SUM(CASE WHEN i.soma IS NULL THEN 1 ELSE 0 END) sem_item,
       SUM(CASE WHEN i.soma IS NOT NULL AND ABS(h.<valor_produtos> - i.soma) > 0.05 THEN 1 ELSE 0 END) divergentes,
       SUM(CASE WHEN i.soma IS NOT NULL AND ABS(h.<valor_produtos> - i.soma) <= 0.05 THEN 1 ELSE 0 END) fecham,
       CAST(SUM(h.<valor_produtos>) AS float) total_cabecalho,
       CAST(SUM(COALESCE(i.soma, 0)) AS float) total_itens_ligados,
       CAST(SUM(h.<valor_produtos> - COALESCE(i.soma, 0)) AS float) diferenca_total
FROM <nota> h
LEFT JOIN (SELECT <cod_loja>, <num_nota>, <serie>, <modelo>, SUM(COALESCE(<valor_total>, 0)) soma
           FROM <nota_item> GROUP BY <cod_loja>, <num_nota>, <serie>, <modelo>) i
       ON i.<cod_loja> = h.<cod_loja> AND i.<num_nota> = h.<num_nota>
      AND i.<serie> = h.<serie> AND i.<modelo> = h.<modelo>
WHERE h.<situacao_autorizada> AND h.<cod_loja> = <loja>
  AND h.<data> >= '2025-07-01' AND h.<data> < '2025-08-01'
```

As três classes são exclusivas: `sem_item` (nota sem nenhum item), `divergentes` (com itens e diferença acima da tolerância) e `fecham` (com itens e diferença dentro dela). Só as autorizadas da loja e do período entram; nota cancelada sem item não infla `sem_item`.

**Antes de chamar de divergência**, elimine as causas estruturais, nesta ordem:
1. chave de junção incompleta (falta série, modelo ou tipo, e notas diferentes se misturam);
2. o valor do item é bruto e o do cabeçalho é líquido de desconto, ou o contrário (teste `item - desconto`);
3. frete, despesas e impostos por fora rateados no item;
4. notas canceladas com itens removidos.

Uma taxa de divergência muito alta (dezenas por cento) quase sempre é uma dessas causas, não erro de emissão. Depois de ajustar, liste as divergentes restantes com número, parceiro, os dois valores e a diferença. Tolerância de R$ 0,05 por nota para arredondamento.
**Prova:** (1) as notas, contadas direto no cabeçalho com os mesmos filtros e sem a junção, = fecham + divergentes + sem item. (2) o total do cabeçalho menos a soma direta do valor dos itens (`SUM` na tabela ou no arquivo de itens, com os mesmos filtros de loja, período e situação, sem passar pela junção) = `diferenca_total`. Itens de nota que não achou cabeçalho, ou chave que não casou, fazem esta segunda parte falhar, e é para isso que ela serve.

**Para exportar:** os mesmos dois relatórios de 3.1 (cabeçalhos e itens do mês), com a chave completa nos dois. Colunas mínimas: número, série, modelo e valor de produtos no cabeçalho; número, série, modelo e valor no item. Recomendadas: desconto, frete, outras despesas, situação.

- Sem a chave completa nos dois lados: a taxa de divergência sai inflada, e a entrega avisa que a causa provável é a chave.
- Sem desconto e frete no cabeçalho: não dá para testar as causas 2 e 3, e a entrega diz isso.
- Sem os itens: não há o que conferir. Este relatório não sai só do cabeçalho.

### 3.4 Entradas x saídas por CFOP

Duas tabelas lado a lado (entradas 1, 2, 3; saídas 5, 6, 7), agrupadas pelo CFOP, com valor contábil, base e ICMS, e os grupos de operação: compra e venda, devolução, transferência, bonificação, remessa e retorno, uso e consumo, baixa de estoque.
A separação entre entrada e saída vem do primeiro dígito do **CFOP do item** (1, 2 e 3 entrada; 5, 6 e 7 saída), que fica no item e não no cabeçalho: uma nota com itens dos dois sentidos reparte o valor entre os lados.
**Leituras típicas:** transferências entre lojas que não fecham (saída de uma sem entrada na outra, no mesmo período), devoluções acima do padrão, entradas de uso e consumo classificadas como revenda.
**Prova:** valor das entradas + valor das saídas = valor dos documentos autorizados do período, somado direto no cabeçalho, pelo total geral. Por lado, a prova só existe se o cabeçalho trouxer o tipo da nota (entrada ou saída); sem ele, fecha só o total.

**Para exportar:** o mesmo arquivo de itens de 3.1, com entradas e saídas, e o cabeçalho para a prova. Colunas mínimas: loja, CFOP, valor. Recomendadas: ICMS, base, data.

- Só saídas ou só entradas no arquivo: o relatório sai de um lado só, e a entrega diz qual.
- Sem a loja: a leitura de transferência entre lojas não existe.
- Sem a data: o período vale o que a pessoa informar.

### 3.5 Resumo de tributos

**Colunas por imposto:** base, valor, alíquota efetiva (valor / base), nas saídas (débito) e nas entradas (crédito destacado).
Apresente como **débitos e créditos destacados nos documentos**. A diferença entre os dois **não é o imposto a recolher**: a apuração tem ajustes, estornos, créditos não aproveitáveis, regimes especiais e ST que não estão nos documentos. Diga isso junto do número.
**Prova:** total por imposto = soma por CFOP = soma por alíquota = total de imposto do cabeçalho, somado direto nele.

**Para exportar:** o arquivo de itens com os tributos, dos dois sentidos. Colunas mínimas: CFOP, valor do item, base e valor de cada imposto (ICMS, PIS, COFINS). Recomendadas: alíquota, IPI, ICMS-ST, total de imposto no cabeçalho.

- Imposto não exportado: o relatório diz que o imposto não veio, não que é zero.
- Sem a base: sem a alíquota efetiva.
- Sem o total de imposto no cabeçalho: a prova compara só CFOP com alíquota, e o selo diz que não houve total independente.
- A apuração do que recolher não sai deste relatório, de arquivo nenhum: é do contador.

### 3.6 Sequência e situação

**Por loja, modelo e série:** primeiro e último número do período, emitidas, canceladas, inutilizadas, denegadas, faltantes.

```sql
SELECT h.<serie>, MIN(h.<num_nota>) primeiro, MAX(h.<num_nota>) ultimo, COUNT(*) registradas,
       MAX(h.<num_nota>) - MIN(h.<num_nota>) + 1 - COUNT(DISTINCT h.<num_nota>) lacunas_aritmeticas
FROM <nota> h
WHERE h.<tipo> = <saida_emissao_propria> AND h.<modelo> = <modelo> AND h.<cod_loja> = <loja>
  AND h.<data> >= '2025-07-01' AND h.<data> < '2025-08-01'
GROUP BY h.<serie>
```

`lacunas_aritmeticas` é só a conta do primeiro ao último: serve de conferência cruzada, não de prova. Os faltantes vêm dos saltos:

```sql
SELECT y.<serie>, y.num + 1 inicio_lacuna, y.proximo - 1 fim_lacuna, y.proximo - y.num - 1 faltantes
FROM (SELECT h.<serie>, h.<num_nota> num,
             LEAD(h.<num_nota>) OVER (PARTITION BY h.<serie> ORDER BY h.<num_nota>) proximo
      FROM <nota> h
      WHERE h.<tipo> = <saida_emissao_propria> AND h.<modelo> = <modelo> AND h.<cod_loja> = <loja>
        AND h.<data> >= '2025-07-01' AND h.<data> < '2025-08-01') y
WHERE y.proximo - y.num > 1
ORDER BY y.<serie>, y.num
```

Sem inutilizadas conhecidas, `faltantes` somados devem igualar `lacunas_aritmeticas`; diferença aponta número repetido. Só vale para **emissão própria**: notas de terceiros não têm sequência. Antes de reportar salto, desconte as faixas inutilizadas e veja se a numeração é compartilhada entre lojas ou PDVs.
**Canceladas:** quantidade, valor, % sobre as emitidas, prazo entre emissão e cancelamento, e por usuário quando a pergunta for de auditoria.
**Prova:** último - primeiro + 1 = emitidas + canceladas + inutilizadas + faltantes, com os faltantes somados da lista de saltos (LEAD) e não da conta do primeiro ao último.

**Para exportar:** peça o relatório de notas emitidas do mês, com as canceladas, e o das faixas inutilizadas. Colunas mínimas: número, série, modelo, situação. Recomendadas: data, loja, valor, data do cancelamento.

- Sem as canceladas na exportação (só as autorizadas): todo cancelamento aparece como salto. Peça com as canceladas.
- Sem o relatório de inutilizadas: não dá para separar número inutilizado de número que sumiu. A entrega lista os saltos como "a conferir".
- Sem série e modelo: a sequência mistura séries.
- Notas de terceiros no arquivo: filtre só a emissão própria, ou a sequência sai errada.

### 3.7 Cadastro tributário

Exceções, cada uma com contagem e amostra, priorizadas pela venda do produto:
- produto ativo sem NCM, ou com NCM de tamanho diferente de 8 dígitos;
- produto com ST sem CEST (Código Especificador da Substituição Tributária);
- mesmo NCM com tributações diferentes entre produtos (pode ser legítimo; é lista de revisão);
- CST que indica tributação com alíquota zero, ou CST de isenção com alíquota preenchida;
- produto vendido no período com tributação diferente da do cadastro atual.

Apresente como **itens a revisar pelo fiscal**. A skill não diz qual é a tributação correta.
**Prova:** produtos avaliados = produtos do cadastro (contagem direta) = com alguma exceção + sem exceção. Uma amostra de 5 itens de cada lista é conferida na origem e dita como conferência de amostra.

**Para exportar:** peça o cadastro de produtos com os dados fiscais. Colunas mínimas: código, descrição, NCM, CST. Recomendadas: CEST, alíquota, situação do produto (ativo ou inativo), venda do período por produto.

- Sem a venda por produto: a lista sai sem prioridade por venda.
- Sem o CEST: sem a exceção de ST sem CEST.
- Sem os itens vendidos com a tributação usada: sem o último tipo de exceção (venda diferente do cadastro).
- Um NCM digitado em planilha pode perder zero à esquerda: confira o tamanho antes de apontar NCM curto.

### 3.8 Campos da reforma tributária

Mede o preenchimento, não o valor: por mês e por modelo, % de itens com CST e classificação tributária de IBS e CBS preenchidos, % com base e valor, e a mesma coisa para IS. Liste os produtos de maior venda sem classificação.
Só existe se o dado tiver as colunas. Sem elas, diga que a versão do ERP ainda não as traz. As regras e as alíquotas de transição mudam por ano: é aqui que a pergunta "uso o que sei ou pesquiso novidades?" pesa mais.
**Prova:** itens com o campo preenchido + itens sem o campo = itens do período, contados direto.

**Para exportar:** peça o relatório de itens das notas dos últimos meses com as colunas de IBS, CBS e IS, se o ERP as tiver. Colunas mínimas: mês ou data, modelo, CST ou classificação de IBS e CBS. Recomendadas: base e valor de cada um, produto.

- Sem essas colunas no arquivo: a versão do ERP ainda não as traz, ou não saíram na exportação. Pergunte qual dos dois antes de concluir.
- Sem o modelo: a medida sai misturada entre NF-e e NFC-e.
- Sem a venda por produto: sem a lista dos maiores produtos sem classificação.
