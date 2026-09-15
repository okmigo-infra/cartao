#!/usr/bin/env python3
"""Converte um manifesto legado em autoria Python integralmente tipada.

Ferramenta de migração, não adaptador de runtime: o resultado contém somente
objetos públicos do ``okmigo_cartao`` e deixa o JSON como artefato compilado.
"""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any


def _indentar(texto: str, quantidade: int = 4) -> str:
    prefixo = " " * quantidade
    return "\n".join(prefixo + linha if linha else linha for linha in texto.splitlines())


def _chamada(nome: str, *args: str, **kwargs: str | None) -> str:
    partes = [*args, *(f"{chave}={valor}" for chave, valor in kwargs.items() if valor is not None)]
    if not partes:
        return f"{nome}()"
    return f"{nome}(\n{_indentar(',\n'.join(partes))},\n)"


def _tupla(itens: list[str]) -> str:
    if not itens:
        return "()"
    return f"(\n{_indentar(',\n'.join(itens))},\n)"


def _enum(nome: str, valor: str, mapa: dict[str, str]) -> str:
    try:
        return f"{nome}.{mapa[valor]}"
    except KeyError as exc:
        raise ValueError(f"valor {valor!r} não coberto por {nome}") from exc


ESPACOS = {
    "none": "NENHUM", "small": "PEQUENO", "default": "PADRAO",
    "medium": "MEDIO", "large": "GRANDE", "extraLarge": "EXTRA_GRANDE",
}
ALINHAMENTOS = {"left": "ESQUERDA", "center": "CENTRO", "right": "DIREITA"}
LARGURAS = {"auto": "AUTOMATICA", "stretch": "FLEXIVEL"}
ALTURAS = {"small": "PEQUENA", "medium": "MEDIA", "large": "GRANDE", "stretch": "DISPONIVEL"}
FORMAS_ESCOLHA = {"compact": "LISTA", "expanded": "CARTOES", "filtered": "BUSCA"}
FORMATOS_ARQUIVO = {"pdf": "PDF", "imagem": "IMAGEM", "xml": "XML", "planilha": "PLANILHA", "texto": "TEXTO"}
FORMAS_GRAFICO = {"barras": "BARRAS", "linha": "LINHA"}
TONS_GRAFICO = {
    "positivo": "POSITIVO", "negativo": "NEGATIVO", "neutro": "NEUTRO",
    "atencao": "ATENCAO", "principal": "PRINCIPAL", "suave": "SUAVE",
}
TEMAS = {
    "financeiro-violeta": "FINANCEIRO", "jornada-ativa": "JORNADA",
    "mercado-editorial": "MERCADO", "operacao-direta": "OPERACAO",
}


def _repeticao(no: dict[str, Any], fabrica) -> str:
    modelo = fabrica(no["_repetir_lista"])
    quando = no.get("_quando")
    return _chamada(
        "Repetir",
        modelo,
        de=repr(no.get("_de")) if "_de" in no else None,
        quando=(
            _chamada("Condicao", repr(quando["campo"]), _tupla([repr(v) for v in quando["em"]]))
            if quando else None
        ),
    )


def _acao(no: dict[str, Any]) -> str:
    tipo = no["type"]
    if tipo == "Action.ToggleVisibility":
        alvos = []
        for alvo in no["targetElements"]:
            if isinstance(alvo, str):
                alvos.append(_chamada("AlvoDeVisibilidade", repr(alvo)))
            else:
                alvos.append(_chamada("AlvoDeVisibilidade", repr(alvo["elementId"]), mostrar=repr(alvo["isVisible"])))
        enfase = None
        if no.get("style") == "positive":
            enfase = "EnfaseDaAcao.PRIMARIA"
        elif no.get("style") == "destructive":
            enfase = "EnfaseDaAcao.DESTRUTIVA"
        return _chamada(
            "Alternar", repr(no["title"]), _tupla(alvos),
            enfase=enfase, modo_secundario="True" if no.get("mode") == "secondary" else None,
        )

    dados = dict(no.get("data") or {})
    operacao = dados.pop("operacao")
    enfase = None
    if no.get("style") == "positive":
        enfase = "EnfaseDaAcao.PRIMARIA"
    elif no.get("style") == "destructive":
        enfase = "EnfaseDaAcao.DESTRUTIVA"
    elif no.get("mode") == "secondary":
        enfase = "EnfaseDaAcao.SECUNDARIA"
    metodo = "consultar" if tipo == "Action.Execute" else "escrever"
    kwargs: dict[str, str | None] = {
        "enfase": enfase,
        "dados": repr(dados) if dados else None,
        "modo_secundario": "True" if no.get("mode") == "secondary" and no.get("style") else None,
    }
    if "okmigoAposEnviar" in no:
        transicao = no["okmigoAposEnviar"]
        tipada = isinstance(transicao, dict)
        alvos_brutos = transicao["targetElements"] if tipada else transicao
        alvos = [
            _chamada(
                "AlvoDeVisibilidade", repr(alvo["elementId"]),
                mostrar=repr(alvo["isVisible"]),
            )
            for alvo in alvos_brutos
        ]
        kwargs["alvos_apos_enviar"] = _tupla(alvos)
        kwargs["transicao_tipada"] = None if tipada else "False"
    return _chamada(f"Acao.{metodo}", repr(no["title"]), repr(operacao), **kwargs)


