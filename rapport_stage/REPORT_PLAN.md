# Plan de travail du rapport de stage — Caiman

Dernière mise à jour : 2026-08-16  
État : audit documentaire et technique terminé ; convention et modèle Word relus ; HIL physique reproduit ; simulateur documenté ; rapport LaTeX compilé et contrôlé visuellement.

Titre de travail retenu : **Conception et préparation à la fabrication d'une électronique embarquée pour une flotte de robots sous-marins autonomes**.  
Sous-titre : **Simulation de mission, supervision et prototypage HIL**.

## 1. Règle de preuve

Le rapport distinguera systématiquement trois niveaux d'affirmation :

- **Démontré** : vérifiable dans Git, dans un fichier de conception, dans une sortie d'outil reproduite ou dans une source primaire.
- **À confirmer** : plausible et cohérent avec les sources, mais nécessitant une preuve de Joab (capture, photo, journal, facture, mesure ou confirmation explicite).
- **À ne pas affirmer** : contredit par l'état audité du dépôt ou sans preuve suffisante.

Cette règle est particulièrement importante pour les termes « DRC clean », « testé sur carte », « validé en conditions réelles », « fabriqué » et « démontré sur ESP32/Raspberry Pi ».

## 2. Cadre institutionnel extrait des modèles

Les deux documents de `rapport/` ont été analysés comme références, sans modification des originaux.

- Volume cible : **30 à 40 pages de corps de rapport**, hors annexes.
- Format A4 ; le modèle prescrit 12 pt, mais le corps a été réduit à 11 pt à la demande de Joab ; interligne simple, recuo de 1,5 cm et marges 2,5 cm à gauche / 2 cm ailleurs.
- Hiérarchie observée dans le modèle : chapitre 20–22 pt, section 14 pt gras, sous-section 12 pt gras italique.
- Les figures doivent être numérotées, légendées et appelées dans le texte.
- Le code détaillé doit aller en annexe ; le corps privilégie schémas, organigrammes, tableaux de résultats et extraits courts.
- Un planning de type Gantt est attendu dans la partie contribution/gestion du projet.
- Le rapport doit contenir résumé et abstract sur une même page, mots-clés, remerciements, sommaire, listes des figures/tableaux, conclusion, bibliographie, glossaire français–anglais et annexes.
- La couverture emploie les logos officiels actuels ENSTA avec IP Paris et Lab-STICC. L'organisme légal d'accueil est le **CNRS**, l'unité le Lab-STICC (UMR 6285), sur le campus ENSTA de Brest, équipe ROBEX.
- La convention impose une autorisation écrite avant diffusion ; le rapport est donc marqué **diffusion soumise à l'autorisation du Lab-STICC / CNRS**, même si le dépôt technique est public.
- Encadrants communiqués par Joab : Franck Ruffier et Quentin Brateau. Les sources institutionnelles identifient Franck Ruffier comme directeur de recherche CNRS en robotique au sein de ROBEX/Lab-STICC et Quentin Brateau comme ingénieur en robotique au Lab-STICC, également présenté comme doctorant en robotique sous-marine.
- Stage : **du 1er juin au 31 août 2026** ; soutenance : **27 août 2026**.
- Formation : cycle ingénieur généraliste, spécialité Robotique autonome, promotion 2027.
- Franck Ruffier est le tuteur principal ; Quentin Brateau assure l'accompagnement technique quotidien sans être le tuteur institutionnel.
- Philippe Xu est ajouté comme référent pédagogique formel indiqué par la convention.

## 3. Angle narratif proposé

Fil directeur : **concevoir et préparer à l'industrialisation une électronique embarquée modulaire pour une flotte de robots sous-marins, puis établir une chaîne progressive de validation allant des vérifications CAO à la simulation réseau et au prototype HIL**.

Le rapport séparera clairement :

1. le travail antérieur présent dans le dépôt amont ;
2. la contribution de Joab, identifiable dans les 15 commits ajoutés après l'amont ;
3. l'état de preuve atteint à la fin du stage ;
4. les limites et validations restant à réaliser.

Le cœur de la contribution est réparti en quatre axes :

