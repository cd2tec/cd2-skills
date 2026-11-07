# Metodologia

Como a skill chega aos números, quais premissas usa e o que ela não considera. É a mesma metodologia da calculadora gratuita da CD2 (https://calc-fim-escala6x1.cd2.com.br/?utm_source=codex&utm_medium=skill&utm_campaign=fim-escala-6x1).

Quando a plataforma roda código, a conta sai do script calc.py da skill. Quando não roda, siga as fórmulas abaixo na ordem e mostre cada conta para a pessoa.

É uma estimativa gerencial. Não é parecer jurídico, trabalhista nem contábil. A convenção coletiva do seu sindicato prevalece sobre os valores usados aqui.

## A regra

Base: [Emenda Constitucional 141/2026](https://www.planalto.gov.br/ccivil_03/constituicao/emendas/emc/emc141.htm), publicada em 16/10/2026.

| Data | O que vale |
|---|---|
| Até 15/12/2026 | 44h semanais |
| A partir de 16/12/2026 | 40h semanais sem acordo coletivo, até 42h com acordo, com 2 folgas por semana |
| A partir de 16/12/2027 | Até 40h semanais para todos, com 2 folgas por semana |

**Com e sem acordo coletivo.** A Constituição mantém o limite de 8 horas por dia. Com 2 folgas sobram 5 dias, e 5 × 8h dá 40h. Para chegar às 42h é preciso trabalhar 8h24 por dia, e só convenção ou acordo coletivo pode ampliar a jornada diária, até 16/12/2027. Por isso a conta mostra as duas situações, começando por "sem acordo". Esta é uma leitura do texto: confirme com seu advogado.

## O que você informa

- **Loja:** dias abertos por semana, horas abertas por dia e encargos sobre o salário.
- **Setor:** pessoas e salário médio. Opcionais: postos abertos ao mesmo tempo e jornada atual, que começa em 44h.
- **Convenção (opcional):** jornada semanal, dias máximos, banco de horas e limite de hora extra por dia.

## As contas

Nas fórmulas, `H` é a jornada semanal da situação (40h ou 42h) e `D` são os dias máximos por semana (5).

**Horas a menos por semana:**
`pessoas × (jornada atual − H)`, nunca abaixo de zero.

**Equivalente em pessoas:**
`horas a menos ÷ H`

**Gente necessária pelas horas:**
`pessoas × jornada atual ÷ H`, arredondado para cima.

**Gente necessária pelos postos**, quando informados:
- `turnos = horas abertas ÷ (H ÷ D)`, arredondado para cima
- `pessoas-dia = dias abertos × postos × turnos`
- `necessárias = pessoas-dia ÷ D`, arredondado para cima

**Gente a mais no setor:**
o maior dos dois critérios, menos as pessoas de hoje, nunca abaixo de zero.

### A faixa da loja

Arredondar setor por setor faz quase todo setor pequeno dar +1, mesmo perdendo poucas horas. Por isso a conta mostra uma faixa:

- **Limite de cima:** a soma da gente a mais de cada setor, com uma contratação em cada setor.
- **Limite de baixo:** o total de horas da loja ÷ `H`, arredondado para cima, menos as pessoas de hoje. É o caso de gente que cobre mais de um setor. Nunca fica abaixo do que falta para fechar os postos informados, nem acima do limite de cima.

### Custos

- **Custo por pessoa:** `salário médio × (1 + encargos)`.
- **Limite de cima:** a soma de gente a mais × custo por pessoa de cada setor.
- **Limite de baixo:** quem falta para fechar os postos custa o valor do próprio setor, e o restante usa o custo médio da loja. Nunca passa do limite de cima.
- **No ano:** custo mensal × 12. Os encargos já incluem 13º e férias.
- **Custo da hora, sem contratar:** `jornada atual ÷ H − 1`. Dá 4,76% em 42h e 10% em 40h, porque o salário não pode cair.
- **Hora extra:** `horas a menos × 4,33 semanas × (salário ÷ divisor) × 1,5`.

### A cor do setor

- **Vermelho (Apertado):** perde meia pessoa ou mais por semana, ou não fecha os postos informados.
- **Amarelo (Atenção):** perde entre um quarto e meia pessoa.
- **Verde (Tranquilo):** perde menos de um quarto de pessoa.

Vermelho quer dizer "aqui falta gente". Verde quer dizer "dá para resolver na escala". Como todo setor perde a mesma proporção, a cor depende do tamanho da equipe, então é normal uma loja grande sair quase toda vermelha.

## Premissas

| Premissa | Valor | Observação |
|---|---|---|
| Encargos e provisões | 70% | A pessoa pode informar outro valor na conversa. Confira com seu contador |
| Semanas por mês | 4,33 | |
| Adicional de hora extra | 50% | |
| Divisor de hora extra | 200 em 40h, 210 em 42h | Jornada semanal × 5. A confirmar com contador |
| Limite de hora extra por dia | 2 horas | A convenção pode trazer outro valor |

## O que a conta não considera

- Adicional noturno, insalubridade, intervalo intrajornada e rescisão.
- Custo de contratar e treinar, e rotatividade.
- Movimento da loja por dia e por hora.
- Horas devolvidas ao time por agentes de IA ou outra automação.
- Regime compensatório por norma coletiva, com média de 2 folgas no mês (§ 2º do art. 7º da Constituição). Quem informa mais de 5 dias recebe um alerta para confirmar com advogado.
- Cláusulas coletivas incompatíveis com a emenda, que perdem efeito em 16/12/2026.
- Empregado com diploma de nível superior e salário de pelo menos 2,5 vezes o teto do RGPS, que fica fora das regras de jornada.
- Medidas transitórias para MEI, microempresa e empresa de pequeno porte, que dependem de lei complementar ainda não publicada.
- Terceirizados da administração pública, que têm regra própria.
- Ganho de escala entre lojas. Em rede, cada loja tem a sua conta, e a rede soma as faixas das lojas: quem cobre duas lojas não entra na conta.
