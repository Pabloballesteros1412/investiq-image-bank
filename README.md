# Banco de imágenes de InvestIQ para carruseles

Un banco de fotos propio, reales y con licencia libre, para el chat de Claude que hace los carruseles de
InvestIQ. Tiene 10 fotos por cada empresa del S&P 500 y por cada empresa famosa que cotiza en EE. UU., 10 por
cada tema de mercado y 10 por cada sector. Las de empresas vienen de Wikimedia Commons y solo se publican las
mejores, revisadas a ojo; las de temas y sectores, de Unsplash y Pexels (y de Commons cuando ellos no tienen lo
que se busca). Las fotos no se copian: el banco guarda el enlace de cada una, qué muestra, su crédito y dónde
recortarla. El chat lo lee en `bank/index.json`. Cómo
conectarlo al chat: [`CAROUSEL_CHAT.md`](CAROUSEL_CHAT.md).

- **Empresas (unas 590):** las del S&P 500, que se leen de Wikipedia en cada `universe`, más 86 empresas
  famosas que cotizan en EE. UU. y no están en el índice (`extras.json`: TSMC, ASML, Novo Nordisk, Alibaba,
  Shopify, Spotify, SpaceX, Rivian, IonQ...). 50 de ellas tienen además tomas escritas a mano en `catalog.json`
  (sede, producto, tienda, evento, CEO).
- **37 temas:** Fed, inflación, recesión, empleo, Wall Street, crash, IA, centros de datos, chips, cripto, oro,
  petróleo, aranceles, China, dólar, bonos, vivienda, resultados, salidas a bolsa, coches eléctricos, nuclear,
  defensa, consumo, bancos, invertir, espacio, GLP-1, política de EE. UU., Europa, computación cuántica,
  robótica, ciberseguridad, India, Japón, metales, viajes y lujo.
- **11 sectores GICS:** tecnología, salud, finanzas, consumo discrecional, comunicación, industria, consumo
  básico, energía, servicios públicos, inmobiliario y materiales. Rellenan los huecos de las empresas que no
  llegan a 10 fotos propias, marcadas como genéricas.

## Estado (4 nov 2026, noche)

Primera construcción completa contra Wikimedia: 3.828 fotos. Tras ver una muestra, Pablo decidió quedarse solo
con las mejores de Commons y usar Unsplash y Pexels. Las 3.828 se revisaron a ojo y **407 tienen nota 3**: son las
únicas que publica el índice (336 de empresas: 220 empresas tienen al menos una; 71 de temas y sectores). Falta
lanzar Unsplash y Pexels, que rellenarán temas y sectores: el código está listo, pero el entorno necesita sus
claves y acceso a sus dominios (ver «Construirlo»).

## Construirlo

Hace falta Python 3.9 o superior (sin más paquetes) y acceso a `en.wikipedia.org`, `www.wikidata.org` y
`commons.wikimedia.org`.

