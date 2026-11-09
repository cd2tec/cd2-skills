# Plugin cd2-varejo para Claude Code e Claude Cowork

Skills da CD2 Tech para o varejo alimentar brasileiro: duas calculadoras, oito relatórios gerenciais, um painel de varejo e a ficha de ferramenta do Archeo MCP Creator da CD2. Cada uma faz a conta com um script, nunca de cabeça, e entrega o resultado com a marca CD2 Tech.

> A pasta `skills/` e os arquivos `LICENSE`, `NOTICE` e `COMMERCIAL.md` deste pacote são **cópias geradas** de [`core/cd2-varejo`](../../../core/cd2-varejo). Edite lá e rode `python3 scripts/sync_plugins.py` na raiz do repositório.

## Instalar

No Claude Code:

```
/plugin marketplace add cd2tec/cd2-skills
/plugin install cd2-varejo@cd2-skills
```

No Claude Cowork, baixe o [`cd2-varejo-claude.zip`](https://github.com/cd2tec/cd2-skills/releases/latest/download/cd2-varejo-claude.zip) e suba em Customize > Plugins (ou, para a organização, em Organization settings > Plugins & skills).

## Skills

| Skill | O que faz |
|---|---|
| [`fim-escala-6x1`](skills/fim-escala-6x1/SKILL.md) | Impacto do fim da escala 6x1 (EC 141/2026): pessoas a contratar, custo por mês e por ano, setores no semáforo e o que fazer primeiro, com e sem acordo coletivo |
| [`custo-vrva`](skills/custo-vrva/SKILL.md) | Quanto o VR e o VA custam de verdade frente ao Decreto 12.712/2025: taxa acima do teto, dinheiro parado, bandeiras no semáforo e o que fazer primeiro |
| [`relatorio-vendas`](skills/relatorio-vendas/SKILL.md) | Relatório gerencial de vendas, como a curva ABC, a carteira de clientes e as devoluções |
| [`relatorio-estoque`](skills/relatorio-estoque/SKILL.md) | Relatório gerencial de estoque, como posição, Kardex e cobertura |
| [`relatorio-compras`](skills/relatorio-compras/SKILL.md) | Relatório gerencial de compras, como a curva ABC de abastecimento e os pedidos pendentes |
| [`relatorio-precos`](skills/relatorio-precos/SKILL.md) | Relatório gerencial de preço, margem e promoção |
| [`relatorio-perdas`](skills/relatorio-perdas/SKILL.md) | Relatório gerencial de perdas, como a quebra por motivo e o índice de perda |
| [`relatorio-financeiro`](skills/relatorio-financeiro/SKILL.md) | Relatório gerencial financeiro, como o aging de contas a pagar e a receber e o fluxo de caixa |
| [`relatorio-fiscal`](skills/relatorio-fiscal/SKILL.md) | Conferência de documentos fiscais por CFOP, cabeçalho contra itens e numeração, como relatório gerencial e não documento oficial |
| [`relatorio-contabil`](skills/relatorio-contabil/SKILL.md) | Conferência de balancete, razão e lançamentos, como relatório gerencial e não escrituração oficial |
| [`painel-varejo`](skills/painel-varejo/SKILL.md) | Painel visual da operação do varejo, com totalizadores, linha do tempo, mapa de calor e leitura. Sem conexão, entrega a foto do período |
| [`ficha-archeo-mcp`](skills/ficha-archeo-mcp/SKILL.md) | Ficha de uma ferramenta para cadastrar no Archeo MCP Creator da CD2, com o SQL e os parâmetros. Sem conexão, entrega um rascunho marcado como não validado |

Exemplos de pedido: *"quantas pessoas vou precisar contratar com o fim da 6x1?"*, *"quanto eu pago a mais de taxa no vale?"*, *"faz a curva ABC de venda desse arquivo"* ou *"monta um painel da operação"*. A entrega visual sai como artefato quando o Claude oferece esse recurso e, se não, como arquivo HTML.

Os relatórios e o painel funcionam de duas formas. **Com conexão**, a skill lê o banco do ERP pelo Archeo MCP Creator da CD2 (ou por outro MCP de dados) e fecha a prova no próprio banco. **Sem conexão**, ela segue com um arquivo exportado do sistema (CSV ou Excel), dado colado ou digitado, e o selo da conferência é "Conferido só contra o arquivo", nunca "Prova fechada". Cada relatório traz a linha "Para exportar", que diz o que pedir ao ERP.

Cada skill é autocontida: traz os scripts, as referências, o template e as logos. Os scripts usam só Python 3 (o `preview_dashboard.py` do painel usa Playwright, que é opcional).

## Licença

CC BY-NC-ND 4.0, da CD2 Tech. Testar na sua operação é livre. Para usar no dia a dia da empresa, com suporte e responsabilidade, fale com a CD2. Veja `LICENSE`, `NOTICE` e `COMMERCIAL.md`. Contato: [WhatsApp](https://wa.me/5519982355172) e [cd2.com.br](https://cd2.com.br/?utm_source=claude&utm_medium=skill&utm_campaign=cd2-varejo).
