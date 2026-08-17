# Action Items pendentes para o aluno Joab (PRe ENSTA)

## Antes de entregar

1. **Attestation de confidentialité / non-confidentialité** — formulário administrativo **separado** do relatório, fornecido pela scolarité. É nele que o organismo de acolhimento (CNRS / Franck Ruffier) indica se o documento pode ser posto online. A página "Note de non-confidentialité" dentro do relatório é uma declaração e já está pronta.

2. **Conferir a data de fim de estágio e a data da soutenance** em `config/metadata.tex` antes de gerar o PDF final.

## Feito

- ~~Figura JLCPCB PCBA das indutâncias L1/L2~~ — inserida como Figure 5.3 (mensagem da revue + superposição das empreintes), a partir de `qqq.png`.
- ~~Captures HIL~~ — Listings 8.1 e 8.2 com saída real via SSH, 5/5 ciclos bidirecionais.
- ~~caimansim.fr~~ — texto ajustado: hospedagem Azure com créditos de estudante, disponibilidade condicionada à validade dos créditos. Demonstra a cadeia de deployment, não disponibilidade contínua.
- ~~Conformidade formal ENSTA~~ — page de garde vierge, paginação contínua desde a página de título, liste des annexes, remerciements em ordem hierárquica com função de cada pessoa, glossário com 21 entradas.

## Depois da entrega

3. **Recepção e bring-up do PCB Caiman**
   - Inspeção visual, teste de continuidade nos rails 5V / 3.3V **antes de energizar**, flash do firmware STM32F7, validação do transceptor nRF24.
   - Nota técnica interna sobre a revisão final do repositório: ver `DRC_JLC_AUDIT.md`.
