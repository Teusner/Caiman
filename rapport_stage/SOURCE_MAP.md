# Cartographie des sources — rapport Caiman

Audit réalisé le 2026-08-16. Les résultats KiCad ci-dessous ont été reproduits avec KiCad CLI 10.0.5. Les chemins sont relatifs à la racine du dépôt.

## Légende

- **Démontré** : preuve directe disponible.
- **À confirmer** : déclaration ou artefact incomplet demandant une preuve supplémentaire.
- **Non démontré** : aucune preuve trouvée dans le périmètre audité.
- **Contredit** : l'état audité ne permet pas l'affirmation envisagée.

## Sources institutionnelles et administratives

| Affirmation | État | Source | Utilisation / précaution |
|---|---|---|---|
| Le rapport PRe vise 30–40 pages hors annexes. | Démontré | `rapport/CONTENU DU RAPPORT_PRe.doc` | Dimensionnement du corps du rapport. |
| Le rapport exige couverture, résumés bilingues, mots-clés, remerciements, sommaire, listes, conclusion, bibliographie, glossaire et annexes. | Démontré | `rapport/CONTENU DU RAPPORT_PRe.doc`, `rapport/Rapport_Modele_PRe.doc` | L'ordre précis doit être confirmé car les deux documents divergent. |
| Le modèle visible emploie Century 12 pt, interligne simple, chapitres 22 pt, sections 14 pt et marges 2,5 cm à gauche / 2 cm ailleurs. | Démontré par lecture Word COM | `rapport/Rapport_Modele_PRe.doc`, `rapport/CONTENU DU RAPPORT_PRe.doc` | Le rapport conserve la hiérarchie et les marges mais réduit le corps à 11 pt à la demande de Joab. |
| Un planning/Gantt doit présenter le déroulement de la contribution. | Démontré et intégré | `rapport/CONTENU DU RAPPORT_PRe.doc`, historique Git et jalons documentés | Figure présente au chapitre 9. |
| Les anciens champs de couverture mentionnent ENSTA Paris. | Démontré | `rapport/Rapport_Modele_PRe.doc` | Ne pas recopier sans adaptation. |
| ENSTA Paris et ENSTA Bretagne ont fusionné au 1er janvier 2025. | Démontré par source primaire | Bilan officiel ENSTA 2024 : <https://www.ensta-bretagne.fr/system/files/2025-09/bilan_recherche_ensta_2024_web.pdf> | Justifie de vérifier la marque officielle actuelle du campus de Brest. |
| L'organisme légal d'accueil est le CNRS ; l'unité est le Lab-STICC (UMR 6285), sur le campus ENSTA de Brest. | Démontré | convention signée, pp. 1–2 ; <https://www.ensta.fr/recherche-et-innovation/decouvrir-nos-activites-de-recherche/les-laboratoires> | ROBEX vient des sources institutionnelles externes, pas de la convention. |
| Le stagiaire est Joab da Silva Bezerra. | Démontré | convention signée, p. 2 ; confirmation de Joab | Utilisé dans les métadonnées PDF, la couverture et le pied de page. |
| Le sujet administratif est « Conception d'un essaim de robots Subsurface ». | Démontré | convention signée, p. 3 | Distinguer les missions prévues des résultats effectivement atteints. |
| Franck Ruffier est directeur de recherche CNRS en robotique dans l'équipe ROBEX du Lab-STICC. | Démontré par source institutionnelle actuelle | <https://www.ensta.fr/actualites/franck-ruffier-un-chercheur-en-robotique-bio-inspire> | Fonction à afficher sous réserve de la place exacte d'encadrant à confirmer. |
| Quentin Brateau est présenté comme doctorant en robotique marine et a assuré l'accompagnement technique quotidien. | Statut institutionnel démontré ; rôle quotidien confirmé par Joab | page officielle de la spécialité Robotique autonome ENSTA : <https://webperso.ensta.fr/sperob/> ; confirmation de Joab | Ne pas le présenter comme tuteur conventionnel : Franck Ruffier est le tuteur désigné. |
| La soutenance a lieu le 27 août 2026. | Confirmé par Joab | réponse du 2026-08-16 | Les dates du stage restent distinctes et à fournir. |
| Le stage se déroule du 1er juin au 31 août 2026. | Confirmé par Joab mais document administratif ambigu | réponse du 2026-08-16 ; convention p. 3 | Le PDF rature 31/08 au profit de 03/08, tout en conservant « trois mois » et 65 jours ; demander l'avenant/version définitive. |
| Formation : cycle ingénieur généraliste, spécialité Robotique autonome, promotion 2027. | Confirmé par Joab ; intitulé recoupé avec l'ENSTA | réponse du 2026-08-16 ; <https://www.ensta.fr/en/find-my-training/ensta-bretagne-engineering-program> | Formulation retenue sur la couverture. |
| Franck Ruffier est le tuteur principal ; Quentin Brateau assure l'accompagnement technique quotidien. | Confirmé par Joab | réponse du 2026-08-16 | Ne pas présenter Quentin comme tuteur institutionnel. |
| Philippe Xu est le référent pédagogique ENSTA. | Démontré | convention signée, p. 2 | Ajouté à la couverture comme référent formel. |
| La diffusion du rapport nécessite une autorisation écrite du Lab-STICC/CNRS. | Démontré | convention signée, p. 10 | Le caractère public du dépôt ne remplace pas l'autorisation ; utiliser « diffusion soumise à autorisation ». |
| Les logos employés sont les identités officielles actuelles ENSTA/IP Paris et Lab-STICC. | Démontré par sources institutionnelles | <https://www.ensta.fr/logo-et-charte-graphique> ; <https://labsticc.fr/img/labsticc_logo.png> | Fichiers RGB conservés sans recoloration ni déformation. |

