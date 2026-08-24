# Audit DRC — révision transmise à la fabrication

Date de l'audit : 2026-08-16 (ré-exécuté et étendu le 2026-08-16)
Outil : KiCad CLI 10.0.5
Carte : `electronics/caiman.kicad_pcb`

## Conclusion

**Le DRC avait bien été validé, mais pas sur la révision qui est partie en fabrication.**

La vérification a été conduite le 9 juin 2026 (`b900398`, message de commit « final DRC verification ») et le résultat était alors conforme. Trois révisions ont ensuite modifié le PCB sans que le contrôle soit réexécuté, et c'est la dernière d'entre elles qui a alimenté l'export des fichiers de production, le jour même de la commande.

## Chronologie reproductible

| Révision | Date | Message | Erreurs DRC | Nature |
|---|---|---|---:|---|
| `654cd20` | 2026-06-08 | DRC Clean | 2 | clearance 0,1291 mm |
| `b900398` | 2026-06-09 | final DRC verification | **1** | clearance 0,1291 mm — **au-dessus** de la capacité JLCPCB (0,10 mm), exclue à raison |
| `4cec774` | 2026-06-10 | Drivers implementation | non exécuté | — |
| `b58eda6` | 2026-06-19 | Footprint correction | non exécuté | — |
| `0c5e24e` | 2026-06-23 | Finalization of PCB → **envoyé à JLCPCB** | **48** | voir ci-dessous |

Le fichier `caiman.kicad_pro`, qui porte les règles et la liste d'exclusions, n'a pas été modifié après `b900398` : le commit final n'a donc jamais fait l'objet d'un contrôle.

La mémoire de l'auteur (« le DRC était propre, et ce que j'ai ignoré tenait dans les tolérances JLCPCB ») est donc exacte — mais elle porte sur `b900398`, pas sur `0c5e24e`. L'unique violation exclue à ce stade est un écart de 0,1291 mm entre `GND` et `/I2C2_SCL` sur U5, effectivement fabricable.

## Résultat sur l'état transmis (`0c5e24e`)

Commande de référence (chemin absolu, pour charger le projet et ses exclusions) :

```powershell
kicad-cli pcb drc `
  --format json `
  --units mm `
  --severity-error --severity-warning `
  --output caiman_drc_0c5e24e.json `
  C:\chemin\absolu\electronics\caiman.kicad_pcb
```

| Catégorie | Nombre |
|---|---:|
| Erreurs | 48 |
| Avertissements | 231 |
| Éléments non connectés | 0 |
| Total | 279 |

Répartition des erreurs : `clearance` 37, `hole_to_hole` 6, `shorting_items` 5.

> Note : avec la liste d'exclusions actuelle du dépôt de travail (une exclusion de moins que la version commitée), le compte passe à 49 erreurs / 280 violations. L'écart correspond exactement à la clearance bénigne de 0,1291 mm mentionnée plus haut. C'est pourquoi la révision **et** la liste d'exclusions doivent être citées avec tout chiffre DRC.
>
> Le refill des zones (`--refill-zones`) n'améliore pas le résultat : 302 violations au lieu de 279. Les erreurs ne sont pas un artefact de remplissage périmé.

## Lecture directe des Gerbers transmis — indépendante de KiCad

L'en-tête de `caiman-F_Cu.gtl` déclare `%FSLAX46Y46*%` (format 4.6) et `%MOMM*%` (millimètres) ; la liste d'ouvertures définit `%ADD59C,0.800000*%`. Les pastilles portent leur net dans le fichier lui-même via les attributs `G04 #@! TO.N,<net>`. Quatre flashs de l'ouverture D59 sont concernés, sur `F.Cu` comme sur `B.Cu` :

| Position (Gerber, mm) | Net déclaré dans le fichier | Ouverture |
|---|---|---|
| (144,825 ; −63,800) | `GND` | D59 = Ø 0,8 mm |
| (144,171593 ; −63,685515) | `+3V3` | D59 = Ø 0,8 mm |
| (160,024265 ; −66,725735) | `GND` | D59 = Ø 0,8 mm |
| (159,975 ; −67,475) | `+3V3` | D59 = Ø 0,8 mm |