Desde las sesiones de Claude en la nube, Wikimedia frena las llamadas anónimas a su API (error 429, «demasiadas
peticiones»), porque muchas sesiones salen por las mismas direcciones. Con una cuenta, el límite es el suyo:
crea una clave de acceso y guárdala en la variable de entorno `WIKIMEDIA_TOKEN`. El programa la usa sola si
existe. Para crearla, inicia sesión en Wikimedia, confirma tu correo (Wikimedia lo exige:
<https://meta.wikimedia.org/wiki/Special:ChangeEmail> y después el enlace que te llega) y abre
<https://meta.wikimedia.org/wiki/Special:OAuthConsumerRegistration/propose/oauth2>, marca «This consumer is for
use only by …» (solo para tu cuenta: se aprueba al momento), elige «Request authorization for specific
permissions» sin añadir permisos y copia el «Access token» que aparece al final. No la subas nunca al repo.

Para Unsplash y Pexels hacen falta sus claves en `UNSPLASH_ACCESS_KEY` y `PEXELS_API_KEY` (gratis: en
<https://unsplash.com/developers>, «New Application», y en <https://www.pexels.com/api/>) y acceso a
`api.unsplash.com`, `images.unsplash.com`, `api.pexels.com` e `images.pexels.com`. Sin clave, esa fuente se
salta. Unsplash da 50 búsquedas por hora a una aplicación nueva (5.000 cuando la aprueba para producción: se
pide en su web) y Pexels 200; el programa espera cuando se acaban y guarda las respuestas en `.cache/` (fuera
del repo), así que repetir una construcción no gasta búsquedas.

```bash
python image_bank.py universe
```
```bash
python image_bank.py build
```

`universe` lee la lista del S&P 500 y busca cada empresa en Wikidata: su categoría de Commons, su CEO y su
imagen principal. `build` busca las fotos. La primera vez tarda una hora o más; si se corta, vuelve a
ejecutarlo y solo hace lo que falta. Al terminar, sube los cambios (`git add -A && git commit && git push`):
el chat ve el banco nuevo en cuanto están en GitHub.

| Comando | Qué hace |
|---|---|
| `universe` | rehace la lista de empresas (`bank/universe.json`); conviene repetirlo cuando cambie el S&P 500 |
| `build` | busca las fotos de todo lo que falta y genera el índice, los créditos y los prompts |
| `build --only NVDA,gold` | repite esas empresas, temas o sectores (sirve el ID, el ticker o un alias) |
| `build --kind topic,sector` | solo temas y sectores (o solo `company`) |
| `build --redo` | repite todo, menos lo corregido a mano |
| `build --no-sa` | descarta las fotos CC BY-SA (ver Licencias) |
| `index --base-url URL` | vuelve a generar el índice con otra dirección pública (por defecto, la del repo en GitHub) |
| `list NVDA` | enlaces, descripción y crédito de las fotos de una empresa, tema o sector |
| `credits` · `prompts [--all]` | vuelve a generar solo los créditos o los prompts |
| `check` | valida `catalog.json` y `extras.json` |
| `python dashboard.py` | vuelve a generar la galería (`docs/index.html`) |

## Qué genera

- `bank/index.json`: todas las fichas (empresas, temas, sectores) con su número de fotos, el enlace a su
  archivo y las reglas de uso para el chat.
- `bank/subjects/<ID>.json`: las fotos de cada ficha. Por cada foto: `url` (la foto en Commons, de 1280 o
  1920 px de ancho), `preview` (500 px), `shows` (qué muestra), `focus` (el punto donde centrar el recorte),
  `credit`, `licence` y `source` (su página en Commons). Si una empresa tiene menos de 10, `fill_from` indica
  el sector que la completa.
- `bank/universe.json`: la lista de empresas con su ficha de Wikidata.
- `bank/manifest.json`: el detalle completo (archivo, autor, año, cómo se encontró, avisos).
- `bank/CREDITS.md` y `bank/credits.csv`: el crédito de cada foto.
- `bank/prompts.jsonl`: un prompt de imagen con IA para cada toma escrita a mano que se quede sin foto.
  Nunca incluye tomas de personas reales.
- `docs/index.html`: la galería para revisar el banco con las miniaturas. Se publica con GitHub Pages
  (Settings → Pages → Branch `main`, carpeta `/docs`).

## Cómo elige cada foto

Los temas y sectores buscan cada una de sus 10 tomas en Unsplash, Pexels y Commons. Una foto de Unsplash o
Pexels solo vale si su descripción nombra todas las palabras de la búsqueda (o una de las palabras `must` de la
toma), y entonces gana a la de Commons, porque suelen estar mucho mejor hechas. Nunca se usan para personas
reales, ni las de Unsplash+ (no tienen licencia libre), ni renders, ilustraciones o frases.

Una empresa recibe primero sus tomas escritas a mano (si las tiene), después su imagen principal de Wikidata,
la foto de su CEO (la de la ficha de esa persona en Wikidata; si no hay, una búsqueda con su nombre completo
que además nombre la empresa), las mejores fotos de su categoría de Commons y de las subcategorías que llevan
su nombre (como mucho dos por subcategoría y sin casi duplicados) y búsquedas de su sede, tiendas, fábricas y
oficinas. Los temas y sectores tienen 10 búsquedas escritas a mano.

Para que una foto no pase por de la empresa sin serlo:

- en la categoría de la empresa, solo cuentan las fotos cuyo nombre de archivo dice lo que muestran (no
  `IMG_0412` ni `P20210825AS-1824`), y nunca las de patrocinios, carreras, equipos, conciertos o eventos, ni las
  de subcategorías de personas o de empresas participadas (la categoría de NextEra lleva a NASCAR; la de
  Blackstone, a canciones de Fleetwood Mac);
- una foto encontrada por búsqueda tiene que nombrar a la empresa y un lugar o cosa suya (sede, tienda,
  planta, producto...) en el nombre del archivo;
- si el nombre corto es ambiguo (el artículo «Blackstone», «Target» o «Ball» de Wikipedia es otra cosa), se
  busca por el nombre completo y la foto tiene que nombrarlo;
- `shows` dice lo que muestra la foto según su nombre en Commons, no lo que se buscaba.

Solo acepta fotos que cumplen todo esto:

- licencia libre: CC0, dominio público, CC BY o CC BY-SA;
- al menos 1600 px de lado largo y 1000 px de lado corto, en JPEG o PNG;
- un nombre de archivo que no indique logo, mapa, gráfico, diagrama, captura o ilustración, y que no sea una
  carta, un cuadro o un plano (salvo en tomas históricas), ni de antes de 1960 (salvo en tomas históricas);
- las fotos de personas pueden ser más pequeñas (1000 px de lado largo);
- que no se use ya en otra ficha.

Puntúan mejor las fotos destacadas o de calidad de Commons, las que recortan bien a 4:5 y 1:1, las recientes
(salvo en tomas históricas) y las de licencia más libre.

Muchas empresas poco conocidas no tendrán 10 fotos libres propias: el índice lo dice y el chat las completa
con las de su sector.

## Revisar las fotos de Commons

Las fotos de Commons son muy desiguales, así que cada una lleva una nota en `bank/review.json`, puesta mirándolas:
3 = de las mejores (se vería bien a toda página en una diapositiva y muestra claramente algo de la empresa o
del tema), 2 = válida pero sosa, 1 = descartada. **El índice solo publica las de nota 3**, y el programa no vuelve a
elegir las de nota 1 o 2. Las de Unsplash y Pexels no necesitan nota. Los criterios, con ejemplos, están en
`RUBRIC.md`.

Después de cada `build`, las fotos nuevas de Commons quedan sin publicar hasta que se revisan:

```bash
python review.py sheets
```

crea hojas de 30 fotos numeradas en `review/` (hace falta Pillow). Las notas se apuntan en un JSON
(`{"sheet-001": {"3": [1, 2], "2": [5]}}`, las que no se nombran quedan con 1) y se guardan con:

```bash
python review.py grade review/notas.json
```
```bash
python image_bank.py index
```

## Corregir a mano

- **Una foto mala:** en `bank/manifest.json`, en la ficha, añade `"exclude": ["File:…"]` y
  `"manual": ["exclude"]`, y después ejecuta `python image_bank.py build --only <ID>`.
- **Una ficha que no se debe tocar más:** `"manual": true`.
- **Una empresa con la categoría de Commons, el CEO o el nombre equivocados:** en `bank/universe.json`,
  corrige el campo y añade `"manual": ["commons_category"]` (o el campo que sea). Se mantiene en cada
  `universe`.
- **Una empresa que falta o sobra:** añádela o quítala en `extras.json`.
- **Una búsqueda de tema que trae fotos que no son:** en `catalog.json`, en la toma, añade `"must": [...]`
  (palabras que tienen que aparecer en el nombre o las categorías de la foto) o `"exclude": ["File:…"]`, y
  ejecuta `python image_bank.py build --only <tema>`.

## Licencias

- **Crédito.** CC BY y CC BY-SA obligan a citar al autor y la licencia. El texto está listo en `credit`,
  por ejemplo: «Daniel L. Lu, CC BY-SA 4.0, via Wikimedia Commons». En un carrusel basta con ponerlo en letra
  pequeña en la diapositiva o en una diapositiva final de créditos.
- **CC BY-SA.** Se discute si un carrusel con una foto CC BY-SA tiene que publicarse con esa misma licencia.
  Para evitar la duda, usa `--no-sa`: deja solo CC0, dominio público y CC BY, a cambio de menos fotos.
- **Personas y marcas.** Las fotos de personas (los CEO) sirven para un uso informativo, no para dar a
  entender que la persona respalda InvestIQ. Los logos y productos que salen en las fotos siguen siendo
  marcas de sus dueños.
- **CEO.** Wikidata dice quién es el CEO, pero puede ir con retraso: comprueba el cargo antes de publicar.
- **Unsplash y Pexels.** Su licencia permite el uso comercial sin pedir permiso ni citar, aunque ambas piden
  el crédito («Photo by … on Unsplash») y el banco lo da en `credit`, con el enlace al fotógrafo en
  `author_url`. No se puede vender la foto tal cual ni montar con ellas otro banco de fotos público.
- **Enlaces.** Si una foto se borra de Commons, su enlace deja de funcionar. Repetir `build --redo` de vez en
  cuando renueva el banco.
- **Descargas desde la nube.** Desde direcciones compartidas (sesiones en la nube), `upload.wikimedia.org`
  también responde 429 a las descargas anónimas. En el navegador de quien ve el carrusel las fotos cargan
  bien; un script en la nube que las descargue tiene que mandar la clave (`Authorization: Bearer`).
