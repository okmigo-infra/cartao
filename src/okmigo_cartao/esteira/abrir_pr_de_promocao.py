"""Abre (ou reaproveita) a PR que promove este commit, e FECHA as superadas.

⭐ O gesto padrão do workspace: a esteira ABRE a porta, quem atravessa é gente.
Ela não toca no cluster — só propõe a troca do `newTag`. **Mergear a PR é
publicar**, e quem aplica é o ArgoCD, observando a branch `prod`.

⛔⛔ **E ela FECHA as anteriores, desde 15/09 (OMINFRA-541).** Cada merge que
muda a imagem abria uma PR nova e a anterior ficava lá: o `radaria` chegou a
ter TRÊS abertas ao mesmo tempo. Mergear uma antiga não rebaixa mais a produção
(o `newTag` na `main` é inerte agora), mas ela ainda é um convite a promover um
artefato velho — e o custo de fechar é uma chamada.

⚠️ Fecha apenas as que MIRAM `prod` e nascem de `promover-*` — nunca uma PR de
gente. E comenta antes de fechar: PR que some sem explicação faz quem a abriu
procurar o que aconteceu.

Uso:
    okmigo-abrir-pr-de-promocao <sha> <branch> [versao]
    python3 -m okmigo_cartao.esteira.abrir_pr_de_promocao <sha> <branch> [versao]

Ambiente:  GH_TOKEN, GITHUB_REPOSITORY, e GHCR_TOKEN quando o pacote do ghcr
não tem vínculo com o repositório (é o caso normal).

⭐⭐ **Migrado de ONZE cópias em CINCO versões, em 18/09 (OMINFRA-576).** A
lógica veio VERBATIM da versão que seis repositórios compartilhavam byte a
byte — o que mudou foi o lugar e a assinatura do `main`, que agora aceita
`argv` para poder ser testado sem mexer em `sys.argv`.

⚠️ **Os cinco desvios, e o que eram de fato**, porque «cinco versões» esconde
coisas diferentes:

- `condominio` (284 linhas): só prosa do corpo da PR. Mesma lógica.
- `calendar` (298): só um comentário a mais, avisando ser cópia. Mesma lógica.
- `old-tyego` e `sohautos` (275): faltava o caminho de promoção SEM imagem
  nova (`PROMOVE_COMMIT`). Era SUBCONJUNTO ESTRITO, não divergência — e nenhum
  dos dois passava a variável, então o comportamento era idêntico até passar.
- `sre` (107): faltava esse caminho **e a guarda do ghcr inteira** (quatro
  funções). Essa é lacuna, não escolha: o `sre` também publica imagem.

⛔ Então adotar esta versão nos três é ganho estrito, nunca troca de
comportamento — e é por isso que a migração pôde começar sem uma decisão de
produto no meio.

⚠️ **O que ele assume do repositório, e é tudo:** um diretório `k8s/` a partir
do diretório de trabalho, de onde `pacotes_no_sha` descobre os pacotes do ghcr.
Nenhum caminho de app, nenhum nome de serviço.
"""

from __future__ import annotations

import base64
import json
import os
import re
import sys
import time
import urllib.error
import urllib.request


def api(caminho: str, dados: dict | None = None, metodo: str | None = None) -> object:
    corpo = json.dumps(dados).encode() if dados else None
    req = urllib.request.Request(
        "https://api.github.com" + caminho,
        data=corpo,
        method=metodo,
        headers={
            "Authorization": "Bearer " + os.environ["GH_TOKEN"],
            "Accept": "application/vnd.github+json",
            "Content-Type": "application/json",
        },
    )
    try:
        bruto = urllib.request.urlopen(req).read()
        return json.loads(bruto) if bruto else {}
    except urllib.error.HTTPError as e:
        print(f"✗ GitHub {e.code}: {e.read().decode()[:300]}", file=sys.stderr)
        raise


