# Relatórios de vendas

Versão inicial. Cada relatório responde a uma pergunta do dono e termina com uma prova.

## Curva ABC de venda

**Pergunta:** quais itens fazem a maior parte da venda?

- Dimensão padrão: produto, por valor líquido. Também vale por cliente, departamento ou vendedor.
- Cortes: classe A até 80% do acumulado, B até 95%, C o restante. Declare se mudar.
- A classe usa o acumulado antes do item, para o item que cruza os 80% ainda ser A.
- Período padrão: 90 dias até a última data com venda. Com menos de 90 dias, item de giro lento classifica mal.
- Itens com venda líquida zero ou negativa ficam fora da curva e são contados à parte.

**Na página:** bloco `pareto` (traz o quadro de classes), sintético por departamento em `barras` e lista em `tabela` com a coluna `classe`.

**Prova:** a soma das classes é igual à venda líquida total do período, pelos mesmos filtros.

**Leituras típicas:** quantos itens fazem a classe A, item A com margem baixa, cauda C longa, dependência de poucos itens.

## Venda por departamento

**Pergunta:** onde está a venda e como ela mudou?

- Use `barras` com `var_pct` quando houver período anterior comparável.
- Mantenha a linha "sem departamento": ela é o tamanho do que o relatório não enxerga.

**Prova:** a soma das linhas é igual à venda total.

## Cuidados com o dado

- Diga qual é a venda: bruta, líquida de desconto, líquida de devolução. Escolha uma e não misture.
- Cancelados e registros indevidos ficam fora da conta; conte quantos e diga isso nas premissas.
- Margem só com custo confiável. Meça quantos produtos têm custo zerado antes de mostrar a coluna.
