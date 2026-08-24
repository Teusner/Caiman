# Evidence Map - Traçabilité des affirmations du PRe

| Affirmation du rapport | Preuve concrète / Fichier | Statut |
|---|---|---|
| Sujet et cadrage PRe | Convention signée (`DA-SILVA-BEZERRA-Joab-25812_...pdf`) | Déclaré |
| Correction du filtre capacitif STM32 | Commit `dd041de` ($C_{12}$--$C_{18}$ de série à parallèle) | Démontré |
| Sélection inductances L1/L2 Würth | Fichiers BOM LCSC (`C2045367` & `C2045382`) & Datasheets AP6320x | Démontré |
| Commande PCB JLCPCB 23/06/2026 | Capture d'écran commande (`jlcpcb_order_details_2026-06-23.png`) | Démontré |
| DRC validé le 09/06/2026 (1 seule clearance, fabricable) | `kicad-cli pcb drc` sur `b900398` — 1 erreur à 0,1291 mm > capacité JLCPCB 0,10 mm | Démontré |
| DRC **non** ré-exécuté avant l'export de production | `git log` : `4cec774`, `b58eda6`, `0c5e24e` modifient le PCB après `b900398` ; `caiman.kicad_pro` inchangé | Démontré |
| 48 erreurs DRC sur la révision transmise `0c5e24e` | `kicad-cli` 10.0.5, JSON archivé ; 37 clearance / 6 hole_to_hole / 5 shorting_items | Démontré |
| 3 paires de nets en court-circuit géométrique | Calcul depuis coordonnées et diamètres du `.kicad_pcb` : −49 µm, −59 µm, contact (`DRC_JLC_AUDIT.md`) | Démontré |
| Quel dossier de production a été téléversé | Téléchargement restreint sur le compte JLCPCB ; poste d'export non conservé | **Non déterminé** |
| État électrique des 5 cartes commandées | Dépend du dossier téléversé, non identifié ; contrôle de continuité prévu à la réception | **Non déterminé** |
| Le pont de cuivre ne se résorbe pas à la gravure | Largeur perpendiculaire 0,276 mm ; ~0,206 mm subsistants après sous-gravure 1 oz | Démontré |
| Identité de la géométrie auditée | `caiman.kicad_pcb` = `a26eb782…` identique sur `0c5e24e`, `HEAD` et arbre de travail | Démontré |
| Modélisation 3D CAO Onshape | Document Onshape `5fdbe64fd9eb405fbd96993d` & Renders API | Démontré |
| Simulateur Python / 33 tests pytest | State Git `77a253e` & suite `pytest` dans `simulator/` | Démontré |
| Protocol HIL 5 cycles bidirectionnels | Code C dans `protocol_hil/` & logs `figures/hil/hil_r1_output.txt`, `hil_r2_output.txt` | Démontré |
| Disponibilité publique de `caimansim.fr` | DNS résout vers la VPS ; ports HTTP/HTTPS sans réponse au 16/08/2026 | Non démontré |
| Absence de bring-up PCB physique | PCB commandé le 23/06/2026, non reçu à la date de remise | Non réalisé |
| Validation du lien radio nRF24 physique | Transport du banc HIL = Wi-Fi/UDP ; nRF24 modélisé en logiciel | Non réalisé |
