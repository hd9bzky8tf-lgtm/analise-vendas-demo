PRAGMA foreign_keys = ON;

CREATE TABLE produtos (
    id_produto TEXT PRIMARY KEY,
    produto TEXT NOT NULL,
    categoria TEXT NOT NULL
);

CREATE TABLE pedidos (
    id_pedido INTEGER PRIMARY KEY,
    data_pedido TEXT NOT NULL,
    canal TEXT NOT NULL CHECK (canal IN ('loja_online', 'marketplace', 'loja_fisica')),
    status TEXT NOT NULL CHECK (status IN ('concluido', 'cancelado'))
);

CREATE TABLE itens_pedido (
    id_pedido INTEGER NOT NULL REFERENCES pedidos(id_pedido),
    id_item INTEGER NOT NULL CHECK (id_item > 0),
    id_produto TEXT NOT NULL REFERENCES produtos(id_produto),
    quantidade INTEGER NOT NULL CHECK (quantidade > 0),
    preco_unitario_centavos INTEGER NOT NULL CHECK (preco_unitario_centavos > 0),
    custo_unitario_centavos INTEGER NOT NULL CHECK (custo_unitario_centavos >= 0),
    desconto_centavos INTEGER NOT NULL CHECK (
        desconto_centavos >= 0
        AND desconto_centavos <= quantidade * preco_unitario_centavos
    ),
    PRIMARY KEY (id_pedido, id_item)
);

-- Uma linha por item; o status é filtrado antes de calcular os indicadores.
CREATE VIEW vendas_concluidas AS
SELECT
    p.id_pedido,
    p.data_pedido,
    p.canal,
    i.id_item,
    i.id_produto,
    pr.produto,
    pr.categoria,
    i.quantidade,
    i.quantidade * i.preco_unitario_centavos AS valor_bruto_centavos,
    i.desconto_centavos,
    i.quantidade * i.preco_unitario_centavos - i.desconto_centavos AS receita_centavos,
    i.quantidade * i.custo_unitario_centavos AS custo_centavos
FROM pedidos p
JOIN itens_pedido i ON i.id_pedido = p.id_pedido
JOIN produtos pr ON pr.id_produto = i.id_produto
WHERE p.status = 'concluido';
