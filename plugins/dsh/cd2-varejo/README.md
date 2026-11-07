# cd2-varejo para DeepSeek Harness (DSH)

Skills da CD2 Tech para o varejo alimentar brasileiro no [DeepSeek Harness](https://www.deepseek.com/en/harness/): `fim-escala-6x1` (impacto do fim da escala 6x1) e `custo-vrva` (quanto o VR e o VA custam de verdade).

O conteúdo das skills é o mesmo dos pacotes para Claude e Codex. Muda só o empacotamento: o DSH lê cada skill solta, uma pasta por skill, então cada pasta de `skills/` já traz tudo o que usa (scripts, referências, template, logos) e também `LICENSE`, `NOTICE` e `COMMERCIAL.md`. Quem gera isso é o `scripts/sync_plugins.py` (layout `flat-skills` em `harnesses.json`). Não edite as cópias.

> **O DSH está em developer preview** e a DeepSeek avisa que haverá mudanças incompatíveis. Se um caminho ou comando mudar, abra uma issue com a versão do DSH (`dsh --version`).

## Requisitos

- DeepSeek Harness instalado, com uma chave de API da DeepSeek configurada.
- Python 3 no PATH, para o `install.py` e para os scripts das skills.

## Instalar

1. Baixe o [`cd2-varejo-dsh.zip`](https://github.com/cd2tec/cd2-skills/releases/latest/download/cd2-varejo-dsh.zip) e descompacte.
2. Na pasta descompactada, rode:

```
python3 install.py
```

Isso copia as skills para `~/.agents/skills/`, que o DSH lê em qualquer projeto. Outras opções:

| Comando | Destino | Quando usar |
|---|---|---|
| `python3 install.py` | `~/.agents/skills` | Padrão. Vale para todos os projetos |
| `python3 install.py --project` | `./.agents/skills` | Só para o projeto atual |
| `python3 install.py --dsh-home` | `$DSH_HOME/skills` (padrão `~/.dsh/skills`) | Quando só o DSH deve ver as skills |
| `python3 install.py --dest CAMINHO` | o caminho informado | Qualquer outro diretório de skills |
| `python3 install.py --dry-run` | nenhum | Mostra o que faria |

O script só toca nas pastas com os nomes das skills da CD2. Outras skills no mesmo diretório ficam como estão.

Pelo clone do repositório:

```
git clone https://github.com/cd2tec/cd2-skills.git
python3 cd2-skills/plugins/dsh/cd2-varejo/install.py
```

## Verificar

Abra uma sessão nova no DSH e peça algo que uma skill cubra, por exemplo *"quantas pessoas vou precisar contratar com o fim da 6x1?"* ou *"quanto eu pago a mais de taxa no vale?"*. A entrega visual sai como arquivo HTML autocontido na pasta de trabalho.

## Atualizar e remover

- **Atualizar:** baixe o ZIP novo e rode `python3 install.py` de novo, no mesmo destino.
- **Remover:** `python3 install.py --remove`, com a mesma opção de destino usada na instalação.

## O que há neste pacote

| Arquivo | O que é |
|---|---|
| `skills/<nome>/` | As skills, geradas a partir de `core/cd2-varejo/`. Não edite aqui |
| `install.py` | Copia as skills para um diretório lido pelo DSH |
| `plugin.json` | Nome, versão e licença do pacote, conferidos pelo CI. O DSH não lê este arquivo |
| `LICENSE`, `NOTICE` e `COMMERCIAL.md` | Licença CC BY-NC-ND 4.0, atribuição à CD2 Tech e licença comercial para clientes CD2 |

## Licença

CC BY-NC-ND 4.0, da CD2 Tech. Avaliar na sua operação é livre. O uso contínuo na empresa é para clientes CD2, com suporte, manutenção e responsabilidade. Contato: [WhatsApp](https://wa.me/5519982355172) e [cd2.com.br](https://cd2.com.br/?utm_source=deepseek&utm_medium=skill&utm_campaign=cd2-varejo).