def _opcao(no: dict[str, Any]) -> str:
    if "_repetir_lista" in no:
        return _repeticao(no, _opcao)
    return _chamada(
        "Opcao", repr(no["title"]), repr(no["value"]),
        nota=repr(no.get("okmigoNota")) if "okmigoNota" in no else None,
        icone=repr(no.get("okmigoIcone")) if "okmigoIcone" in no else None,
    )


def _fato(no: dict[str, Any]) -> str:
    if "_repetir_lista" in no:
        return _repeticao(no, _fato)
    return _chamada("Fato", repr(no["title"]), repr(no["value"]))


def _serie(no: dict[str, Any]) -> str:
    if "_repetir_lista" in no:
        return _repeticao(no, _serie)
    tom = no.get("cor", "neutro")
    tom_expr = _enum("TomDoGrafico", tom, TONS_GRAFICO) if tom in TONS_GRAFICO else repr(tom)
    return _chamada("Serie", repr(no["rotulo"]), tom=tom_expr)


def _ponto(no: dict[str, Any]) -> str:
    if "_repetir_lista" in no:
        return _repeticao(no, _ponto)
    return _chamada("Ponto", repr(no["rotulo"]), _tupla([repr(v) for v in no["valores"]]))


def _lancamento(no: dict[str, Any]) -> str:
    if "_repetir_lista" in no:
        return _repeticao(no, _lancamento)
    return _chamada(
        "LancamentoFinanceiro", repr(no["titulo"]), repr(no["valor"]),
        subtitulo=repr(no.get("subtitulo", "")), icone=repr(no.get("icone", "")),
        semantica=repr(no.get("semantica", "neutro")), id=repr(no.get("id", "")),
        grupo=repr(no.get("grupo", "")), tipo=repr(no.get("tipo", "todas")),
    )


def _cartao_financeiro(no: dict[str, Any]) -> str:
    if "_repetir_lista" in no:
        return _repeticao(no, _cartao_financeiro)
    kwargs = {chave: repr(no.get(chave, "")) for chave in (
        "id", "tipo", "bandeira", "numero", "titular", "validade", "tom",
        "fatura_rotulo", "fatura", "limite_rotulo", "limite", "progresso_rotulo",
        "progresso_texto", "progresso_feito", "progresso_de",
    )}
    kwargs["lancamentos"] = _tupla([_lancamento(item) for item in no.get("lancamentos", [])])
    return _chamada("CartaoFinanceiro", repr(no["titulo"]), **kwargs)


def _item_distribuicao(no: dict[str, Any]) -> str:
    if "_repetir_lista" in no:
        return _repeticao(no, _item_distribuicao)
    return _chamada(
        "ItemDeDistribuicao", repr(no["rotulo"]), repr(no["valor"]),
        texto=repr(no.get("texto", "")), tom=repr(no.get("tom", "principal")),
    )


def _linha_tabela(no: dict[str, Any]) -> str:
    if "_repetir_lista" in no:
        return _repeticao(no, _linha_tabela)
    return _chamada(
        "LinhaDeTabela",
        _tupla([_celula_tabela(celula) for celula in no["cells"]]),
        ao_tocar=_acao(no["selectAction"]) if "selectAction" in no else None,
    )