def fechar_superadas(repo: str, manter: str) -> None:
    """Fecha as PRs de promoção anteriores. ⛔ Só as da ESTEIRA.

    ⚠️ O filtro é duplo — base `prod` E branch começando em `promover-` — porque
    cada um sozinho erraria: só pela base fecharia uma PR de gente que mira
    `prod`; só pelo nome fecharia uma que alguém abriu à mão para outro destino.
    """
    for pr in api(f"/repos/{repo}/pulls?state=open&base=prod"):
        ramo = pr["head"]["ref"]
        if ramo == manter or not ramo.startswith("promover-"):
            continue
        api(f"/repos/{repo}/issues/{pr['number']}/comments",
            {"body": "Fechada pela esteira: há uma promoção mais nova.\n\n"
                     "⚠️ **Não perdeu nada** — a PR nova carrega este commit e os "
                     "seguintes. Mergear esta aqui promoveria um artefato mais "
                     "velho que o topo da `main`.\n\n"
                     "Ver OMINFRA-541."})
        api(f"/repos/{repo}/pulls/{pr['number']}", {"state": "closed"}, metodo="PATCH")
        print(f"  · fechei a superada #{pr['number']} ({ramo})")


# ── o guarda: a etiqueta tem imagem? ───────────────────────────────────────────
# ⛔⛔ **A esteira já abriu promoção para um SHA que ninguém construiu.** Em
# 15/09, no sohautos: o passo que CONSTRÓI é guardado por «mudou código desde o
# commit anterior?» e o que PROMOVE, por «mudou algo desde o que está no ar?».
# São perguntas diferentes, e quando discordam nasce uma PR que leva a produção
# para uma etiqueta sem imagem — `ImagePullBackOff`, com a PR verde e o YAML
# impecável. O que pegou foi alguém conferir o ghcr à mão antes de mergear;
# nada no sistema reclamou.
#
# ⚠️ E a causa não é só aquele `if`: push ao registry que falha, limpeza de
# registry que apaga etiqueta em uso, build que morre depois do teste — todos
# desembocam no mesmo lugar. Por isso o guarda pergunta ao REGISTRY, que é a
# única fonte que sabe, em vez de reproduzir a lógica de quem constrói.


def pacotes_no_sha(sha: str, raiz: str = ".") -> set[str]:
    """Os pacotes do ghcr que os manifestos amarram A ESTE `sha`.

    ⛔ **Não é «todo ghcr que aparece na árvore»** — essa foi a primeira versão, e
    ela quebrava no okmigo: lá os manifestos citam 14 pacotes, entre eles um
    exemplo em prosa (`ghcr.io/ORG/nome`), um molde (`okmigo-agentes-X`) e os
    runners da esteira, que têm etiqueta PRÓPRIA e não são promovidos junto. O
    guarda recusaria promoção legítima — e guarda que dá alarme falso é guarda
    que alguém desliga.

    ⛔ E os nomes são DESCOBERTOS, não decorados: o `comcontabil` publica
    `comcontabil-api`, o `radaria` publica `radaria`. Um mapa aqui seria mais uma
    cópia para envelhecer calada — e, envelhecida, ela faria o guarda aprovar sem
    ter olhado, que é a pior falha possível num guarda.
    """
    achados: set[str] = set()
    direto = re.compile(
        r"ghcr\.io/[^/\s\"']+/([A-Za-z0-9._-]+):" + re.escape(sha) + r"\b")
    for pasta, _sub, arqs in os.walk(os.path.join(raiz, "k8s")):
        for a in arqs:
            if not a.endswith((".yaml", ".yml")):
                continue
            try:
                texto = open(os.path.join(pasta, a), encoding="utf-8").read()
            except OSError:
                continue
            # 1. a imagem escrita inteira, com a etiqueta junto
            achados |= set(direto.findall(texto))
            # 2. o kustomize, que separa `name:` e `newTag:` em campos vizinhos
            for bloco in re.split(r"\n(?=\s*-\s)", texto):
                # ⚠️ `newName:` E `name:`: o kustomize aceita os dois, e os
                # repos daqui usam o PRIMEIRO — `name: sohautos-api` é o nome
                # LÓGICO que ele casa nos manifestos, e o endereço real vem no
                # `newName`. Procurar só em `name:` faz a descoberta voltar
                # vazia, e vazio aqui vira recusa de promoção legítima.
                m = re.search(r"(?:new)?[Nn]ame:\s*ghcr\.io/[^/\s]+/([A-Za-z0-9._-]+)", bloco)
                t = re.search(r"newTag:\s*\"?([A-Za-z0-9._-]+)\"?", bloco)
                if m and t and t.group(1) == sha:
                    achados.add(m.group(1))
    return achados