## Historique Git et attribution

| Affirmation | État | Source | Utilisation / précaution |
|---|---|---|---|
| La base amont est `5fc0681`. | Démontré | `git merge-base upstream/main origin/main` | Point de départ des comparaisons. |
| `origin/main` ajoute 15 commits après l'amont. | Démontré | `git rev-list --count upstream/main..origin/main` | Délimitation de la contribution versionnée. |
| La branche locale et `origin/main` sont à `77a253e`. | Démontré | fast-forward puis `git status --branch`, `git rev-parse` | Les modifications préexistantes du dossier électronique et du rapport ont été conservées. |
| Les vues `docs/caiman_pcb_front.png` et `docs/caiman_pcb_rear.png` existaient déjà dans l'amont. | Démontré | historique Git des deux fichiers | Utilisables comme illustration générique, pas comme preuve directe de la contribution finale. |
| `CONTEXTO_CONVERSA.txt` est une source contextuelle non versionnée. | Démontré | `git status --short` | À traiter comme information fournie par l'utilisateur, non comme résultat Git. |

## Architecture électronique

| Affirmation | État | Source | Utilisation / précaution |
|---|---|---|---|
| Le microcontrôleur principal est un STM32F765VITx. | Démontré | `electronics/caiman.kicad_sch`, netlist XML KiCad | Décrire les interfaces réellement câblées. |
| I²C2 dessert LPS22HB, LIS2MDL, LSM6DSO et des connecteurs ; I²C1 est exposé séparément. | Démontré | schéma/netlist KiCad | Figure de bus recommandée. |
| Le nRF24 utilise SPI1, CE, CSN, IRQ et une antenne U.FL. | Démontré | schéma/netlist KiCad | Ne pas confondre câblage avec validation radio physique. |
| Le stockage microSD utilise SDMMC et une détection de carte. | Démontré | schéma/netlist KiCad | Peut soutenir la partie journalisation. |
| L'alimentation comprend AP63205 5 V puis AP63203 3,3 V, avec protection LM74700. | Démontré | schéma/netlist KiCad | Architecture et calcul d'ondulation présentés au chapitre 4. |
| À 1,1 MHz, le modèle buck idéal donne environ 0,56 A d'ondulation pour L1 et 0,26 A pour L2 dans les conditions nominales retenues. | Calcul reproductible, non mesuré | datasheet AP6320x, schéma/netlist et équation du chapitre 4 | À 2 A, le pic L1 estimé dépasse l'Isat typique publiée ; présenter comme risque de dimensionnement à vérifier. |
| La carte est à 2 couches cuivre et comporte 134 empreintes, 510 pastilles et 214 vias. | Démontré | `electronics/caiman.kicad_pcb`, statistiques KiCad | Toujours associer ces chiffres à la révision finale auditée. |
| Le paquet de production contient Gerbers cuivre/masque/pâte/sérigraphie/contour, perçages, BOM et CPL. | Démontré | archive de production sous `electronics/` | Vérifie la préparation de fichiers, pas leur acceptation ni la fabrication. |

## ERC, DRC et évolution du PCB