def _celula_tabela(no: dict[str, Any]) -> str:
    if "_repetir_lista" in no:
        return _repeticao(no, _celula_tabela)
    return _chamada(
        "CelulaDeTabela",
        _tupla([_componente(item) for item in no.get("items", [])]),
    )


def _componente(no: dict[str, Any]) -> str:
    if "_repetir_lista" in no:
        return _repeticao(no, _componente)
    tipo = no["type"]
    if tipo == "TextBlock":
        return _chamada(
            "Texto", repr(no["text"]),
            alinhamento=(
                _enum("Alinhamento", no["horizontalAlignment"], ALINHAMENTOS)
                if "horizontalAlignment" in no else None
            ),
            separador=repr(no["separator"]) if "separator" in no else None,
            espaco=(
                _enum("Espaco", no["spacing"], ESPACOS) if "spacing" in no else None
            ),
            tamanho=repr(no["size"]) if "size" in no else None,
            peso=repr(no["weight"]) if "weight" in no else None,
            sutil=repr(no["isSubtle"]) if "isSubtle" in no else None,
            quebrar=repr(no.get("wrap")) if "wrap" in no else "None",
        )
    if tipo == "Container":
        alvos: list[str] = []
        if "selectAction" in no:
            for alvo in no["selectAction"]["targetElements"]:
                if isinstance(alvo, str):
                    alvos.append(_chamada("AlvoDeVisibilidade", repr(alvo)))
                else:
                    alvos.append(_chamada("AlvoDeVisibilidade", repr(alvo["elementId"]), mostrar=repr(alvo["isVisible"])))
        return _chamada(
            "Secao", _tupla([_componente(item) for item in no["items"]]),
            id=repr(no["id"]) if "id" in no else None,
            visivel=repr(no["isVisible"]) if "isVisible" in no else None,
            tom=repr(no["style"]) if "style" in no else "None",
            grade=repr(no["okmigoGrade"]) if "okmigoGrade" in no else None,
            ao_tocar=_tupla(alvos) if alvos else None,
            espaco=repr(no["spacing"]) if "spacing" in no else None,
            separador=repr(no["separator"]) if "separator" in no else None,
        )
    if tipo == "Column":
        return _chamada(
            "Area", _tupla([_componente(item) for item in no["items"]]),
            largura=_enum("LarguraDaArea", no["width"], LARGURAS),
            tom=repr(no["style"]) if "style" in no else None,
            alinhamento_vertical=repr(no["verticalContentAlignment"]) if "verticalContentAlignment" in no else None,
        )
    if tipo == "ColumnSet":
        return _chamada(
            "Faixa", _tupla([_componente(item) for item in no["columns"]]),
            espaco=_enum("Espaco", no["spacing"], ESPACOS) if "spacing" in no else None,
        )
    if tipo == "FactSet":
        return _chamada(
            "Fatos", _tupla([_fato(item) for item in no["facts"]]),
            espaco=_enum("Espaco", no["spacing"], ESPACOS) if "spacing" in no else None,
            separador=repr(no["separator"]) if "separator" in no else None,
        )
    if tipo == "Image":
        return _chamada(
            "Imagem", repr(no["url"]), repr(no["altText"]),
            altura=_enum("AlturaDaImagem", no["height"], ALTURAS),
            alternativa=_componente(no["fallback"]) if isinstance(no.get("fallback"), dict) else None,
        )
    if tipo == "Input.Text":
        return _chamada(
            "CampoTexto", repr(no["id"]), repr(no.get("campo")), repr(no.get("label")),
            placeholder=repr(no.get("placeholder", "")),
            valor=repr(no["value"]) if "value" in no else "None",
            obrigatorio=repr(no.get("isRequired")) if "isRequired" in no else "None",
            varias_linhas=repr(no.get("isMultiline")) if "isMultiline" in no else "None",
            maximo_de_caracteres=repr(no["maxLength"]) if "maxLength" in no else None,
            somente_leitura="True" if no.get("okmigoSomenteLeitura") else None,
            visivel="False" if no.get("isVisible") is False else None,
        )
    if tipo == "Input.Number":
        return _chamada(
            "CampoNumero", repr(no["id"]), repr(no.get("campo")), repr(no.get("label")),
            placeholder=repr(no.get("placeholder", "")),
            valor=repr(no["value"]) if "value" in no else None,
            obrigatorio=repr(no.get("isRequired")) if "isRequired" in no else "None",
            minimo=repr(no["min"]) if "min" in no else None,
            maximo=repr(no["max"]) if "max" in no else None,
        )
    if tipo == "Input.ChoiceSet":
        forma = no.get("style", "compact")
        return _chamada(
            "Escolha", repr(no["id"]), repr(no.get("campo")), repr(no.get("label")),
            opcoes=(_tupla([_opcao(item) for item in no["choices"]]) if "choices" in no else "None"),
            forma=_enum("FormaDaEscolha", forma, FORMAS_ESCOLHA),
            placeholder=repr(no.get("placeholder", "")),
            valor=repr(no["value"]) if "value" in no else "None",
            obrigatoria=repr(no.get("isRequired")) if "isRequired" in no else "None",
            quem_opera="True" if no.get("okmigoQuemOpera") else None,
            estrita=repr(no["okmigoEstrito"]) if "okmigoEstrito" in no else None,
        )
    if tipo in {"Action.Submit", "Action.Execute", "Action.ToggleVisibility"}:
        return _acao(no)
    if tipo == "ActionSet":
        return _chamada(
            "Acoes", _tupla([_acao(item) for item in no["actions"]]),
            rodape="True" if no.get("okmigoRodape") else None,
            espaco=_enum("Espaco", no["spacing"], ESPACOS) if "spacing" in no else None,
        )
    if tipo == "Table":
        fallback = no.get("fallback")
        return _chamada(
            "TabelaFlexivel", _tupla([repr(coluna["width"]) for coluna in no["columns"]]),
            _tupla([_linha_tabela(item) for item in no["rows"]]),
            cabecalho=repr(no["firstRowAsHeader"]) if "firstRowAsHeader" in no else "None",
            grade=repr(no["showGridLines"]) if "showGridLines" in no else "None",
            vazio="None",
            alternativa=_componente(fallback) if isinstance(fallback, dict) else None,
        )
    if tipo == "okmigoArquivo":
        return _chamada(
            "Arquivo", repr(no["id"]), repr(no["campo"]), repr(no["label"]),
            aceita=_tupla([_enum("FormatoDeArquivo", valor, FORMATOS_ARQUIVO) for valor in no.get("aceita", [])]),
            obrigatorio=repr(no.get("isRequired", False)),
        )
    if tipo == "okmigoDocumento":
        ler = no["ler"]
        return _chamada(
            "Documento", repr(no["titulo"]), repr(no["nome"]), repr(no["tipo"]),
            repr(ler["operacao"]), repr(ler.get("pedido", {})),
            tamanho=repr(no["tamanho"]) if "tamanho" in no else None,
        )
    if tipo == "okmigoCopiar":
        return _chamada("Copiar", repr(no["rotulo"]), repr(no["valor"]))
    if tipo == "okmigoCronometro":
        return _chamada(
            "Cronometro", repr(no["rotulo"]), repr(no["segundos"]),
            com_alternativa="True" if "fallback" in no else "False",
        )
    if tipo == "okmigoProgresso":
        return _chamada(
            "Progresso", repr(no["feito"]), repr(no["de"]),
            rotulo=repr(no["rotulo"]) if "rotulo" in no else "None",
            tom=repr(no["tom"]) if "tom" in no else None,
            com_alternativa="True" if "fallback" in no else "False",
        )
    if tipo == "okmigoAutorizar":
        return _chamada("Autorizar", repr(no["rotulo"]), repr(no["motivo"]), repr(no["url"]))
    if tipo == "okmigoGrafico":
        return _chamada(
            "Grafico", repr(no["titulo"]), _tupla([_serie(item) for item in no["series"]]),
            _tupla([_ponto(item) for item in no["pontos"]]),
            forma=_enum("FormaDoGrafico", no.get("forma", "barras"), FORMAS_GRAFICO),
        )
    if tipo == "okmigoListaFinanceira":
        return _chamada(
            "ListaFinanceira", repr(no.get("titulo", "")),
            _tupla([_lancamento(item) for item in no["itens"]]),
            busca=repr(no.get("busca", False)), filtros=repr(tuple(no.get("filtros", ["todas"]))),
        )
    if tipo == "okmigoCartaoBancario":
        return _chamada("CartoesFinanceiros", _tupla([_cartao_financeiro(item) for item in no["cartoes"]]))
    if tipo == "okmigoDistribuicao":
        return _chamada("Distribuicao", repr(no["titulo"]), _tupla([_item_distribuicao(item) for item in no["itens"]]))
    raise ValueError(f"componente não coberto: {tipo}")


