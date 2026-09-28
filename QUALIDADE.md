# Qualidade — os gates deste repositório

Retrato de **28/09** (OMINFRA-836), lido dos workflows da `main` mais a PR que
trouxe este arquivo. ⚠️ Quem manda é o `.github/workflows/`: se este texto e os
workflows discordarem, vale o workflow, e este arquivo ficou atrasado — conserte
os dois no mesmo commit.

## O que reprova, e onde

| gate | onde | reprova quando |
|---|---|---|
| a suíte | `ci.yml` · «suíte» (Python 3.11 e 3.12) | um teste falha |
| instala como o consumidor | `ci.yml` · «instala como o consumidor instala, e os assets vêm junto» | o tarball não instala num venv limpo, falta asset do renderer, ou o `__all__` promete o que não existe |
| a versão | `ci.yml` · «mudou o crivo, mudou a versão?» | o crivo mudou e a versão não subiu |
| o contrato só cresce | `ci.yml` · «o contrato só cresce» | um nome público sumiu (quebraria os doze consumidores) |
| publicar | `publicar.yml` (tag `v*`) · «a tag é a versão?» e «o tarball que o consumidor vai baixar» | a tag ≠ a versão do `pyproject.toml`, ou o tarball não instala |

## Exceções — o que se pode furar, e como

- Nenhuma declarada.

## Cadência e dono das dependências

- **Dependabot** toda segunda, 06:00 (`.github/dependabot.yml`): pip (só o `dev`) e github-actions.
  Dono de toda PR dele: **Victor**. ⛔ A PR de `github-actions` muda
  Dono de toda PR dele: **Victor**.
- **Alertas do GitHub** (Dependabot alerts): LIGADOS (repo público; medido em
  28/09). As PRs automáticas de segurança seguem desligadas.

## O que NÃO é gate (ainda)

- **Auditoria de dependência**: o crivo não tem dependência de execução (`dependencies = []`, de propósito: ele entra em doze consumidores). Quem audita o que chega por ele é a auditoria de cada consumidor.
- **Cobertura e tipos**: não medidos. Cobertura seria sinal, não substituto de cenário.
- **Branch protection**: o repo é PÚBLICO e poderia tê-la, e em 28/09 não tem nenhuma
  — nem na `main`, nem nas tags `v*`, que são o gesto de PUBLICAR. A proposta está
  no relatório do OMINFRA-835; aplicar é gesto do dono. Enquanto isso, a guarda das
  branches do `sre` enxerga push direto e force-push.
