"""O crivo: um Adaptive Card (subconjunto) entra, uma tela RECONSTRUÍDA sai.

O serviço escreve a tela como quiser, dentro do subconjunto; o produto valida e
reconstrói no vocabulário dele. A regra que governa tudo aqui: **o que não é
construído não existe.** O crivo nunca repassa a árvore que recebeu — ele monta
outra, nó a nó, e descarta em silêncio o que não conhece.

Por que assim, e não uma lista de proibições sobre a árvore original:

- **Quem escolhe a aparência é o produto.** O Adaptive Card é semântico — diz
  «um texto grande e negrito», não «22px, #E8ECF4». Por isso não existe campo
  de cor, de fonte nem de pixel neste vocabulário: o serviço declara INTENÇÃO
  (tamanho como palavra, estilo como hierarquia, altura como faixa) e o
  cliente traduz para o tema dele, no claro e no escuro.
- **Degradar em vez de quebrar.** Um cartão escrito para uma versão mais nova
  continua utilizável num cliente velho: nó desconhecido some (ou cai no
  `fallback` do próprio schema). Só o que é ESTRUTURAL recusa a tela inteira —
  cartão sem corpo, aninhamento acima do teto, operação que o serviço não
  declarou — porque aí não há tela para degradar.
- **Ação nomeia CAPACIDADE, nunca endereço.** Um botão não carrega URL; ele
  nomeia uma operação do contrato congelado na instalação, e quem transforma
  isso em chamada é o cliente, batendo numa rota do produto. O aparelho de
  quem abre a tela nunca alcança o serviço — com UMA exceção, `okmigoAutorizar`,
  cercada de travas próprias.

O subconjunto é pequeno de propósito e NÃO é o Adaptive Cards inteiro. Cada
tipo que entra é uma decisão e dois renderizadores. Há chaves com prefixo
`okmigo` para o que o schema não tem (calendário, arquivo, documento, cópia,
autorização, cronômetro, progresso, gráfico) e DICAS com o mesmo prefixo em
tipos que existem (`okmigoGrade`, `okmigoSobreposto`, `okmigoRodape`,
`okmigoAposEnviar`, `okmigoNota`, `okmigoIcone`, `okmigoEstrito`,
`okmigoSomenteLeitura`, `okmigoBuscar`). Dica em tipo existente degrada sozinha; tipo novo
some no cliente que não o conhece — e é por isso que tipo novo é mais caro.
"""

from __future__ import annotations

import re
from contextvars import ContextVar
from dataclasses import dataclass
from typing import Any
from urllib.parse import urlsplit


@dataclass(frozen=True)
class Config:
    """O que o crivo precisa saber sobre o AMBIENTE que o hospeda.

    - `dominios`: as zonas de DNS do produto. Uma imagem só entra se for servida
      por um destes hosts (ou subdomínio); uma autorização em terceiro só entra
      se NÃO for. É a única definição de «nosso», para as duas perguntas.
    - `base_de_imagens`: prefixo que torna absoluta uma URL relativa `/img/...`
      — um app nativo não tem origem, e uma URL relativa lá é uma foto quebrada.
    - `anexo_max_bytes`: o teto de um arquivo enviado. O serviço só pode
      APERTAR esse teto (`maxBytes`), nunca subir: quem paga o arquivo em
      memória é o produto.
    """

    dominios: tuple[str, ...] = ()
    base_de_imagens: str = ""
    anexo_max_bytes: int = 10 * 1024 * 1024


# ── Listas fechadas ─────────────────────────────────────────────────────────
# Tudo aqui é lista fechada de PALAVRAS. Valor fora da lista cai no padrão ou
# some; nunca passa adiante. É o que permite ao cliente escolher o valor real
# (quantos pixels é «large») e à tela parecer do produto.

#: Tetos que são do PRODUTO, não do autor. Uma lista com dez mil opções é uma
#: tela que não abre num telefone, e quem a declarasse não pagaria por isso.
_MAX_OPCOES = 60
#: Eventos por calendário. O bloco vale 1 nó; o custo está no que viaja e no
#: que o cliente guarda em memória. 500 é um ano cheio de agenda.
_MAX_EVENTOS = 500

TAMANHOS = {"small", "default", "medium", "large", "extraLarge"}
PESOS = {"lighter", "default", "bolder"}
ESPACOS = {"none", "small", "default", "medium", "large", "extraLarge", "padding"}
#: `emphasis` é painel; `accent` é a caixa PREENCHIDA com o acento (a porta
#: recomendada, o que a tela quer que se toque primeiro); `good`, `attention` e
#: `warning` são o TOM da caixa — o estado do que ela carrega. Nada disso é
#: tinta: é hierarquia e semântica. Qual cor cada palavra vira é do cliente.
#: `TextBlock.color` segue recusado: tom é da caixa, nunca de uma palavra.
ESTILOS = {"default", "emphasis", "accent", "good", "attention", "warning"}
LARGURAS = {"auto", "stretch"}
#: Alinhamento é semântico (esquerda/centro/direita), não pixel.
ALINHAMENTOS = {"left", "center", "right"}
#: Vistas de calendário. Fechada como as demais: cada uma é um desenho a
#: manter em dois clientes; entra uma por vez, com motivo.
VISTAS = {"mes", "semana", "dia"}

#: O que o CLIENTE sabe sobre o dia tocado e pode entregar a um campo. O
#: serviço nomeia o campo, nunca o valor.
DADOS_DO_DIA = {"data"}
#: Idem para o EVENTO tocado ou arrastado. `id` é o que separa «ver a agenda»
#: de «mexer nela». Os três `nova_*` são o DESTINO de um arrasto e só existem
#: nesse gesto: num toque chegariam vazios e a operação gravaria lixo.
DADOS_DO_EVENTO = {
    "id",
    "data",
    "hora",
    "duracao_minutos",
    "titulo",
    "detalhe",
    "novo_inicio",
    "nova_data",
    "nova_hora",
}
_DADOS_SO_DE_ARRASTO = {"novo_inicio", "nova_data", "nova_hora"}
#: A que evento uma ação se aplica. Fechada porque as operações são outras:
#: uma ação sem `para` apareceria nos dois tipos e chamaria a errada.
EVENTOS_PARA = {"atendimento", "compromisso"}
#: Teto de LEITURA, não de tela: um menu com dez itens em cima de um
#: compromisso é um labirinto.
_MAX_ACOES_DO_EVENTO = 6
ALTURAS_IMG = {"small", "medium", "large", "stretch"}
#: Altura de caixa é semântica; o pixel do autor (`minHeight`) é só a DICA que
#: cai numa das três faixas. Sem faixa, uma célula de grade encolhe até o
#: tamanho do texto e um mês com dias vazios vira uma tira ilegível.
ALTURAS_CAIXA = {"baixa", "media", "alta"}
#: O que uma entrada de arquivo pode aceitar — palavras, não MIME nem extensão.
#: Quem traduz para `accept=` e para o seletor do celular é o cliente.
FORMATOS_DE_ARQUIVO = {"pdf", "imagem", "xml", "planilha", "texto"}
#: O que um documento É, para o cliente saber se desenha (pdf, imagem) ou só
#: oferece baixar. Derivado do MIME/nome, nunca aceito como palavra do autor.
FORMATOS_DE_DOCUMENTO = {"pdf", "imagem", "outro"}
#: Tetos da tabela e do gráfico. 16 colunas cabem um ano por mês; 200 linhas é
#: o que se lê sem rolagem infinita — acima, o serviço pagina. 4 séries se
#: distinguem por cor sem legenda virar decodificação; 24 pontos são dois anos
#: por mês. Acima disso o serviço agrega antes de mandar.
_MAX_COLUNAS = 16
_MAX_LINHAS = 200
_MAX_SERIES = 4
_MAX_PONTOS = 24
_MAX_IMAGENS = 12
_MAX_ETAPAS = 24
#: O total de uma barra de progresso. «3 de 1000000» não é barra, é número.
_MAX_PROGRESSO = 10_000
#: Um cronômetro conta descanso, em segundos; uma hora é folga generosa, e o
#: teto existe para um número absurdo não virar contagem de dias.
_MAX_CRONOMETRO_S = 3600

_FORMAS_DE_GRAFICO = {"barras", "linha"}
#: Cores SEMÂNTICAS, nunca hexadecimal: o serviço declara o que o número
#: significa; quem pinta é o cliente, com a paleta do tema dele.
_CORES_DO_GRAFICO = {"positivo", "negativo", "neutro", "atencao", "principal", "suave"}
#: Temas são MODOS de apresentação escolhidos pelo produto, não paletas que o
#: serviço controla. O manifesto só declara a natureza da experiência; web e
#: app traduzem a palavra para seus próprios tokens. Manter a lista fechada
#: impede que um serviço transforme `okmigoTema` em CSS disfarçado.
_TEMAS_DO_CARTAO = {
    "financeiro-violeta",
    "jornada-ativa",
    "mercado-editorial",
    "operacao-direta",
}
_NAVEGACOES_DO_CARTAO = {"inferior"}
_TONS_FINANCEIROS = {
    "principal",
    "suave",
    "violeta",
    "verde",
    "laranja",
    "vermelho",
    "azul",
    "escuro",
    "cinza",
}
_TONS_DE_ETIQUETA = {"neutro", "positivo", "atencao", "negativo", "informativo"}
_ESTADOS_DA_ETAPA = {"concluida", "atual", "futura", "erro"}
_FORMATOS_DO_CAMPO = {
    "data",
    "hora",
    "mes",
    "moeda",
    "documento",
    "telefone",
    "url",
    "etiquetas",
    "unidade",
}