- correction et finalisation du schéma et du PCB ;
- préparation des fichiers de fabrication ;
- mise en place des pilotes et de l'architecture firmware ;
- simulation de flotte et prototypage du protocole de communication/HIL.

## 4. Proposition de structure et budget de pages

| Partie | Contenu principal | Cible |
|---|---|---:|
| Pages liminaires | Couverture, résumé/abstract, mots-clés, remerciements, sommaire, listes | hors décompte |
| 1. Introduction générale | Problème, objectifs, démarche, limites et structure | 2 p. |
| 2. Organisme d'accueil et contexte | ENSTA Brest, Lab-STICC, équipe, contexte robotique marine | 3 p. |
| 3. Besoin et cahier des charges | Mission de flotte, contraintes énergie/environnement/communication, critères de validation | 3 p. |
| 4. Conception de l'électronique embarquée | Architecture d'alimentation, STM32, capteurs, radio, stockage et interfaces | 7 p. |
| 5. Routage, DRC et préparation à la fabrication | État initial, corrections, règles, exclusions, DFM, BOM/CPL/Gerbers | 4 p. |
| 6. Logiciel embarqué | Architecture, pilotes effectivement intégrés, composants partiels/stubs, journalisation | 5 p. |
| 7. Simulation, protocole et HIL | Modèle de flotte, trame 32 octets, sécurité, relais, scénarios, prototype ESP32/Raspberry Pi | 6 p. |
| 8. Vérification et résultats | ERC/DRC reproductibles, tests Python, tests natifs si preuves disponibles, essais physiques | 4 p. |
| 9. Gestion du projet et recul critique | Chronologie/Gantt, décisions, difficultés, écarts, compétences acquises | 2 p. |
| 10. Conclusion et perspectives | Bilan mesuré, limites, prochaines validations | 2 p. |
| **Total estimé** | Corps du rapport | **38 p.** |

Annexes envisagées : nomenclature détaillée, fichiers de placement, règles DRC/exclusions, tableaux ERC/DRC complets, brochage, format des trames, résultats de tests, extraits de code utiles et procédure de reproduction.

## 5. État technique audité

### 5.1 Historique et périmètre Git

- Branche locale `main` et `origin/main` : commit `77a253e`.
- `upstream/main` : `5fc0681`.
- Base commune : `5fc0681` ; **15 commits** sont présents dans `origin/main` après cette base.
- Les quatre commits intégrés lors du fast-forward portent notamment sur le tableau de bord, la génération de terrains bathymétriques et le prototype HIL ESP32/Raspberry Pi.
- Les fichiers non suivis `CONTEXTO_CONVERSA.txt` et `rapport/` préexistaient à l'audit et n'ont pas été modifiés.

### 5.2 Électronique

Architecture vérifiée dans le schéma/netlist : STM32F765, double conversion 5 V/3,3 V, protection d'entrée, capteurs LPS22HB/LIS2MDL/LSM6DSO, nRF24, microSD, RGB, sorties propulseurs et interfaces série/I²C.

La carte finale contient 2 couches cuivre, 134 empreintes, 510 pastilles, 773 segments et 214 vias. Le paquet de production contient Gerbers, perçages PTH/NPTH, nomenclature et positions.

Évolution ERC reproduite avec KiCad 10.0.5 :

| Révision | Erreurs | Avertissements | Lecture |
|---|---:|---:|---|
| `5fc0681` (amont) | 10 | 44 | état initial |
| `dd041de` | 3 | 42 | alimentation STM32 corrigée |
| `c66b3fb` | 1 | 38 | correction GND du LSM6DSO |
| `2be6335` | 0 | 42 | plus d'erreur ERC bloquante |
| état final audité | 0 | 42 | avertissements encore présents |

Évolution DRC reproduite avec KiCad 10.0.5, sans remplissage automatique des zones, en chargeant le projet et ses exclusions :

| Révision | Erreurs actives | Avertissements | Non connectés | Observation |
|---|---:|---:|---:|---|
| `5fc0681` | 288 | 259 | 1 | état initial très dégradé |
| `654cd20` | 1 | 254 | 0 | forte réduction |
| `b900398` | 1 | 254 | 0 | commit nommé « final DRC verification » |
| `4cec774` | 2 | 223 | 0 | ajout des pilotes/production |
| `b58eda6` | 2 | 229 | 0 | correction d'empreinte |
| `0c5e24e` / final local | 49 | 231 | 0 | mesure reproduite le 2026-08-16 ; régression après modification du routage/vias |

