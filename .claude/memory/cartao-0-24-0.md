---
name: cartao-0-24-0
description: 05/10 — 0.23.0 (dia inteiro) e 0.24.0 (recurso) publicadas; a versão sobe DENTRO da PR porque a main exige os checks; o que ainda falta no EVENTOS_PARA
metadata:
  type: project
---

- **0.23.0** (#33): `dia_inteiro: true` no evento do `calendario`, com
  `inicio`/`fim` só `AAAA-MM-DD` (`fim` inclusivo); com hora, o evento é
  DESCARTADO e o relatório o nomeia por índice. **0.24.0** (#34): `recurso`
  (≤ 60; acima o CAMPO some e o evento fica) e `recursos` no elemento. Tag
  `v0.24.0` em `f742aa2`.
- ⛔ **A versão sobe DENTRO da PR**: a `main` exige `testes (3.11)` e
  `testes (3.12)`, e o `scripts/versao_subiu.py` é um passo deles. Com PRs
  empilhadas, a de cima rebaseia sobre a de baixo já mergeada e sobe de novo
  (0.23.0 → 0.24.0); o conflito é o marcador `versao_pacote` do README.
- O `compatibilidade.py` pediu «correcao» (chave nova em todo evento, classe
  `forma`) e a versão fez «menor» — o portão aceita salto maior que o pedido.
- ⚠️ `EVENTOS_PARA` ainda só conhece `atendimento` e `compromisso`: as ações
  para `pedido` e `anotacao`, que o calendar já declara, são descartadas
  (OMINFRA-971).
