# Mapeamento de ERP e custo por entrada

O que mais de uma skill de relatório precisa e, por isso, fica neste arquivo comum: onde achar estoque e venda no banco e como comparar custo entre entradas. Venda por cupom, itens, produto, departamento, loja, pagamento e custo estão em `references/indicadores-varejo.md`, seção 1.

Conteúdo:
1. Estoque
2. Venda
3. Variação de custo de compra

Sem conexão, as mesmas linhas servem para achar a coluna certa no perfil do arquivo: a coluna "O que confirmar" vira o que você pergunta à pessoa ou mede no perfil.

## 1. Estoque

| Domínio | Para quê | Termos de busca | O que confirmar |
|---|---|---|---|
| Saldo | Estoque geral, ruptura, cobertura | `estoque`, `saldo`, `sld`, `qtd_estoque`, `posicao`, `stock` | Chave (produto + loja + depósito?), unidade, data de atualização, se há saldo reservado, em trânsito ou bloqueado |
| Movimento | Kardex, giro, posição retroativa | `movimento`, `mov_est`, `kardex`, `historico_estoque`, `lancamento` | Data, tipo de operação, quantidade, custo no movimento, documento e parceiro de origem |
| Tipo de operação | Sinal e nome do movimento | `tipo_mov`, `operacao`, `cod_oper`, `natureza`, `historico` | Quais entram, quais saem, quais são estorno |
| Inventário (lote) | Análise de balanço | `inventario`, `balanco`, `contagem`, `lote`, `congelado` | Cabeçalho (data, loja, situação) e itens (quantidade congelada, contada, custo) |
| Produto | Descrição, departamento, situação | `produto`, `mercadoria`, `item`, `sku` | Se o cadastro é por loja; flag de ativo, de fora de linha e de controla estoque |
| Mercadológico | Quebras do relatório | `departamento`, `secao`, `grupo`, `subgrupo`, `categoria`, `familia` | Níveis da árvore e chave |
| Fornecedor do produto | Filtro por fornecedor | `fornecedor`, `prod_fornec`, `fabricante` | Fornecedor principal, quando o produto tem vários |
| Custo e preço | Valorização | `custo`, `custo_medio`, `custo_reposicao`, `preco_venda` | Qual custo é (médio, última entrada), se é por loja, cobertura |
| Venda por item | Cobertura, ruptura, parado | Os termos de itens vendidos em `references/indicadores-varejo.md`, seção 1 | Mesma unidade do saldo |

## 2. Venda

Além do mapeamento de `references/indicadores-varejo.md`, seção 1:

| Domínio | Para quê | Termos de busca | O que confirmar |
|---|---|---|---|
| Pedido e faturamento | Venda em atacado e distribuição | `pedido`, `pedido_venda`, `nota_saida`, `nf_saida`, `faturamento`, `romaneio` | Situação do pedido, data de emissão x faturamento x entrega, tipo de operação (venda, bonificação, remessa) |
| Cliente | Ranking, carteira | `cliente`, `pessoa`, `parceiro`, `consumidor` | Chave, tipo (PF ou PJ), situação, data de cadastro |
| Segmento e canal | Quebras | `segmento`, `ramo`, `atividade`, `canal`, `tipo_cliente`, `rede`, `grupo_cliente` | Onde fica (cliente, pedido, tabela de preço) e % preenchido |
| Vendedor | Quebra comercial | `vendedor`, `representante`, `rca`, `supervisor`, `equipe` | Hierarquia e se o vendedor vem do pedido ou da carteira |
| Devolução | Venda líquida, motivos | `devolucao`, `troca`, `motivo_dev`, `nf_entrada` com operação de devolução | Vínculo com a venda original, motivo |
| Composição | Produto final x componentes | `composicao`, `receita`, `ficha_tecnica`, `kit`, `estrutura`, `componente`, `rendimento`, `producao` | Quantidade do componente por unidade do pai, perda prevista, se a venda baixa o pai ou os componentes |

## 3. Variação de custo de compra

**Colunas:** produto, fornecedor, custo da penúltima entrada, custo da última entrada, variação %, data, quantidade comprada, impacto estimado (variação x quantidade vendida mensal), preço de venda atual, margem antes e depois.

Compare entradas de **compra** (sem bonificação, devolução ou transferência) do mesmo fornecedor e da mesma embalagem. Para pegar as duas últimas entradas por produto, use `ROW_NUMBER() OVER (PARTITION BY produto ORDER BY data DESC, chave DESC)` em tabela derivada e filtre `rn <= 2`.

**Leituras típicas:** aumento ainda não repassado ao preço (margem comprimida, cruze com o relatório de preços), variação grande por mudança de embalagem ou de composição de imposto (falso aumento), queda de custo não aproveitada.

**Para exportar:** peça o relatório de notas de entrada por item, de um período longo o bastante para cada produto ter pelo menos duas entradas. Colunas mínimas: produto, fornecedor, data de entrada, custo unitário, quantidade.

- Sem tipo de operação: não dá para separar compra de bonificação, devolução e transferência, e o custo zerado de uma bonificação parece queda. Peça a exportação só com notas de compra e registre isso nas premissas.
- Sem embalagem: a troca de caixa com 12 por caixa com 24 parece variação de custo. Avise que pode haver falso aumento.
- Sem venda mensal por produto: sai a variação, mas não o impacto estimado.
- Sem preço de venda atual: sai a variação, mas não a margem antes e depois.
