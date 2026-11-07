# Plugin cd2-varejo para Claude Code e Claude Cowork

Skills da CD2 Tech para o varejo alimentar brasileiro. Cada skill faz a mesma conta da calculadora gratuita da CD2, com os números da sua loja, e entrega o resultado com a marca CD2 Tech.

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

Exemplos de pedido: *"quantas pessoas vou precisar contratar com o fim da 6x1?"* ou *"quanto eu pago a mais de taxa no vale?"*. A entrega visual sai como artefato quando o Claude oferece esse recurso e, se não, como arquivo HTML.

Cada skill é autocontida: traz os scripts (`calc.py`, `render.py` e `brand.py`), as referências, o template e as logos. Os scripts usam só Python 3.

## Licença

CC BY-NC-ND 4.0, da CD2 Tech. Avaliar na sua operação é livre. O uso contínuo na empresa é para clientes CD2, com suporte, manutenção e responsabilidade. Veja `LICENSE`, `NOTICE` e `COMMERCIAL.md`. Contato: [WhatsApp](https://wa.me/5519982355172) e [cd2.com.br](https://cd2.com.br/?utm_source=claude&utm_medium=skill&utm_campaign=cd2-varejo).
