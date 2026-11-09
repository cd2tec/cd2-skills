# Plugin cd2-varejo para Codex e ChatGPT Work

Skills da CD2 Tech para o varejo alimentar brasileiro. Cada skill faz a mesma conta da calculadora gratuita da CD2, com os números da sua loja, e entrega o resultado com a marca CD2 Tech.

> A pasta `skills/` e os arquivos `LICENSE`, `NOTICE` e `COMMERCIAL.md` deste pacote são **cópias geradas** de [`core/cd2-varejo`](../../../core/cd2-varejo). Edite lá e rode `python3 scripts/sync_plugins.py` na raiz do repositório.

## Instalar

No Codex:

```
codex plugin marketplace add cd2tec/cd2-skills
codex plugin add cd2-varejo@cd2-skills
```

No app do Codex, depois de adicionar o marketplace, você também pode instalar o `cd2-varejo` pelo diretório de plugins, no marketplace `cd2-skills`. Para atualizar: `codex plugin marketplace upgrade cd2-skills`.

No ChatGPT Work (planos de empresa), quem administra o workspace importa o repositório `cd2tec/cd2-skills`, que usa este mesmo pacote.

## Skills

| Skill | O que faz |
|---|---|
| [`fim-escala-6x1`](skills/fim-escala-6x1/SKILL.md) | Impacto do fim da escala 6x1 (EC 141/2026): pessoas a contratar, custo por mês e por ano, setores no semáforo e o que fazer primeiro, com e sem acordo coletivo |
| [`custo-vrva`](skills/custo-vrva/SKILL.md) | Quanto o VR e o VA custam de verdade frente ao Decreto 12.712/2025: taxa acima do teto, dinheiro parado, bandeiras no semáforo e o que fazer primeiro |

A entrega visual sai como arquivo HTML autocontido, salvo na pasta de trabalho. Cada skill traz os scripts (`calc.py`, `render.py` e `brand.py`), as referências, o template e as logos. Os scripts usam só Python 3.

## Licença

CC BY-NC-ND 4.0, da CD2 Tech. Testar na sua operação é livre. Para usar no dia a dia da empresa, com suporte e responsabilidade, fale com a CD2. Veja `LICENSE`, `NOTICE` e `COMMERCIAL.md`. Contato: [WhatsApp](https://wa.me/5519982355172) e [cd2.com.br](https://cd2.com.br/?utm_source=codex&utm_medium=skill&utm_campaign=cd2-varejo).
