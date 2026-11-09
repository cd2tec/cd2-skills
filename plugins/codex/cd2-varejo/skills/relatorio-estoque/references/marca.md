# Marca CD2 Tech nas entregas

Instruções para você, modelo. Use este resumo do design system da CD2 Tech em toda entrega visual. O dono da marca é a CD2 Tech.

## Voz

- Português do Brasil, frases curtas e afirmativas. Prefira o dado ao adjetivo.
- "Você" para quem lê e "nós" para a CD2.
- Títulos em caixa normal (só a primeira letra maiúscula).
- Sem emoji e sem travessão.

## Cores

| Nome | Valor | Uso |
| --- | --- | --- |
| blue-retail | #0000ff | Cor da marca, botões, destaques. Texto sobre ela em white-human. |
| blue-tech | #3c1fff | Segundo azul, hover do botão. |
| white-human | #f2f2f2 | Fundo claro padrão. Não use branco puro como fundo de página. |
| black-agile | #000000 | Fundo escuro e texto no claro. |
| purple-shift | #210e9e | Segunda cor do logo. |
| yellow-like | #dbff2a | Grifo e foco, só sobre fundo escuro ou azul. |
| blue-sky | #019eff | Links no tema escuro. |
| frente-neutro-escuro | #464a53 | Texto secundário no tema claro. |
| gray-solution | #a1a6ae | Texto secundário no tema escuro. |
| gray-tech | #6a717f | Bordas e divisores. |

Regras de contraste:

- Nunca use `blue-sky`, `gray-solution` ou `yellow-like` como texto sobre fundo claro.
- Para texto secundário, use `frente-neutro-escuro` no claro e `gray-solution` no escuro.

## Tipografia e forma

- Fonte Manrope, com fallback `system-ui`. Títulos em peso 700 a 800, corpo em 400, no mínimo 16px.
- Raios: 6px (campos), 12px (cards), 24px (blocos grandes) e 999px (botões e chips).
- Marca plana. Sem sombra em card. Separe superfícies por cor e por borda.
- Layout em coluna de até 1200px, com margem lateral de 16px no celular.
- Dois temas: claro e escuro (`prefers-color-scheme`).
- Ícones em linha fina, sem preenchimento.

## Logo

- Fundo claro: `cd2tech-horizontal.svg`. Fundo escuro ou azul: `cd2tech-horizontal-white.svg`.
- Abaixo de 24px de altura, use o símbolo (`simbolo.svg`).
- Nunca gire, distorça, troque as cores ou aplique a versão colorida sobre imagem.

## Rodapé de assinatura (toda entrega)

Toda entrega termina com o rodapé de assinatura:

- **HTML:** o logo da CD2 Tech ao lado do aviso de isenção. O script `scripts/brand.py` gera isso com `footer_html`.
- **CSV, WhatsApp e Markdown:** o texto literal `CD2 Tech` no lugar do logo, seguido do aviso. Use `footer_text`.

Aviso de isenção (preencha `{regra}` e `{data}` conforme a skill):

> Estas contas e informações são apenas gerenciais, uma referência. Elas usam os números informados e a nossa leitura da regra em {data} ({regra}), que pode mudar. A CD2 Tech não tem nenhuma responsabilidade sobre estes resultados nem sobre decisões tomadas com base neles. Confira com seu contador e seu advogado antes de agir.

## Links

- Todo link para cd2.com.br, archeo.cd2.com.br e para os sites das calculadoras leva UTM: `utm_source=codex&utm_medium=skill&utm_campaign=<skill>`. Use `link()` do `brand.py`.
- Archeo MCP Creator: https://archeo.cd2.com.br/?utm_source=codex&utm_medium=skill&utm_campaign=cd2-varejo
- Contato comercial: WhatsApp via `whatsapp_link()`, e https://cd2.com.br
- A mensagem do WhatsApp é sempre a padrão. Nunca ponha número digitado pela pessoa em URL.