| Affirmation | État | Source | Utilisation / précaution |
|---|---|---|---|
| L'ERC passe de 10 erreurs/44 avertissements à 0 erreur/42 avertissements. | Démontré | rapports KiCad reproduits sur `5fc0681` et l'état final | Dire « zéro erreur ERC », pas « ERC sans avertissement ». |
| Le DRC initial `5fc0681` produit 288 erreurs, 259 avertissements et 1 non connecté. | Démontré | KiCad CLI 10.0.5, JSON, sans refill | Proche du nombre mémorisé d'environ 293–297 ; publier le chiffre reproductible et son protocole. |
| `654cd20` et `b900398` ne laissent qu'une erreur DRC active avec l'outil actuel. | Démontré | rapports KiCad reproduits | Ne pas annoncer zéro sans une ancienne capture/configuration expliquant l'écart. |
| Les exclusions DRC stockées passent de 11 à 7 ; les exclusions restantes concernent surtout des géométries internes de composants/polygones cuivre. | Démontré | fichiers `.kicad_pro`, rapport KiCad | Chaque exclusion publiée doit être justifiée, jamais masquée dans un total. |
| `0c5e24e` est la révision envoyée en fabrication. | Confirmé par Joab et identité des fichiers vérifiée | réponse du 2026-08-16 ; hash du PCB courant identique à `0c5e24e` | La carte n'est pas encore reçue. |
| La dernière révision `0c5e24e` présente 49 erreurs actives, 231 avertissements et 0 non connecté dans l'exécution de référence du 2026-08-16. | Démontré | rapport KiCad 10.0.5 ; `DRC_JLC_AUDIT.md` | 6 erreurs de trous sont imputables à une règle KiCad plus conservatrice ; les autres nécessitent une lecture par catégorie. |
| Les 49 erreurs sont uniquement dues à des règles KiCad plus strictes que JLCPCB. | Contredit | `DRC_JLC_AUDIT.md` | 14 clearances sont sous 0,10 mm et 5 rapports signalent 3 couples de nets en court-circuit. |
| La révision finale du dépôt est « DRC clean ». | Contredit dans l'environnement audité | `electronics/caiman.kicad_pcb`, rapport KiCad sur `0c5e24e` | Écrire que la fabrication a été lancée mais que l'audit final a identifié des risques non testés physiquement. |
| Le passage `b58eda6` → `0c5e24e` redimensionne les vias et augmente segments/zones. | Démontré | comparaison sémantique des PCB | Hypothèse de régression DFM ; ne pas attribuer une intention sans confirmation. |
| La carte ne contient plus de nets non routés dans les révisions après `654cd20`. | Démontré avec l'outil audité | rapports DRC | Distinguer « 0 non connecté » de « 0 violation ». |

### Protocole de reproduction DRC

Exécuter sur une archive complète de chaque commit, avec chemin absolu vers le PCB afin que le fichier projet et ses exclusions soient chargés :

```powershell
kicad-cli pcb drc --format json --units mm --severity-error --severity-warning --output report.json C:\chemin\absolu\caiman.kicad_pcb
```

Ne pas ajouter `--refill` si l'objectif est de reproduire les chiffres du tableau. Documenter la version de KiCad et tout filtre ajouté.

## BOM, CPL, fabrication et inductances

