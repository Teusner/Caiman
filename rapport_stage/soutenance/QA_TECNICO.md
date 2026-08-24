# Perguntas prováveis — o que eles realmente vão perguntar

Quem está na banca muda tudo:

- **Philippe Xu** — presidente, referente pedagógico. É ele que avalia a soutenance (**/50**).
  Não é especialista em PCB. Vai perguntar **dificuldade, aprendizado, ligação com o curso, o que
  faria diferente.**
- **Franck Ruffier e Quentin Brateau** — convidados. O Franck avalia **por fora**, na fiche
  d'évaluation (**/30**), não pela soutenance — é o que diz o Art. 12 da convenção. Se estiverem
  presentes, o Franck puxaria conceito de frota e energia; o Quentin é o único capaz de pergunta
  funda de código.

**Então quase tudo vem do Philippe Xu, e é pedagógico, não técnico.** Este documento segue essa
proporção.

---

## 1. As quase-certas — prepare estas de verdade

### "Qual foi a maior dificuldade?"

A placa não chegar. Mas responda focando na **decisão**, não na reclamação.

> *"The board was ordered on 23 June, but fabrication and assembly lead times put delivery after
> today. The hard part was not the delay — it was deciding what to do with the two months left.
> I chose to validate everything that did not need the board, and to be strict about never
> presenting those results as hardware results."*

### "O que você faria diferente?"

Três coisas concretas. Ter três respostas prontas é o que separa uma boa resposta de um "sei lá".

> *"Three things. First, I would order the board in the first two weeks instead of the fourth —
> the lead time was the single thing that shaped the whole internship. Second, I would re-run the
> design rule check on the exact files I export, and archive them together with the order. Third,
> I would keep raw logs from every bench, including the exploratory ones."*

### "O que você aprendeu?"

Duas coisas que você **não** esperava aprender — isso soa muito melhor que "aprendi KiCad".

> *"Two things I did not expect. First, that a bill of materials is a set of geometric
> commitments, not a list of values — I learned that when the manufacturer suspended assembly
> because the inductor pads did not match my footprint, even though the package was the same
> 4 by 4 millimetres. Second, that traceability is part of engineering rather than paperwork.
> When I changed workstation mid-project, I could no longer prove which files had gone to the
> fabricator."*

### "Você fez isso sozinho?"

> *"The electronics review, the routing, the simulator and the bench are my work. Quentin Brateau
> gave me day-to-day technical support and Franck Ruffier set the direction. The mechanical
> design and the original schematic came from the existing Caiman project — I corrected the
> schematic rather than drawing it."*

---

## 2. Ligação com o curso — Philippe Xu vai perguntar

### "Quais matérias do curso você usou?"

Quatro, e tem exemplo concreto pra cada:

| Matéria | Onde apareceu |
|---|---|
| Arquitetura de microcontroladores | STM32F7, barramentos SPI/I²C/UART, FreeRTOS a 10 Hz |
| Sinal e estimação | Filtro complementar para atitude, geometria do feixe do sonar |
| Redes e comunicação | Trama de 32 B, roteamento distribuído, tolerância a falhas |
| Engenharia de software | Git, modularidade, testes automatizados, journalisation |

> *"Microcontroller architecture, for the STM32 peripherals and the FreeRTOS scheduling. Signal
> and estimation theory, for the complementary filter and the sonar geometry. Network engineering,
> for the 32-byte frame and the distributed routing. And software engineering practice — version
> control, modularity and automated tests — which is what made the simulator usable as a
> reference."*

### "Como isso se liga à especialidade Robótica Autônoma?"

A resposta boa: **autonomia sob restrição de comunicação.**

> *"The defining constraint is that radio does not work underwater. That forces genuine autonomy:
> each vehicle has to run its share of the mission with no contact, decide alone, and store what
> it observes. It is the opposite of a teleoperated system. The whole architecture follows from
> that one physical fact."*

### ⚠️ "Qual é a contribuição de pesquisa?" — a pergunta difícil

É um PRe, **Projet de Recherche**. Se você disser "é só engenharia" soa fraco; se inventar
contribuição científica, eles derrubam. Caminho do meio:

> *"This is an engineering PRe and I would not oversell it as a research contribution. What I
> think transfers is the separation between the model's internal state and what the surface
> station can actually know — that is what makes the supervision view honest rather than a
> display of ground truth. Plus a frame designed to a hard physical limit, and a portable
> protocol the team can reuse as a reference."*

---

## 3. O que faltou na apresentação — e pode ser cobrado