def tem_imagem(pacote: str, tag: str, token: str) -> "bool | None":
    """O manifesto responde com camadas? `None` = não consegui perguntar.

    ⛔ HTTP 200 não basta: o GHCR devolve JSON de erro com status 200 em alguns
    casos. A prova é o corpo trazer `manifests` (índice) ou `layers` (imagem).
    """
    aceita = ",".join([
        "application/vnd.oci.image.index.v1+json",
        "application/vnd.docker.distribution.manifest.list.v2+json",
        "application/vnd.oci.image.manifest.v1+json",
        "application/vnd.docker.distribution.manifest.v2+json",
    ])
    dono = os.environ["GITHUB_REPOSITORY"].split("/")[0]
    req = urllib.request.Request(
        f"https://ghcr.io/v2/{dono}/{pacote}/manifests/{tag}",
        headers={"Authorization": "Bearer " + base64.b64encode(token.encode()).decode(),
                 "Accept": aceita})
    for tentativa in range(3):
        try:
            with urllib.request.urlopen(req, timeout=20) as r:
                m = json.loads(r.read())
            return bool(m.get("manifests") or m.get("layers"))
        except urllib.error.HTTPError as e:
            if e.code == 404:
                return False              # ⭐ 404 é o ÚNICO «não existe»
            # ⛔⛔ **401/403 é «não consegui perguntar», nunca «não existe».**
            # A primeira versão deste guarda devolvia `False` para 403, e em
            # 16/09 ele RECUSOU a promoção do okmigo dizendo que três imagens
            # não existiam — elas estavam lá, com digest, empurradas na mesma
            # corrida. O token é que não alcançava o pacote. Transformar uma
            # negativa de acesso em afirmação sobre o mundo é o mesmo erro que
            # este guarda existe para impedir, cometido pelo guarda.
            if tentativa == 2:
                return None
        except Exception:
            if tentativa == 2:
                return None
        time.sleep(2 ** tentativa)
    return None


def credenciais_do_ghcr() -> list:
    """Os tokens que podem ler o registry, na ordem de quem alcança mais.

    ⛔⛔ **O `GITHUB_TOKEN` da corrida NÃO alcança todo pacote.** O `deploy.yml`
    do okmigo já dizia isso, num comentário ao lado do login: «nascido de PAT
    pessoal não herda acesso do repositório (`permission_denied`). Quem serve é
    o `GHCR_TOKEN`, segredo de REPO». O guarda ignorou aquele aviso, usou o
    token da corrida, levou `permission_denied` e concluiu que as imagens não
    existiam. Agora ele tenta o mesmo crachá com que a esteira EMPURRA.
    """
    return [t for t in (os.environ.get("GHCR_TOKEN"), os.environ.get("GH_TOKEN")) if t]


def a_imagem_existe(sha: str, token: str = "") -> bool:
    tokens = credenciais_do_ghcr() or ([token] if token else [])
    if not tokens:
        print("✗ sem credencial para perguntar ao ghcr (GHCR_TOKEN ou GH_TOKEN).",
              file=sys.stderr)
        return False
    pacotes = sorted(pacotes_no_sha(sha))
    if not pacotes:
        # ⛔ «Não achei o que conferir» é falha, nunca aprovação silenciosa.
        print(f"✗ nenhum manifesto de `k8s/` amarra uma imagem a `{sha}`.", file=sys.stderr)
        print("  Ou a promoção não trocou a etiqueta, ou ela mora onde não procurei.",
              file=sys.stderr)
        print("  ⛔ Aprovar aqui seria desligar o guarda — então recuso.", file=sys.stderr)
        return False
    ruins = []
    for p in pacotes:
        # ⭐ Tenta cada credencial até uma dar resposta DEFINITIVA (True ou
        # False). `None` de uma não decide nada — pode ser a outra que alcança.
        r = None
        for t in tokens:
            r = tem_imagem(p, sha, t)
            if r is not None:
                break
        marca = {True: "✅", False: "⛔", None: "⚠️"}[r]
        sufixo = {True: "", False: " — NÃO existe no ghcr",
                  None: " — não consegui perguntar"}[r]
        print(f"    {marca} {p}:{sha}{sufixo}")
        if r is not True:
            ruins.append((p, r))
    if not ruins:
        print(f"  ✅ as {len(pacotes)} imagem(ns) de `{sha}` estão no ghcr")
        return True
    print(file=sys.stderr)
    print(f"✗ NÃO abro a promoção: {len(ruins)} imagem(ns) de `{sha}` não conferem.",
          file=sys.stderr)
    for p, r in ruins:
        print(f"    · {p}: {'ausente' if r is False else 'não consegui perguntar'}",
              file=sys.stderr)
    print("  Mergear uma promoção assim leva a produção a `ImagePullBackOff`, com a",
          file=sys.stderr)
    print("  PR verde e o YAML impecável. ⚠️ Causa provável: o passo que CONSTRÓI foi",
          file=sys.stderr)
    print("  pulado — ele e este respondem perguntas diferentes — ou o push para o",
          file=sys.stderr)
    print("  ghcr falhou. Confira a corrida deste commit antes de reabrir.", file=sys.stderr)
    return False