#: Vírgula decimal com ou sem ponto de milhar («1200,00» ou «1.200,00») — a
#: forma que uma ponte produz ao substituir um número num molde, porque ela
#: formata para leitura humana.
_NUMERO_BR = re.compile(r"^-?(?:\d{1,3}(\.\d{3})+|\d+)(,\d+)?$")

_MAX = {"texto": 400, "titulo": 120, "valor": 200}
#: O teto de nós do cartão. Uma grade declarada célula a célula estoura isto
#: com facilidade (um mês custa centenas de nós); é para isso que existem os
#: blocos que valem 1 nó e carregam DADO (`okmigoCalendario`, `okmigoGrafico`).
MAX_NOS = 2000
#: Quantas autorizações em terceiro um cartão pode oferecer. UMA, e o teto é
#: metade da garantia: seis botões «autorizar» para seis endereços é uma
#: superfície de phishing com a moldura do produto.
_MAX_AUTORIZACOES = 1
#: Teto do endereço de autorização. Generoso porque o token do provedor viaja
#: na query e passa de 900 caracteres. Quem passar é RECUSADO, nunca cortado.
_MAX_ENDERECO = 2048

#: A ênfase de um botão, nas palavras do próprio Adaptive Cards
#: (`Action.style`). A tradução impede ler `positive` como uma COR verde.
_ENFASES = {"positive": "primaria", "destructive": "destrutiva"}
#: As quatro que o cliente tem de saber desenhar. `padrao` é o de sempre.
ENFASES = ("primaria", "padrao", "discreta", "destrutiva")


# ── Contexto de UMA validação ────────────────────────────────────────────────
# Vivem em ContextVar, não em parâmetro, porque `_um` é recursivo e passa por
# vários construtores até chegar num `ActionSet`: repetir a trava em cada
# assinatura é trava que alguém esquece numa delas. `None` = «não confira», que
# é o que vale para quem valida um cartão sem serviço por trás.
_config: ContextVar[Config] = ContextVar("config_do_crivo", default=Config())
_escrituras: ContextVar[frozenset[str] | None] = ContextVar(
    "escrituras_permitidas", default=None
)
_leituras: ContextVar[frozenset[str] | None] = ContextVar(
    "leituras_permitidas", default=None
)
_autorizacoes: ContextVar[list[int] | None] = ContextVar(
    "autorizacoes_do_cartao", default=None
)


class _Erro(Exception):
    """Recusa da tela INTEIRA — só para o que é estrutural."""


def _txt(v: Any, papel: str = "texto") -> str:
    return " ".join(str(v or "").split())[: _MAX[papel]]


def _numero_do_ponto(v: Any) -> float | None:
    """Aceita número, `"1234.25"` e `"1.234,25"` — e recusa o resto.

    Os três existem porque o mesmo dado chega numérico quando o serviço manda
    cru e formatado quando passa por uma ponte que embeleza números. Um crivo
    que só aceitasse `float` descartaria metade dos gráficos em silêncio.
    Recusa vira `None`, não zero: ponto sem valor SOME; um zero inventado
    desenharia uma barra afirmando «não entrou nada».
    """
    if isinstance(v, bool):
        return None
    if isinstance(v, (int, float)):
        return _finito(float(v))
    t = str(v).strip()
    if not t:
        return None
    if _NUMERO_BR.match(t):
        t = t.replace(".", "").replace(",", ".")
    try:
        n = float(t)
    except ValueError:
        return None
    return _finito(n)


def _finito(n: float) -> float | None:
    """NaN e infinito atravessam `float()` e quebram qualquer desenho — escala,
    eixo, altura. Vale para os dois caminhos (número cru e texto)."""
    return n if n == n and abs(n) != float("inf") else None


_MIN_HEIGHT = re.compile(r"^\s*(\d{1,5})px\s*$")


def _faixa_de_altura(v: Any) -> str | None:
    """`"120px"` → `"media"`. Fora de forma, `None` (o padrão).

    A forma é EXATA (`\\d+px`), não «tem dígito em algum lugar»: varrer o texto
    aceitaria `100%` e `96px; width:9999px`, e um filtro que aceita lixo ensina
    quem escreve o cartão que lixo é aceito.
    """
    if not isinstance(v, str):
        return None
    m = _MIN_HEIGHT.match(v)
    if not m:
        return None
    px = int(m.group(1))
    if px < 60:
        return "baixa"
    return "media" if px < 140 else "alta"


def _host_de(url: str) -> str:
    try:
        return (urlsplit(url or "").hostname or "").lower()
    except ValueError:
        return ""


def _e_nosso(host: str) -> bool:
    """`host` está numa zona de DNS do produto? (`Config.dominios`, inclusive
    subdomínios). UMA definição de «nosso» para as duas perguntas opostas:
    `_nossa()` aceita imagem se for; `_para_autorizar()` recusa destino se for.
    Duas respostas para a mesma pergunta divergem — e a definição certa é a do
    DNS, não uma lista de endereços exatos."""
    nossos = {h.lower().strip() for h in _config.get().dominios if h and h.strip()}
    return any(host == n or host.endswith("." + n) for n in nossos)


def _para_autorizar(bruto: Any) -> tuple[str, str] | None:
    """`(url, host)` de uma autorização em terceiro — ou `None` se não serve.

    É o ÚNICO endereço de terceiro que atravessa o crivo, e as travas são o que
    o separam de um `Action.OpenUrl` (que segue recusado). Um botão anônimo
    apontando para qualquer lugar é phishing com a moldura do produto; aqui o
    endereço não é anônimo:

    1. `https:` e nada mais — `http:` entrega a sessão em claro; `javascript:`,
       `data:` e `intent:` nem são navegação.
    2. Sem credencial embutida (`user:senha@host`) — o truque de fazer
       `banco.com@site-falso` parecer o banco.
    3. Sem porta esquisita e sem IP cru — destino legítimo tem nome e mora na 443.
    4. NUNCA um host do produto — a própria tela viraria o disfarce.
    5. O host volta separado, e desenhá-lo é obrigação do cliente: a pessoa
       lê para onde vai ANTES de tocar. Sem isso as outras travas impedem o
       endereço torto, não o errado.

    Isto NÃO valida que o destino é confiável — impede que a confiança seja
    construída no escuro.
    """
    # Não passa pelo `_txt`: aquele corta em 400, e um endereço de autorização
    # carrega o token do provedor. Cortado, continua um https válido e passa
    # por todas as travas — para uma página que responde «token inválido».
    if not isinstance(bruto, str):
        return None
    url = " ".join(bruto.split())[:_MAX_ENDERECO]
    if not url or len(bruto.strip()) > _MAX_ENDERECO:
        return None  # maior que o teto é RECUSADO, nunca encurtado
    try:
        partes = urlsplit(url)
    except ValueError:
        return None
    if partes.scheme != "https" or not partes.hostname:
        return None
    if "@" in (partes.netloc or ""):
        return None
    if partes.port not in (None, 443):
        return None
    host = partes.hostname.lower()
    if re.fullmatch(r"[0-9.]+", host) or ":" in host:
        return None
    if _e_nosso(host):
        return None
    return url, host


def _nossa(url: str) -> str | None:
    """A URL de uma imagem, ABSOLUTA — ou `None` se ela não é do produto.

    Quem hospeda imagem é o produto, e o serviço guarda só a URL. Endereço de
    outro domínio é recusado, e não é zelo: uma imagem servida pelo terceiro
    faria o aparelho de CADA pessoa que abre a tela bater no servidor dele,
    entregando o IP de quem ela não escolheu contatar.

    Resolve para absoluto porque `/img/chave` funciona no navegador e não
    significa nada num app nativo — lá não existe origem.

    O parsing é rígido, não um `startswith`: `https://dominio.com.br/` começa
    com `https://dominio.com` e passaria sem a barra, e `@` na autoridade
    (`https://mau.example@sub.dominio.com/x`) é o disfarce que comparação de
    texto não pega.
    """
    url = (url or "").strip()
    if not url:
        return None
    base = (_config.get().base_de_imagens or "").rstrip("/")
    if url.startswith("/img/"):
        return f"{base}{url}"
    try:
        partes = urlsplit(url)
    except ValueError:
        return None
    if partes.scheme != "https" or not partes.hostname:
        return None
    if "@" in (partes.netloc or ""):
        return None
    if partes.port not in (None, 443):
        return None
    return url if _e_nosso(partes.hostname.lower()) else None


def _formato_do_documento(tipo: str, nome: str) -> str:
    """`application/pdf` → `pdf`; `image/png` → `imagem`; o resto → `outro`.
    Só imagem RASTER é `imagem`: um SVG servido em linha executa script na
    origem de quem o serve, então ele é `outro` — baixa, não desenha."""
    t = (tipo or "").lower().split(";")[0].strip()
    n = (nome or "").lower()
    if t == "application/pdf" or n.endswith(".pdf"):
        return "pdf"
    if t in ("image/png", "image/jpeg", "image/gif", "image/webp") or n.endswith(
        (".png", ".jpg", ".jpeg", ".gif", ".webp")
    ):
        return "imagem"
    return "outro"