### Estado da arte — o relatório TEM bibliografia, o deck não

**Boa notícia: o relatório não tem essa lacuna.** Conferi o `.bib`: **26 entradas, 23 citadas**,
espalhadas por 6 capítulos (cap. 2 ×3, cap. 3 ×1, cap. 4 ×5, cap. 5 ×2, cap. 6 ×3, cap. 7 ×9).
A bibliografia impressa tem 23 referências. Está tudo lá.

A lacuna real é menor e dupla:
- **O deck** quase não cita literatura — mas isso é normal numa apresentação de 20 min.
- **A introdução (cap. 1) não tem nenhuma citação.** O posicionamento na literatura está no
  cap. 3 e no cap. 7.

⚠️ **Não diga "está no capítulo 1".** Não está. Se o Philippe Xu for olhar, não acha nada.

Se perguntarem onde o trabalho se situa:

> *"The report positions it against four main sources. Fossen for marine vehicle modelling and
> Paull's review of AUV navigation and localisation, both in chapter 3. Akyildiz on underwater
> acoustic sensor networks — which is the basis for ruling out an acoustic modem — and Fall's
> delay-tolerant network architecture, which is the closest existing framing for surface-only
> rendezvous. Those two are in chapter 7. I kept the presentation on what I built rather than on
> the review."*

Decore os quatro nomes **e onde estão**:

| Referência | Sobre | Capítulo |
|---|---|---|
| **Fossen** | Modelagem de veículos marinhos | 3 |
| **Paull** | Review de navegação e localização de AUV | 3 |
| **Akyildiz** | Redes de sensores acústicos submarinas | 7 |
| **Fall** | Delay-tolerant networks | 7 |

⚠️ **Urick e Lurton estão no seu `.bib` mas nunca foram citados** — as duas referências clássicas
de acústica submarina (*Principles of Underwater Sound* e *An Introduction to Underwater
Acoustics*). Como não estão citadas, **não aparecem na bibliografia impressa**. Se você realmente
as consultou, são a sua resposta para *"por que não acústico?"*. Se só coletou o BibTeX, não as
mencione — inventar leitura é o único jeito de transformar uma pergunta fácil em problema.

### Mecânica e CAO

> *"The mechanical design is in the report: a sealed PMMA cylinder, two machined end caps with
> double O-ring grooves, hybrid M10 bulkheads for the thrusters. I modelled it in Onshape. I left
> it out of the presentation because my contribution was the electronics and the software."*

### O banco STM32/IMU (tirei do deck)

> *"Before the board existed I ran an exploratory bench with a NUCLEO-H743ZI2 and an ICM-20948
> nine-axis module, to get a sensor acquisition chain working on STM32. I kept photographs but no
> logged data, so I claim nothing quantitative from it — no accuracy, no drift figure. That is
> exactly why it is not in the presentation."*

### O deployment web

> *"The dashboard is containerised — Python and Streamlit behind a Caddy reverse proxy with a
> health endpoint, deployed to a VPS under the caimansim.fr domain. What I demonstrate is the
> deployment chain. The hosted instance lapsed when the student credits ran out, so I run it
> locally."*

---

## 4. Perguntas técnicas — versão simples, sem jargão

Você não precisa entrar em criptografia. Estas respostas curtas resolvem.

### "Explica o protocolo"

> *"The radio chip can only carry 32 bytes in one message — that is a hard limit of the hardware.
> So I designed the message to that limit: 8 bytes to say who is talking to whom, 8 bytes of
> actual data, and 16 bytes of a signature that proves the message was not modified in transit.
> The data is squeezed into 64 bits: position, depth, battery and a few flags."*

Se insistirem em "por que 16 bytes só de assinatura?":

> *"Because a message that arrives corrupted or forged is worse than no message. Half the frame
> buys the guarantee that what the station displays is what the robot actually sent."*

### "Explica o HIL"

> *"Hardware-in-the-loop means running the real code on real processors, with part of the system
> replaced by a model. I took the protocol code and ran it on an ESP32 and a Raspberry Pi,
> exchanging messages both ways. The processors are real and the code is real. What is not real
> is the radio — there is no nRF24 chip on the bench, so the messages travel over Wi-Fi instead."*

### Respostas de uma linha