def _fonte(no: dict[str, Any]) -> str:
    def consulta(item: dict[str, Any]) -> str:
        return _chamada(
            "ConsultaDaFonte", repr(item["operacao"]),
            caminho=repr(item["caminho"]) if "caminho" in item else None,
            pedido=repr(item["pedido"]) if "pedido" in item else None,
        )
    return _chamada(
        "Fonte", consulta(no["resumo"]),
        lista=consulta(no["lista"]) if "lista" in no else None,
    )


def _tela_resumida(no: dict[str, Any]) -> str:
    paineis = [
        _chamada(
            "PainelResumido", repr(item["rotulo"]), repr(item["valor"]),
            quebra=repr(tuple(item.get("quebra", []))) if item.get("quebra") else None,
        )
        for item in no.get("paineis", [])
    ]
    item = no["item"]
    return _chamada(
        "TelaResumida", repr(no["titulo"]), repr(no["resumo"]), _tupla(paineis),
        _chamada(
            "ItemResumido", repr(item["id"]), repr(item["texto"]),
            repr(item["apoio"]), repr(item["marca"]),
        ),
        agrupar_por=repr(no["agrupar_por"]) if "agrupar_por" in no else None,
        ordem_dos_grupos=repr(tuple(no.get("ordem_dos_grupos", []))) if no.get("ordem_dos_grupos") else None,
        titulo_do_grupo=repr(no["titulo_do_grupo"]) if "titulo_do_grupo" in no else None,
    )


