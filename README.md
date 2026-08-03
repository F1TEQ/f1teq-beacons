# F1TEQ — Base internationale de balises pour ESP32

Dépôt de données utilisé par le **F1TEQ Rotor Controller ESP32-S3**.

## Fichiers consommés par l’ESP32

- `data/manifest.json` : version, nombre d’entrées, taille et SHA-256.
- `data/beacons.min.json` : base compacte téléchargée par l’ESP32.
- `data/beacons.json` : base détaillée et lisible sur ordinateur.

La base initiale de ce dépôt contient **250 couples balise/fréquence** :

- **152 entrées internationales** ;
- **98 entrées françaises et ultramarines REF** ;
- **90 entrées IBP** avec les créneaux 1 à 18 sur cinq bandes HF.

## Mise à jour automatique

L’action GitHub **Mise à jour des balises** s’exécute chaque lundi à 04:17 UTC.
Elle tente de rafraîchir la source IARU Région 1, puis réinjecte obligatoirement :

1. la base internationale de secours ;
2. les 98 entrées REF de `data/manual_extra.json` ;
3. les créneaux NCDXF/IARU IBP.

Le workflow refuse toute publication contenant moins de **250 entrées**, moins de **98 REF** ou un nombre différent de **90 créneaux IBP**.

## URL utilisées par le firmware

```text
https://raw.githubusercontent.com/F1TEQ/f1teq-beacons/main/data/manifest.json
https://raw.githubusercontent.com/F1TEQ/f1teq-beacons/main/data/beacons.min.json
```

## Ajouter ou corriger une balise française

Modifier `data/manual_extra.json`, puis lancer manuellement l’action GitHub.
L’identifiant unique est le couple `call` + `frequency_hz`.

## Contrôle local

```bash
python scripts/build_beacons.py --offline
python scripts/validate_repository.py
```

## Sources

- IARU Région 1, base coordonnée VHF/UHF/SHF ;
- NCDXF/IARU International Beacon Project ;
- REF, liste française et ultramarine.

Les sources et dates sont conservées dans chaque enregistrement. Une base mondiale absolument exhaustive n’existe pas ; les données doivent donc être vérifiées avant un usage critique.
