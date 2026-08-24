# Rapport de Révision Finale (PRe ENSTA)

## Révision 2 — audit DRC et corrections de conformité (2026-08-16)

| Modification | Motif / Requisito | Fonte / Evidência |
|---|---|---|
| **Réécriture de la section DRC (§5.1)** | La version précédente affirmait que le routage « respecte les contraintes technologiques », en contradiction avec l'audit. La cause réelle est identifiée : le DRC a été validé sur `b900398` (09/06) mais trois révisions ont suivi et c'est `0c5e24e` (23/06) qui est partie en fabrication, sans nouveau contrôle. | `git log` + `kicad-cli pcb drc` 10.0.5 sur les trois révisions ; `DRC_JLC_AUDIT.md` |
| Sévérités DRC corrigées | Le texte annonçait « 49 avertissements / 231 remarques » : les 48 sont des **erreurs**, les 231 des avertissements. | JSON `kicad-cli` |
| Nouveau tableau des courts-circuits (`tab:drc-shorts`) | Distinguer un défaut géométrique d'une question de tolérance fabricant. Recouvrements calculés depuis le `.kicad_pcb` : −49 µm, −59 µm, contact. | Coordonnées et diamètres du fichier PCB |
| Cohérence chap. 5 ↔ chap. 8 | Le tableau de validation contredisait le chapitre 5. Il distingue désormais la révision vérifiée de la révision transmise. | `08_validation.tex` |
| Conclusion et perspectives réordonnées | La révision corrective du routage et le contrôle de continuité `+3V3`/`GND` deviennent les deux premières actions. | `10_conclusion.tex` |
| `convenção` → `convention` | Mot portugais resté dans la page de non-confidentialité. | `frontmatter/non_confidentiality.tex` |
| `(*land pattern*)` → `\emph{land pattern}` ; `` `74438356033` `` → `\texttt{}` | Syntaxe Markdown rendue littéralement dans le PDF. | `05_fabrication.tex` |
| « plages de sédimentation » → « plages de brasage » | Terme inexistant en électronique française. | `05_fabrication.tex` |
| Ordre du front matter : remerciements avant résumé | Ordre prescrit par le guide de rédaction PRe. | `CONTENU DU RAPPORT_PRe.doc` |
| Glossaire étendu à 21 entrées | Sigles demandés et effectivement employés : ACK, AEAD, CAO, DCR, GNSS, HKDF, IMU, MCU, PCBA, RF, SPI, UART, VPS. | Guide PRe §glossaire |
| Citations ChaCha20, AEAD, HKDF ajoutées | Sources primaires présentes dans la bibliographie mais jamais citées. | `bernstein2008chacha`, `rogaway2002authenticated`, `krawczyk2010hkdf` |
| Photographie HIL dédupliquée | La même bancada apparaissait aux chapitres 7 et 8. | `08_validation.tex` (renvoi vers `fig:hil-setup`) |
| Explication du `MAX_RT` final | Le journal R1 se termine par un échec apparent : c'est la 6ᵉ émission après l'arrêt de R2 (`--count 5`). | `08_validation.tex` |
| `\crefname` pour annexes et listings ; accords `le/la` | `\cref` produisait « appendix A » et « La tableau 5.1 ». | `config/commands.tex` |

## Révision 1 — conformité formelle initiale

| Modification | Motivo / Requisito ENSTA | Fonte / Evidência |
|---|---|---|
| Titre du PRe ajusté | Alignement strict sur la convention de stage ENSTA (*INT_4PRe_TA*) | Fiche de stage ENSTA & `metadata.tex` |
| Mentions de rôle encadrement | Rôles exacts : CNRS (organisme), Lab-STICC (unité), F. Ruffier (tuteur), P. Xu (référent ENSTA), Q. Brateau (accompagnement technique) | Convention signée ENSTA/CNRS |
| Tag `NON CONFIDENTIEL` en rouge | Exigence formelle du guide de rédaction PRe ENSTA sur la page de garde | `CONTENU DU RAPPORT_PRe.doc` |
| Précision sur la non-confidentialité | Distinction entre classification non confidentielle et autorisation effective de publication externe | Clauses CNRS de la convention |
| Tableau de traçabilité des missions | Rapprochement explicite entre les objectifs initiaux et le travail réalisé | Convention vs état final du code/PCB |
| Section Inductances de puissance (L1/L2) | Description de la sélection finale Würth WE-MAPI 4020 (`74438356047` L1 4,7 µH & `74438356033` L2 3,3 µH) | Revue PCBA JLCPCB & Datasheets |
| Rendu 3D Onshape HD sans coupe | Insertion de visuels 3D complets sans découpe aux marges (assemblage + berceau batterie + flasques) | API REST Onshape & `chapters/03_systeme_caiman.tex` |
| Section Banc HIL & Précisions | Clarification des 5 cycles HIL et avertissement explicite sur les limites (Wi-Fi/UDP vs nRF24 SPI physique) | Code C protocole & logs HIL |
| Suppression des pages blanches | Passage en `oneside, openany` et remplacement des `\cleardoublepage` par `\clearpage` | Structure LaTeX `main.tex` |
