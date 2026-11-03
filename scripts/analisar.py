"""Executa consultas SQL, concilia os totais com os CSVs e gera o relatório."""

from __future__ import annotations

import csv
from collections import Counter, defaultdict
from contextlib import closing
from decimal import Decimal, ROUND_HALF_UP
from html import escape
from pathlib import Path
import re
import sqlite3

ROOT = Path(__file__).resolve().parents[1]


def moeda(centavos: int | Decimal) -> str:
    valor = (Decimal(centavos) / 100).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    return "R$ " + f"{valor:,.2f}".replace(",", "_").replace(".", ",").replace("_", ".")


def percentual(numerador: int, denominador: int) -> str:
    if denominador == 0:
        return "n.a."
    valor = (Decimal(numerador) * 100 / Decimal(denominador)).quantize(
        Decimal("0.1"), rounding=ROUND_HALF_UP
    )
    return f"{valor:.1f}%".replace(".", ",")


def tabela(cabecalhos: list[str], linhas: list[list[str]]) -> str:
    return "\n".join([
        "| " + " | ".join(cabecalhos) + " |",
        "| " + " | ".join("---" for _ in cabecalhos) + " |",
        *("| " + " | ".join(linha) + " |" for linha in linhas),
    ])


def consultar(conn: sqlite3.Connection) -> dict[str, list[dict]]:
    texto = (ROOT / "sql" / "analises.sql").read_text(encoding="utf-8")
    blocos = re.split(r"^-- consulta: (\w+)\s*$", texto, flags=re.MULTILINE)
    consultas = {}
    for posicao in range(1, len(blocos), 2):
        nome, sql = blocos[posicao:posicao + 2]
        consultas[nome] = [dict(row) for row in conn.execute(sql)]
    if set(consultas) != {"resumo", "mensal", "canais", "categorias", "produtos", "cancelamentos"}:
        raise ValueError("O arquivo SQL deve conter as seis consultas documentadas.")
    return consultas


def validar_e_conciliar(conn: sqlite3.Connection, consultas: dict[str, list[dict]]) -> dict:
    if conn.execute("PRAGMA integrity_check").fetchone()[0] != "ok":
        raise ValueError("Falha de integridade SQLite.")
    if conn.execute("PRAGMA foreign_key_check").fetchall():
        raise ValueError("Relacionamentos inválidos no banco.")
    dados = {}
    for nome in ("produtos", "pedidos", "itens_pedido"):
        with (ROOT / "data" / f"{nome}.csv").open(encoding="utf-8", newline="") as arquivo:
            leitor = csv.DictReader(arquivo)
            colunas = leitor.fieldnames
            dados[nome] = list(leitor)
        ordem = "id_pedido, id_item" if nome == "itens_pedido" else colunas[0]
        no_banco = [tuple(str(valor) for valor in row) for row in conn.execute(
            f"SELECT * FROM {nome} ORDER BY {ordem}"
        )]
        no_csv = [tuple(row[coluna] for coluna in colunas) for row in dados[nome]]
        if no_banco != no_csv:
            raise ValueError(f"CSV e banco diferem na tabela {nome}; regenere os dados.")
    pedidos = {int(row["id_pedido"]): row for row in dados["pedidos"]}
    produtos = {row["id_produto"]: row for row in dados["produtos"]}
    pedidos_com_itens = {int(row["id_pedido"]) for row in dados["itens_pedido"]}
    if pedidos_com_itens != set(pedidos):
        raise ValueError("Existe pedido sem itens ou item sem pedido.")
    status = Counter(p["status"] for p in pedidos.values())
    if dict(status) != {r["status"]: r["pedidos"] for r in consultas["cancelamentos"]}:
        raise ValueError("Contagem de status não conciliada.")
    # Cálculo independente a partir dos CSVs: nenhuma consulta SQL é reutilizada aqui.
    total = Counter()
    concluidos = set()
    grupos = {nome: defaultdict(Counter) for nome in ("mensal", "canais", "categorias", "produtos")}
    ids_grupos = {nome: defaultdict(set) for nome in grupos}
    for item in dados["itens_pedido"]:
        id_pedido = int(item["id_pedido"])
        pedido = pedidos[id_pedido]
        if pedido["status"] != "concluido":
            continue
        concluidos.add(id_pedido)
        quantidade = int(item["quantidade"])
        bruto = quantidade * int(item["preco_unitario_centavos"])
        desconto = int(item["desconto_centavos"])
        receita = bruto - desconto
        custo = quantidade * int(item["custo_unitario_centavos"])
        metricas = {
            "unidades": quantidade, "valor_bruto_centavos": bruto,
            "desconto_centavos": desconto, "receita_centavos": receita,
            "custo_centavos": custo, "margem_bruta_centavos": receita - custo,
        }
        total.update(metricas)
        chaves = {
            "mensal": pedido["data_pedido"][:7], "canais": pedido["canal"],
            "categorias": produtos[item["id_produto"]]["categoria"],
            "produtos": item["id_produto"],
        }
        for nome, chave in chaves.items():
            grupos[nome][chave].update(metricas)
            ids_grupos[nome][chave].add(id_pedido)
    total["pedidos_concluidos"] = len(concluidos)
    if dict(total) != consultas["resumo"][0]:
        raise ValueError("Resumo SQL não conciliado com o cálculo independente em Python.")
    for nome, campo in (("mensal", "mes"), ("canais", "canal"),
                        ("categorias", "categoria"), ("produtos", "id_produto")):
        if {r[campo] for r in consultas[nome]} != set(grupos[nome]):
            raise ValueError(f"Grupos divergentes: {nome}.")
        for linha in consultas[nome]:
            chave = linha[campo]
            for metrica in ("unidades", "receita_centavos", "custo_centavos", "margem_bruta_centavos"):
                if metrica in linha and linha[metrica] != grupos[nome][chave][metrica]:
                    raise ValueError(f"Total divergente: {nome}/{chave}/{metrica}.")
            for metrica in ("pedidos_concluidos", "pedidos_com_categoria"):
                if metrica in linha and linha[metrica] != len(ids_grupos[nome][chave]):
                    raise ValueError(f"Pedidos distintos divergentes: {nome}/{chave}.")
    return {"pedidos": len(pedidos), "itens": len(dados["itens_pedido"]),
            "produtos": len(produtos), "cancelados": status["cancelado"]}