Entraxes : 0,663361 mm et 0,750883 mm, pour une somme de rayons de 0,800 mm. Soit **deux fusions de cuivre `GND`/`+3V3` distinctes**, de 137 µm et 49 µm.

### Le DRC de KiCad sous-déclare

Seule la paire à 49 µm est signalée comme `shorting_items`. La paire à 137 µm — pourtant la plus large — n'apparaît que comme violations de `clearance` (0,1034 mm et 0,1070 mm contre des pistes voisines) et `hole_to_hole` (0,2634 mm).

Dans les deux paires, l'une des traversées porte l'attribut `(free yes)` : via non rattachée à un net dans le fichier source, mais résolue en `GND` au moment de l'export Gerber. C'est l'hypothèse la plus probable pour expliquer la différence de traitement, sans qu'elle soit établie avec certitude.

**Conséquence méthodologique : la liste de courts-circuits produite par le DRC est un minorant. Sur ce dossier, la géométrie exportée fait foi.**

## Courts-circuits — vérification géométrique

Ces cinq rapports ne dépendent ni de la version de KiCad, ni des règles de sévérité, ni des tolérances du fabricant. Les distances ci-dessous sont calculées directement depuis les coordonnées et les diamètres inscrits dans le `.kicad_pcb`.

| Nets | Objets | Géométrie | Recouvrement cuivre |
|---|---|---|---:|
| `GND` ↔ `+3V3` | 2 vias Ø 0,8 mm @ (160,0243 ; 66,7257) et (159,975 ; 67,475) | entraxe 0,750883 mm vs somme des rayons 0,8 mm | **−49 µm** |
| `/I2C2_SDA` ↔ `+3V3` | piste 0,3 mm (B.Cu) vs via Ø 0,8 mm @ (154,5 ; 87,1) | distance axe 0,491315 mm vs 0,55 mm | **−59 µm** |
| `/CSN` ↔ `+3V3` | via Ø 0,6 mm @ (172,8 ; 85,275) vs piste 0,6 mm (F.Cu) | distance axe 0,600 mm vs 0,600 mm | **contact exact** |

À quoi s'ajoute une quatrième proximité critique, classée `clearance` et non `shorting_items` parce qu'elle ne se recouvre pas tout à fait :

| Nets | Objets | Clearance mesurée |
|---|---|---:|
| `/VBAT` ↔ `/I2C1_SCL` | piste VBAT (F.Cu) vs via @ (144,6427 ; 67,1427) | **1×10⁻⁶ mm** |

La paire `GND` / `+3V3` est un court-circuit du rail 3,3 V. Une usine capable de reproduire fidèlement la géométrie reproduira également ces contacts.

## Quel dossier a réellement été téléversé — NON DÉTERMINÉ

Le dépôt contient trois versions successives du dossier de production :

| Dossier de production | Généré le | Pads en recouvrement |
|---|---|---|
| `4cec774` | 09/06/2026 13:41 | 0 |
| `b58eda6` | 19/06/2026 15:30 | 0 |
| `0c5e24e` | 22/06/2026 15:45 | 2 |
| arbre de travail | 16/08/2026 00:44 | 2 |

**Lequel a été envoyé n'est pas établi.** Deux obstacles :

- le bouton *Production file* du portail JLCPCB est désactivé sur le compte utilisé (« You do not have permission to perform this action. Please contact your account admin ») ;
- le poste de travail employé au moment de l'export n'est plus accessible, et l'auteur indique avoir travaillé depuis une machine dont l'état n'a pas été commité.

Une analyse antérieure avait conclu à tort que le dossier téléversé correspondait à `0c5e24e`, sur la base d'une copie locale dont la provenance avait été mal attribuée. **Cette conclusion est retirée.**