Les comptes peuvent varier si KiCad remplit les zones ou si les filtres/versions changent. La commande, la version et la révision devront accompagner tout chiffre publié.

Joab confirme que `0c5e24e` est la révision envoyée en fabrication. Le passage de `b58eda6` à ce commit redimensionne les vias et augmente les segments/zones.

Une analyse détaillée des 49 erreurs se trouve dans `DRC_JLC_AUDIT.md` :

- 6 erreurs de distance trou-à-trou sont dues à la règle KiCad de 0,5 mm, plus conservatrice que la capacité JLCPCB publiée de 0,2 mm ;
- 38 erreurs concernent le clearance cuivre : 19 sont entre 0,10 et 0,15 mm, 5 sont à 0,10 mm et 14 sont inférieures à 0,10 mm ;
- 5 rapports de court-circuit représentent 4 couples d'objets et 3 couples de nets : `/I2C2_SDA`–`+3V3`, `/CSN`–`+3V3` et `GND`–`+3V3`.

Les règles JLCPCB expliquent donc une partie du total, mais ne permettent pas d'écarter les clearances sous la limite générale ni les courts-circuits entre nets. Le rapport présentera ce constat comme une limite de la révision envoyée, découverte avant réception et impossible à arbitrer par un essai physique dans le calendrier du stage.

### 5.3 Fabrication et inductances

- La BOM générique du dépôt comporte 64 groupes et 116 composants placés, mais sa colonne `LCSC Part #` est vide.
- Joab a ajouté `electronics/production/bom_selected_for_jlc_latest.csv`, identifié comme la BOM sélectionnée pour la commande.
- Cette BOM maintient L1 = 4,7 µH et L2 = 3,9 µH ; l'hypothèse antérieure d'une substitution par 3,3 µH est abandonnée.
- L1 sélectionnée : Vishay `IHLP1616BZER4R7M5A`, LCSC `C3223759`, 4,7 µH, boîtier 4,5 × 4,1 mm, courant thermique typique 3,2 A et courant de saturation typique 1,8 A.
- L2 sélectionnée : Sunlord `SWPA4030S3R9MT`, JLCPCB `C96899`, 3,9 µH, boîtier 4 × 4 mm, courant nominal 2,1 A et saturation 3 A.
- Les empreintes, courants réels des rails et marges de saturation seront présentés comme vérifications de conception ; aucune mesure physique n'est disponible avant la remise du rapport.
- La capture `order details.png` confirme une commande du 23 juin 2026 : 5 cartes, FR-4 TG135, 2 couches, 100,87 × 93,94 mm, épaisseur 0,8 mm, cuivre externe 1 oz, ENIG, masque noir, sérigraphie blanche, vias tented, flying-probe et IPC classe 2.
- L'épaisseur commandée de 0,8 mm diffère du stackup KiCad configuré à 1,6 mm ; cette différence sera explicitée comme paramètre mécanique de fabrication.

### 5.4 Firmware

Éléments intégrés dans la tâche applicative principale : LSM6DSO, LIS2MDL, LPS22HB, mesure batterie, RGB, journalisation microSD et GNSS sous forme de stub. La boucle vise environ 10 Hz.

Éléments disposant de code mais non appelés dans le chemin principal audité : nRF24, ESC et Bar30/MS5837. Éléments encore essentiellement stubs : GNSS, Ping2, récepteur RC, fuite d'eau et contact magnétique.

Joab confirme qu'aucun pilote n'a été testé physiquement sur la carte. La carte commandée n'a pas encore été reçue et le délai de fabrication ne permettra pas un bring-up avant le rapport. Le document `DRIVERS_IMPLEMENTATION.md` décrit d'ailleurs l'état comme prêt pour le premier bring-up. Un écart à corriger/mentionner a été détecté : l'en-tête CSV du logger annonce 10 colonnes, tandis que l'application écrit 18 champs.

### 5.5 Simulation et HIL