def _superficie(no: dict[str, Any]) -> str:
    cartao = no["cartao"]
    tema = cartao.get("okmigoTema")
    return _chamada(
        "Superficie", repr(no["nome"]), repr(no["titulo"]),
        repr(no.get("rotulo")) if "rotulo" in no else "None",
        repr(no.get("icone")) if "icone" in no else "None",
        repr(no["hint"]), _fonte(no["fonte"]),
        _chamada(
            "Tela", repr(no["titulo"]), _tupla([_componente(item) for item in cartao["body"]]),
            tema=_enum("Tema", tema, TEMAS) if tema else None,
            navegacao="Navegacao.INFERIOR" if cartao.get("okmigoNavegacao") == "inferior" else None,
            versao=repr(cartao.get("version", "1.5")), mostrar_cabecalho="False",
        ),
        representacao=_tela_resumida(no["tela"]) if "tela" in no else None,
        visivel=repr(no["isVisible"]) if "isVisible" in no else None,
        rotulo_superficie=repr(no["rotulo_superficie"]) if "rotulo_superficie" in no else None,
    )


def _operacao_parametrizada(no: dict[str, Any]) -> str:
    return _chamada("OperacaoParametrizada", repr(no["operacao"]), repr(no["parametro"]))


def _aplicativo(no: dict[str, Any]) -> tuple[str, str]:
    conhecido = {
        "slug", "endpoint", "forma", "para_tipo", "descricao", "descricao_humana",
        "nome_visivel", "versao", "conversa", "superficies", "eventos", "avisa_antes",
        "relata_mudancas", "convite", "quer_a_marca", "aceita_contato", "publico",
        "marca_horario", "so_por_convite", "em_breve", "tipo", "tenant_sondagem",
        "credencial_sondagem", "vitrine_url",
    }
    desconhecido = set(no) - conhecido
    if desconhecido:
        raise ValueError(f"metadados do aplicativo sem tipo: {sorted(desconhecido)}")
    kwargs: dict[str, str | None] = {
        "slug": repr(no["slug"]), "endpoint": repr(no["endpoint"]),
        "para_tipo": repr(no.get("para_tipo")), "descricao": repr(no["descricao"]),
        "descricao_humana": repr(no.get("descricao_humana")),
        "nome_visivel": repr(no.get("nome_visivel")), "versao": repr(no["versao"]),
        "conversa": repr(tuple(no["conversa"])) if "conversa" in no else "None",
        "superficies": _tupla([_superficie(item) for item in no["superficies"]]),
        "forma": repr(no.get("forma", "do_operador")),
        "eventos": _operacao_parametrizada(no["eventos"]) if "eventos" in no else None,
        "avisa_antes": _operacao_parametrizada(no["avisa_antes"]) if "avisa_antes" in no else None,
        "relata_mudancas": _operacao_parametrizada(no["relata_mudancas"]) if "relata_mudancas" in no else None,
        "convite": (_chamada("Convite", repr(no["convite"]["operacao"]), repr(no["convite"]["parametro"]), repr(no["convite"]["par"])) if "convite" in no else None),
        "quer_a_marca": (_chamada("MarcaSolicitada", repr(no["quer_a_marca"]["operacao"]), repr(no["quer_a_marca"]["nome"]), repr(no["quer_a_marca"]["logo"])) if "quer_a_marca" in no else None),
        "aceita_contato": (_chamada("ContatoAceito", repr(no["aceita_contato"]["operacao"]), repr(no["aceita_contato"]["parametro"]), repr(no["aceita_contato"]["rotulo"])) if "aceita_contato" in no else None),
        "publico": (_chamada("CatalogoPublico", repr(no["publico"]["ofertas"]), expediente=repr(no["publico"]["expediente"]) if "expediente" in no["publico"] else None) if "publico" in no else None),
        "marca_horario": (_chamada("MarcaHorario", repr(no["marca_horario"]["operacao"]), repr(no["marca_horario"]["ofertas"])) if "marca_horario" in no else None),
        "so_por_convite": "True" if no.get("so_por_convite") else None,
        "em_breve": "True" if no.get("em_breve") else None,
        "tipo": repr(no["tipo"]) if "tipo" in no else None,
        "tenant_sondagem": repr(no["tenant_sondagem"]) if "tenant_sondagem" in no else None,
        "credencial_sondagem": repr(no["credencial_sondagem"]) if "credencial_sondagem" in no else None,
        "vitrine_url": repr(no["vitrine_url"]) if "vitrine_url" in no else None,
    }
    simbolo = "APLICATIVO_" + re.sub(r"[^A-Z0-9]+", "_", no["slug"].upper()).strip("_")
    return simbolo, _chamada("Aplicativo", **kwargs)


