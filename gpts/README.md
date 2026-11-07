# GPTs da CD2 Tech na GPT Store

Um GPT por skill, para quem usa o ChatGPT Plus ou o gratuito. A GPT Store não tem API pública de publicação, então este repositório entrega o conteúdo pronto e quem publica cola campo a campo na interface da OpenAI.

| Pasta | GPT |
|---|---|
| [`fim-escala-6x1/`](fim-escala-6x1/) | CD2 Escala 6x1 |
| [`custo-vrva/`](custo-vrva/) | CD2 VR/VA: quanto custa |

> As pastas dos GPTs e os arquivos `LICENSE`, `NOTICE` e `COMMERCIAL.md` daqui são **gerados** por `python3 scripts/sync_plugins.py` a partir de `core/cd2-varejo/` (as instruções vêm de `core/cd2-varejo/gpts/`). Não edite aqui: edite lá e rode o sync. Só este README é escrito à mão.

Em cada pasta:

| Arquivo | Onde vai no editor do GPT |
|---|---|
| `gpt.json` | Name, Description, Conversation starters e Capabilities |
| `instructions.md` | Instructions (até 8.000 caracteres; o sync falha se passar) |
| `knowledge/` | Knowledge: todos os arquivos, de todas as subpastas |
| `knowledge/assets/brand/simbolo.svg` | Base para a foto de perfil (veja o passo 2) |

## Publicar, campo a campo

Use a conta da CD2 Tech, com o perfil de criador verificado no domínio `cd2.com.br`. Repita para cada pasta.

1. Abra https://chatgpt.com/gpts/editor e escolha a aba **Configure**. Não use a aba Create, que reescreve as instruções.
2. **Foto de perfil:** o editor não aceita SVG. Exporte o `knowledge/assets/brand/simbolo.svg` como PNG quadrado (512 x 512 px, com margem em volta do símbolo e fundo `#f2f2f2`) e suba no círculo da foto. Não gere imagem pelo DALL-E.
3. **Name:** o campo `name` do `gpt.json` (`CD2 Escala 6x1` ou `CD2 VR/VA: quanto custa`).
4. **Description:** o campo `description` do `gpt.json`.
5. **Instructions:** abra o `instructions.md`, copie o arquivo inteiro e cole. Confira que o fim do texto colado é o fim do arquivo.
6. **Conversation starters:** as 4 frases de `conversation_starters`, uma por campo, na ordem.
7. **Knowledge:** clique em **Upload files** e suba todos os arquivos de `knowledge/`, inclusive os das subpastas `scripts/`, `references/`, `assets/`, `assets/fonts/` e `assets/brand/` (16 arquivos no CD2 Escala 6x1 e 17 no CD2 VR/VA; o limite do GPT é 20). Detalhes em [Como o ChatGPT guarda os arquivos](#como-o-chatgpt-guarda-os-arquivos).
8. **Capabilities**, conforme `capabilities` do `gpt.json`:
   - **Web Search:** ligado (`web_browsing: true`). É o que permite a pesquisa de novidades da etapa 3.
   - **Code Interpreter & Data Analysis:** ligado (`code_interpreter: true`). Sem ele o GPT não roda o `calc.py` nem o `render.py`.
   - **Image Generation:** desligado (`image_generation: false`).
   - **Canvas:** pode ficar desligado.
9. **Actions:** nenhuma. Os GPTs não conectam a sistema externo; para isso as instruções indicam o Archeo MCP Creator, no Claude ou no Codex.
10. Em **Additional settings**, desmarque o uso das conversas para treinar modelos, se a opção aparecer.
11. Teste no painel **Preview** com um dos conversation starters até a entrega em HTML sair com o rodapé da CD2 Tech e o link de download.
12. Clique em **Create** (ou **Update**). Em **Share**, escolha **Everyone** para aparecer na GPT Store e a categoria **Productivity**. Confirme.
13. Anote o link do GPT publicado para o README e o site.

## Como o ChatGPT guarda os arquivos

O ChatGPT achata o upload: todos os arquivos do Knowledge ficam numa pasta só, `/mnt/data`, sem as subpastas. Por isso:

- os scripts acham os vizinhos tanto no layout com subpastas quanto na pasta plana. O `calc.py` procura `legal-params.json` e `assumptions.json` em `../references/` e, se não achar, ao lado de si; o `render.py` procura `template.html` e a fonte em `../assets/` e ao lado de si; o `brand.py` procura as logos em `../assets/brand/` e ao lado de si;
- as instruções mandam rodar `python3 /mnt/data/calc.py` e `python3 /mnt/data/render.py`, gravando a entrada e as entregas em `/mnt/data`;
- nenhum arquivo do conhecimento repete nome, para nada se perder no achatamento.

O teste `test_gpt_knowledge_runs_flat` em `tests/test_sync.py` copia todos os arquivos de `knowledge/` para uma pasta só e roda o `calc.py` e o `render.py` dali, como no ChatGPT.

Se o editor recusar algum arquivo:

- `Manrope-Variable.woff2`: a página sai com a fonte do sistema (`system-ui`). Funciona, só fica menos fiel à marca;
- uma logo `.svg` do rodapé (`cd2tech-horizontal.svg` ou `cd2tech-horizontal-white.svg`): a página visual não sai. Avise o time da CD2 e não publique;
- os `.png` das logos e o `OFL.txt` não são usados pelos scripts, mas vão juntos: o `OFL.txt` é a licença da fonte.

## Atualizar a cada release

1. Baixe o `cd2-varejo-gpts.zip` da release nova em https://github.com/cd2tec/cd2-skills/releases/latest e descompacte.
2. Para cada GPT, abra o editor em **Configure**:
   - substitua o texto de **Instructions** pelo `instructions.md` novo, inteiro;
   - em **Knowledge**, apague todos os arquivos antigos e suba de novo todos os de `knowledge/`. Arquivo velho esquecido faz o GPT rodar script de outra versão;
   - confira Name, Description e Conversation starters com o `gpt.json`.
3. Teste no **Preview** e clique em **Update**. A visibilidade **Everyone** se mantém.

## Licença

CC BY-NC-ND 4.0, da CD2 Tech. Avaliar é livre. O uso contínuo na empresa é para clientes CD2. Veja `LICENSE`, `NOTICE` e `COMMERCIAL.md`.