Toute affirmation sur l'état électrique des cinq cartes commandées reste donc indéterminée jusqu'au contrôle de continuité à la réception.

### Comment lever le doute

Demander le fichier de production à l'administrateur du compte JLCPCB, ou au support via le chat du portail, en citant la commande `W2026062315153820` / `Y4-12661268A`. Comparer ensuite ses empreintes SHA-256 aux trois dossiers ci-dessus.

### Le pont de cuivre ne peut pas disparaître à la gravure

Deux pastilles de rayon 0,400 mm distantes de 0,750883 mm se recoupent sur une largeur perpendiculaire de
2·√(0,400² − 0,375441²) = **0,276 mm**.

Avec une sous-gravure latérale typique de l'ordre de 35 µm par bord pour un cuivre 1 oz, il subsiste environ 0,206 mm de cuivre continu. La liaison est franche, non marginale.

## Erreurs trou-à-trou (6) — non bloquantes

Distances mesurées : 0,2634 ; 0,3509 ; 0,4071 ; 0,4461 ; 0,4689 et 0,4842 mm.

Toutes sont inférieures à la règle interne du projet (0,4995 mm) mais supérieures à la capacité JLCPCB publiée de 0,20 mm entre vias. Il s'agit bien d'un conservatisme de projet, pas d'une impossibilité de fabrication.

## Erreurs de clearance (37)

Règle interne : 0,15 mm. Capacité JLCPCB 1–2 couches, cuivre 1 oz : piste/espacement 0,10/0,10 mm.
Source primaire : <https://jlcpcb.com/capabilities/Capabilities?type=1> (consultée le 2026-08-16).

| Intervalle mesuré | Nombre | Lecture |
|---|---:|---|
| `< 0,10 mm` | 13 | sous la capacité générale du procédé — à corriger |
| `= 0,10 mm` | 5 | exactement à la limite publiée |
| `0,10 – 0,15 mm` | 18 | sous la règle interne, fabricable |

Les plus faibles : `/CSN`–`+3V3` 0,025 mm ; `/CE`–`/SCK`, `/I2C1_SCL`–`/I2C1_SDA`, `/I2C2_SDA`–`/I2C2_SCL`, `/I2C2_SDA`–`GND` à 0,050 mm ; `/CSN`–`/IRQ` 0,0502 mm.

La valeur `clearance` de KiCad mesure le cuivre, alors que certaines capacités JLCPCB sont exprimées depuis le bord du trou. Cette nuance peut requalifier certaines occurrences via-piste, mais elle ne concerne pas les courts-circuits ci-dessus.

## Identité de la révision

| Fichier | Hash Git (`0c5e24e`) |
|---|---|
| `electronics/caiman.kicad_pcb` | `a26eb7826b09a1cded091d075b8684b1d8a1fea8` |

Le `.kicad_pcb` est identique octet pour octet entre `0c5e24e`, `HEAD` et l'arbre de travail : la géométrie auditée est bien celle qui a produit les Gerbers.

Le projet KiCad est configuré en 2 couches, 1,6 mm, 35 µm de cuivre. La commande JLCPCB confirme 2 couches et 1 oz mais fixe l'épaisseur fabriquée à 0,8 mm ; la comparaison des clearances utilise donc bien le cas 1 oz, l'écart d'épaisseur restant une différence mécanique entre la CAO et la commande.

## Formulation retenue dans le rapport

Voir `chapters/05_fabrication.tex`, section « Évolution du DRC et régression de la révision transmise ».

Éviter « DRC clean », « carte validée » et « fonctionnement électrique confirmé » pour la révision `0c5e24e`.

## Action requise (hors rapport)

Avant tout assemblage des cinq cartes commandées : corriger les trois courts-circuits et les 13 proximités sous 0,10 mm, puis rétablir le DRC comme condition de sortie de l'export de production. Contrôler la continuité `+3V3` / `GND` au multimètre dès réception, avant toute mise sous tension.
