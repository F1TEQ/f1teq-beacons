# Format de la base compacte ESP32

Le document `beacons.min.json` contient :

- `v` : version du schéma ;
- `t` : date de génération UTC ;
- `n` : nombre d’entrées ;
- `k` : dictionnaire des clés ;
- `d` : tableau des balises.

| Clé | Signification |
|---|---|
| `c` | indicatif |
| `f` | fréquence en hertz |
| `b` | bande |
| `g` | locator Maidenhead |
| `y` | pays ou code pays |
| `r` | région, État ou département |
| `n` | ville ou QTH |
| `a` | latitude |
| `o` | longitude |
| `s` | état numérique |
| `m` | mode |
| `u` | source |
| `q` | créneau IBP, seulement pour le réseau IBP |
