Regras do relatório perdas, reaproveitadas aqui: valem para conta, recorte e prova. Entrega e fechamento são os desta skill.


# Relatório de perdas

Esta skill é da CD2 Tech. Ela responde às perguntas da prevenção de perdas: quanto você perde, em quê, por quê, onde e o quanto disso é conhecido, do dado até um relatório com veredito, leitura e prova.

Os caminhos entre crases abaixo são relativos à pasta desta skill. Rode os comandos sempre a partir da pasta de trabalho da pessoa (a pasta da conversa ou do projeto), chamando os scripts pelo caminho completo, como em python3 <pasta da skill>/scripts/render_relatorio.py. Assim a entrada e as entregas ficam na pasta de trabalho, nunca dentro da pasta do plugin.

Siga o roteiro de conversa em `references/fluxo-dados.md` e o método em `references/metodo-analise.md`. Mapeamento, colunas, consultas-modelo, provas e o que exportar de cada relatório estão em `references/relatorios-perdas.md`. Movimento e inventário são mapeados em `references/mapeamento-erp.md`, seção 1.

**Esta skill ou o painel?** Painel para acompanhar a operação (cards, linha do tempo, mapa de calor) é `painel-varejo`. Aqui o resultado é um relatório analítico, com linhas e prova, para decidir onde atacar a perda e o que auditar.

## Relatórios

| A pessoa pede | Relatório | Seção |
|---|---|---|
| "quebras", "perdas por setor", "motivos de perda" | Quebra por motivo e departamento | 3.1 |
| "índice de perda", "perda sobre a venda", "shrink" | Perda total: identificada e não identificada | 3.2 |
| "vencidos", "o que vai vencer" | Validade | 3.3 |
| "ajustes de estoque", "quem ajustou" | Ajustes manuais | 3.4 |
| "cancelamentos no caixa", "descontos por operador" | Exceções de frente de caixa | 3.5 |
| "trocas e devoluções suspeitas" | Trocas e devoluções | 3.6 |

Pedido genérico ("como estão as perdas") recebe a **perda total** (3.2) com a quebra por departamento.

## Padrões de recorte

- **Período:** últimos 30 dias até a última data com movimento; para perda não identificada, o intervalo entre os dois últimos inventários do departamento.
- **Valorização:** a custo. Perda a preço de venda mistura margem que nunca existiu; se a pessoa pedir a venda, mostre as duas colunas.
- **Base do percentual:** venda líquida do mesmo período, do mesmo departamento e da mesma loja.

## Definições (declare)

- **Perda identificada (quebra conhecida):** baixa lançada com motivo: vencimento, avaria, furto constatado, degustação, uso interno, quebra operacional de produção.
- **Perda não identificada:** falta apurada no inventário, sem lançamento que a explique. É a divergência **líquida** do balanço (faltas - sobras), a custo.
- **Perda total** = identificada + não identificada.
- **Índice de perda %** = perda a custo / venda líquida. Informe sempre a base: há empresas que usam venda a custo ou venda bruta, e o número muda.

## O que perdas tem de particular

1. **Motivo é texto livre ou código mal usado.** Meça a distribuição dos motivos primeiro. Um motivo genérico ("outros", "ajuste") dominante é o achado principal: a empresa não sabe por que perde.
2. **Quebra pode estar em três lugares:** tipo de movimento de estoque, nota fiscal de baixa (CFOP, Código Fiscal de Operações e Prestações, 5.927) e módulo próprio de perdas. Compare os três antes de escolher; somar dois deles duplica.
3. **Uso e consumo, degustação e transferência para produção** saem do estoque e não são perda no mesmo sentido. Separe na apresentação.
4. **Inventário rotativo x geral.** Perda não identificada só existe onde houve contagem. Departamento sem inventário no período não tem "zero de perda", tem perda desconhecida.
5. **Sobra não é ganho.** Sobra grande ao lado de falta grande aponta erro de processo (troca de código no recebimento ou no caixa).
6. **Operador é pessoa.** Relatórios por operador servem para priorizar auditoria, não para acusar. Mostre taxa com a base (cupons, valor) e o comparativo com a média da loja; nunca apresente como prova de fraude (`references/metodo-analise.md`, seção 6).

## Prova obrigatória por relatório

| Relatório | Prova |
|---|---|
| Quebra por motivo | Soma por motivo = soma por departamento = total de quebras |
| Perda total | Não identificada = divergência líquida dos lotes considerados (lista dos lotes na entrega) |
| Validade | Vencido + faixas a vencer + vence depois de 30 dias = saldo dos lotes na fonte de saldo |
| Ajustes manuais | Ajustes do relatório = movimentos dos tipos de ajuste no período |
| Exceções de caixa | Cancelado + válido = total registrado |
| Trocas e devoluções | Soma das devoluções por operador = total de devoluções do período |

Sem ela, o script recusa. Origem `arquivo` ou `digitado` nunca vira "Prova fechada": o selo é "Conferido só contra o arquivo", mesmo com o total do ERP igual. Quem decide se a prova fechou é o script: não ajuste número para fechar.

## Sem conexão

Siga `references/metodo-analise.md`, seção 2.7. Antes de pedir o arquivo, leia a linha **Para exportar** do relatório: ela diz o que pedir ao ERP, as colunas mínimas e o que fica de fora sem cada coluna opcional. Diga isso à pessoa em uma frase, sem listar a tabela inteira. Coluna que falta não se inventa: diga qual é e o que deixa de sair.

