"""Galeria local para conferir uma tela do SDK antes de ligá-la ao produto.

O preview executa um alvo Python local, compila o SDK, expande os dados e só
desenha a árvore reconstruída pelo crivo. Ele não abre uma nova fronteira do
contrato: ações são simuladas no navegador e nunca fazem requisição externa.
"""

from __future__ import annotations

import argparse
import html
import importlib.util
import inspect
import json
import sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from importlib.resources import files
from pathlib import Path
from types import ModuleType
from typing import Any

from .casca import expandir
from .crivo import Config, validar
from .manifesto import e_manifesto

Json = dict[str, Any]


class ErroDePreview(ValueError):
    """Entrada local que não consegue virar uma tela conferida."""


def _separar_alvo(alvo: str) -> tuple[Path, str]:
    arquivo, separador, fabrica = alvo.rpartition(":")
    if not separador or not arquivo or not fabrica:
        raise ErroDePreview(
            "o alvo precisa ter a forma arquivo.py:objeto, por exemplo "
            "exemplos/sdk_catalogo.py:APLICATIVO"
        )
    caminho = Path(arquivo).expanduser().resolve()
    if caminho.suffix != ".py":
        raise ErroDePreview("o alvo do SDK precisa apontar para um arquivo .py")
    if not caminho.is_file():
        raise ErroDePreview(f"arquivo não encontrado: {caminho}")
    return caminho, fabrica


def _carregar_modulo(caminho: Path) -> ModuleType:
    nome = f"_okmigo_preview_{abs(hash(caminho))}"
    spec = importlib.util.spec_from_file_location(nome, caminho)
    if spec is None or spec.loader is None:
        raise ErroDePreview(f"não consegui importar {caminho}")
    modulo = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(modulo)
    return modulo


def _compilar_objeto(objeto: Any, nome: str) -> Json:
    resultado = objeto() if callable(objeto) else objeto
    if hasattr(resultado, "compilar") and callable(resultado.compilar):
        resultado = resultado.compilar()
    if not isinstance(resultado, dict):
        raise ErroDePreview(
            f"{nome} precisa ser Tela, Aplicativo, uma fábrica ou dict; "
            f"recebi {type(resultado).__name__}"
        )
    return resultado


def carregar_alvo(alvo: str) -> Json:
    """Carrega ``arquivo.py:objeto`` e devolve o cartão/app bruto compilado."""
    caminho, fabrica = _separar_alvo(alvo)
    modulo = _carregar_modulo(caminho)
    objeto = getattr(modulo, fabrica, None)
    if objeto is None:
        raise ErroDePreview(f"{fabrica!r} não existe em {caminho}")
    return _compilar_objeto(objeto, fabrica)


