# Metodologia

Como a skill chega aos números, quais premissas usa e o que ela não considera. É a mesma metodologia da calculadora gratuita de VR e VA da CD2 (https://calc-vrva.cd2.com.br/?utm_source=gpt-store&utm_medium=skill&utm_campaign=custo-vrva).

Quando a plataforma roda código, a conta sai do script calc.py da skill. Quando não roda, siga as fórmulas abaixo na ordem e mostre cada conta para a pessoa.

É uma estimativa gerencial. Não é parecer jurídico nem contábil. O contrato e o extrato de cada operadora são a referência do que foi cobrado de verdade.

Conferido em 06/11/2026.

## Regras usadas

Fonte: [Decreto 12.712/2025 no site do Planalto](https://www.planalto.gov.br/ccivil_03/_ato2023-2026/2025/decreto/D12712.htm), que altera o Decreto 10.854/2021.

- Teto da taxa de desconto (MDR) cobrada do estabelecimento: 3,6% (art. 182-B, I). MDR é a taxa que a operadora desconta de cada venda paga com o vale.
- Repasse: até 15 dias corridos, contados da data da transação (art. 182-C).
- Interoperabilidade plena: 360 dias da publicação, em 07/11/2026 (art. 177 e art. 182-D). A partir daí, qualquer maquininha pode aceitar qualquer cartão de vale.
- A tarifa de intercâmbio (2%, art. 182-B, II) é cobrada entre emissora e credenciadora, não da loja, e por isso não entra na conta.

## O que você informa

- **Por bandeira:** vendas no mês em vale (R$), taxa cobrada (% por venda) e prazo de recebimento (dias corridos da venda até o dinheiro cair).
- **Da loja:** custo do dinheiro parado, em % ao mês. Começa em 2%.
- **Rede:** as bandeiras de cada loja. Cada loja tem a sua conta, e a rede soma.

## Fórmulas, por bandeira

- Taxa acima do teto, em pontos = máximo entre 0 e (taxa menos 3,6).
- Acima do teto por mês = vendas no mês × taxa acima do teto ÷ 100.
- Dias além do prazo = máximo entre 0 e (prazo menos 15).
- Dinheiro parado = vendas no mês ÷ 30 × dias além do prazo.
- Custo do parado por mês = dinheiro parado × custo do dinheiro ÷ 100.
- Total por mês = acima do teto por mês + custo do parado por mês.
- Por ano = por mês × 12.

Os totais da loja somam as bandeiras com vendas maiores que zero. A bandeira que puxa o custo é a de maior total por mês.

## Premissas

- Custo do dinheiro parado: 2% ao mês. A pessoa pode informar outro valor na conversa, por exemplo o que pagaria num capital de giro.
- Mês de 30 dias.

## Cores

- Verde (Dentro): taxa até 3,6% e prazo até 15 dias.
- Vermelho (Acima): taxa 1 ponto ou mais acima do teto, ou prazo de 30 dias ou mais.
- Amarelo (Pouco acima): o resto.

## O que fazer, em ordem

1. Comece pela bandeira de maior custo, quando houver custo.
2. Se alguma taxa passa de 3,6%: peça por escrito a taxa de até 3,6%, que é o teto do decreto.
3. Se algum prazo passa de 15 dias: peça por escrito o repasse em até 15 dias corridos da venda.
4. Confira se há cobrança além da taxa, como aluguel ou anuidade, e pergunte à operadora com base em quê.
5. Compare a sua maquininha atual com uma que aceite todos os vales.
6. Confira todo mês no extrato se a taxa cobrada é a do contrato.

## Valores de conferência

Padaria de exemplo, com custo do dinheiro de 2% ao mês:

| Bandeira | Vendas/mês | Taxa | Prazo | Acima do teto/mês | Parado | Custo do parado/mês |
|---|---|---|---|---|---|---|
| Alelo | R$ 18.000 | 6,5% | 30 | R$ 522,00 | R$ 9.000,00 | R$ 180,00 |
| Pluxee | R$ 12.000 | 5,9% | 30 | R$ 276,00 | R$ 6.000,00 | R$ 120,00 |
| Ticket | R$ 10.000 | 6,0% | 32 | R$ 240,00 | R$ 5.666,67 | R$ 113,33 |
| VR | R$ 8.000 | 4,5% | 25 | R$ 72,00 | R$ 2.666,67 | R$ 53,33 |

Total: R$ 1.576,67 por mês e R$ 18.920 por ano. Esses valores são testes do script calc.py da skill.

## Situação na Justiça

Conferida em 06/11/2026: as grandes operadoras ainda contestam o decreto na Justiça. Fontes:

- https://www.congressoemfoco.com.br/noticia/116224/mudancas-no-vale-alimentacao-entram-em-vigor-sob-pressao-de-liminares
- https://www.bloomberglinea.com.br/negocios/justica-derruba-liminares-e-abre-caminho-para-novas-regras-a-empresas-de-vale-refeicao/
- https://atarde.com.br/economia/vale-alimentacao-nao-sera-aceito-em-todas-as-maquininhas-a-partir-de-sabado-entenda-1408507

Este é o ponto que mais muda. Com pesquisa, confira de novo no dia.

## Limites

- Não entram tarifa de intercâmbio, aluguel de maquininha, antecipação, impostos ou outras cobranças.
- A situação judicial pode mudar quem precisa cumprir o decreto. Conferida em 06/11/2026: as grandes operadoras ainda contestam o decreto na Justiça.
- O Comitê Gestor do PAT pode alterar o teto e o prazo.
- A conta usa a taxa e o prazo informados. O que foi cobrado de verdade está no extrato de cada operadora.
