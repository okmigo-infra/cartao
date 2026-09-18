"""Os scripts que TODAS as esteiras do padrão rodam, num lugar só.

⛔⛔ **Por que este subpacote existe: 28 cópias, 15 versões** (OMINFRA-576).
Medido no disco em 18/09, com os quinze repos clonados:

| script                         | cópias | versões |
|--------------------------------|--------|---------|
| abre a PR de promoção          |     11 |       5 |
| registra o serviço no okmigo   |      9 |       9 |
| confere a versão do manifesto  |      8 |       1 |

⚠️ **O do registro é o caso exemplar e o mais perigoso**: nove cópias, nove
versões, nenhum par idêntico — não existe versão canônica de onde copiar. E o
gesto dele é destrutivo por desenho (`POST /instancias` é `insert or replace`),
então cada cópia carrega a SUA versão de uma defesa contra apagar a tela de
gente. Em 11/09 uma delas falhou e o POST respondeu 201.

⭐ **Por que aqui e não num repositório novo.** Dez repos já pinam
`okmigo-cartao` por SHA, e o `sre` já sabe comparar o pino e propor PR quando
ele anda. Repo novo significaria reconstruir essa distribuição inteira — e
somar um décimo sexto à contagem que este projeto já errou três vezes.

⚠️ **E `scripts/` na raiz deste repo NÃO é empacotado** (`packages.find` só olha
`src/`). Quem instala o cartão não recebe nada de lá. Alguém já teve esta ideia
e ela parou no meio; é por isso que o código novo entra AQUI.

⭐ **O que já migrou**, e a ordem não foi por gosto:

1. `versao_do_manifesto` (18/09) — oito cópias idênticas, zero debate sobre
   qual era a canônica. Veio primeiro para provar o mecanismo no caso barato.
2. `abrir_pr_de_promocao` (18/09) — seis idênticas davam a base, e os cinco
   desvios se leram um a um: dois eram SUBCONJUNTO ESTRITO (faltava o caminho
   de promoção sem imagem nova) e um era subconjunto maior ainda (faltava a
   guarda do ghcr inteira). Nenhum era divergência de comportamento, então
   adotar a canônica é ganho estrito nos três.

⏳ **Falta o do registro**, e ele é outro tipo de trabalho: é bash com blocos de
Python dentro de heredocs, então trazê-lo é PORTAR, não mover. É também o mais
perigoso dos três, e por isso não vem de carona numa PR de mudança de lugar.

⛔ **Nomes: o assunto, nunca o gesto.** O `scripts/versao_subiu.py` deste repo
confere se o CRIVO mudou sem a versão do PACOTE subir; o dos oito apps confere
se o MANIFESTO mudou sem a versão DELE subir. São checagens diferentes que
compartilhavam o nome do arquivo, e eu mesmo supus que fossem a mesma até
diffar. Daí `versao_do_manifesto` aqui.
"""