| Affirmation | État | Source | Utilisation / précaution |
|---|---|---|---|
| La BOM propre contient 64 lignes groupées pour 116 composants, cohérents avec 116 positions CPL. | Démontré | BOM et fichier de positions de production | Les 134 empreintes incluent des éléments sans achat/placement. |
| La colonne `LCSC Part #` de la BOM générique est vide, mais une BOM sélectionnée a été ajoutée. | Démontré | `electronics/production/bom.csv`, `electronics/production/bom_selected_for_jlc_latest.csv` | Utiliser la BOM sélectionnée pour parler de la commande. |
| La BOM sélectionnée et le schéma indiquent L1 = 4,7 µH et L2 = 3,9 µH. | Démontré | BOM sélectionnée, `electronics/caiman.kicad_sch` | L'hypothèse L2 = 3,3 µH est abandonnée. |
| L1 choisie : Vishay IHLP1616BZER4R7M5A, 4,7 µH, LCSC C3223759. | Démontré pour la sélection | BOM sélectionnée ; <https://www.lcsc.com/product-detail/C3223759.html> ; <https://www.vishay.com/docs/48330/48330.pdf> | Courant thermique typ. 3,2 A ; saturation typ. 1,8 A. Vérifier la marge au courant de sortie réel. |
| L2 choisie : Sunlord SWPA4030S3R9MT, 3,9 µH, JLCPCB C96899. | Démontré pour la sélection | BOM sélectionnée ; <https://jlcpcb.com/partdetail/Sunlord-SWPA4030S3R9MT/C96899> | 2,1 A nominal, 3 A saturation, 74 mΩ. |
| L'AP63203/AP63205 est un convertisseur 2 A, 3,8–32 V ; la plage générale d'inductance recommandée est 2,2–10 µH. | Démontré par source primaire | <https://www.diodes.com/assets/Datasheets/AP63200-AP63201-AP63203-AP63205.pdf> | Le tableau nominal propose 3,9 µH pour AP63203 et 4,7 µH pour AP63205 ; justifier 3,3 µH avec le calcul d'ondulation et les conditions réelles. |
| La révision `0c5e24e` et la BOM sélectionnée ont été envoyées en fabrication ; la carte n'est pas encore reçue. | Confirmé par Joab | réponse du 2026-08-16 | Dire « commandée/en attente de réception », jamais « validée ». |
| La commande PCB date du 23 juin 2026 et porte sur 5 cartes FR-4 TG135, 2 couches, 100,87 × 93,94 mm, 0,8 mm, cuivre 1 oz, ENIG, masque noir et sérigraphie blanche. | Démontré | `order details.png` | La capture confirme aussi vias tented, flying-probe et IPC classe 2. |
| Le stackup KiCad et la commande utilisent la même épaisseur. | Contredit | `electronics/caiman.kicad_pcb` = 1,6 mm ; `order details.png` = 0,8 mm | Mentionner l'écart et son impact mécanique potentiel. |

## Firmware embarqué

| Affirmation | État | Source | Utilisation / précaution |
|---|---|---|---|
| La tâche principale initialise et lit LSM6DSO, LIS2MDL, LPS22HB, batterie, RGB et logger. | Démontré par code | `firmware/Core/Src/main.c`, couche applicative/capteurs | « Intégré au logiciel », pas « validé sur matériel ». |
| La période visée est environ 100 ms/10 Hz. | Démontré par code | tâche `AppSensors_Task` et délais | Mesure temporelle physique non démontrée. |
| Les pilotes nRF24, ESC et Bar30 ont du code mais ne sont pas reliés au chemin principal audité. | Démontré par code | `firmware/` et références d'appels | Classer comme implémentation partielle/non intégrée. |
| GNSS, Ping2, RC, fuite et contact magnétique restent des stubs ou squelettes. | Démontré par code | `firmware/` | À présenter honnêtement dans une matrice de maturité. |
| Les pilotes sont prêts pour le premier bring-up. | Démontré comme intention documentaire | `firmware/DRIVERS_IMPLEMENTATION.md` | Ce document ne constitue pas une preuve de bring-up réalisé. |
| Les pilotes ont été validés sur la carte physique. | Faux à la date du rapport | confirmation de Joab le 2026-08-16 | Aucun pilote n'a été testé ; le délai de fabrication empêche le bring-up avant la remise. |
| Le logger écrit un CSV cohérent. | À corriger/clarifier | en-tête à 10 colonnes, enregistrement à 18 champs | Signaler comme anomalie détectée ou corriger avant validation. |

## Simulation et protocole

