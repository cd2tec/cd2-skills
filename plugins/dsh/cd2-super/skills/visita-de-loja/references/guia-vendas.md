Regras do relatório vendas, reaproveitadas aqui: valem para conta, recorte e prova. Entrega e fechamento são os desta skill.


# Relatório de vendas

Esta skill é da CD2 Tech. Ela responde às perguntas do módulo gerencial: quem compra, o quê, por qual canal, com que margem e o que mudou. Serve tanto ao varejo de loja (cupom) quanto ao atacado e à distribuição (pedido e nota por cliente), do dado até um relatório com veredito, leitura e prova.

Os caminhos entre crases abaixo são relativos à pasta desta skill. Rode os comandos sempre a partir da pasta de trabalho da pessoa (a pasta da conversa ou do projeto), chamando os scripts pelo caminho completo, como em python3 <pasta da skill>/scripts/render_relatorio.py. Assim a entrada e as entregas ficam na pasta de trabalho, nunca dentro da pasta do plugin.

Siga o roteiro de conversa em `references/fluxo-dados.md` e o método em `references/metodo-analise.md`. Mapeamento, colunas, consultas-modelo, provas e o que exportar de cada relatório estão em `references/relatorios-vendas.md`.

**Esta skill ou o painel?** Painel para acompanhar a operação (cards, linha do tempo, mapa de calor) é `painel-varejo`. Aqui o resultado é um relatório analítico, com linhas, classes e prova, para decidir sobre sortimento, carteira e política comercial.

## Relatórios

| A pessoa pede | Relatório | Seção |
|---|---|---|
| "curva ABC de venda", "quais produtos fazem 80% da venda" | ABC de venda | 3.1 |
| "venda por cliente", "receita por segmento", "maiores clientes" | Venda por cliente e segmento | 3.2 |
| "produto final e componentes", "rendimento da receita", "kit" | Produto final x componentes | 3.3 |
| "comparado com o ano passado", "mesmas lojas" | Comparativo de períodos | 3.4 |
| "devoluções", "trocas", "cancelamentos" | Devoluções e cancelamentos | 3.5 |
| "clientes inativos", "positivação", "quem parou de comprar" | Carteira de clientes | 3.6 |

Pedido genérico ("análise de vendas") recebe a **ABC de venda por produto** com o resumo das classes e o sintético por departamento.

## Padrões de recorte

- **Período:** últimos 30 dias até a última data com venda; ABC e carteira usam 90 dias (30 dias classificam mal item de giro lento). Declare.
- **Medida:** venda líquida (sem cancelados, líquida de devolução e desconto). Diga qual coluna foi usada e o que ela inclui (impostos, frete, acréscimos).
- **Dimensão da ABC:** produto, por valor. Por quantidade ou por margem quando a pessoa pedir; as três classificações divergem bastante e vale dizer isso.
- **Cortes ABC:** A até 80% do acumulado, B até 95%, C o restante. Ajustável.

## O que venda tem de particular

1. **Qual é a venda.** Bruta, líquida de desconto, líquida de devolução, com ou sem impostos, faturada ou pedida. Em distribuição, pedido, faturamento e entrega são datas e valores diferentes. Escolha uma, declare e não misture.
2. **Devolução não é venda negativa do mesmo dia.** Ela acontece em outro período e, em muitos ERPs, em outra tabela (nota de entrada de devolução). Decida se o relatório é por competência da venda original ou da devolução.
3. **Canal e segmento.** Loja, e-commerce, marketplace, televendas, atacado. O segmento pode estar no cliente, no pedido ou na tabela de preço. Meça o preenchimento antes de quebrar por ele.
4. **Cliente não identificado.** No varejo de loja, a maior parte dos cupons não tem cliente. Relatório por cliente cobre só a parcela identificada: informe o percentual da venda coberto.
5. **Margem depende do custo.** Antes de qualquer coluna de margem, meça cobertura e dispersão do custo como em `references/indicadores-varejo.md`, seção 4.9 (custo estimado gera margem uniforme e falsa).
6. **Mesmas lojas.** Comparar períodos com lojas que abriram ou fecharam mistura crescimento com expansão. Compare só as lojas com venda nos dois períodos e mostre o total à parte.
7. **Dado pessoal.** Ranking de clientes pessoa física usa código e nome; CPF mascarado (***.123.456-**); sem endereço ou contato (`references/metodo-analise.md`, seção 6).

## Prova obrigatória por relatório

| Relatório | Prova |
|---|---|
| ABC | Soma das classes = venda total do período; participações somam 100% |
| Cliente e segmento | Venda identificada + não identificada = venda total |
| Produto final x componentes | Custo dos componentes x quantidade produzida = custo atribuído ao produto final (ou diferença explicada como perda) |
| Comparativo | Total = mesmas lojas + lojas novas + lojas encerradas |
| Devoluções | Devolução por motivo = devolução total |
| Carteira de clientes | Ativos + inativos = clientes distintos da carteira, com contagem direta |

Sem ela, o script recusa. Origem `arquivo` ou `digitado` nunca vira "Prova fechada": o selo é "Conferido só contra o arquivo", mesmo com o total do ERP igual. Quem decide se a prova fechou é o script: não ajuste número para fechar.

## Sem conexão

Siga `references/metodo-analise.md`, seção 2.7. Antes de pedir o arquivo, leia a linha **Para exportar** do relatório: ela diz o que pedir ao ERP, as colunas mínimas e o que fica de fora sem cada coluna opcional. Diga isso à pessoa em uma frase, sem listar a tabela inteira. Coluna que falta não se inventa: diga qual é e o que deixa de sair.

