# Regras do SQLite temporário

Quando você não tem conexão com o banco, o relatório roda sobre um arquivo que a pessoa exportou do ERP. O `scripts/dados_arquivo.py` coloca esse arquivo num SQLite temporário e as mesmas consultas do relatório rodam em cima dele. O resultado vale para o arquivo enviado, não para o banco inteiro: o selo do relatório precisa dizer isso.

## Como carregar

```
python3 <pasta da skill>/scripts/dados_arquivo.py carregar --base <pasta temporária>/base.sqlite ARQUIVO [ARQUIVO ...]
```

Rode a partir da pasta de trabalho da pessoa, com o caminho completo do script. `<pasta temporária>` é a pasta temporária do sistema, que muda de uma máquina para outra: descubra com `python3 -c "import tempfile; print(tempfile.gettempdir())"`. Use o mesmo caminho em `consultar` e em `apagar`.

**Todos os arquivos vão na mesma chamada.** `carregar` apaga a base que já existe naquele caminho: uma segunda chamada não soma tabelas, troca a base inteira.

- Aceita CSV (Windows-1252 ou UTF-8, separado por ponto e vírgula, vírgula, tab ou barra vertical) e XLSX (só a primeira planilha). Arquivo `.xls` antigo: peça para a pessoa abrir no Excel e salvar como CSV ou XLSX.
- Cada arquivo vira uma tabela, com o nome do arquivo sem acento e em minúsculas. Cada coluna vira um nome seguro (`Preço Líquido` vira `preco_liquido`). O nome original fica no perfil.
- Números como `1.234,56` e `(R$ 1.234,50)` viram valor. Datas como `31/01/2026` viram `2026-01-31`. Código com zero à esquerda, código de barras e código de conta contábil como `1.1.01` continuam texto: com ponto como separador, a data exige ano de quatro dígitos.
- Título, período e outras linhas antes do cabeçalho saem, e o aviso cita até três delas. O cabeçalho é a primeira linha com a largura mais comum do arquivo em que a maioria das células é texto. Se a detecção errar, carregue de novo com `--cabecalho N` (N é a linha do cabeçalho, a primeira é 1), que vale para todos os arquivos da chamada.
- Linhas de subtotal e total geral vão para `<tabela>__totais` e não entram na tabela principal. É total a linha com número e com uma célula que é apenas o rótulo (`Subtotal`, `TOTAL GERAL`, `Total do dia`, `Total Depto`, `Total Loja 3`, `Total:`), em qualquer coluna, desde que o rótulo seja a primeira célula preenchida ou que a linha deixe vazia uma coluna quase sempre preenchida. Produto chamado "Total Clean Detergente" fica na principal, e rótulo que se repete em mais de 20% das linhas completas é categoria (`Baixa = Total`) e também fica. Rótulo cujas ocorrências são, todas, a soma das linhas acima delas vai para os totais em qualquer coluna. Linha que começa com `Total` e mais uma palavra (`Total Depto Mercearia`, mas também o produto `Total Clean Detergente`) só vai para os totais se duas ou mais dessas linhas fecharem, em toda coluna numérica, a soma de ao menos duas linhas acima. Linha com as duas primeiras colunas vazias e só números vai para os totais, com aviso de possível subtotal sem rótulo. Some a principal; use a de totais só para conferir.
- **Linha com rótulo de total, ou que começa com `Total` e mais uma palavra, e que ficou na tabela principal gera aviso, com a coluna e a quantidade.** Não dá para saber só pelo arquivo se é categoria, produto ou total. Pergunte à pessoa antes de calcular. Se forem totais, tire essas linhas na consulta (`WHERE <coluna> <> 'Total'`), senão a soma conta em dobro. Se forem dados reais, como `Baixa = Total`, siga e registre a resposta nas premissas.
- Coluna em que ao menos 80% dos valores são número ou data vira número ou data; o que não converter (`n/d`, `31/02/2026`) fica vazio (NULL) e o aviso lista os primeiros valores. Data zerada (`00/00/0000`) é data em branco, como título em aberto: fica vazia e não conta nesses 80%, e o aviso diz quantas são. Linhas que repetem o cabeçalho (paginação do ERP) saem e entram no aviso.
- CPF vira `***.456.789-**` ao carregar, em coluna de CPF e em qualquer texto com CPF pontuado. Coluna sem "cpf" no nome com valores de 11 dígitos não é mascarada, mas o aviso aponta e o perfil não mostra `min`, `max` nem `valores` dela. Não peça nem repita o número inteiro.
- Arquivo que não é base SQLite nunca é apagado nem sobrescrito: `apagar` e `carregar` recusam, e a base não pode ser um dos arquivos de entrada.
- A resposta é um perfil em JSON: tabelas, linhas, colunas com tipo, percentual de vazios, mínimo, máximo e quantidade de valores distintos, mais a lista de avisos. Coluna de texto com até 20 valores distintos traz `valores`, com cada valor e quantas linhas ele tem: é onde aparecem status, tipo e cancelado.

Leia os avisos antes de qualquer conta e repasse à pessoa os que mudam o número. O mais importante: coluna sem vírgula com algum valor no formato `1.234` (peso, por exemplo) é lida como decimal, não como milhar, e o aviso diz isso. Se algum valor da coluna tiver dois grupos de ponto (`1.234.567`), todos os pontos são milhar. Confirme com a pessoa antes de seguir.

## Como medir

Antes de consultar, olhe o perfil: quantas linhas, período (`min` e `max` da coluna de data), colunas muito vazias, quantidade de valores distintos. Se a coluna de data tem lacunas ou o período é menor que o pedido, diga isso no relatório.

## Como consultar

```
python3 <pasta da skill>/scripts/dados_arquivo.py consultar --base <pasta temporária>/base.sqlite --sql "SELECT ..." [--limite 500]
```

- Só leitura, uma instrução por vez. `INSERT`, `DROP`, `PRAGMA` e `ATTACH` são recusados.
- A resposta traz `colunas`, `linhas` e `truncado`. Se vier truncado, agregue com `GROUP BY` em vez de pedir mais linhas.
- Se a coluna ou a tabela não existir, o erro lista o que existe. Corrija a consulta com esses nomes.
- Funções de janela (`OVER`), `WITH` e `CAST(... AS float)` funcionam. O perfil avisa quando o SQLite da máquina é anterior ao 3.25 e não tem janela.

## Como apagar

Terminou o relatório, apague a base temporária:

```
python3 <pasta da skill>/scripts/dados_arquivo.py apagar --base <pasta temporária>/base.sqlite
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
| `DATEDIFF(day, a, b)` | `CAST(julianday(date(b)) - julianday(date(a)) AS integer)` |
| `CONVERT(varchar(10), x, 23)` | `date(x)` |
| `CONVERT(float, x)` | `CAST(x AS float)` |
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