def _respostas_do_preview(
    modulo: ModuleType | None,
    dados: Json,
    escrituras: frozenset[str],
    leituras: frozenset[str],
) -> list[Json]:
    """Compila respostas locais de operações sem colocá-las no manifesto.

    O JSON fornece somente conteúdo de demonstração e o nome da fábrica Python.
    O layout continua vindo do SDK e cada resposta passa pelo mesmo crivo.
    """
    configuracao = dados.get("_preview") or {}
    if not configuracao:
        return []
    if modulo is None or not isinstance(configuracao, dict):
        raise ErroDePreview("respostas do preview exigem um alvo Python")
    declaracoes = configuracao.get("respostas") or []
    if not isinstance(declaracoes, list) or len(declaracoes) > 20:
        raise ErroDePreview("_preview.respostas precisa ser uma lista de até 20 itens")

    respostas: list[Json] = []
    for declaracao in declaracoes:
        if not isinstance(declaracao, dict):
            raise ErroDePreview("cada resposta do preview precisa ser um objeto")
        operacao = str(declaracao.get("operacao") or "")
        fabrica = str(declaracao.get("fabrica") or "")
        campo = str(declaracao.get("campo") or "ticker")
        voltar_para = str(declaracao.get("voltar_para") or "")
        exemplos = declaracao.get("exemplos") or []
        if operacao not in leituras or not fabrica or not voltar_para:
            raise ErroDePreview(
                "resposta precisa nomear uma leitura, fábrica e superfície de volta"
            )
        if not isinstance(exemplos, list) or len(exemplos) > 20:
            raise ErroDePreview("resposta aceita uma lista de até 20 exemplos")
        funcao = getattr(modulo, fabrica, None)
        if not callable(funcao):
            raise ErroDePreview(f"fábrica de resposta {fabrica!r} não encontrada")
        for exemplo in exemplos:
            if not isinstance(exemplo, dict) or campo not in exemplo:
                raise ErroDePreview(
                    f"cada exemplo de {operacao!r} precisa do campo {campo!r}"
                )
            # Moldes de superfície são frequentemente fábricas sem dados:
            # a expansão usa o `exemplo` logo abaixo. Fichas de detalhe, por
            # outro lado, precisam dos dados para construir o próprio molde.
            sem_argumentos = not inspect.signature(funcao).parameters
            bruto = funcao() if sem_argumentos else funcao(exemplo)
            if hasattr(bruto, "compilar") and callable(bruto.compilar):
                bruto = bruto.compilar()
            if not isinstance(bruto, dict):
                raise ErroDePreview(f"{fabrica} não devolveu uma Tela compilável")
            if sem_argumentos:
                bruto = expandir(bruto, exemplo, [])
            tela, erro = validar(bruto, escrituras, leituras, config=Config())
            if erro or tela is None:
                raise ErroDePreview(
                    f"resposta {operacao!r} recusada pelo crivo: {erro or 'sem corpo'}"
                )
            respostas.append(
                {
                    "operacao": operacao,
                    "campo": campo,
                    "valor": str(exemplo[campo]),
                    "voltar_para": voltar_para,
                    "tela": tela,
                }
            )
    return respostas


def _dados(caminho: Path | None) -> tuple[Json, list[Any]]:
    if caminho is None:
        return {}, []
    try:
        bruto = json.loads(caminho.read_text(encoding="utf-8"))
    except FileNotFoundError as erro:
        raise ErroDePreview(f"arquivo de dados não encontrado: {caminho}") from erro
    except json.JSONDecodeError as erro:
        raise ErroDePreview(
            f"JSON inválido em {caminho}:{erro.lineno}:{erro.colno}: {erro.msg}"
        ) from erro
    if isinstance(bruto, list):
        return {}, bruto
    if not isinstance(bruto, dict):
        raise ErroDePreview("--dados precisa conter {resumo, linhas} ou uma lista")
    linhas = bruto.get("linhas") or []
    if not isinstance(linhas, list):
        raise ErroDePreview("dados.linhas precisa ser uma lista")
    resumo = bruto.get("resumo") or {}
    if not isinstance(resumo, dict):
        raise ErroDePreview("dados.resumo precisa ser um objeto")
    return resumo, linhas


def inferir_operacoes(cartao: Any) -> tuple[frozenset[str], frozenset[str]]:
    """Extrai o contrato mínimo do código local para a conferência do piloto."""
    escrituras: set[str] = set()
    leituras: set[str] = set()

    def visitar(valor: Any) -> None:
        if isinstance(valor, list):
            for item in valor:
                visitar(item)
            return
        if not isinstance(valor, dict):
            return
        tipo = valor.get("type")
        dados = valor.get("data")
        operacao = dados.get("operacao") if isinstance(dados, dict) else None
        if isinstance(operacao, str) and operacao:
            if tipo == "Action.Submit":
                escrituras.add(operacao)
            elif tipo == "Action.Execute":
                leituras.add(operacao)
        buscar = valor.get("okmigoBuscar")
        if isinstance(buscar, str) and buscar:
            leituras.add(buscar)
        # Blocos nativos também nomeiam capacidades sem usar Action.*. É o
        # caso do calendário: arrastar um evento leva ``enviar``. A inferência
        # precisa enxergar essa escrita para o preview conferir o mesmo
        # contrato que o renderer real confere.
        enviar = valor.get("enviar")
        if isinstance(enviar, str) and enviar:
            escrituras.add(enviar)
        consultar = valor.get("consultar")
        if isinstance(consultar, str) and consultar:
            leituras.add(consultar)
        if tipo == "okmigoDocumento":
            ler = valor.get("ler")
            operacao_de_leitura = (
                ler.get("operacao") if isinstance(ler, dict) else None
            )
            if isinstance(operacao_de_leitura, str) and operacao_de_leitura:
                leituras.add(operacao_de_leitura)
        for filho in valor.values():
            visitar(filho)

    visitar(cartao)
    return frozenset(escrituras), frozenset(leituras)