def _tamanho(v: Any) -> int | None:
    """Bytes, como número — aceitando `"12.345"`, que é como uma ponte que
    formata números entrega um inteiro. Só os dígitos contam."""
    if isinstance(v, bool):
        return None
    if isinstance(v, (int, float)):
        return int(v) if v >= 0 else None
    if isinstance(v, str):
        digitos = "".join(ch for ch in v if ch.isdigit())
        return int(digitos) if digitos else None
    return None


def _enfase(acao: Any) -> str:
    """A HIERARQUIA de um botão: qual é o gesto principal, qual desfaz algo.

    Não é a cor entrando pela porta dos fundos: `color` do `TextBlock` é lido e
    descartado porque nomeia TINTA; aqui o serviço diz «este é o gesto
    principal» e «este destrói algo», e qual violeta ou qual vermelho desenha
    isso é do cliente. `mode: "secondary"` é o nível quieto (um link). `style`
    vence `mode` quando os dois vêm: «destrói algo» é mais importante de dizer
    do que «é secundário». Valor desconhecido cai em `padrao`, nunca some.
    """
    if not isinstance(acao, dict):
        return "padrao"
    if acao.get("style") in _ENFASES:
        return _ENFASES[acao["style"]]
    if acao.get("mode") == "secondary":
        return "discreta"
    return "padrao"


def _icone_de_acao(acao: Any) -> str | None:
    """A small closed vocabulary of semantic action icons."""
    if not isinstance(acao, dict):
        return None
    return {"delete": "lixeira", "trash": "lixeira", "lixeira": "lixeira"}.get(
        acao.get("okmigoIcone")
    )


def _confirmacao_de_acao(acao: Any) -> dict[str, str] | None:
    """Confirmação declarativa, sem HTML e sem código executável."""
    if not isinstance(acao, dict) or not isinstance(acao.get("okmigoConfirmacao"), dict):
        return None
    bruto = acao["okmigoConfirmacao"]
    titulo = _txt(bruto.get("titulo"), "titulo")
    mensagem = _txt(bruto.get("mensagem"))
    confirmar = _txt(bruto.get("confirmar"), "titulo")[:40]
    cancelar = _txt(bruto.get("cancelar"), "titulo")[:40]
    if not titulo or not mensagem or not confirmar or not cancelar:
        return None
    return {
        "titulo": titulo,
        "mensagem": mensagem,
        "confirmar": confirmar,
        "cancelar": cancelar,
    }


def _consulta_de_acao(acao: Any) -> dict[str, Any] | None:
    """Rebuild one read-only Execute action for a button or a table row."""
    if not isinstance(acao, dict) or acao.get("type") != "Action.Execute":
        return None
    dados = acao.get("data")
    operacao = (
        _txt(dados.get("operacao"), "titulo")[:60]
        if isinstance(dados, dict)
        else ""
    )
    titulo = _txt(acao.get("title"), "titulo")[:40]
    if not operacao or not titulo:
        return None
    if _leituras.get() is not None and operacao not in _leituras.get():
        raise _Erro(
            f"o cartão manda consultar '{operacao}', que não é uma "
            "operação de leitura deste serviço"
        )
    saida = {"titulo": titulo, "consultar": operacao, "enfase": _enfase(acao)}
    icone = _icone_de_acao(acao)
    if icone:
        saida["icone"] = icone
    confirmacao = _confirmacao_de_acao(acao)
    if confirmacao:
        saida["confirmacao"] = confirmacao
    return saida


def _alvos_de_toggle(acao: Any) -> list[dict]:
    """Os alvos de um `Action.ToggleVisibility` — a mesma forma (`{id, mostrar}`)
    venha de um botão ou do `selectAction` de uma caixa. `mostrar: None` é a
    alternância cega; booleano é o sinal explícito."""
    if not isinstance(acao, dict) or acao.get("type") != "Action.ToggleVisibility":
        return []
    alvos = []
    for t in acao.get("targetElements") or []:
        if isinstance(t, str):
            alvos.append({"id": _txt(t, "titulo")[:60], "mostrar": None})
        elif isinstance(t, dict) and t.get("elementId"):
            alvos.append(
                {
                    "id": _txt(t["elementId"], "titulo")[:60],
                    "mostrar": bool(t.get("isVisible")),
                }
            )
    return alvos


def _um(no: Any, contador: list[int]) -> dict | None:
    """Reconstrói UM elemento — e, se ele CAIR, entrega o `fallback` do autor.

    ⭐ **O `fallback` vale para QUALQUER queda, não só para tipo desconhecido**
    (11/09). Antes ele era consultado em dois lugares: no tipo que não
    conhecemos e na imagem de fora. Mas a queda mais comum desta plataforma não
    é «não conheço esse tipo» — é **«o elemento veio vazio»**: a tabela com só o
    cabeçalho porque a lista não repetiu nada, a escolha sem opção válida.
    Nesses casos o elemento sumia **mesmo com o autor tendo dito o que pôr no
    lugar**.

    ⛔ E a promessa já estava escrita para quem integra: *«elemento fora dessa
    lista some — a menos que você diga o que aparece no lugar, com o `fallback`
    do próprio schema. Use-o»*. Ela só era verdade para metade dos casos, e a
    metade em que falhava é a que acontece todo dia: um negócio sem agendamento
    hoje abria a tela sem a tabela e **sem nenhuma frase explicando o vazio**.

    ⚠️ **O `fallback` não é um atalho para dentro:** ele volta por aqui, então
    passa pelo mesmo crivo. Um fallback proibido cai igual — e cai com o
    `fallback` DELE, se tiver. O `contador` é quem impede a corrente infinita.

    ⚠️ A imagem de fora segue tratando o `fallback` por conta própria, e não é
    redundância: ela não CAI — vira `sem_imagem`, um marcador que preserva a
    altura da linha. Sem aquele ramo, quem declarou alternativa receberia o
    marcador em vez dela.
    """
    saida = _reconstruir(no, contador)
    if saida is not None or not isinstance(no, dict):
        return saida
    alternativa = no.get("fallback")
    if isinstance(alternativa, dict):
        return _um(alternativa, contador)
    return None


