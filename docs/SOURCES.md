# Sources et stratégie de conservation

## IARU Région 1

Le workflow tente de télécharger le CSV public de coordination IARU Région 1.
Si le téléchargement ou le décodage échoue, la base de secours de
`data/international_seed.json` est conservée.

## NCDXF/IARU IBP

Les 18 sites et leurs cinq fréquences sont conservés dans la base internationale
de secours. Le champ `slot` vaut de 1 à 18.

## REF

Les 98 entrées françaises et ultramarines sont conservées dans
`data/manual_extra.json`. Elles sont réinjectées à chaque construction et sont
prioritaires en cas de doublon indicatif/fréquence.
