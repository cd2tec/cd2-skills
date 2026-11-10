Regras do relatório estoque, reaproveitadas aqui: valem para conta, recorte e prova. Entrega e fechamento são os desta skill.


# Relatório de estoque

Esta skill é da CD2 Tech. Ela responde às perguntas do módulo de estoque: quanto você tem, onde está, quanto vale, como chegou a esse saldo e o quanto dá para confiar nele. Vai do dado até um relatório com veredito, leitura e prova.

Os caminhos entre crases abaixo são relativos à pasta desta skill. Rode os comandos sempre a partir da pasta de trabalho da pessoa (a pasta da conversa ou do projeto), chamando os scripts pelo caminho completo, como em python3 <pasta da skill>/scripts/render_relatorio.py. Assim a entrada e as entregas ficam na pasta de trabalho, nunca dentro da pasta do plugin.

Siga o roteiro de conversa em `references/fluxo-dados.md` e o método em `references/metodo-analise.md`. Mapeamento, colunas, consultas-modelo, provas e o que exportar de cada relatório estão em `references/relatorios-estoque.md`.

**Esta skill ou o painel?** Painel para acompanhar a operação (cards, linha do tempo, mapa de calor) é `painel-varejo`. Aqui o resultado é um relatório analítico, com linhas e prova, para decidir sobre reposição, balanço e capital parado.

## Relatórios

| A pessoa pede | Relatório | Seção |
|---|---|---|
| "posição de estoque", "quanto tenho de X", "estoque por departamento" | Estoque geral | 3.1 |
| "Kardex", "extrato do produto", "o que movimentou esse item" | Kardex | 3.2 |
| "resultado do balanço", "divergência do inventário", "acuracidade" | Análise de lote de inventário | 3.3 |
| "o que está faltando", "ruptura", "dias de estoque", "excesso" | Cobertura e ruptura | 3.4 |
| "estoque parado", "sem giro", "encalhe" | Estoque sem venda | 3.5 |
| "estoque negativo", "saldo errado" | Inconsistências de saldo | 3.6 |
| "giro de estoque" | Giro e estoque médio | 3.7 |
| "quanto eu tinha no dia X" | Posição retroativa | 3.8 |

Pedido genérico ("me mostra o estoque") recebe o **estoque geral sintético por departamento**, com os 20 maiores itens em valor e a contagem de negativos e zerados.

## Padrões de recorte

- **Posição:** a mais recente. Descubra a data real da posição (coluna de data de atualização ou a maior data de movimento) e mostre no cabeçalho; posição sem data conhecida sai com esse aviso. Com arquivo, a posição é a da exportação: pergunte a data se o arquivo não trouxer.
- **Movimento (Kardex, giro, cobertura):** últimos 30 dias até a última data com movimento. Kardex é sempre por produto: sem produto informado, peça o código ou mostre os 20 itens com mais movimento para a pessoa escolher.
- **Valorização:** custo médio quando existir; senão o custo que o dado tiver, dizendo qual é (médio, última entrada, reposição, líquido de impostos ou não).
- **Unidade:** todas as lojas e depósitos, com quebra quando houver mais de um.

## O que estoque tem de particular

1. **Saldo atual não é saldo histórico.** A tabela de saldo guarda a posição de agora. Posição em data passada vem de fotografia diária, se o ERP guardar, ou de recomposição pelo Kardex (3.8). Nunca apresente o saldo atual como se fosse o de outra data.
2. **Sentido do movimento.** Entrada, saída, transferência, ajuste, quebra, devolução e estorno costumam ter quantidade positiva e o sinal em um tipo de operação. Liste os tipos distintos com a soma de cada um e monte o `CASE` de sinal a partir disso. Transferência entre lojas aparece duas vezes (saída em uma, entrada na outra): soma zero na rede.
3. **Unidade e embalagem.** Compra em caixa, venda em unidade, pesável em quilo. Confirme em que unidade o saldo está antes de multiplicar por custo ou comparar com venda.
4. **Produto composto.** Kits, cestas, produção própria (padaria, açougue) e itens com receita movimentam os componentes, não o produto final. Saldo zerado no pai pode ser normal.
5. **Custo zerado ou ausente** distorce o valor de estoque. Meça a cobertura de custo (percentual do saldo com custo maior que zero) e informe.
6. **Inventário tem estados.** Lote aberto, congelado, em contagem, encerrado, cancelado. A análise de divergência só vale para lotes com contagem lançada; lote encerrado já ajustou o saldo.

## Prova obrigatória por relatório

| Relatório | Prova |
|---|---|
| Estoque geral | Soma por departamento = soma total sem join com cadastro |
| Kardex | Saldo inicial + entradas - saídas = saldo final; saldo final = saldo atual quando o período vai até a última data |
| Lote de inventário | Itens do lote = contados + não contados; divergência em valor = soma das divergências por item |
| Cobertura e ruptura | Venda usada no cálculo = venda do período pela fonte de vendas |
| Estoque sem venda | Soma do valor por faixa, mais o valor dos itens com venda recente, = valor a custo da posição inteira |
| Inconsistências de saldo | Itens de cada exceção, contados direto na fonte, = listados + omitidos além dos 20 maiores; a soma do valor bate com a soma direta. Amostra de 5 itens conferida na origem, dita como amostra |
| Giro e estoque médio | Custo da mercadoria vendida usado = total a custo da venda do período, somado direto na fonte de vendas |
| Posição retroativa | Recompor até hoje devolve o saldo atual |

Sem ela, o script recusa. Origem `arquivo` ou `digitado` nunca vira "Prova fechada": o selo é "Conferido só contra o arquivo", mesmo com o total do ERP igual. Quem decide se a prova fechou é o script: não ajuste número para fechar.

Kardex que não fecha com o saldo atual é um achado importante (movimento fora da tabela, ajuste direto no saldo, tipo de operação com sinal errado). Mostre a diferença e os tipos de movimento envolvidos em vez de forçar o fechamento.

## Sem conexão

Siga `references/metodo-analise.md`, seção 2.7. Antes de pedir o arquivo, leia a linha **Para exportar** do relatório: ela diz o que pedir ao ERP, as colunas mínimas e o que fica de fora sem cada coluna opcional. Diga isso à pessoa em uma frase, sem listar a tabela inteira. Coluna que falta não se inventa: diga qual é e o que deixa de sair.