| Affirmation | État | Source | Utilisation / précaution |
|---|---|---|---|
| La simulation locale possède 32 tests Python passants. | Démontré par exécution | `python -m pytest simulator/tests -q` sur `4162c87` | Résultat reproductible localement. |
| `origin/main` possède 33 tests Python passants. | Démontré par exécution sur archive | tests à `77a253e` | Le test supplémentaire concerne l'évolution récente du terrain bathymétrique. |
| La simulation modélise cinq AUV, bathymétrie, flotte, relais surface, pertes, énergie et télémétrie. | Démontré par code/tests | `simulator/`, `simulator/tests/` | Préciser quelles valeurs proviennent d'hypothèses utilisateur. |
| L'exécution locale du 16 août 2026 passe 33 tests. | Démontré par nouvelle exécution | `python -m pytest -q` dans `simulator/` | Résultat : 33 réussites en 5,32 s. |
| Le démonstrateur a été conteneurisé pour une VPS avec Streamlit et Caddy. | Démontré pour le déploiement/configuration | `Dockerfile`, `compose.yaml`, `Caddyfile`, `DEPLOY.md` | Le DNS `caimansim.fr` résout, mais HTTP/HTTPS public ne répondait pas depuis le poste d'audit le 16 août ; ne pas affirmer une disponibilité continue. |
| Une télémétrie tient dans une trame nRF24 exacte de 32 octets. | Démontré par test | `simulator/tests/test_compact_protocol.py` | À illustrer par un tableau octet/champ. |
| Chiffrement, intégrité, anti-rejeu, relais, rotation de clés et scénario de capture sont testés. | Démontré en simulation | `test_crypto.py`, `test_network.py`, `test_replay_protection.py`, `test_simulation.py` | Ne pas présenter comme sécurité certifiée ni test radio physique. |
| L'empreinte d'un faisceau de 25° à 3 m vaut environ 1,33 m. | Calcul géométrique | documentation technique Ping ; équation du chapitre 7 | Modèle de sonar, pas mesure hydrographique. |
| Le filtre complémentaire présenté pour l'IMU est une perspective théorique. | Démontré comme modèle publié, non implémenté dans le banc | Narkhede et al. (2021), DOI 10.3390/s21061937 | Ne publier ni coefficient, ni calibration, ni précision obtenue. |

## HIL ESP32 / Raspberry Pi

| Affirmation | État | Source | Utilisation / précaution |
|---|---|---|---|
| Le prototype HIL existe dans la branche locale et `origin/main`. | Démontré par code | commit `77a253e`, dossier `protocol_hil/` | Base versionnée utilisée pour le banc. |
| Le prototype contient bibliothèque C portable, cibles ESP32/Raspberry Pi, codec, chiffrement et modèle nRF24. | Démontré par code | `protocol_hil/README.md`, sources et tests | Décrire comme prototype logiciel/HIL. |
| Des tests natifs couvrent vecteur de référence, tamper/replay, FIFO, IRQ, doublons, portée et codec. | Démontré par lecture et exécution | `protocol_hil/tests/` ; `evidence/hil_2026-08-16.log` | 2/2 tests réussis sur Raspberry Pi 4 avec GCC 14.2.0 et Mbed TLS 3.6.5. |
| Le firmware HIL compile et se flashe sur l'ESP32 réel. | Démontré | ESP-IDF 6.0.2, ESP32-D0WDQ6, `/dev/ttyUSB0` CP210x | Build réussi, écritures vérifiées par hash et reset matériel effectué. |
| Le protocole a été démontré sur un ESP32 et un Raspberry Pi réels. | Démontré | `evidence/hil_2026-08-16.log` | 5/5 cycles bidirectionnels authentifiés ; support nRF24 simulé sur Wi-Fi/UDP, pas de validation radio nRF24 physique. |
| Le scénario bidirectionnel exact est entièrement versionné dans `77a253e`. | Non démontré | état Git du Raspberry le 2026-08-16 | `node_node` est une évolution locale non commitée au-dessus de la base ; archiver/versionner avant une reproduction indépendante. |

## Assets disponibles et manquants

| Asset | État | Source / besoin |
|---|---|---|
| Vues 3D PCB avant/arrière | Disponible, mais héritée de l'amont | `docs/caiman_pcb_front.png`, `docs/caiman_pcb_rear.png` |
| Texture/illustration océan du simulateur | Disponible | assets du simulateur |
| Capture DRC avant/après | Manquante | À produire avec commit, version et filtres visibles |
| Capture JLCPCB des détails de commande | Disponible | `order details.png` |
| Photo PCB nue/assemblée | Manquante | À fournir par Joab |
| Photo et logs de bring-up | Manquants | À fournir par Joab |
| Logs HIL ESP32/Raspberry Pi | Disponible | `evidence/hil_2026-08-16.log` |
| Photo HIL ESP32/Raspberry Pi | Disponible | `figures/hil/raspberry_pi4_esp32_2026-08-16.jpeg` ; documente le matériel, pas le banc câblé en fonctionnement |
| Photos STM32/IMU | Disponibles | `figures/stm32/nucleo_h743zi2_banc_2026-06-10.jpg`, `imu_icm20948_detail_2026-06-10.jpg` |
| Captures du simulateur | Disponibles | `figures/simulator/` : mission, maillage de surface, trame et capture physique |
| Logos institutionnels | Disponibles | `figures/logos/`, sources officielles documentées dans `figures/README.md` |
| Gantt réel du stage | Disponible | reconstruit depuis Git, commande et essais documentés |
