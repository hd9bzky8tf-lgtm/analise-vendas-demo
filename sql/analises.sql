-- Os valores monetários de entrada e saída permanecem em centavos inteiros.
-- O script Python formata moeda e percentuais apenas na apresentação.

-- consulta: resumo
SELECT
    COUNT(DISTINCT id_pedido) AS pedidos_concluidos,
    SUM(quantidade) AS unidades,
    SUM(valor_bruto_centavos) AS valor_bruto_centavos,
    SUM(desconto_centavos) AS desconto_centavos,
    SUM(receita_centavos) AS receita_centavos,
    SUM(custo_centavos) AS custo_centavos,
    SUM(receita_centavos - custo_centavos) AS margem_bruta_centavos
FROM vendas_concluidas;

-- consulta: mensal
SELECT
    SUBSTR(data_pedido, 1, 7) AS mes,
    COUNT(DISTINCT id_pedido) AS pedidos_concluidos,
    SUM(quantidade) AS unidades,
    SUM(receita_centavos) AS receita_centavos,
    SUM(custo_centavos) AS custo_centavos,
    SUM(receita_centavos - custo_centavos) AS margem_bruta_centavos
FROM vendas_concluidas
GROUP BY mes
ORDER BY mes;

-- consulta: canais
SELECT
    canal,
    COUNT(DISTINCT id_pedido) AS pedidos_concluidos,
    SUM(receita_centavos) AS receita_centavos,
    SUM(custo_centavos) AS custo_centavos
FROM vendas_concluidas
GROUP BY canal
ORDER BY receita_centavos DESC, canal;

-- consulta: categorias
-- Um pedido pode conter mais de uma categoria; não somar pedidos entre categorias.
SELECT
    categoria,
    COUNT(DISTINCT id_pedido) AS pedidos_com_categoria,
    SUM(quantidade) AS unidades,
    SUM(receita_centavos) AS receita_centavos,
    SUM(custo_centavos) AS custo_centavos
FROM vendas_concluidas
GROUP BY categoria
ORDER BY receita_centavos DESC, categoria;

-- consulta: produtos
SELECT
    id_produto,
    produto,
    SUM(quantidade) AS unidades,
    SUM(receita_centavos) AS receita_centavos,
    SUM(custo_centavos) AS custo_centavos
FROM vendas_concluidas
GROUP BY id_produto, produto
ORDER BY receita_centavos DESC, id_produto;

-- consulta: cancelamentos
-- Contagem na tabela de pedidos para não multiplicar pedidos por número de itens.
SELECT status, COUNT(*) AS pedidos
FROM pedidos
GROUP BY status
ORDER BY status;