def gerar_grafico(mensal: list[dict]) -> None:
    largura, altura = 880, 410
    maior = max(row["receita_centavos"] for row in mensal)
    elementos = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{largura}" height="{altura}" '
        f'viewBox="0 0 {largura} {altura}" role="img" aria-labelledby="titulo descricao">',
        '<title id="titulo">Receita mensal simulada — janeiro a junho de 2026</title>',
        '<desc id="descricao">Gráfico de barras com dados inteiramente fictícios. '
        'Valores de cada mês estão escritos acima das barras.</desc>',
        '<rect width="880" height="410" fill="#f6f8fa"/>',
        '<g font-family="Arial, sans-serif" fill="#172b3a">',
        '<text x="32" y="42" font-size="24" font-weight="700">Receita mensal simulada</text>',
        '<text x="32" y="69" font-size="14">Dados fictícios · pedidos concluídos · jan–jun/2026</text>',
        '<line x1="42" y1="330" x2="842" y2="330" stroke="#9aaaba"/>',
    ]
    for posicao, linha in enumerate(mensal):
        x = 65 + posicao * 130
        altura_barra = round(linha["receita_centavos"] / maior * 185)
        y = 330 - altura_barra
        elementos.extend([
            f'<rect x="{x}" y="{y}" width="90" height="{altura_barra}" rx="5" fill="#176b87"/>',
            f'<text x="{x + 45}" y="{y - 12}" text-anchor="middle" font-size="13">'
            f'{escape(moeda(linha["receita_centavos"]))}</text>',
            f'<text x="{x + 45}" y="354" text-anchor="middle" font-size="14">'
            f'{linha["mes"]}</text>',
        ])
    elementos.extend([
        '<text x="32" y="390" font-size="12">O volume mensal foi definido no gerador; '
        'este exercício não demonstra sazonalidade real.</text>',
        '</g></svg>',
    ])
    (ROOT / "docs" / "receita-mensal.svg").write_text("\n".join(elementos) + "\n", encoding="utf-8")