def construir_tela(
    alvo: str,
    dados: Path | None,
    *,
    escrituras: frozenset[str] | None = None,
    leituras: frozenset[str] | None = None,
) -> tuple[Json, frozenset[str], frozenset[str]]:
    bruto = carregar_alvo(alvo)
    inferidas_escrita, inferidas_leitura = inferir_operacoes(bruto)
    resumo, linhas = _dados(dados)
    if dados is not None:
        bruto = expandir(bruto, resumo, linhas)
    esc = inferidas_escrita if escrituras is None else escrituras
    lei = inferidas_leitura if leituras is None else leituras
    tela, erro = validar(bruto, esc, lei, config=Config())
    if erro or tela is None:
        raise ErroDePreview(f"tela recusada pelo crivo: {erro or 'sem corpo'}")
    return tela, esc, lei


def construir_aplicativo(
    alvo: str,
    dados: Path | None,
    *,
    escrituras: frozenset[str] | None = None,
    leituras: frozenset[str] | None = None,
) -> tuple[Json, frozenset[str], frozenset[str]]:
    """Carrega um Aplicativo/manifesto ou embrulha uma Tela como app de 1 tela."""
    modulo: ModuleType | None = None
    if ":" in alvo:
        caminho, nome_do_objeto = _separar_alvo(alvo)
        modulo = _carregar_modulo(caminho)
        objeto = getattr(modulo, nome_do_objeto, None)
        if objeto is None:
            raise ErroDePreview(f"{nome_do_objeto!r} não existe em {caminho}")
        compilado = _compilar_objeto(objeto, nome_do_objeto)
        if not e_manifesto(compilado):
            tela, esc, lei = construir_tela(
                alvo, dados, escrituras=escrituras, leituras=leituras
            )
            return (
                {
                    "nome": caminho.stem,
                    "atual": "preview",
                    "superficies": [
                        {
                            "nome": "preview",
                            "rotulo": "Preview",
                            "icone": "ativos",
                            "tela": tela,
                        }
                    ],
                },
                esc,
                lei,
            )
        manifesto = compilado
    else:
        caminho = Path(alvo).expanduser().resolve()
        try:
            manifesto = json.loads(caminho.read_text(encoding="utf-8"))
        except FileNotFoundError as erro:
            raise ErroDePreview(f"manifesto não encontrado: {caminho}") from erro
        except json.JSONDecodeError as erro:
            raise ErroDePreview(
                f"JSON inválido em {caminho}:{erro.lineno}:{erro.colno}: {erro.msg}"
            ) from erro
    if not e_manifesto(manifesto):
        raise ErroDePreview(
            "sem ':objeto', o alvo precisa ser um manifesto com superficies"
        )

    dados_lidos: Json = {}
    dados_do_app: Json = {}
    if dados is not None:
        try:
            lidos = json.loads(dados.read_text(encoding="utf-8"))
        except FileNotFoundError as erro:
            raise ErroDePreview(f"arquivo de dados não encontrado: {dados}") from erro
        except json.JSONDecodeError as erro:
            raise ErroDePreview(
                f"JSON inválido em {dados}:{erro.lineno}:{erro.colno}: {erro.msg}"
            ) from erro
        if not isinstance(lidos, dict):
            raise ErroDePreview(
                "para um manifesto, --dados precisa mapear cada nome de superfície"
            )
        dados_lidos = lidos
        dados_do_app = lidos.get("superficies", lidos)
        if not isinstance(dados_do_app, dict):
            raise ErroDePreview("dados.superficies precisa ser um objeto")

    brutos: list[tuple[Json, Json]] = []
    inferidas_escrita: set[str] = set()
    inferidas_leitura: set[str] = set()
    for superficie in manifesto.get("superficies") or []:
        if not isinstance(superficie, dict) or not isinstance(
            superficie.get("cartao"), dict
        ):
            continue
        cartao = superficie["cartao"]
        brutos.append((superficie, cartao))
        esc, lei = inferir_operacoes(cartao)
        inferidas_escrita.update(esc)
        inferidas_leitura.update(lei)
    if not brutos:
        raise ErroDePreview("o manifesto não tem nenhuma superfície com cartão")

    esc_final = frozenset(inferidas_escrita) if escrituras is None else escrituras
    lei_final = frozenset(inferidas_leitura) if leituras is None else leituras
    prontas = []
    for superficie, molde in brutos:
        nome = str(superficie.get("nome") or "")
        dado = dados_do_app.get(nome, {})
        if dado and not isinstance(dado, dict):
            raise ErroDePreview(f"os dados de {nome!r} precisam ser um objeto")
        resumo = (dado or {}).get("resumo") or {}
        linhas = (dado or {}).get("linhas") or []
        if not isinstance(resumo, dict) or not isinstance(linhas, list):
            raise ErroDePreview(
                f"os dados de {nome!r} precisam ter resumo objeto e linhas lista"
            )
        bruto = expandir(molde, resumo, linhas)
        tela, erro = validar(bruto, esc_final, lei_final, config=Config())
        if erro and not dado and "nenhum elemento" in erro:
            # Algumas telas são integralmente dirigidas por dados (uma tabela
            # sem título, por exemplo). Sem fixture o preview não deve apagar
            # a rota inteira: mantém o destino navegável e explicita que falta
            # conteúdo de demonstração. Com dados fornecidos, qualquer erro
            # continua sendo fatal.
            substituto = {
                "type": "AdaptiveCard",
                "version": "1.5",
                "okmigoTema": molde.get("okmigoTema"),
                "okmigoNavegacao": molde.get("okmigoNavegacao"),
                "body": [
                    {"type": "TextBlock", "text": str(superficie.get("titulo") or nome), "size": "large", "weight": "bolder"},
                    {"type": "TextBlock", "text": "Adicione dados de demonstração para visualizar o conteúdo desta tela.", "wrap": True, "isSubtle": True},
                ],
            }
            tela, erro = validar(substituto, esc_final, lei_final, config=Config())
        if erro or tela is None:
            raise ErroDePreview(
                f"superfície {nome!r} recusada pelo crivo: {erro or 'sem corpo'}"
            )
        prontas.append(
            {
                "nome": nome,
                "rotulo": str(
                    superficie.get("rotulo_superficie")
                    or superficie.get("rotulo")
                    or superficie.get("titulo")
                    or nome
                )[:24],
                "icone": str(superficie.get("icone") or nome)[:30],
                "tela": tela,
            }
        )
    respostas = _respostas_do_preview(modulo, dados_lidos, esc_final, lei_final)
    return (
        {
            "nome": str(
                manifesto.get("nome_visivel") or manifesto.get("slug") or caminho.stem
            )[:40],
            "atual": prontas[0]["nome"],
            "superficies": prontas,
            "respostas": respostas,
        },
        esc_final,
        lei_final,
    )