| Pergunta | Resposta |
|---|---|
| "Por que STM32F765?" | Já estava no projeto herdado. Cortex-M7, periféricos suficientes para todos os barramentos. |
| "Por que nRF24 e não modem acústico?" | Custo. Acústico funciona submerso mas é caro, lento e consome muito. A frota só faz sentido se cada unidade for barata. |
| "Por que 5 robôs?" | Configuração de referência dada ao projeto. É um parâmetro, não um resultado. |
| "Por que 32 bytes?" | Limite físico do chip de rádio. Não é escolha minha. |
| "Por que 2 camadas na placa?" | Custo. Duas camadas é o processo mais barato e couberam os 116 componentes. |
| "O sonar é de feixe único?" | Sim, Ping2 com 25° de abertura. Multi-feixe daria cobertura melhor mas custa muito mais. |

---

## 5. As desconfortáveis — não hesite

### "Você testou alguma coisa na placa?"

Resposta curta e direta. Não enrole.

> *"No. Nothing. The board was not delivered, so there is no electrical measurement of any kind."*

### "Então o que você validou de verdade?"

> *"Three things. The production file, which passed the manufacturer's own engineering review.
> The fleet logic and the protocol, in a deterministic simulator. And the protocol code itself,
> running on two physical processors on the bench. What I did not validate is the board."*

### "Isso não é só simulação?"

> *"Partly, and I am explicit about the boundary. The simulator is a model. But the protocol code
> on the bench is the real C source running on real silicon — that part is not simulated. What is
> modelled there is the radio chip, not the processor and not the code."*

### "E o DRC?" ⚠️

**Não improvise.** Está preparada em `QA_PREP.md`, resposta 1, cinco pontos em ordem. Leia antes.

### "caimansim.fr não abre"

> *"The hosting ran on an Azure subscription under student credits, which have lapsed. DNS still
> resolves. What I claim is the deployment chain, not continuous availability."*

---

## 6. O que melhoraria / o que vem depois

Franck Ruffier provavelmente pergunta isso. Tenha a ordem de prioridade pronta:

1. **Receber a placa e fazer o bring-up** — continuidade em +3V3/GND antes de energizar, rampa
   com limite de corrente, medir os trilhos, gravar o STM32, periféricos um por um.
2. **Rádio nRF24 real no banco**, substituindo o Wi-Fi. O código já está preparado para isso.
3. **Chave por veículo** em vez de chave de grupo — hoje um robô capturado compromete a frota.
4. **Corrigir o logger CSV** — o cabeçalho declara 10 colunas e a aplicação escreve 18 campos.
5. **Testar com mais de 5 veículos** — nada acima de 5 foi exercitado, não afirmo escalabilidade.

### "Isso é útil para o laboratório?"

> *"I think so. The simulator and its test suite describe how a Caiman fleet is expected to
> behave independently of any particular board, so they work as a reference the final firmware
> can be checked against. And the protocol implementation is portable C — it already runs
> unchanged on two different processors."*

### "Você continuaria o projeto?"

Responda com honestidade e com um passo concreto — mostra que você pensou além do prazo.

---

## 7. Se travar

Três frases que salvam qualquer pergunta:

1. *"That was not measured, so I will not claim it."*
2. *"That is a limitation I am aware of — it is [X], and the fix would be [Y]."*
3. *"I would rather check the exact figure in the repository than give you a number from memory."*

A terceira é **perfeitamente aceitável** numa banca. Inventar número não é.

---

## 8. Só se o Quentin apertar de verdade

Cinco fatos técnicos que valem ter na cabeça. Não puxe assunto sobre eles.

- **O código Python e o C geram tramas idênticas byte a byte.** Verifiquei o nonce das duas
  implementações: dá o mesmo resultado. É a prova de que o simulador e o firmware concordam.
- **O cabeçalho é autenticado mas não cifrado.** É de propósito: um relay precisa ler o destino
  para encaminhar, mas não consegue alterar nada sem quebrar a assinatura.
- **A codificação foi dimensionada para esta missão.** Posição em 14 bits dá 0–1638 m (zona é
  1000 × 700 m); profundidade em 11 bits a 1 cm dá 0–20,47 m (fundo é 13–20 m). Acima disso satura
  — é limitação conhecida.
- **ChaCha20 e não AES** porque o STM32F765 não tem acelerador AES; em software ChaCha é rápido
  e imune a ataque de temporização.
- **O modelo do nRF24 não é um stub.** FIFO de 3 níveis e os bits de interrupção nas posições
  reais do registrador do chip.

⚠️ Se ele perguntar tempo no ar da trama: o slide 15 diz **320 µs**, mas o modelo calcula
**329 µs** (o slide não conta os 9 bits de controle de pacote). Use 329 e explique a diferença.