def _reconstruir(no: Any, contador: list[int]) -> dict | None:
    """Reconstrói UM elemento. Devolve `None` para o que não conhece.

    Devolver `None` (some) em vez de levantar é a degradação que o schema
    desenhou. Só o estrutural levanta `_Erro`.
    """
    contador[0] += 1
    if contador[0] > MAX_NOS:
        raise _Erro(f"cartão grande demais (mais de {MAX_NOS} elementos)")
    if not isinstance(no, dict):
        return None
    tipo = no.get("type")

    comum = {
        "separador": bool(no.get("separator")),
        "espaco": no["spacing"] if no.get("spacing") in ESPACOS else "default",
        "alinhamento": (
            no["horizontalAlignment"]
            if no.get("horizontalAlignment") in ALINHAMENTOS
            else "left"
        ),
        # `id` e `isVisible` existem para o ToggleVisibility. O id é cortado e
        # não vai a lugar nenhum além do próprio cartão.
        "id": _txt(no.get("id"), "titulo")[:60] or None,
        "visivel": no.get("isVisible") is not False,
    }

    if tipo == "TextBlock":
        texto = _txt(no.get("text"))
        if not texto:
            return None
        return {
            "tipo": "texto",
            **comum,
            "texto": texto,
            "tamanho": no["size"] if no.get("size") in TAMANHOS else "default",
            "peso": no["weight"] if no.get("weight") in PESOS else "default",
            # `color` existe no schema e NÃO é lido: nomeia cores de acento que
            # pintariam a tela. `isSubtle` fica: é hierarquia de leitura.
            "discreto": bool(no.get("isSubtle")),
            "quebra": no.get("wrap") is not False,
        }

    # ── okmigoCalendario: uma grade que não cabe em nó por célula ──────────
    # Vale 1 nó e carrega DADO (eventos); quem desenha o mês é o cliente. O
    # evento é genérico de propósito (`inicio`, `fim`, `titulo`, `detalhe`):
    # com campos do domínio de um serviço, o bloco vira a tela DAQUELE serviço
    # e o segundo não cabe.
    if tipo == "okmigoCalendario":
        eventos = []
        for e in (no.get("eventos") or [])[:_MAX_EVENTOS]:
            if not isinstance(e, dict):
                continue
            inicio = _txt(e.get("inicio"), "titulo")
            titulo = _txt(e.get("titulo"), "titulo")
            if not inicio or not titulo:  # sem início não há onde; sem título, o quê
                continue
            eventos.append(
                {
                    "inicio": inicio,
                    "fim": _txt(e.get("fim"), "titulo"),
                    "titulo": titulo,
                    "detalhe": _txt(e.get("detalhe")),
                    # Evento SEM id continua desenhando — só não aceita ação.
                    # Descartá-lo faria a agenda mentir sobre estar livre.
                    "id": _txt(e.get("id"), "titulo")[:64],
                    "tipo": e["tipo"] if e.get("tipo") in EVENTOS_PARA else "",
                }
            )
        # Um toque abre um FORMULÁRIO; nunca escreve. A confirmação é apertar
        # Salvar. E o serviço nomeia o CAMPO, nunca o VALOR — quem sabe a data
        # é o cliente, que recebeu o toque.
        ao_tocar = None
        bruto_toque = no.get("aoTocarODia")
        if isinstance(bruto_toque, dict):
            preencher = {
                _txt(k, "titulo")[:60]: v
                for k, v in (bruto_toque.get("preencher") or {}).items()
                if v in DADOS_DO_DIA and _txt(k, "titulo")
            }
            mostrar = _txt(bruto_toque.get("mostrar"), "titulo")[:60]
            if mostrar or preencher:
                ao_tocar = {"mostrar": mostrar or None, "preencher": preencher}

        # Ações do EVENTO: dizem a que evento se aplicam (`para`) e fazem UMA de
        # duas coisas — mandam uma operação do contrato (`enviar`) ou abrem um
        # formulário preenchido (`mostrar`/`preencher`). A trava do `Submit`
        # vale igual: operação de fora RECUSA o cartão, em vez de sumir.
        acoes_do_evento = []
        for a in (no.get("acoesDoEvento") or [])[:_MAX_ACOES_DO_EVENTO]:
            if not isinstance(a, dict):
                continue
            para = a.get("para") if a.get("para") in EVENTOS_PARA else ""
            if not para:
                continue
            # `arrastar` não tem título: quem convida ao arrasto é o evento na
            # régua. Gesto desconhecido cai em «tocar», a degradação segura.
            arrasta = a.get("gesto") == "arrastar"
            titulo = _txt(a.get("titulo"), "titulo")[:40]
            if not arrasta and not titulo:
                continue

            op = _txt(a.get("enviar"), "titulo")[:60]
            if op:
                if _escrituras.get() is not None and op not in _escrituras.get():
                    raise _Erro(
                        f"o cartão manda gravar em '{op}', que não é uma "
                        "operação de escrita deste serviço"
                    )
                campos = {
                    _txt(k, "titulo")[:60]: v
                    for k, v in (a.get("campos") or {}).items()
                    if v in DADOS_DO_EVENTO
                    and _txt(k, "titulo")
                    # Num TOQUE não existe destino: `novo_inicio` chegaria vazio.
                    and (arrasta or v not in _DADOS_SO_DE_ARRASTO)
                }
                if not campos:
                    continue
                acoes_do_evento.append(
                    {
                        "titulo": titulo or None,
                        "para": para,
                        "arrasta": arrasta,
                        "enviar": op,
                        "campos": campos,
                    }
                )
                continue

            if arrasta:  # arrastar para um formulário não é gesto nenhum
                continue
            preencher = {
                _txt(k, "titulo")[:60]: v
                for k, v in (a.get("preencher") or {}).items()
                if v in DADOS_DO_EVENTO
                and _txt(k, "titulo")
                and v not in _DADOS_SO_DE_ARRASTO
            }
            mostrar = _txt(a.get("mostrar"), "titulo")[:60]
            if not mostrar and not preencher:
                continue
            acoes_do_evento.append(
                {
                    "titulo": titulo,
                    "para": para,
                    "arrasta": False,
                    "mostrar": mostrar or None,
                    "preencher": preencher,
                }
            )

        return {
            "tipo": "calendario",
            **comum,
            "ao_tocar_o_dia": ao_tocar,
            "acoes_do_evento": acoes_do_evento,
            "vista": no["vista"] if no.get("vista") in VISTAS else "mes",
            "de": _txt(no.get("de"), "titulo"),
            "eventos": eventos,
        }

    if tipo == "Container":
        itens = _muitos(no.get("items"), contador)
        # Caixa que perdeu um campo OBRIGATÓRIO perde os botões: sem isto o
        # formulário fica com «Aceitar» e nada para escolher, e o erro só
        # apareceria vindo do serviço, para quem já apertou. É por CAIXA, não
        # pela tela — a aba de leitura ao lado segue tendo o que dizer.
        if _perdeu_campo_obrigatorio(no.get("items")):
            itens = [i for i in itens if i.get("tipo") != "acoes"]
        saida = {
            "tipo": "caixa",
            **comum,
            "estilo": no["style"] if no.get("style") in ESTILOS else "default",
            "altura": _faixa_de_altura(no.get("minHeight")),
            # `okmigoGrade`: os filhos se arrumam em GRADE, não empilhados. É
            # uma dica de arranjo, não uma medida — quantos cabem por linha é
            # do cliente. Quatro intenções: `true` (grade comum, para números
            # curtos), `"larga"` (cada filho é um cartão inteiro; no máximo
            # dois por linha), `"compacta"` (filhos pequenos — um glifo, um
            # nome curto —, o máximo que couber; é a única que dá duas colunas
            # num telefone), `"etiquetas"` (palavras curtas correndo em linha,
            # cada uma do tamanho do próprio texto). Cliente que não conhece
            # uma palavra desenha grade comum ou empilha; nenhum quebra.
            "grade": (
                no["okmigoGrade"]
                if no.get("okmigoGrade") in ("larga", "compacta", "etiquetas")
                else bool(no.get("okmigoGrade"))
            ),
            "itens": itens,
        }
        # `selectAction`: a caixa INTEIRA vira alvo do toque. Pode alternar
        # conteúdo local ou fazer uma consulta declarada; nunca escreve.
        alvo = _alvos_de_toggle(no.get("selectAction"))
        if alvo:
            saida["ao_tocar"] = {"alvos": alvo}
        else:
            consulta = _consulta_de_acao(no.get("selectAction"))
            if consulta:
                consulta["campos"] = _campos_de(itens)
                saida["ao_tocar"] = consulta
        # `okmigoSobreposto`: a caixa sai do FLUXO e aparece por cima. É
        # intenção («isto não pertence ao fluxo»), não aparência — se vira um
        # diálogo centrado com fundo escurecido é do cliente. Existe porque um
        # formulário dentro de uma célula de 1/7 da tela é inutilizável num
        # telefone, mesmo passando em todo teste.
        if no.get("okmigoSobreposto") is True:
            saida["sobreposto"] = True
        return saida

    if tipo == "ColumnSet":
        colunas = []
        for c in no.get("columns") or []:
            if not isinstance(c, dict):
                continue
            largura = c.get("width")
            colunas.append(
                {
                    "largura": largura if largura in LARGURAS else "stretch",
                    "estilo": c["style"] if c.get("style") in ESTILOS else "default",
                    "altura": _faixa_de_altura(c.get("minHeight")),
                    "itens": _muitos(c.get("items"), contador),
                }
            )
        return {"tipo": "colunas", **comum, "colunas": colunas} if colunas else None

    # ── Table: a grade com colunas ALINHADAS entre linhas ─────────────────
    # `ColumnSet` só tem `auto`/`stretch`, e duas linhas nunca alinham. Aqui as
    # larguras são proporções numéricas, a primeira linha é cabeçalho e a grade
    # aparece. `TableCell` é uma caixa: seus itens passam pelos mesmos
    # construtores, e um `Submit` dentro dela escopa os campos da célula.
    if tipo == "Table":
        colunas = []
        for c in (no.get("columns") or [])[:_MAX_COLUNAS]:
            w = c.get("width") if isinstance(c, dict) else None
            colunas.append(
                {
                    "largura": int(w)
                    if isinstance(w, (int, float)) and not isinstance(w, bool) and w > 0
                    else 1
                }
            )
        linhas = []
        for r in (no.get("rows") or [])[:_MAX_LINHAS]:
            if not isinstance(r, dict) or r.get("type") != "TableRow":
                continue
            celulas = []
            for c in (r.get("cells") or [])[: (len(colunas) or _MAX_COLUNAS)]:
                if not isinstance(c, dict) or c.get("type") != "TableCell":
                    continue
                contador[0] += 1  # a célula conta como nó: é uma caixa
                celulas.append({"itens": _muitos(c.get("items"), contador)})
            if celulas:
                linha: dict[str, Any] = {"celulas": celulas}
                acao = _consulta_de_acao(r.get("selectAction"))
                if acao:
                    acao["campos"] = _campos_de(
                        [item for celula in celulas for item in celula["itens"]]
                    )
                    linha["acao"] = acao
                linhas.append(linha)
        # Cabeçalho sem linha de dado NÃO é tabela — é um título que promete
        # dado e não entrega. Some, como a lista suspensa sem opção some.
        cabecalho = no.get("firstRowAsHeader") is not False
        if not linhas or (cabecalho and len(linhas) < 2):
            return None
        if not colunas:
            colunas = [{"largura": 1}] * max(len(r["celulas"]) for r in linhas)
        return {
            "tipo": "tabela",
            **comum,
            "colunas": colunas,
            "cabecalho": cabecalho,
            "grade": no.get("showGridLines") is not False,
            "linhas": linhas,
        }

    if tipo == "FactSet":
        fatos = [
            {
                "titulo": _txt(f.get("title"), "titulo"),
                "valor": _txt(f.get("value"), "valor"),
            }
            for f in (no.get("facts") or [])
            if isinstance(f, dict) and str(f.get("title") or "").strip()
        ]
        return {"tipo": "fatos", **comum, "fatos": fatos} if fatos else None

    if tipo == "Image":
        url = _nossa(no.get("url"))
        if url is None:
            # Não some: vira um MARCADOR desenhado pelo cliente. Uma imagem que
            # some deixa cada item de uma lista com altura diferente, e a tela
            # parece quebrada justamente para quem tem menos foto. O marcador é
            # do cliente porque um desenho vindo do manifesto seria recusado
            # pela mesma regra que recusou a imagem. Quem declarou `fallback`
            # continua mandando.
            alt = no.get("fallback")
            if isinstance(alt, dict):
                return _um(alt, contador)
            return {
                "tipo": "sem_imagem",
                **comum,
                "altura": no["height"] if no.get("height") in ALTURAS_IMG else "medium",
                "alt": _txt(no.get("altText"), "titulo"),
            }
        return {
            "tipo": "imagem",
            **comum,
            "url": url,
            "altura": no["height"] if no.get("height") in ALTURAS_IMG else "medium",
            # `altText` é o único texto que a imagem carrega — é o que um
            # leitor de tela lê.
            "alt": _txt(no.get("altText"), "titulo"),
        }

    if tipo == "okmigoEtiqueta":
        texto = _txt(no.get("texto"), "titulo")
        if not texto:
            return None
        tom = no.get("tom") if no.get("tom") in _TONS_DE_ETIQUETA else "neutro"
        return {
            "tipo": "etiqueta",
            **comum,
            "texto": texto,
            "tom": tom,
            "status": no.get("status") is True,
        }

    if tipo == "okmigoGaleria":
        imagens = []
        for imagem in (no.get("imagens") or [])[:_MAX_IMAGENS]:
            pronta = _um(imagem, contador)
            if pronta and pronta.get("tipo") in {"imagem", "sem_imagem"}:
                imagens.append(pronta)
        if not imagens:
            return None
        return {
            "tipo": "galeria",
            **comum,
            "rotulo": _txt(no.get("rotulo"), "titulo") or "Galeria de imagens",
            "imagens": imagens,
        }

    if tipo == "okmigoLinhaDoTempo":
        etapas = []
        for etapa in (no.get("etapas") or [])[:_MAX_ETAPAS]:
            if not isinstance(etapa, dict):
                continue
            titulo = _txt(etapa.get("titulo"), "titulo")
            if not titulo:
                continue
            etapas.append(
                {
                    "titulo": titulo,
                    "detalhe": _txt(etapa.get("detalhe")),
                    "estado": etapa.get("estado")
                    if etapa.get("estado") in _ESTADOS_DA_ETAPA
                    else "futura",
                }
            )
        if not etapas:
            return None
        return {
            "tipo": "linha_do_tempo",
            **comum,
            "rotulo": _txt(no.get("rotulo"), "titulo") or "Andamento",
            "etapas": etapas,
        }

    if tipo == "okmigoBarraDeValor":
        valor = _numero_do_ponto(no.get("valor"))
        de = _numero_do_ponto(no.get("de"))
        if valor is None or de is None or de <= 0 or de > _MAX_PROGRESSO:
            return None
        return {
            "tipo": "barra_valor",
            **comum,
            "rotulo": _txt(no.get("rotulo"), "titulo"),
            "valor": max(0.0, min(de, valor)),
            "de": de,
            "texto": _txt(no.get("texto"), "titulo"),
            "tom": no.get("tom")
            if no.get("tom") in _TONS_DE_ETIQUETA
            else "neutro",
        }

    if tipo in ("Input.Text", "Input.Number"):
        # O `id` é obrigatório: é a CHAVE de ESTADO no cliente. Um campo sem id
        # é um texto que a pessoa digita e que não chega a lugar nenhum.
        campo_id = _txt(no.get("id"), "titulo")[:60]
        if not campo_id:
            return None
        formato_padrao = "numero" if tipo == "Input.Number" else "texto"
        formato = no.get("okmigoFormato")
        if formato not in _FORMATOS_DO_CAMPO:
            formato = formato_padrao
        # Formatos numéricos não podem transformar texto arbitrário em número.
        if formato in {"moeda", "unidade"} and tipo != "Input.Number":
            formato = formato_padrao
        passo = _numero_do_ponto(no.get("okmigoPasso"))
        if passo is not None and passo <= 0:
            passo = None
        return {
            "tipo": "campo",
            **comum,
            # `campo` é o NOME NO SERVIÇO e pode se repetir entre caixas (um
            # formulário por dia, todos gravando em `quando`); o `id` tem de ser
            # único no cartão para o estado não colidir. O escopo do `Submit`
            # (`_campos_de`) garante que só os da mesma caixa viajam juntos.
            "campo": _txt(no.get("campo"), "titulo")[:60] or campo_id,
            "rotulo": _txt(no.get("label"), "titulo"),
            # `value` é o que já está gravado — o formulário de CORREÇÃO.
            "valor": _txt(no.get("value")),
            "dica": _txt(no.get("placeholder"), "titulo"),
            "somente_leitura": bool(no.get("okmigoSomenteLeitura")),
            # NÚMERO É UM TIPO: «62.900» digitado num campo de texto vira 62,9
            # do outro lado, sem erro. O campo diz que é número e o cliente
            # impede na digitação — validar depois não devolve o dado perdido.
            "formato": formato,
            "linhas": 4 if no.get("isMultiline") else 1,
            "obrigatorio": bool(no.get("isRequired")),
            # `maxLength` é do autor, mas o teto é do produto.
            "max": min(int(no["maxLength"]), _MAX["texto"])
            if isinstance(no.get("maxLength"), int) and no["maxLength"] > 0
            else _MAX["texto"],
            # Só do `Input.Number`, e só quando declarados: limite inventado
            # recusaria um valor legítimo.
            "min": no["min"] if isinstance(no.get("min"), (int, float)) else None,
            "max_valor": no["max"] if isinstance(no.get("max"), (int, float)) else None,
            "controle": "quantidade"
            if tipo == "Input.Number" and no.get("okmigoControle") == "quantidade"
            else None,
            "passo": passo,
            "unidade": _txt(no.get("okmigoUnidade"), "titulo")[:20],
            "moeda": (
                _txt(no.get("okmigoMoeda"), "titulo")[:3].upper()
                if formato == "moeda"
                else ""
            ),
        }

    if tipo == "Input.ChoiceSet":
        # A lista existe porque ela NÃO PODE SER CHUTADA: as opções são as que
        # o serviço declarou, e o valor que volta é sempre uma delas.
        campo_id = _txt(no.get("id"), "titulo")[:60]
        if not campo_id:
            return None

        # ⭐ **`okmigoQuemOpera`: as opções são QUEM OPERA aquele negócio, e
        # quem as preenche é o PRODUTO.** Existe porque a alternativa obriga o
        # serviço a conhecer o quadro de pessoal do cliente dele — e o produto
        # não entrega isso. Aqui ele declara o buraco; o nome escolhido volta
        # no Submit como qualquer outro valor, e é só isso que ele recebe.
        #
        # ⛔ **As `choices` declaradas são IGNORADAS quando a dica está
        # presente.** Não é rigor: aceitar as duas coisas faria a lista do
        # autor conviver com a do produto, e a tela ofereceria gente que não
        # opera ao lado de gente que opera — sem nada na tela distinguindo.
        #
        # ⚠️ E ela força o ESTRITO. Um typeahead livre com nomes de pessoal
        # seria um campo de texto com sugestão: quem digitasse um nome de fora
        # passaria. A dica existe justamente para isso não acontecer.
        quem_opera = no.get("okmigoQuemOpera") is True

        opcoes = []
        for escolha in ([] if quem_opera else (no.get("choices") or []))[:_MAX_OPCOES]:
            if not isinstance(escolha, dict):
                continue
            # `value` é o que VIAJA; `title` é o que a pessoa lê. Os dois são
            # obrigatórios e não se confundem.
            valor = _txt(escolha.get("value"))[: _MAX["texto"]]
            rotulo = _txt(escolha.get("title"), "titulo")
            if not valor or not rotulo:
                continue
            # `okmigoNota`: a linha de apoio de uma opção (só em fichas).
            # `okmigoIcone`: o glifo — texto curto (um emoji), nunca imagem;
            # cortado em 12 porque um emoji com modificador chega a 7 pontos de
            # código e o resto seria texto disfarçado.
            opcoes.append(
                {
                    "valor": valor,
                    "rotulo": rotulo,
                    "nota": _txt(escolha.get("okmigoNota"), "titulo"),
                    "icone": _txt(escolha.get("okmigoIcone"), "titulo")[:12],
                }
            )
        # `style: "filtered"` sozinho é o typeahead LIVRE: a lista sugere, mas
        # o valor não fica restrito a ela (um horário fora da grade de 30 min).
        # Com `okmigoEstrito: true`, é a BUSCA que filtra e só aceita o que está
        # na lista — sai como o tipo ESTRITO com `forma: "busca"`, então um
        # cliente que não conheça a forma desenha a lista suspensa e perde o
        # filtro, nunca a trava. São garantias diferentes, e por isso tipos
        # diferentes na saída.
        if no.get("style") == "filtered" and no.get("okmigoEstrito") is True:
            pass  # cai no caminho ESTRITO abaixo, com forma "busca"
        elif quem_opera:
            pass  # ⛔ idem: `okmigoQuemOpera` nunca é livre, com ou sem estilo
        elif no.get("style") == "filtered":
            buscar = _txt(no.get("okmigoBuscar"), "titulo")[:60]
            if buscar and _leituras.get() is not None and buscar not in _leituras.get():
                raise _Erro(
                    f"o cartão manda autocompletar em '{buscar}', que não é uma "
                    "operação de leitura deste serviço"
                )
            return {
                "tipo": "escolha_livre",
                **comum,
                "campo": _txt(no.get("campo"), "titulo")[:60] or campo_id,
                "rotulo": _txt(no.get("label"), "titulo"),
                # Aqui `value` é o que já estava gravado, mesmo fora das sugestões.
                "valor": _txt(no.get("value"))[: _MAX["texto"]],
                "dica": _txt(no.get("placeholder"), "titulo"),
                "opcoes": opcoes,
                "obrigatorio": bool(no.get("isRequired")),
                "buscar": buscar or None,
            }

        # Lista vazia derruba o CAMPO (e a caixa em volta perde os botões — ver
        # `_perdeu_campo_obrigatorio`), não a tela: lista vazia é o caso normal
        # de «nada esperando», e a aba ao lado segue tendo o que dizer.
        #
        # ⚠️ **Com `okmigoQuemOpera` a lista vazia é o ESTADO ESPERADO aqui** —
        # quem a preenche é o produto, depois deste crivo. Derrubar o campo
        # apagaria justamente o que a dica pede. ⛔ Quem hospeda o crivo e NÃO
        # sabe preencher deve tratar a lista vazia como sempre: campo sem opção
        # não se desenha.
        if not opcoes and not quem_opera:
            return None

        multipla = no.get("isMultiSelect") is True
        crus = [v.strip() for v in _txt(no.get("value")).split(",") if v.strip()]
        validos = [o["valor"] for o in opcoes]
        selecionados = [v for v in crus if v in validos]
        if not multipla:
            selecionados = selecionados[:1]

        regras = []
        for regra in (no.get("okmigoAoAlterar") or [])[:_MAX_OPCOES]:
            if not isinstance(regra, dict) or regra.get("valor") not in validos:
                continue
            bruto_alvos = regra.get("alvos")
            alvos_validos = [
                alvo
                for alvo in (bruto_alvos if isinstance(bruto_alvos, list) else [])[:60]
                if isinstance(alvo, dict) and isinstance(alvo.get("isVisible"), bool)
            ]
            alvos = _alvos_de_toggle(
                {"type": "Action.ToggleVisibility", "targetElements": alvos_validos}
            )
            if alvos:
                regras.append({"valor": regra["valor"], "alvos": alvos})

        return {
            "tipo": "escolha",
            **comum,
            # `style: "expanded"` (do próprio schema): as opções viram FICHAS
            # tocáveis em vez de lista suspensa. O valor continua sendo de um
            # `Input` — viaja no Submit, escopado, recusado se fora das opções.
            # Nenhuma fronteira nova; só o desenho muda. E é CAMPO em tipo que
            # existe: cliente velho ignora e desenha a lista de sempre.
            "forma": (
                "cartoes"
                if no.get("style") == "expanded"
                else "busca"
                if no.get("style") == "filtered"
                else "lista"
            ),
            "campo": _txt(no.get("campo"), "titulo")[:60] or campo_id,
            "rotulo": _txt(no.get("label"), "titulo"),
            # `value` só é aceito se for UMA das opções: um padrão fora da lista
            # abriria o formulário já inválido.
            "valor": ",".join(selecionados),
            "dica": _txt(no.get("placeholder"), "titulo"),
            "opcoes": opcoes,
            "obrigatorio": bool(no.get("isRequired")),
            "multipla": multipla,
            "controle": "alternancia"
            if no.get("okmigoControle") == "alternancia"
            and {o["valor"] for o in opcoes} == {"true", "false"}
            else None,
            **({"ao_alterar": regras} if regras else {}),
            # ⭐ O buraco a preencher, marcado na saída: quem hospeda o crivo
            # põe aqui quem opera aquele negócio. Ausente = escolha comum.
            **({"quem_opera": True} if quem_opera else {}),
        }

    # ── okmigoArquivo: a ENTRADA de um arquivo (o schema não tem Input.File) ──
    # O serviço declara o campo, o que aceita e o teto; o cliente abre o
    # seletor da plataforma e o produto passa o arquivo ao serviço sem guardar
    # byte. `maxBytes` só pode APERTAR o teto do produto.
    if tipo == "okmigoArquivo":
        campo_id = _txt(no.get("id"), "titulo")[:60]
        if not campo_id:
            return None
        aceita = [f for f in (no.get("aceita") or []) if f in FORMATOS_DE_ARQUIVO]
        teto = _config.get().anexo_max_bytes
        declarado = no.get("maxBytes")
        if isinstance(declarado, int) and 0 < declarado < teto:
            teto = declarado
        return {
            "tipo": "arquivo",
            **comum,
            "campo": _txt(no.get("campo"), "titulo")[:60] or campo_id,
            "rotulo": _txt(no.get("label"), "titulo"),
            "aceita": sorted(set(aceita)),
            "max_bytes": teto,
            "obrigatorio": bool(no.get("isRequired")),
        }

    # ── okmigoDocumento: um arquivo que o serviço GUARDA, para ver ou baixar ──
    # O nó não carrega o arquivo: carrega o nome de uma operação de LEITURA do
    # contrato e o pedido que a identifica. Quem busca os bytes é o cliente,
    # por uma rota do produto — o aparelho nunca alcança o terceiro. A trava
    # do `Submit` com o sinal trocado: `ler.operacao` fora das leituras
    # declaradas recusa o cartão inteiro.
    if tipo == "okmigoDocumento":
        ler = no.get("ler")
        op = _txt(ler.get("operacao"), "titulo")[:60] if isinstance(ler, dict) else ""
        titulo = _txt(no.get("titulo"), "titulo")
        nome = _txt(no.get("nome"), "titulo")
        if not op or not (titulo or nome):
            return None
        if _leituras.get() is not None and op not in _leituras.get():
            raise _Erro(
                f"o cartão manda ler um documento em '{op}', que não é uma "
                "operação de leitura deste serviço"
            )
        pedido = ler.get("pedido") if isinstance(ler.get("pedido"), dict) else {}
        # Só valores ESCALARES, cortados: o pedido volta do cliente tal qual.
        pedido = {
            _txt(k, "titulo")[:60]: (
                v if isinstance(v, (int, float, bool)) else _txt(v)
            )
            for k, v in pedido.items()
            if _txt(k, "titulo") and isinstance(v, (str, int, float, bool))
        }
        tipo_mime = _txt(no.get("tipo"), "titulo")
        return {
            "tipo": "documento",
            **comum,
            "titulo": titulo or nome,
            "nome": nome,
            "formato": _formato_do_documento(tipo_mime, nome),
            "tamanho": _tamanho(no.get("tamanho")),
            "ler": {"operacao": op, "pedido": pedido},
        }

    # ── okmigoAutorizar: a ida ao terceiro para AUTORIZAR ─────────────────
    # Quem pergunta a senha do banco é o banco, na página dele. Não é um
    # `Action.OpenUrl` com outro nome — as travas de `_para_autorizar` são a
    # diferença, mais: UM por cartão, `motivo` obrigatório (é o que a pessoa
    # lê antes de sair), e o host volta separado para o cliente ESCREVER. O
    # endereço é efêmero (o token do provedor vale minutos): viaja no dado,
    # montado a cada abertura, nunca no molde.
    if tipo == "okmigoAutorizar":
        contas = _autorizacoes.get()
        if contas is not None and contas[0] >= _MAX_AUTORIZACOES:
            return None
        alvo = _para_autorizar(no.get("url"))
        rotulo = _txt(no.get("rotulo") or no.get("title"), "titulo")[:40]
        motivo = _txt(no.get("motivo"), "texto")
        if not alvo or not rotulo or not motivo:
            return None
        if contas is not None:
            contas[0] += 1
        url, onde = alvo
        return {
            "tipo": "autorizar",
            **comum,
            "rotulo": rotulo,
            "motivo": motivo,
            "url": url,
            # Separado da URL de propósito: deixar cada cliente extrair o host
            # faria cada um extrair de um jeito — e é onde o disfarce mora.
            "onde": onde,
        }

    # okmigoCopiar: um valor para a área de transferência. Não alcança nada —
    # nem rede, nem escrita. Sem valor, some.
    if tipo == "okmigoCopiar":
        valor = _txt(no.get("valor"))
        rotulo = _txt(no.get("rotulo") or no.get("title"), "titulo")[:40]
        if not valor or not rotulo:
            return None
        return {"tipo": "copiar", **comum, "rotulo": rotulo, "valor": valor}

    # ── okmigoCronometro: o tempo que passa DENTRO do cartão ──────────────
    # Contagem REGRESSIVA de um valor declarado; não alcança nada. NÃO começa
    # sozinho — um cronômetro que arranca ao abrir conta o descanso de quem só
    # está lendo, e dá a quem declara a tela o poder de fazer o aparelho de
    # outra pessoa trabalhar. Sem hora do servidor: sincronia faria 90 s durar
    # horas com um fuso errado.
    if tipo == "okmigoCronometro":
        rotulo = _txt(no.get("rotulo") or no.get("title"), "titulo")[:40]
        segundos = _numero_do_ponto(no.get("segundos"))
        if not rotulo or segundos is None:  # um «iniciar» que conta 0 s não faz nada
            return None
        segundos = int(segundos)
        if segundos < 1 or segundos > _MAX_CRONOMETRO_S:
            return None
        return {"tipo": "cronometro", **comum, "rotulo": rotulo, "segundos": segundos}

    # ── okmigoProgresso: quanto do caminho já andou ───────────────────────
    # Recebe `feito` e `de`, NUNCA uma porcentagem: «4 de 6» é o que a pessoa
    # quer saber («faltam dois»); o % se deriva, o contrário não. `de` tem de
    # ser positivo; `feito` é PRENSADO na faixa — barra cheia é a leitura certa
    # de «acabou», e derrubar o bloco esconderia o progresso inteiro. É tipo
    # NOVO: some num cliente velho, então quem o declara põe o «4 de 6» num
    # `TextBlock` ao lado.
    if tipo == "okmigoProgresso":
        de = _numero_do_ponto(no.get("de"))
        feito = _numero_do_ponto(no.get("feito"))
        if de is None or feito is None or de <= 0 or de > _MAX_PROGRESSO:
            return None
        de, feito = int(de), int(max(0.0, min(float(de), feito)))
        tom = no.get("tom") if no.get("tom") in _TONS_FINANCEIROS else None
        return {
            "tipo": "progresso",
            **comum,
            "rotulo": _txt(no.get("rotulo") or no.get("title"), "titulo")[:40],
            "feito": feito,
            "de": de,
            **({"tom": tom} if tom else {}),
        }

    if tipo == "okmigoCartaoBancario":
        cartoes = []
        for item in (no.get("cartoes") or no.get("cards") or [])[:12]:
            if not isinstance(item, dict):
                continue
            lancamentos = []
            for linha in (item.get("lancamentos") or item.get("linhas") or [])[:12]:
                if not isinstance(linha, dict):
                    continue
                lancamentos.append(
                    {
                        "icone": _txt(linha.get("icone"), "texto")[:8],
                        "titulo": _txt(
                            linha.get("titulo") or linha.get("descricao"), "titulo"
                        )[:80],
                        "subtitulo": _txt(
                            linha.get("subtitulo") or linha.get("detalhe"), "texto"
                        )[:120],
                        "valor": _txt(
                            linha.get("valor") or linha.get("valor_texto"), "texto"
                        )[:40],
                        "semantica": (
                            linha.get("semantica")
                            if linha.get("semantica")
                            in {"positivo", "negativo", "neutro"}
                            else "neutro"
                        ),
                    }
                )
            titulo = _txt(item.get("titulo") or item.get("nome"), "titulo")[:40]
            if not titulo:
                continue
            cartoes.append(
                {
                    "id": _txt(item.get("id"), "valor")[:80]
                    or f"cartao-{len(cartoes) + 1}",
                    "titulo": titulo,
                    "tipo": _txt(item.get("tipo"), "titulo")[:24],
                    "bandeira": _txt(item.get("bandeira"), "titulo")[:24],
                    "numero": _txt(item.get("numero"), "texto")[:40],
                    "titular": _txt(item.get("titular"), "texto")[:50],
                    "validade": _txt(item.get("validade"), "texto")[:16],
                    "tom": (
                        item.get("tom")
                        if item.get("tom") in _TONS_FINANCEIROS
                        else "principal"
                    ),
                    "fatura_rotulo": _txt(item.get("fatura_rotulo"), "titulo")[:40],
                    "fatura": _txt(item.get("fatura"), "texto")[:40],
                    "limite_rotulo": _txt(item.get("limite_rotulo"), "titulo")[:40],
                    "limite": _txt(item.get("limite"), "texto")[:40],
                    "progresso_rotulo": _txt(item.get("progresso_rotulo"), "titulo")[
                        :40
                    ],
                    "progresso_texto": _txt(item.get("progresso_texto"), "texto")[:80],
                    "progresso_feito": int(
                        max(
                            0,
                            min(
                                100, _numero_do_ponto(item.get("progresso_feito")) or 0
                            ),
                        )
                    ),
                    "progresso_de": int(
                        max(
                            1,
                            min(100, _numero_do_ponto(item.get("progresso_de")) or 100),
                        )
                    ),
                    "lancamentos": lancamentos,
                }
            )
        if not cartoes:
            return None
        return {"tipo": "cartao_bancario", **comum, "cartoes": cartoes}

    if tipo == "okmigoDistribuicao":
        itens = []
        for item in (no.get("itens") or no.get("items") or [])[:12]:
            if not isinstance(item, dict):
                continue
            valor = _numero_do_ponto(item.get("valor"))
            if valor is None:
                continue
            itens.append(
                {
                    "rotulo": _txt(item.get("rotulo") or item.get("titulo"), "titulo")[
                        :50
                    ],
                    "valor": max(0.0, float(valor)),
                    "texto": _txt(item.get("texto") or item.get("percentual"), "texto")[
                        :24
                    ],
                    "tom": (
                        item.get("tom")
                        if item.get("tom") in _TONS_FINANCEIROS
                        else "principal"
                    ),
                }
            )
        if not itens:
            return None
        return {
            "tipo": "distribuicao",
            **comum,
            "titulo": _txt(no.get("titulo") or no.get("title"), "titulo")[:80],
            "itens": itens,
        }

    if tipo == "okmigoListaFinanceira":
        filtros_validos = {"todas", "entradas", "saidas"}
        filtros = [
            f
            for f in (no.get("filtros") or ["todas"])
            if isinstance(f, str) and f in filtros_validos
        ][:3]
        itens = []
        for item in (no.get("itens") or no.get("items") or [])[:120]:
            if not isinstance(item, dict):
                continue
            titulo = _txt(item.get("titulo") or item.get("descricao"), "titulo")[:80]
            if not titulo:
                continue
            itens.append(
                {
                    "id": _txt(item.get("id"), "valor")[:80],
                    "grupo": _txt(
                        item.get("grupo") or item.get("grupo_data"), "titulo"
                    )[:40],
                    "tipo": item.get("tipo")
                    if item.get("tipo") in filtros_validos
                    else "todas",
                    "icone": _txt(item.get("icone"), "texto")[:8],
                    "titulo": titulo,
                    "subtitulo": _txt(
                        item.get("subtitulo") or item.get("detalhe"), "texto"
                    )[:120],
                    "valor": _txt(
                        item.get("valor") or item.get("valor_texto"), "texto"
                    )[:40],
                    "semantica": (
                        item.get("semantica")
                        if item.get("semantica") in {"positivo", "negativo", "neutro"}
                        else "neutro"
                    ),
                }
            )
        if not itens:
            return None
        return {
            "tipo": "lista_financeira",
            **comum,
            "titulo": _txt(no.get("titulo") or no.get("title"), "titulo")[:80],
            "busca": bool(no.get("busca")),
            "filtros": filtros or ["todas"],
            "itens": itens,
        }

    # ── okmigoGrafico: a grade vira DESENHO ───────────────────────────────
    # Barras ou linha, séries com cor SEMÂNTICA. Não existe pizza: julga-se
    # magnitude melhor por posição e comprimento do que por ângulo e área —
    # 23% e 27% são indistinguíveis como fatia e óbvios como barra. `valores`
    # casa com `series` por índice; ponto faltando vira buraco honesto, nunca
    # série deslocada. Gráfico sem ponto some, como a tabela só com cabeçalho.
    if tipo == "okmigoGrafico":
        forma = no.get("forma") if no.get("forma") in _FORMAS_DE_GRAFICO else "barras"
        series = []
        for sr in (no.get("series") or [])[:_MAX_SERIES]:
            if not isinstance(sr, dict):
                continue
            rotulo = _txt(sr.get("rotulo") or sr.get("title"), "titulo")[:24]
            if not rotulo:
                continue
            series.append(
                {
                    "rotulo": rotulo,
                    "cor": sr["cor"]
                    if sr.get("cor") in _CORES_DO_GRAFICO
                    else "neutro",
                }
            )
        if not series:
            return None
        pontos = []
        for pt in (no.get("pontos") or [])[:_MAX_PONTOS]:
            if not isinstance(pt, dict):
                continue
            contador[0] += 1  # cada ponto conta como nó, igual à célula
            rotulo = _txt(pt.get("rotulo"), "titulo")[:16]
            crus = pt.get("valores")
            crus = crus if isinstance(crus, list) else [crus]
            valores = [_numero_do_ponto(v) for v in crus[: len(series)]]
            valores += [None] * (len(series) - len(valores))
            if all(v is None for v in valores):
                continue
            pontos.append({"rotulo": rotulo, "valores": valores})
        if not pontos:
            return None
        return {
            "tipo": "grafico",
            **comum,
            "forma": forma,
            "titulo": _txt(no.get("titulo") or no.get("title"), "titulo")[:80],
            "series": series,
            "pontos": pontos,
        }

    if tipo == "ActionSet":
        # Três ações, e só três. `Action.ToggleVisibility` não ALCANÇA nada —
        # mostra e esconde o que já está no cartão; é o que permite abas e
        # telas que se sucedem sem abrir fronteira. `Action.Submit` é a
        # escrita: quem preencheu e apertou já confirmou. `Action.Execute` é
        # a consulta: leva os campos da própria caixa a uma operação de
        # LEITURA e recebe outro cartão, reconstruído por este mesmo crivo.
        # O botão NÃO carrega
        # URL — nomeia uma OPERAÇÃO do contrato, e operação fora do declarado
        # RECUSA a tela inteira em vez de sumir (botão que aparece e não grava
        # faz a pessoa culpar o produto, e pior: ela aperta achando que
        # gravou). `Action.OpenUrl` fica de fora: ação nomeia capacidade, nunca
        # endereço.
        botoes = []
        brutas = no.get("actions") or []
        if no.get("okmigoMenu") is True:
            brutas = brutas[:10]
        for a in brutas:
            if not isinstance(a, dict):
                continue
            if a.get("type") == "Action.Execute":
                consulta = _consulta_de_acao(a)
                if consulta:
                    botoes.append(consulta)
                continue
            if a.get("type") == "Action.Submit":
                dados = a.get("data")
                op = (
                    _txt(dados.get("operacao"), "titulo")[:60]
                    if isinstance(dados, dict)
                    else ""
                )
                titulo = _txt(a.get("title"), "titulo")[:40]
                if not op or not titulo:
                    continue
                if _escrituras.get() is not None and op not in _escrituras.get():
                    raise _Erro(
                        f"o cartão manda gravar em '{op}', que não é uma "
                        "operação de escrita deste serviço"
                    )
                botao = {"titulo": titulo, "enviar": op, "enfase": _enfase(a)}
                icone = _icone_de_acao(a)
                if icone:
                    botao["icone"] = icone
                confirmacao = _confirmacao_de_acao(a)
                if confirmacao:
                    botao["confirmacao"] = confirmacao
                # `okmigoAposEnviar`: a transição DEPOIS de salvar — um
                # `ToggleVisibility` com estados booleanos EXPLÍCITOS. Sem URL,
                # sem segunda escrita, sem alternância cega. É o que faz telas
                # em etapas avançarem ao gravar, sem que «uma tela por etapa»
                # estoure o teto de nós.
                depois = a.get("okmigoAposEnviar")
                if (
                    isinstance(depois, dict)
                    and depois.get("type") == "Action.ToggleVisibility"
                ):
                    bruto = depois.get("targetElements")
                    alvos = [
                        t
                        for t in (bruto if isinstance(bruto, list) else [])[:60]
                        if isinstance(t, dict) and isinstance(t.get("isVisible"), bool)
                    ]
                    alvos = _alvos_de_toggle({**depois, "targetElements": alvos})
                    if alvos:
                        botao["apos_enviar"] = alvos
                botoes.append(botao)
                continue
            if a.get("type") != "Action.ToggleVisibility":
                continue
            alvos = _alvos_de_toggle(a)
            titulo = _txt(a.get("title"), "titulo")[:40]
            if titulo and alvos:
                botoes.append({"titulo": titulo, "alvos": alvos, "enfase": _enfase(a)})
        if not botoes:
            return None
        saida = {"tipo": "acoes", **comum, "botoes": botoes}
        # `okmigoRodape`: o bloco de botões fica PRESO ao pé da tela enquanto a
        # caixa dele estiver à vista — o gesto que fecha a tela sempre ao
        # alcance. Intenção, como tudo: como vira barra fixa é do cliente.
        if no.get("okmigoRodape") is True:
            saida["rodape"] = True
        if no.get("okmigoMenu") is True:
            saida["menu"] = True
            saida["rotulo"] = (
                _txt(no.get("okmigoRotulo"), "titulo")[:40] or "Mais opções"
            )
        if no.get("okmigoSegmentado") is True:
            saida["segmentado"] = True
        if no.get("okmigoExpansivel") is True:
            saida["expansivel"] = True
        return saida

    # Desconhecido: cai. ⭐ O `fallback` é tentado por QUEM CHAMA (`_um`), e
    # não mais aqui — assim ele vale para toda queda, e não só para esta.
    return None