def _e(valor: Any) -> str:
    return html.escape(str(valor or ""), quote=True)


def pagina(tela: Json, alvo: str, esc: frozenset[str], lei: frozenset[str]) -> str:
    aplicativo = {
        "nome": Path(alvo.split(":", 1)[0]).stem,
        "atual": "preview",
        "superficies": [
            {
                "nome": "preview",
                "rotulo": "Preview",
                "icone": "ativos",
                "tela": tela,
            }
        ],
    }
    return pagina_aplicativo(aplicativo, alvo, esc, lei)


def _ativo_do_renderer(nome: str) -> str:
    """Lê o renderer Web oficial que viaja dentro do pacote Python."""
    try:
        return files("okmigo_cartao").joinpath("assets", nome).read_text(encoding="utf-8")
    except (FileNotFoundError, ModuleNotFoundError) as erro:
        raise ErroDePreview(
            "renderer Web não encontrado no pacote; reinstale okmigo-cartao"
        ) from erro


def pagina_aplicativo(
    aplicativo: Json, alvo: str, esc: frozenset[str], lei: frozenset[str]
) -> str:
    """Monta a galeria com o mesmo bundle React usado pelo OkMigo Web.

    O Python só entrega a árvore já expandida e conferida. Aparência,
    responsividade e componentes pertencem ao renderer empacotado; assim o
    preview externo não mantém uma terceira tradução visual do contrato.
    """
    configuracao = (
        json.dumps(aplicativo, ensure_ascii=False, separators=(",", ":"))
        .replace("<", "\\u003c")
        .replace("&", "\\u0026")
        .replace("\u2028", "\\u2028")
        .replace("\u2029", "\\u2029")
    )
    css = _ativo_do_renderer("renderer.css").replace("</style", "<\\/style")
    javascript = _ativo_do_renderer("renderer.js").replace("</script", "<\\/script")
    return f"""<!doctype html>
<html lang="pt-BR" data-tema="claro">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width,initial-scale=1">
  <title>Preview · {_e(alvo)}</title>
  <style>{css}</style>
</head>
<body>
  <div id="okmigo-cartao-preview"></div>
  <script>window.OKMIGO_CARTAO_PREVIEW={configuracao};</script>
  <script>{javascript}</script>
</body>
</html>"""


