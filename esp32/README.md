# Utilisation depuis l’ESP32

Le firmware F1TEQ 1.7.5.x intègre déjà le téléchargement sécurisé.

1. Lire `data/manifest.json`.
2. Comparer la version distante à la version locale.
3. Télécharger `data/beacons.min.json` dans un fichier temporaire.
4. Vérifier la taille, le nombre d’entrées et le SHA-256.
5. Remplacer la base locale uniquement après validation complète.

URL :

```text
https://raw.githubusercontent.com/F1TEQ/f1teq-beacons/main/data/manifest.json
https://raw.githubusercontent.com/F1TEQ/f1teq-beacons/main/data/beacons.min.json
```