def _perdeu_campo_obrigatorio(itens: Any) -> bool:
    """Algum campo `isRequired` desta caixa não sobreviveu ao crivo?

    Olha o BRUTO, não a saída: um campo derrubado não aparece nela, e é a
    ausência que interessa. Só os filhos diretos — uma caixa aninhada responde
    por si. Hoje só a lista ESTRITA pode cair por falta de dado; a `filtered`
    (livre) fica de fora porque sem opção ainda funciona como texto.
    """
    for filho in itens or []:
        if not isinstance(filho, dict) or not filho.get("isRequired"):
            continue
        if filho.get("type") != "Input.ChoiceSet" or filho.get("style") == "filtered":
            continue
        validas = [
            e
            for e in (filho.get("choices") or [])
            if isinstance(e, dict) and _txt(e.get("value")) and _txt(e.get("title"))
        ]
        if not validas:
            return True
    return False


def _campos_de(itens: list[dict]) -> list[str]:
    """Os `id` (não `campo`!) de Input que moram nesta lista, aninhados.

    É o ESCOPO de um `Action.Submit`: sem ele, o botão mandaria os campos do
    cartão inteiro, e dois formulários independentes não poderiam conviver.
    `id`, não `campo`: o cliente guarda o digitado num mapa único chaveado por
    `id`; escopar pelo `campo` juntaria «quando_c30» e «quando_c31», que
    partilham o nome no serviço de propósito.
    """
    saida: list[str] = []
    for it in itens:
        if not isinstance(it, dict):
            continue
        if it.get("tipo") in (
            "campo",
            "escolha",
            "escolha_livre",
            "arquivo",
        ) and it.get("id"):
            saida.append(it["id"])
        if it.get("itens"):
            saida.extend(_campos_de(it["itens"]))
        for c in it.get("colunas") or []:
            saida.extend(_campos_de(c.get("itens") or []))
        for l in (it.get("linhas") or []) if it.get("tipo") == "tabela" else []:
            for c in l.get("celulas") or []:
                saida.extend(_campos_de(c.get("itens") or []))
    return saida


