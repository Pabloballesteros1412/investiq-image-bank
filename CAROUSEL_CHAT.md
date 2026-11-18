# Conectar el banco al chat de carruseles

El chat de Claude que hace los carruseles de InvestIQ encuentra las fotos en un índice público
(`bank/index.json`). Las fotos están en Wikimedia Commons (las de empresas: solo las mejores, revisadas a ojo),
Unsplash, Flickr (solo licencias libres, también a través de Openverse), la NASA, Pixabay, la Biblioteca del
Congreso de EE. UU. (archivo de Carol M. Highsmith, dominio público) y WordPress Photos (CC0), y el chat las
recorta a la diapositiva.

1. **El repo tiene que ser público** (ya lo es).
2. **Pega este bloque en las instrucciones del proyecto** de Claude que hace los carruseles:

```
Banco de imágenes de InvestIQ
- Índice: https://raw.githubusercontent.com/Pabloballesteros1412/investiq-image-bank/main/bank/index.json
- Antes de elegir fotos para un carrusel, lee el índice y sus reglas ("rules"). Busca la empresa por ticker o
  nombre, el tema por alias (por ejemplo "fed", "inflation", "gold", "ai") o el sector, y abre el archivo de
  esa ficha (su "file"): hasta 10 fotos por empresa, 30 por empresa famosa y 50 por tema o sector
  ("target" dice cuántas debería tener).
- Elige por lo que muestra cada foto ("shows"); mira "preview" si necesitas verla antes de elegir.
- Recorta "url" a la diapositiva: 4:5 (1200×1500) o 1:1 (1200×1200), centrada en "focus" [x, y]
  (en HTML: object-fit: cover; object-position: x% y%).
- Usa solo fotos del banco, nunca imágenes de otras webs.
- Pon el crédito de cada foto que uses tal cual aparece en "credit", en letra pequeña en la diapositiva o en
  una diapositiva final de créditos. Si la foto trae "author_url" (Unsplash, Flickr, NASA, Pixabay, Biblioteca del Congreso, WordPress) y el texto del post
  admite enlaces, enlaza ahí al fotógrafo.
- Solo recortar: no retoques, no redibujes y no generes imágenes parecidas. En las fotos de personas reales
  ("person": true) no des a entender que esa persona respalda InvestIQ. Los cargos (CEO, presidente...) pueden
  estar desfasados: compruébalos antes de nombrarlos.
- Si una empresa tiene "fill_from", sus fotos propias no llegan a 10: puedes completar con las de ese
  sector, pero son genéricas y nunca las presentes como de la empresa.
- Las fotos con "plain": true son de la empresa pero sosas (una fachada sin nombre, luz gris): van después
  de las demás. Usa antes las otras y, para la portada, mejor una del sector que una "plain".
- Las fotos con "low_res": true (Flickr vía Openverse) solo miden 1024 px y a toda la diapositiva se ven
  blandas: nunca de portada; úsalas en pequeño (media diapositiva, recuadro o mosaico).
```

3. **Prueba:** pide al chat «lee el índice del banco y enséñame las fotos de Nvidia».

Si el chat crea las diapositivas con código y no consigue leer el índice o descargar las fotos, en los
ajustes de claude.ai permite los dominios `raw.githubusercontent.com`, `upload.wikimedia.org`,
`images.unsplash.com`, `images.pexels.com`, `live.staticflickr.com`, `tile.loc.gov` y `pd.w.org` en el acceso a internet de la ejecución de código.

Cada vez que se rehace el banco (`build` y `git push`), el chat ve los cambios en el siguiente carrusel. No
hace falta cambiar nada en el proyecto.

## Vídeos (desde el 18 de noviembre de 2026)

El banco también guarda clips de vídeo de los temas y sectores: Pixabay (la fuente principal), Wikimedia Commons
(solo CC0, dominio público y CC BY, y solo los que tienen nota 3) y la NASA (espacio). Igual que las fotos, se
enlazan y no se copian, y cada clip se revisa a ojo. Hay clips verticales (Reels, TikTok, Shorts) y horizontales.
Cuando el índice de vídeos tenga clips, pega también este bloque en las instrucciones del proyecto que haga los
vídeos (o en el de carruseles):

```
Banco de vídeos de InvestIQ
- Índice: https://raw.githubusercontent.com/Pabloballesteros1412/investiq-image-bank/main/bank/videos/index.json
- Lee el índice y sus reglas ("rules"). Busca el tema o el sector por su "id" (por ejemplo "gold", "oil",
  "sector-tech") y abre su archivo ("file"): hasta 10 clips por tema y sector.
- Elige por lo que muestra el clip ("shows", y "poster" para verlo), su orientación ("orientation") y su
  duración ("duration", en segundos).
- Para Reels, TikTok o Shorts usa clips "vertical". Un clip horizontal con "vertical_crop_ok": true es 4K y se
  puede recortar a 9:16 (1080×1920) sin perder calidad; los demás horizontales van en vídeo 16:9 o como franja
  dentro de un vídeo vertical.
- Descarga el archivo para editarlo: "url" es el mejor (a menudo 4K) y "url_1080" uno más ligero en 1080p.
  Quita el sonido original del clip.
- Son clips genéricos del tema: nunca los presentes como imágenes de una empresa, persona o suceso concreto.
- Pon el crédito de cada clip ("credit") en el texto del post o en el cierre del vídeo.
- Si un tema no tiene clips, usa sus fotos (bank/index.json).
```

Si el chat descarga los clips con código, permite también `cdn.pixabay.com` e `images-assets.nasa.gov`
(además de `upload.wikimedia.org`, que ya está en la lista de arriba).
