# F1TEQ — Base complète de balises radioamateur

Ce dépôt est prêt à être utilisé par le micrologiciel F1TEQ Rotor Controller 1.7.5.4 et versions suivantes.

## Contenu garanti

- 152 couples balise/fréquence internationaux de secours ;
- 98 couples balise/fréquence français et ultramarins provenant de la liste REF ;
- 250 entrées au total au moment de la livraison ;
- créneaux 1 à 18 pour les 18 balises NCDXF/IARU IBP sur 14,100, 18,110, 21,150, 24,930 et 28,200 MHz ;
- fréquences stockées en hertz entiers ;
- tri par fréquence, locator, pays, département ou lieu, puis indicatif.

## Sécurité du workflow

Le fichier `.github/workflows/update-beacons.yml` lance un seul constructeur :

```text
scripts/build_beacons.py
```

Ce constructeur réalise lui-même la fusion complète. Il n’existe plus de patch séparé ni de second script pouvant être oublié.

Avant publication, `scripts/validate_repository.py` vérifie obligatoirement :

- au moins 250 entrées ;
- au moins 98 entrées REF ;
- exactement 90 entrées IBP avec un créneau ;
- aucun doublon indicatif/fréquence ;
- cohérence des trois fichiers JSON ;
- taille et SHA-256 du manifeste.

## Installation sur GitHub

Lire `A_LIRE_AVANT_TELEVERSEMENT.txt` à la racine du dépôt.