IMPORTACOES = """from okmigo_cartao import (
    Acao, Acoes, Alinhamento, Aplicativo, Area, Arquivo, Autorizar,
    CatalogoPublico, CampoNumero, CampoTexto, CartaoFinanceiro,
    CartoesFinanceiros, CelulaDeTabela, Condicao, ConsultaDaFonte,
    ContatoAceito, Convite, Copiar, Cronometro, Distribuicao, Documento,
    EnfaseDaAcao, Escolha, Espaco, Faixa, Fato, Fatos, Fonte,
    FormaDaEscolha, FormaDoGrafico, FormatoDeArquivo, Grafico, Imagem,
    ItemDeDistribuicao, ItemResumido, LancamentoFinanceiro, LarguraDaArea,
    LinhaDeTabela, ListaFinanceira, MarcaHorario, MarcaSolicitada,
    Navegacao, Opcao, OperacaoParametrizada, PainelResumido, Ponto, Progresso,
    Repetir, Secao, Serie, Superficie, TabelaFlexivel, Tela, TelaResumida, Tema, Texto,
    TomDoGrafico, AlvoDeVisibilidade, Alternar, AlturaDaImagem,
)
"""


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("manifestos", nargs="+", type=Path)
    parser.add_argument("--saida", required=True, type=Path)
    args = parser.parse_args()
    aplicativos = [_aplicativo(json.loads(path.read_text(encoding="utf-8"))) for path in args.manifestos]
    blocos = [
        '"""Aplicativos OkMigo escritos integralmente com o SDK Python.\n\nArquivo gerado uma vez durante a migração; a partir daqui ele é código-fonte.\n"""',
        "from __future__ import annotations",
        IMPORTACOES.rstrip(),
    ]
    for simbolo, expressao in aplicativos:
        blocos.append(f"{simbolo} = {expressao}")
    blocos.append(
        "APLICATIVOS_POR_SLUG = {\n"
        + "\n".join(f"    {simbolo}.slug: {simbolo}," for simbolo, _ in aplicativos)
        + "\n}"
    )
    args.saida.write_text("\n\n\n".join(blocos) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
