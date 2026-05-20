# Créas du marquee — landing V2

## Convention de nommage

Dépose tes fichiers ici en suivant cette convention :

- `01.jpg` à `08.jpg` → cards de la **rangée 1** (qui défile vers la gauche)
- `09.jpg` à `16.jpg` → cards de la **rangée 2** (qui défile vers la droite)

## Formats acceptés

- **Images** : `.jpg`, `.png`, `.webp` — extension à mettre en dur dans `index-mvp-v2.html` si différent de `.jpg`
- **Vidéos** : `.mp4` (autoplay, loop, muted, sans son) — modifier la balise dans le HTML pour passer de `<img>` à `<video>`

## Dimensions recommandées

- **Ratio** : 4:5 (portrait, format Meta natif)
- **Dimensions** : minimum 800×1000 px, idéal 1080×1350 px
- **Poids** : <300 Ko par image pour ne pas casser le temps de chargement
- **Compression** : passe les images dans [TinyPNG](https://tinypng.com) ou [Squoosh](https://squoosh.app) avant dépôt

## Tips

- Tu peux mixer images et vidéos dans la même rangée
- Si tu n'as que 8 créas pour l'instant, mets-les en `01-08` et duplique-les en `09-16`
- Pour cacher les labels (les pills "Hook · Problem/Solution" etc.), supprime les `<span class="ad-card-label">...</span>` correspondants dans le HTML
