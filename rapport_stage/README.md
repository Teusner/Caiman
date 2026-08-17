# Rapport de stage Caiman

Compilation prévue :

```powershell
latexmk -pdf main.tex
```

Nettoyage :

```powershell
latexmk -C
```

Le projet utilise `biblatex` avec le moteur BibTeX. Une distribution LaTeX complète, telle que MiKTeX ou TeX Live, doit fournir `pdflatex`, `latexmk` et `bibtex`.

À la date de création du scaffold, aucune distribution LaTeX complète n'était détectée dans le système. La version de revue a néanmoins été compilée avec Tectonic portable 0.17.0, téléchargé dans le dossier temporaire et vérifié par SHA-256. Le fichier `main.pdf` a été généré avec succès (44 pages au 16 août 2026). La commande `latexmk` ci-dessus reste à vérifier lorsqu'une distribution MiKTeX ou TeX Live sera installée.

Avant la remise :

1. traiter les points administratifs et les preuves facultatives listés dans `TODO_JOAB.md` ;
2. confirmer l'autorisation écrite de diffusion et la date de fin de stage ;
3. vérifier l'accès public à `caimansim.fr` ;
4. recompiler puis relire le PDF final après toute modification.

Les logos institutionnels, les photographies, les captures du simulateur et les traces HIL sont organisés dans `figures/` et `evidence/`. Les sources et le statut de chaque affirmation importante sont consignés dans `SOURCE_MAP.md`.
