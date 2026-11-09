# Regras do SQLite temporário

Quando você não tem conexão com o banco, o relatório roda sobre um arquivo que a pessoa exportou do ERP. O `scripts/dados_arquivo.py` coloca esse arquivo num SQLite temporário e as mesmas consultas do relatório rodam em cima dele. O resultado vale para o arquivo enviado, não para o banco inteiro: o selo do relatório precisa dizer isso.

## Como carregar

```
python3 scripts/dados_arquivo.py carregar --base /tmp/base.sqlite ARQUIVO [ARQUIVO ...]
```

- Aceita CSV (Windows-1252 ou UTF-8, separado por ponto e vírgula, vírgula, tab ou barra vertical) e XLSX (só a primeira planilha). Arquivo `.xls` antigo: peça para a pessoa abrir no Excel e salvar como CSV ou XLSX.
- Cada arquivo vira uma tabela, com o nome do arquivo sem acento e em minúsculas. Cada coluna vira um nome seguro (`Preço Líquido` vira `preco_liquido`). O nome original fica no perfil.
- Números como `1.234,56` e `(R$ 1.234,50)` viram valor. Datas como `31/01/2026` viram `2026-01-31`. Código com zero à esquerda, código de barras e código de conta contábil como `1.1.01` continuam texto: com ponto como separador, a data exige ano de quatro dígitos.
- Linhas de subtotal e total geral vão para `<tabela>__totais` e não entram na tabela principal. Só conta como total a linha em que a célula é apenas o rótulo (`Subtotal`, `TOTAL GERAL`, `Total do dia`, `Total:`) e há número na linha; produto chamado "Total Clean Detergente" fica na principal. Some a principal; use a de totais só para conferir.
- Coluna em que ao menos 80% dos valores são número vira número; o que não for número fica vazio (NULL) e o aviso lista os primeiros valores. Linhas que repetem o cabeçalho (paginação do ERP) saem e entram no aviso.
- CPF vira `***.456.789-**` ao carregar, em coluna de CPF e em qualquer texto com CPF pontuado. Coluna sem "cpf" no nome com valores de 11 dígitos não é mascarada, mas o aviso aponta. Não peça nem repita o número inteiro.
- Arquivo que não é base SQLite nunca é apagado nem sobrescrito: `apagar` e `carregar` recusam, e a base não pode ser um dos arquivos de entrada.
- A resposta é um perfil em JSON: tabelas, linhas, colunas com tipo, percentual de vazios, mínimo, máximo e valores distintos, mais a lista de avisos.

Leia os avisos antes de qualquer conta e repasse à pessoa os que mudam o número. O mais importante: coluna sem vírgula com algum valor no formato `1.234` (peso, por exemplo) é lida como decimal, não como milhar, e o aviso diz isso. Se algum valor da coluna tiver dois grupos de ponto (`1.234.567`), todos os pontos são milhar. Confirme com a pessoa antes de seguir.

## Como medir

Antes de consultar, olhe o perfil: quantas linhas, período (`min` e `max` da coluna de data), colunas muito vazias, quantidade de valores distintos. Se a coluna de data tem lacunas ou o período é menor que o pedido, diga isso no relatório.

## Como consultar

```
python3 scripts/dados_arquivo.py consultar --base /tmp/base.sqlite --sql "SELECT ..." [--limite 500]
```

- Só leitura, uma instrução por vez. `INSERT`, `DROP`, `PRAGMA` e `ATTACH` são recusados.
- A resposta traz `colunas`, `linhas` e `truncado`. Se vier truncado, agregue com `GROUP BY` em vez de pedir mais linhas.
- Se a coluna ou a tabela não existir, o erro lista o que existe. Corrija a consulta com esses nomes.
- Funções de janela (`OVER`), `WITH` e `CAST(... AS float)` funcionam. O perfil avisa quando o SQLite da máquina é anterior ao 3.25 e não tem janela.

## Como apagar

Terminou o relatório, apague a base temporária:

```
python3 scripts/dados_arquivo.py apagar --base /tmp/base.sqlite
```

Só apaga arquivo que é base SQLite. A resposta confirma com `"apagado": true`.

## Traduzindo de SQL Server

| SQL Server | SQLite |
|---|---|
| `SELECT TOP 10 ...` | `SELECT ... LIMIT 10` |
| `OFFSET 0 ROWS FETCH NEXT 10 ROWS ONLY` | `LIMIT 10` (sem `OFFSET 0 ROWS`) |
| `DATEADD(day, -30, GETDATE())` | `date('now', '-30 day')` |
| `DATEADD(month, -1, x)` | `date(x, '-1 month')` |
| `GETDATE()` | `datetime('now')` |
| `CAST(x AS float)` | igual, funciona |
| `ISNULL(a, b)` | `COALESCE(a, b)` |
| `LEN(x)` | `LENGTH(x)` |
| `a + b` com texto | `a || b` |
| `FORMAT(data, 'yyyy-MM')` | `strftime('%Y-%m', data)` |
| `YEAR(x)`, `MONTH(x)` | `CAST(strftime('%Y', x) AS integer)`, `CAST(strftime('%m', x) AS integer)` |
| `dbo.tabela` | `tabela` (sem esquema) |
| `[coluna]` | `"coluna"` |
| funções de janela (`SUM() OVER`, `ROW_NUMBER()`) | iguais |

As datas já estão em ISO (`aaaa-mm-dd`), então comparar com `>=` e `<` e ordenar como texto funciona.