def main(argv: list[str] | None = None) -> int:
    # ⭐ `argv` explícito para o teste não precisar mexer em `sys.argv`. As onze
    # cópias liam `sys.argv` direto, e nenhuma tinha teste — as duas coisas
    # andam juntas mais vezes do que parece.
    args = list(sys.argv[1:] if argv is None else argv)
    if len(args) < 2:
        print("uso: okmigo-abrir-pr-de-promocao <sha> <branch> [versao]",
              file=sys.stderr)
        return 2
    sha, branch = args[0], args[1]
    # ⚠️ O okmigo passa a VERSÃO como 3º argumento (os apps do padrão não têm
    # versão de release — a etiqueta deles é o SHA e pronto).
    versao = args[2] if len(args) > 2 else ""
    # ⭐ `PROMOVE_COMMIT` (OMINFRA-562): o commit que está sendo LEVADO, quando
    # ele não é a etiqueta — uma promoção sem imagem nova mantém o `newTag` no
    # que está no ar e carrega só o que roda a partir da `prod` (o `prod.yml`,
    # o `registrar.sh`, o overlay). O guarda confere a imagem da ETIQUETA; o
    # título e o corpo dizem o COMMIT.
    commit = os.environ.get("PROMOVE_COMMIT") or sha
    sem_imagem = ("" if commit == sha else
                  f"⭐ **Sem imagem nova**: o `newTag` fica em `{sha}` (o que está no ar); "
                  f"o que esta PR leva é o que roda a partir da `prod` — `prod.yml`, "
                  f"`registrar.sh`, overlay — até `{commit}`.\n\n")
    repo = os.environ["GITHUB_REPOSITORY"]
    dono = repo.split("/")[0]

    # ⛔⛔ O guarda vem ANTES de tudo, inclusive de fechar as superadas:
    # recusar depois de ter fechado a PR anterior deixaria o repo sem
    # promoção nenhuma aberta — pior do que como estava.
    if not a_imagem_existe(sha):
        return 1

    fechar_superadas(repo, branch)

    # ⚠️ Reaproveitar a PR aberta em vez de abrir a segunda: empurrar de novo na
    # mesma branch já atualizou o conteúdo dela.
    abertas = api(f"/repos/{repo}/pulls?state=open&head={dono}:{branch}")
    if abertas:
        print(f"  · PR de promoção já aberta: #{abertas[0]['number']} {abertas[0]['html_url']}")
        return 0

    corpo = (
        f"Aberta pela esteira a partir de `{commit}`.\n\n" + sem_imagem +
        "**Mergear isto publica.** Quem aplica no cluster é o **ArgoCD**, "
        "observando a branch `prod` — ele reconcilia sozinho depois do merge, e "
        "leva Deployment, CronJob e tudo o mais que o overlay declarar.\n\n"
        "⛔ Confira o `newTag` antes de mergear: é a primeira linha a conferir. "
        "Um overlay já nasceu neste ecossistema apontando para a etiqueta de "
        "outro serviço.\n\n"
        "⚠️ Se esta PR mudar ESTRUTURA além da imagem, isso vai ao ar junto — e "
        "agora sem `apply` nenhum no meio: o Argo aplica o que a branch declara."
    )
    pr = api(
        f"/repos/{repo}/pulls",
        {"title": f"prod: promover {commit}" + (f" (v{versao})" if versao else "")
                  + ("" if commit == sha else f" — sem imagem nova, fica {sha}"),
         "head": branch, "base": "prod", "body": corpo},
    )
    print(f"  ✅ PR de promoção aberta: #{pr['number']} {pr['html_url']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
