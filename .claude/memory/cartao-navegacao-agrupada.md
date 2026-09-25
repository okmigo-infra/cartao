---
name: cartao-navegacao-agrupada
description: 0.16.0→0.20.0 (19–25/09) — a navegação agrupada é TUDO OU NADA, e do lado do okmigo o desvio é SILENCIOSO; o pino é mudo e o marketplace prova isso em v0.11.0
metadata:
  type: project
---

**O arco destes dias** (tags no `cartao`, uma por versão):

| versão | o que entrou | card |
|---|---|---|
| 0.16.0 | a navegação agrupada do aplicativo | — |
| 0.17.0 | o agente de domínio (contrato 1) | 766 |
| 0.18.0 | rotas tipadas, busca do aplicativo, estado restaurável | 570 |
| 0.18.1 | o CTA de rodapé reserva espaço no quadro de celular | 617 |
| 0.19.0 | `NavegacaoDoCalendario`: vistas, período, faixa de horas | agenda canônica |
| 0.20.0 | `okmigo_cartao.grupo`: ações e conteúdo com escopo de grupo | 806 |

## ⛔⛔ A regra mora em DOIS lugares, e só um grita

O SDK recusa com exceção (`sdk.py`, `NavegacaoAgrupada`): de 2 a 5 grupos, sem
grupo repetido, cada superfície coberta **exatamente uma vez**. Mas o manifesto
que chega ao okmigo é **JSON**, e pode ter sido escrito à mão — então a
plataforma repete a régua em `delegation.navegacao_agrupada()`.

⛔ **Lá ela é MUDA.** Qualquer desvio (tipo, contagem, tela de fora, tela
repetida, `inicial` de outro grupo) faz a função devolver `{}` — e aí *o
agrupamento inteiro é descartado e a barra volta à antiga*, sem erro, sem log,
com o registro respondendo 200. O motivo está escrito lá: um agrupamento que
deixa tela de fora faria ela **sumir** da barra, pior que a gaveta que veio
substituir. Então é tudo ou nada.

⭐ **Como se confere, sem abrir tela** — o grupo viaja DENTRO de cada
superfície, no mesmo `jsonb`, então o que ficou gravado responde:

    select s->'grupo'->>'ordem', s->'grupo'->>'rotulo', s->>'nome'
      from agent_registry a, jsonb_array_elements(a.superficies) s
     where a.name = '<slug>';

`grupo` nulo em qualquer linha = agrupamento recusado. Medido assim no
estoufit-aluno 0.44.0 em 25/09: 7 telas, 4 grupos, aceito.

⚠️ **E registrar não basta se o `registrar.sh` não levar as chaves.** As duas
chaves novas do manifesto são `rotas` e `navegacao`, e a tupla `CHAVES` do
`okmigo/registrar.sh` de cada consumidor precisa citá-las — o dogiromoney
gastou uma versão inteira só nisso (0.22.1, «a navegação agrupada viaja pelo
registrar.sh»). Chave que o script não copia não chega, e não há erro.

## ⛔ `NOMES_RESERVADOS_DA_ROTA` — sete nomes proibidos, escritos duas vezes

`credencial`, `tenant`, `hoje`, `grupos`, `grupos_nomes`, `rota`, `parametros`.
São os campos que a PLATAFORMA afirma ao pedir a tela; um parâmetro de rota com
esse nome seria a tela escolhendo quem ela é. A lista está no SDK **e** copiada
em `delegation.py` do okmigo, de propósito e com o porquê no comentário: o
registro não pode depender de o manifesto ter vindo do SDK.

## ⛔⛔ Publicar é TAG — e o pino é MUDO

`git tag vX.Y.Z` publica; quem consome pina por **SHA** (`…/cartao/archive/<sha>.tar.gz`),
imutável de propósito. Quando o crivo anda, **nada nos consumidores acusa**:
quem avisa é o `sre/pino-do-cartao.py`, de 3 em 3 horas, abrindo PR em quem
está atrás — e o CI de cada consumidor é quem julga.

⭐ **A prova de que o aviso é o que segura tudo** (medido em 25/09):

| onde | pino | versão |
|---|---|---|
| 8 repos (cardapmesa, comcontabil, condominio, dinfinance, dogiromoney, estoufit, radaria, sohautos) | `d64d2e0` | v0.18.1 |
| calendar, horaok, tyego (o trio da agenda canônica) | `ea2ac36` | v0.19.0 |
| **marketplace** | `5ed2bcc` | **v0.11.0** |

O `marketplace` está **nove versões atrás** — e não por esquecimento de quem
mergeia: ele é o único que **não está no `REPOS` do `sre/pino-do-cartao.py`**
(onze entradas, medidas em 25/09), porque monta o cartão com dicionários
simples em vez do SDK. Ninguém nunca abriu a PR para ele. ⚠️ A decisão é de
rever, não de esquecer — mas o efeito é que o único repo fora do aviso é o
único muito atrás, e isso mede o valor do aviso.

⚠️ O `cartao` está em **0.20.0** e nenhum consumidor chegou lá ainda.
