# Changelog

As notas de cada versão entram na release do GitHub. Use um título `## <versão>` por versão, da mais recente para a mais antiga.

## 0.2.1

Correção de instalação. A descrição do plugin passou de 500 caracteres, e o envio do ZIP no Claude recusava o pacote. A descrição ficou mais curta, e o `--check` agora confere esse limite. As skills não mudaram.

## 0.2.0

Dez skills novas, todas com nome em português, e teste livre e sem prazo.

- **Oito relatórios gerenciais**: `relatorio-vendas`, `relatorio-estoque`, `relatorio-compras`, `relatorio-precos`, `relatorio-perdas`, `relatorio-financeiro`, `relatorio-fiscal` e `relatorio-contabil`. Relatório com linhas, classes e a prova da conta: a soma das partes tem de bater com o total, e, se não bater, a página abre em vermelho. O fiscal e o contábil são conferência, não documento oficial.
- **`painel-varejo`**: painel visual da operação, com totalizadores, linha do tempo, mapa de calor e leitura. Sem conexão, entrega a foto do período.
- **`ficha-archeo-mcp`**: ficha de ferramenta para cadastrar no Archeo MCP Creator da CD2, com o SQL e os parâmetros. Sem conexão, entrega um rascunho marcado como não validado.
- **Funcionam sem conexão.** Com o banco do ERP conectado (pelo Archeo MCP Creator da CD2 ou por outro MCP de dados), a prova fecha no banco. Sem conexão, a skill segue com um arquivo exportado (CSV ou Excel), dado colado ou digitado, e o selo é "Conferido só contra o arquivo", nunca "Prova fechada". Cada relatório traz a linha "Para exportar", com o que pedir ao ERP.
- **Teste livre e sem prazo.** Sai a regra dos 90 dias, nas calculadoras também: testar na sua operação é livre, sem suporte, garantia nem responsabilidade da CD2, e o uso contínuo no dia a dia segue sendo para clientes CD2 com contrato ativo (`COMMERCIAL.md`).
- A conta das duas calculadoras não mudou. A saída delas mudou só na frase da licença.
- README, site e pacotes mostram as doze skills. Os GPTs seguem só para as duas calculadoras.
- Para quem já instalou o plugin `cd2-varejo`: as skills novas entram com nomes novos, em português, e as duas calculadoras mantêm os nomes `fim-escala-6x1` e `custo-vrva`. Se você usava as análises de ERP de outro pacote, peça pelos nomes novos.

## 0.1.0

Publicada em 2026-11-07. Primeira versão do plugin `cd2-varejo`, da CD2 Tech.

- **`fim-escala-6x1`**: o impacto do fim da escala 6x1 (Emenda Constitucional 141/2026) na loja ou na rede. Pessoas a contratar, custo por mês e por ano, setores no semáforo e o que fazer primeiro, sem e com acordo coletivo. Parâmetros conferidos em 02/11/2026.
- **`custo-vrva`**: quanto o VR e o VA custam de verdade frente ao Decreto 12.712/2025. Taxa acima do teto de 3,6%, dinheiro parado além dos 15 dias, bandeiras no semáforo e o que fazer primeiro. Parâmetros conferidos em 06/11/2026.
- Mesma conta das calculadoras gratuitas da CD2, em Python só com biblioteca padrão, com os valores de conferência das metodologias como testes.
- Conversa guiada em sete passos, entregas no design system da CD2 Tech (página visual, planilha, WhatsApp ou texto) e assinatura com logo e aviso de isenção.
- Pacotes para Claude Code e Claude Cowork, Codex e ChatGPT Work, DeepSeek Harness (developer preview) e dois GPTs para a GPT Store: CD2 Escala 6x1 e CD2 VR/VA: quanto custa.
- Licença CC BY-NC-ND 4.0, com avaliação gratuita na empresa por até 90 dias e uso contínuo para clientes CD2 (`COMMERCIAL.md`).
- README e site no GitHub Pages.