- L'état `4162c87` passe **32 tests Python**.
- L'état `77a253e` passe **33 tests Python**, avec compilation Python vérifiée.
- Les scénarios couvrent notamment la retransmission, les relais, la portée surface/sous-marine, la bathymétrie, le chiffrement, l'anti-rejeu, la rotation de clés et une capture physique simulée.
- Le chapitre décrit l'architecture Streamlit, la mission bathymétrique, la séparation entre vérité simulée et connaissance du PC, le graphe radio de surface, les exports, les limites et le déploiement Docker/Caddy sur VPS.
- Quatre captures locales reproductibles documentent la mission, le maillage de surface, la trame exacte et la capture physique. Le DNS public résout, mais le service externe devra être remis en ligne avant la soutenance.
- Le HIL ajouté dans `origin/main` fournit une implémentation C portable, une cible ESP32, une cible Raspberry Pi, un modèle nRF24 et des tests natifs du protocole.
- Les tests natifs ont été compilés et exécutés sur un Raspberry Pi 4 Model B Rev 1.5 : **2/2 tests réussis** avec CMake 3.31.6, GCC 14.2.0 et Mbed TLS 3.6.5.
- Le firmware bidirectionnel `node_node` a été compilé avec ESP-IDF 6.0.2 puis flashé sur un ESP32-D0WDQ6 connecté en USB/CP210x.
- Le HIL réel a été reproduit le 2026-08-16 sur Wi-Fi/UDP entre l'ESP32/R1 (`192.168.4.1`) et le Raspberry/R2 (`192.168.4.2`) : **5/5 cycles R1–R2–R1 réussis**, trames chiffrées/authentifiées de 32 octets et séquences monotones dans les deux directions.
- Un `MAX_RT` initial a précédé le démarrage du récepteur ; trois réponses R2 ont ensuite utilisé une retransmission simulée avant `TX_DS`. Le journal synthétique est conservé dans `evidence/hil_2026-08-16.log`.
- Le scénario `node_node` exécuté est présent dans l'arbre de travail non versionné du Raspberry, au-dessus de la base `77a253e` ; il devra être versionné ou archivé pour une reproduction indépendante complète.

## 6. Figures et tableaux

Déjà intégrés :

1. logos institutionnels officiels et couverture administrative ;
2. vues 3D avant/arrière héritées du dépôt ;
3. détails de la commande JLCPCB ;
4. matrice des pilotes et calcul d'ondulation L1/L2 ;
5. photos NUCLEO-H743ZI2 et ICM-20948 ;
6. architecture du simulateur, mission, maillage, trame et sécurité ;
7. photo du matériel HIL, résultats et journaux ;
8. tableau des tests reproductibles et Gantt ;
9. calculs simples d'énergie, estimation d'attitude, sonar, graphe et efficacité de trame ;
10. correspondance entre activités et enseignements du cursus.

Les compléments photographiques encore utiles sont classés dans `TODO_JOAB.md`.

Les vues PCB présentes dans `docs/` pourront être utilisées comme artefacts du dépôt, mais elles viennent de l'historique amont et ne prouvent pas à elles seules la contribution ni la version fabriquée.

## 7. Stratégie de rédaction

1. Obtenir l'autorisation de diffusion et lever l'ambiguïté administrative sur la date de fin.
2. Remettre en ligne le démonstrateur public et capturer l'URL.
3. Ajouter, si disponibles, les preuves visuelles complémentaires classées dans `TODO_JOAB.md`.
4. Effectuer une dernière relecture avec les encadrants sans supprimer les limites DRC, HIL et absence de bring-up.

## 8. Critères de fin

Le rapport sera considéré prêt lorsque :

- chaque résultat important renvoie à une source ou à une preuve ;
- la version de PCB envoyée en fabrication est identifiée sans ambiguïté ;
- DRC/ERC sont décrits avec version d'outil, commit et traitement des exclusions ;
- les validations simulées, HIL et physiques ne sont jamais confondues ;
- la couverture et les mentions institutionnelles sont confirmées, ainsi que l'autorisation de diffusion ;
- la compilation LaTeX est reproductible sans erreur ;
- aucune question P0 ne subsiste sans être explicitement transformée en limite du projet.