def _muitos(itens: Any, contador: list[int]) -> list[dict]:
    prontos = [x for x in (_um(i, contador) for i in (itens or [])) if x]
    # Todo botão que atravessa a fronteira ganha `campos`: os ids da caixa em
    # que ele mora. Consulta e escrita têm a mesma regra de escopo; o efeito
    # continua inequívoco pelas chaves `consultar` e `enviar`.
    campos: list[str] | None = None
    for it in prontos:
        if it.get("tipo") == "acoes":
            for b in it["botoes"]:
                if "enviar" in b or "consultar" in b:
                    if campos is None:
                        campos = _campos_de(prontos)
                    b["campos"] = campos
    return prontos


def validar(
    bruto: Any,
    escrituras: frozenset[str] | set[str] | None = None,
    leituras: frozenset[str] | set[str] | None = None,
    *,
    config: Config | None = None,
) -> tuple[dict | None, str | None]:
    """`(tela, None)` ou `(None, motivo)` — reconstruído, nunca repassado.

    `escrituras` são as operações de ESCRITA que o serviço declarou; um
    `Action.Submit` que nomeie outra coisa recusa o cartão inteiro. `leituras`
    são as de LEITURA (para `Action.Execute` e `okmigoDocumento`), pela mesma régua. `None`
    desliga a conferência — só para quem valida sem serviço por trás.
    `config` diz o que é «nosso» e os tetos do ambiente (ver `Config`).
    """
    ficha_c = _config.set(config if config is not None else Config())
    ficha = _escrituras.set(frozenset(escrituras) if escrituras is not None else None)
    ficha_l = _leituras.set(frozenset(leituras) if leituras is not None else None)
    # Zerado por CARTÃO, não por processo: o teto de autorizações é do cartão.
    ficha_a = _autorizacoes.set([0])
    try:
        return _validar(bruto)
    finally:
        _autorizacoes.reset(ficha_a)
        _leituras.reset(ficha_l)
        _escrituras.reset(ficha)
        _config.reset(ficha_c)


def _validar(bruto: Any) -> tuple[dict | None, str | None]:
    if not isinstance(bruto, dict):
        return None, "o cartão precisa ser um objeto"
    if bruto.get("type") != "AdaptiveCard":
        return None, "falta 'type': 'AdaptiveCard'"
    if not isinstance(bruto.get("body"), list) or not bruto["body"]:
        return None, "cartão sem 'body'"
    try:
        corpo = _muitos(bruto["body"], [0])
    except _Erro as e:
        return None, str(e)
    if not corpo:
        # Corpo vazio depois de reconstruir = NADA do que veio é conhecido.
        # Devolver a tela em branco seria a tela que abre e não mostra nada,
        # sem ninguém saber por quê.
        return None, (
            "nenhum elemento do cartão é conhecido — versão do "
            "schema mais nova que este cliente?"
        )
    tema = bruto.get("okmigoTema")
    navegacao = bruto.get("okmigoNavegacao")
    saida = {"versao": str(bruto.get("version") or "1.5")[:8], "corpo": corpo}
    if tema in _TEMAS_DO_CARTAO:
        saida["tema"] = tema
    if navegacao in _NAVEGACOES_DO_CARTAO:
        saida["navegacao"] = navegacao
    return saida, None
