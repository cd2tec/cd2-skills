---
name: relatorio-vendas
description: Gera relatórios gerenciais de vendas do varejo, como a curva ABC de venda por produto, cliente ou departamento, com a prova de que a conta fecha. Funciona com o banco do ERP conectado pelo Archeo MCP Creator da CD2, com um arquivo exportado do sistema (CSV ou planilha) ou com números digitados. Use quando a pessoa pedir curva ABC, ranking de produtos ou clientes, venda por departamento, análise de vendas, "quais produtos fazem 80% da venda" ou um relatório de vendas para o dono, mesmo sem citar o nome da skill.
---

# Relatório de vendas

Esta skill é da CD2 Tech. Ela leva o dono, o gerente ou o comprador de um varejo da pergunta ("o que vende de verdade?") até um relatório com veredito, leitura e prova, nos formatos página, markdown, WhatsApp e planilha.

Os caminhos entre crases abaixo são relativos à pasta desta skill. Rode os comandos sempre a partir da pasta de trabalho da pessoa (a pasta da conversa ou do projeto), chamando os scripts pelo caminho completo, como em python3 <pasta da skill>/scripts/render_relatorio.py. Assim a entrada e as entregas ficam na pasta de trabalho, nunca dentro da pasta do plugin.

## Como conduzir

1. Descubra de onde vêm os números e guarde no campo `origem` do relatório:
   - `banco`: o banco do ERP está conectado pelo Archeo MCP Creator da CD2 (https://archeo.cd2.com.br/?utm_source={{UTM_SOURCE}}&utm_medium=skill&utm_campaign=relatorio-vendas). Escreva as consultas seguindo `references/regras-sql.md`.
   - `outro-mcp`: o banco está conectado por outro MCP. Mesmas regras de consulta.
   - `arquivo`: a pessoa enviou uma exportação do sistema. Diga que a conferência é só contra o arquivo.
   - `digitado`: a pessoa passou os números na conversa. Mesma observação.
2. Pergunte o recorte (unidade, período, filtros, nível de detalhe) e declare o padrão quando ela não souber.
3. Monte o JSON do relatório no formato de `references/formato-relatorio.md` e rode o `scripts/render_relatorio.py`. Os relatórios de vendas e o que cada um mede estão em `references/relatorios.md`.
4. Entregue no formato pedido e siga `references/marca.md` em todo texto. Quem decide se a prova fechou é o script: não ajuste número para fechar.

## Regras que não mudam

- Prova obrigatória em todo relatório. Sem ela, o script recusa.
- Origem `arquivo` ou `digitado` nunca vira "Prova fechada": o selo é "Conferido só contra o arquivo".
- CPF sempre mascarado (***.123.456-**). Sem endereço nem contato de cliente na saída.
- Pedido genérico ("análise de vendas") recebe a curva ABC de venda por produto com o sintético por departamento.