def gerar_relatorio(consultas: dict[str, list[dict]], qualidade: dict) -> None:
    resumo = consultas["resumo"][0]
    receita = resumo["receita_centavos"]
    pedidos = resumo["pedidos_concluidos"]
    mensal = consultas["mensal"]
    melhor_mes = max(mensal, key=lambda r: r["receita_centavos"])
    canal = consultas["canais"][0]
    produto = consultas["produtos"][0]
    partes = [
        "# Resultados da análise demonstrativa",
        "> Dados inteiramente fictícios, gerados com seed 42. Não representam uma empresa, "
        "clientes ou resultados profissionais reais.",
        "Este relatório é gerado por `python scripts/analisar.py`, após a execução das "
        "consultas em `sql/analises.sql` e a conciliação independente em Python.",
        "## Escopo e qualidade",
        f"Período: janeiro a junho de 2026. Base com **{qualidade['pedidos']} pedidos**, "
        f"**{qualidade['itens']} itens de pedido** e **{qualidade['produtos']} produtos**. "
        f"Há **{qualidade['cancelados']} pedidos cancelados** "
        f"({percentual(qualidade['cancelados'], qualidade['pedidos'])} dos pedidos), "
        "excluídos da receita e do custo.",
        "Verificações concluídas: integridade SQLite, chaves estrangeiras, pedidos com itens, "
        "igualdade dos CSVs com o banco e conciliação dos totais e agrupamentos SQL/Python.",
        "## Indicadores",
        tabela(["Indicador", "Resultado"], [
            ["Pedidos concluídos", str(pedidos)],
            ["Unidades em pedidos concluídos", str(resumo["unidades"])],
            ["Valor bruto antes de descontos", moeda(resumo["valor_bruto_centavos"])],
            ["Descontos", moeda(resumo["desconto_centavos"])],
            ["Receita após descontos", moeda(receita)],
            ["Custo simulado dos produtos", moeda(resumo["custo_centavos"])],
            ["Margem bruta simulada — valor", moeda(resumo["margem_bruta_centavos"])],
            ["Margem bruta simulada — percentual", percentual(resumo["margem_bruta_centavos"], receita)],
            ["Ticket médio por pedido concluído", moeda(Decimal(receita) / pedidos)],
        ]),
        "## Evolução mensal",
        "![Receita mensal com dados fictícios](receita-mensal.svg)",
        tabela(["Mês", "Pedidos concluídos", "Receita", "Ticket médio", "Margem bruta simulada"], [
            [r["mes"], str(r["pedidos_concluidos"]), moeda(r["receita_centavos"]),
             moeda(Decimal(r["receita_centavos"]) / r["pedidos_concluidos"]),
             percentual(r["margem_bruta_centavos"], r["receita_centavos"])] for r in mensal
        ]),
        "## Canais",
        tabela(["Canal", "Pedidos concluídos", "Receita", "Participação na receita"], [
            [r["canal"], str(r["pedidos_concluidos"]), moeda(r["receita_centavos"]),
             percentual(r["receita_centavos"], receita)] for r in consultas["canais"]
        ]),
        "## Categorias",
        tabela(["Categoria", "Unidades", "Receita", "Margem bruta simulada"], [
            [r["categoria"], str(r["unidades"]), moeda(r["receita_centavos"]),
             percentual(r["receita_centavos"] - r["custo_centavos"], r["receita_centavos"])]
            for r in consultas["categorias"]
        ]),
        "Um pedido pode conter várias categorias. Contagens de pedidos por categoria "
        "não devem ser somadas para obter o total de pedidos.",
        "## Cinco produtos com maior receita",
        tabela(["Produto", "Unidades", "Receita"], [
            [r["produto"], str(r["unidades"]), moeda(r["receita_centavos"])]
            for r in consultas["produtos"][:5]
        ]),
        "## Leituras do exercício",
        f"- **{melhor_mes['mes']}** apresenta a maior receita simulada: "
        f"{moeda(melhor_mes['receita_centavos'])}, com {melhor_mes['pedidos_concluidos']} "
        "pedidos concluídos. O número de pedidos por mês foi definido no gerador; "
        "esse desenho impede interpretar a evolução como sazonalidade de um negócio real.",
        f"- **{canal['canal']}** concentra {percentual(canal['receita_centavos'], receita)} "
        "da receita simulada. A comparação é descritiva e não mede a eficiência do canal: "
        "não há gastos de aquisição, frete ou taxas de plataforma na base.",
        f"- **{produto['produto']}** tem a maior receita entre os produtos "
        f"({moeda(produto['receita_centavos'])}). Esse ranking não demonstra preferência "
        "de clientes, pois produtos, quantidades e preços foram sorteados pelo gerador.",
        "## Limitações",
        "A margem bruta simulada considera apenas receita após desconto menos custo dos "
        "produtos. Não representa lucro líquido: tributos, frete, despesas fixas, taxas de "
        "plataforma, devoluções e diferenças de prazo não estão modelados. O custo registrado "
        "em pedidos cancelados não é reconhecido na análise; não há perdas ou custos de "
        "cancelamento. Não existem clientes, identificação pessoal, estoque ou metas. "
        "As conclusões servem para demonstrar consultas e conciliação, sem orientar decisões reais.",
    ]
    (ROOT / "docs").mkdir(exist_ok=True)
    (ROOT / "docs" / "resultados.md").write_text("\n\n".join(partes) + "\n", encoding="utf-8")
    gerar_grafico(mensal)


def main() -> None:
    banco = ROOT / "data" / "demo.sqlite"
    if not banco.exists():
        raise SystemExit("Execute primeiro: python scripts/gerar_dados.py")
    # mode=ro evita alterações no banco durante a análise.
    with closing(sqlite3.connect(banco.as_uri() + "?mode=ro", uri=True)) as conn:
        conn.row_factory = sqlite3.Row
        consultas = consultar(conn)
        qualidade = validar_e_conciliar(conn, consultas)
    gerar_relatorio(consultas, qualidade)
    print("Validacao OK: integridade, relacionamentos e totais SQL/Python conciliados.")
    print("Relatorio: docs/resultados.md | Grafico: docs/receita-mensal.svg")
    print(f"Receita sintetica: {moeda(consultas['resumo'][0]['receita_centavos'])}")


if __name__ == "__main__":
    main()
