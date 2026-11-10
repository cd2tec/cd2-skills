# Bloco de perfil da operação

O perfil é um bloco de texto que a skill `perfil-da-operacao` gera e a pessoa salva nas instruções do projeto. O plugin não grava nada: sem o bloco nas instruções, a próxima conversa começa inferindo de novo.

Toda rotina procura este bloco antes de perguntar qualquer coisa. O que a pessoa escreveu vale mais do que o que foi inferido.

```text
PERFIL DA OPERAÇÃO
Empresa: <nome>
Papel de quem usa: <dono, gerente, comprador, comercial, financeiro>
Lojas: <código e nome de cada loja>
Departamentos: <nomes como estão no ERP>
Banco: <nome da conexão, se houver mais de uma>
Metas: <arquivo de metas ou "loja, AAAA-MM, meta do mês">
Horários: <abertura das lojas, hora do briefing>
Tom da comunicação: <uma linha, como "direto e próximo, sem gíria">
Voz da loja: <como a loja fala com o cliente: tratamento, tamanho das frases, palavras que usa, palavras que evita e até duas frases reais de exemplo>
Canais de oferta: <encarte, WhatsApp, app, rádio de loja, cartaz>
Cortes dos sinais: <só o que mudar do padrão de sinais-da-operacao>
Semana de resultado: <segunda a domingo, ou o que a loja usa>
```

Campo sem resposta fica com `a confirmar`, e a rotina segue sem ele. Meta de outro mês não vale para o mês atual: a rotina diz que não viu a meta.
