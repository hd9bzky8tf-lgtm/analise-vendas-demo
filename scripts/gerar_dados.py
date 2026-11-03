"""Gera dados sintéticos reproduzíveis, sem acessar serviços ou arquivos externos."""

from __future__ import annotations

import argparse
import calendar
import csv
from contextlib import closing
import io
from pathlib import Path
import random
import sqlite3
import tempfile

ROOT = Path(__file__).resolve().parents[1]
SEED = 42
PEDIDOS_POR_MES = (90, 110, 120, 135, 145, 160)
CANAIS = ("loja_online", "marketplace", "loja_fisica")
# Catálogo inventado para este exercício; preços/custos não são cotações de mercado.
CATALOGO = (
    ("P001", "Caderno A5 liso", "Papelaria", 1890, 890),
    ("P002", "Bloco de notas", "Papelaria", 1290, 590),
    ("P003", "Caneta azul", "Papelaria", 490, 190),
    ("P004", "Lapis grafite", "Papelaria", 290, 90),
    ("P005", "Pasta simples", "Escritorio", 890, 390),
    ("P006", "Grampeador pequeno", "Escritorio", 2590, 1290),
    ("P007", "Caixa de clipes", "Escritorio", 690, 250),
    ("P008", "Tesoura pequena", "Escritorio", 1590, 690),
    ("P009", "Organizador de mesa", "Organizacao", 3990, 1990),
    ("P010", "Caixa organizadora", "Organizacao", 3290, 1690),
    ("P011", "Porta-canetas", "Organizacao", 1490, 690),
    ("P012", "Estojo simples", "Organizacao", 2190, 990),
)
CAMPOS = {
    "produtos": ("id_produto", "produto", "categoria"),
    "pedidos": ("id_pedido", "data_pedido", "canal", "status"),
    "itens_pedido": (
        "id_pedido", "id_item", "id_produto", "quantidade",
        "preco_unitario_centavos", "custo_unitario_centavos", "desconto_centavos",
    ),
}


def gerar_registros() -> dict[str, list[tuple]]:
    rng = random.Random(SEED)
    dados: dict[str, list[tuple]] = {
        "produtos": [p[:3] for p in CATALOGO], "pedidos": [], "itens_pedido": []
    }
    id_pedido = 0
    for mes, quantidade_pedidos in enumerate(PEDIDOS_POR_MES, start=1):
        for _ in range(quantidade_pedidos):
            id_pedido += 1
            dia = rng.randint(1, calendar.monthrange(2026, mes)[1])
            canal = rng.choice(CANAIS)
            # 8% é um parâmetro arbitrário do gerador, não uma taxa observada.
            status = "cancelado" if rng.randrange(100) < 8 else "concluido"
            dados["pedidos"].append((id_pedido, f"2026-{mes:02d}-{dia:02d}", canal, status))
            for id_item, produto in enumerate(rng.sample(CATALOGO, rng.randint(1, 4)), start=1):
                quantidade = rng.randint(1, 4)
                preco = produto[3] * rng.randint(96, 110) // 100
                custo = produto[4] * rng.randint(90, 110) // 100
                desconto_pct = rng.choice((0, 0, 0, 5, 10))
                desconto = quantidade * preco * desconto_pct // 100
                dados["itens_pedido"].append(
                    (id_pedido, id_item, produto[0], quantidade, preco, custo, desconto)
                )
    return dados


def csv_bytes(tabela: str, registros: list[tuple]) -> bytes:
    buffer = io.StringIO(newline="")
    writer = csv.writer(buffer, lineterminator="\n")
    writer.writerow(CAMPOS[tabela])
    writer.writerows(registros)
    return buffer.getvalue().encode("utf-8")


def validar_arquivos(dados: dict[str, list[tuple]]) -> None:
    for tabela, registros in dados.items():
        caminho = ROOT / "data" / f"{tabela}.csv"
        if not caminho.exists() or caminho.read_bytes() != csv_bytes(tabela, registros):
            raise ValueError(f"Arquivo diferente do gerador deterministico: data/{tabela}.csv")
    banco = ROOT / "data" / "demo.sqlite"
    if not banco.exists():
        raise ValueError("Banco ausente: execute o gerador sem --verificar primeiro.")
    with closing(sqlite3.connect(banco)) as conn:
        for tabela, registros in dados.items():
            ordem = "id_pedido, id_item" if tabela == "itens_pedido" else CAMPOS[tabela][0]
            atual = conn.execute(f"SELECT * FROM {tabela} ORDER BY {ordem}").fetchall()
            if atual != registros:
                raise ValueError(f"Tabela diferente do gerador deterministico: {tabela}")
    print("Reproducibilidade OK: CSVs e tabelas correspondem ao gerador com seed 42.")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--verificar", action="store_true", help="Compara dados existentes sem regravar.")
    args = parser.parse_args()
    dados = gerar_registros()
    if args.verificar:
        validar_arquivos(dados)
        return
    pasta = ROOT / "data"
    pasta.mkdir(parents=True, exist_ok=True)
    # O banco é reconstruído em arquivo temporário e substituído ao concluir.
    with tempfile.NamedTemporaryFile(dir=pasta, suffix=".tmp", delete=False) as arquivo:
        temporario = Path(arquivo.name)
    try:
        with closing(sqlite3.connect(temporario)) as conn:
            conn.executescript((ROOT / "sql" / "schema.sql").read_text(encoding="utf-8"))
            for tabela, registros in dados.items():
                marcadores = ",".join("?" for _ in CAMPOS[tabela])
                conn.executemany(f"INSERT INTO {tabela} VALUES ({marcadores})", registros)
            conn.commit()
        temporario.replace(pasta / "demo.sqlite")
    finally:
        if temporario.exists():
            temporario.unlink()
    for tabela, registros in dados.items():
        (pasta / f"{tabela}.csv").write_bytes(csv_bytes(tabela, registros))
    print(f"Dados sinteticos gerados: {len(dados['pedidos'])} pedidos, "
          f"{len(dados['itens_pedido'])} itens e {len(dados['produtos'])} produtos.")
    print("Arquivos: data/*.csv e data/demo.sqlite (banco local ignorado pelo Git).")


if __name__ == "__main__":
    main()