def _lista(valor: str | None) -> frozenset[str] | None:
    if valor is None:
        return None
    return frozenset(item.strip() for item in valor.split(",") if item.strip())


def main_preview(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="okmigo-cartao preview",
        description="Compila, confere e mostra uma tela do SDK no desktop e no celular.",
    )
    parser.add_argument(
        "alvo",
        help="manifesto.json ou arquivo.py:objeto (Tela, Aplicativo ou fábrica)",
    )
    parser.add_argument(
        "--dados",
        type=Path,
        help="JSON da tela ou mapa {superficie: {resumo, linhas}} do aplicativo",
    )
    parser.add_argument(
        "--escrituras", help="operações de escrita; por padrão são inferidas do SDK"
    )
    parser.add_argument(
        "--leituras", help="operações de leitura; por padrão são inferidas do SDK"
    )
    parser.add_argument(
        "--host", default="0.0.0.0", help="interface do servidor (padrão: 0.0.0.0)"
    )
    parser.add_argument(
        "--port", type=int, default=4173, help="porta do servidor (padrão: 4173)"
    )
    parser.add_argument(
        "--saida", type=Path, help="grava um HTML autocontido e não inicia servidor"
    )
    args = parser.parse_args(argv)

    def construir() -> tuple[str, frozenset[str], frozenset[str]]:
        aplicativo, esc, lei = construir_aplicativo(
            args.alvo,
            args.dados,
            escrituras=_lista(args.escrituras),
            leituras=_lista(args.leituras),
        )
        return pagina_aplicativo(aplicativo, args.alvo, esc, lei), esc, lei

    try:
        documento, esc, lei = construir()
    except (ErroDePreview, OSError, AttributeError, TypeError, ValueError) as erro:
        print(f"✗ preview recusado — {erro}", file=sys.stderr)
        return 1

    print(f"✓ preview validado · {len(lei)} leitura(s) · {len(esc)} escrita(s)")
    if args.saida:
        args.saida.parent.mkdir(parents=True, exist_ok=True)
        args.saida.write_text(documento, encoding="utf-8")
        print(f"  HTML escrito em {args.saida.resolve()}")
        return 0

    class Manipulador(BaseHTTPRequestHandler):
        def do_GET(self) -> None:
            if self.path.startswith("/favicon.ico"):
                self.send_response(204)
                self.end_headers()
                return
            try:
                atual, _, _ = construir()
                corpo = atual.encode("utf-8")
                status = 200
            except Exception as erro:  # noqa: BLE001 — código-alvo pode falhar ao importar
                corpo = (
                    "<!doctype html><meta charset=utf-8><title>Erro no preview</title>"
                    f"<pre>{_e(erro)}</pre><p>Corrija o arquivo e recarregue a página.</p>"
                ).encode()
                status = 500
            self.send_response(status)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(corpo)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(corpo)

        def log_message(self, formato: str, *valores: Any) -> None:
            return

    try:
        servidor = ThreadingHTTPServer((args.host, args.port), Manipulador)
    except OSError as erro:
        print(f"✗ não consegui abrir {args.host}:{args.port} — {erro}", file=sys.stderr)
        return 1
    print(f"  desktop + celular: http://localhost:{args.port}")
    print("  no container, publique/encaminhe essa porta; Ctrl+C encerra")
    try:
        servidor.serve_forever()
    except KeyboardInterrupt:
        print("\n  preview encerrado")
    finally:
        servidor.server_close()
    return 0
