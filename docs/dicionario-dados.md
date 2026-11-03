# Dicionário de dados

Todos os registros são fictícios e gerados por código com a semente fixa `42`. Não há nomes, documentos, contatos ou identificadores de clientes. O período da demonstração é janeiro a junho de 2026.

## Convenções

- Datas seguem o formato ISO `AAAA-MM-DD`.
- Quantidades e valores monetários são inteiros.
- Campos monetários terminados em `_centavos` representam centavos de real: `1250` equivale a R$ 12,50.
- O desconto é um valor total do item, e não um valor unitário.
- Identificadores servem somente para relacionar os registros da demonstração.

## `produtos`

Catálogo de 12 produtos fictícios de papelaria, sem referência a marcas.

| Campo | Significado |
| --- | --- |
| `id_produto` | Identificador único do produto e chave primária da tabela |
| `produto` | Descrição do produto fictício |
| `categoria` | Categoria utilizada para agrupar os produtos na análise |

Um produto pode aparecer em vários pedidos por meio da tabela `itens_pedido`. Preço e custo são registrados no item da venda, permitindo que cada registro mantenha os valores utilizados na simulação.

## `pedidos`

Uma linha por pedido. A base contém 760 pedidos distribuídos em seis meses: 90 em janeiro, 110 em fevereiro, 120 em março, 135 em abril, 145 em maio e 160 em junho de 2026.

| Campo | Significado |
| --- | --- |
| `id_pedido` | Identificador único do pedido e chave primária da tabela |
| `data_pedido` | Data de referência do pedido na simulação |
| `canal` | Canal fictício: `loja_online`, `marketplace` ou `loja_fisica` |
| `status` | Situação do pedido: `concluido` ou `cancelado` |

O status se aplica ao pedido inteiro. A demonstração não modela cancelamento parcial, mudança de status ao longo do tempo ou devolução.

## `itens_pedido`

Uma linha por item de pedido. A combinação `id_pedido` e `id_item` identifica o item dentro do modelo.

| Campo | Significado |
| --- | --- |
| `id_pedido` | Pedido ao qual o item pertence; referencia `pedidos.id_pedido` |
| `id_item` | Identificador do item dentro do pedido |
| `id_produto` | Produto vendido; referencia `produtos.id_produto` |
| `quantidade` | Número de unidades do produto no item |
| `preco_unitario_centavos` | Preço por unidade, antes do desconto |
| `custo_unitario_centavos` | Custo por unidade utilizado na simulação |
| `desconto_centavos` | Desconto total aplicado ao item |

## Cálculos derivados

| Medida | Cálculo |
| --- | --- |
| Valor bruto do item | `quantidade × preco_unitario_centavos` |
| Receita do item, líquida de desconto | `quantidade × preco_unitario_centavos − desconto_centavos` |
| Custo do item | `quantidade × custo_unitario_centavos` |
| Resultado bruto simulado do item | Receita do item menos custo do item |

Receita, custo e resultado bruto são somados somente para pedidos com `status = 'concluido'`. Para o ticket médio, primeiro considera-se o total de receita dos itens concluídos e depois divide-se pelo número de **pedidos distintos** concluídos.

A margem bruta simulada é a razão entre o resultado bruto simulado e a receita líquida de descontos. Ela não inclui tributos, fretes, taxas de canal, despesas operacionais ou devoluções.

## Visão `vendas_concluidas`

A visão reúne os dados de pedidos, itens e produtos, com uma linha por item e somente pedidos concluídos. Ela é a base das consultas de receita, custo e resultado bruto. Além dos identificadores e dimensões, expõe `valor_bruto_centavos`, `desconto_centavos`, `receita_centavos` e `custo_centavos`, calculados conforme as regras acima.

O campo `margem_bruta_centavos` nas consultas de resumo e de evolução mensal representa um **valor monetário**: receita menos custo. O percentual de margem é calculado dividindo esse valor pela receita; o sufixo `_centavos` não representa uma taxa.

## Arquivos e fontes

| Arquivo | Conteúdo |
| --- | --- |
| `data/produtos.csv` | Exportação sintética da tabela `produtos` |
| `data/pedidos.csv` | Exportação sintética da tabela `pedidos` |
| `data/itens_pedido.csv` | Exportação sintética da tabela `itens_pedido` |
| `data/demo.sqlite` | Banco local gerado pelos scripts; não versionado |
| `sql/schema.sql` | Definição das tabelas e das restrições de integridade |
| `sql/analises.sql` | Consultas utilizadas no relatório |

A origem de todos os dados é o gerador incluído no próprio repositório. Não há importação de arquivos externos ou conexão com serviços de terceiros.
