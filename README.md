# Banco de imágenes de InvestIQ para carruseles

Un banco de fotos propio, reales y con licencia libre, para el chat de Claude que hace los carruseles de
InvestIQ. Tiene 10 fotos por cada empresa del S&P 500 y por cada empresa famosa que cotiza en EE. UU., 10 por
cada tema de mercado y 10 por cada sector. Las fotos no se copian: el banco guarda el enlace de cada una en
Wikimedia Commons, qué muestra, su crédito y dónde recortarla. El chat lo lee en `bank/index.json`. Cómo
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

Una empresa recibe primero sus tomas escritas a mano (si las tiene), después su imagen principal de Wikidata,
una foto de su CEO, las mejores fotos de su categoría de Commons y subcategorías (como mucho dos por
subcategoría y sin casi duplicados) y, si aún faltan, búsquedas de su sede, tiendas, fábricas y oficinas en
las que aparezca el nombre de la empresa. Los temas y sectores tienen 10 búsquedas escritas a mano.

Solo acepta fotos que cumplen todo esto:

- licencia libre: CC0, dominio público, CC BY o CC BY-SA;
- al menos 1600 px de lado largo y 1000 px de lado corto, en JPEG o PNG;
- un nombre de archivo que no indique logo, mapa, gráfico, diagrama, captura o ilustración;
- que no se use ya en otra ficha.

Puntúan mejor las fotos destacadas o de calidad de Commons, las que recortan bien a 4:5 y 1:1, las recientes
(salvo en tomas históricas) y las de licencia más libre.

Muchas empresas poco conocidas no tendrán 10 fotos libres propias: el índice lo dice y el chat las completa
con las de su sector.

## Corregir a mano

- **Una foto mala:** en `bank/manifest.json`, en la ficha, añade `"exclude": ["File:…"]` y
  `"manual": ["exclude"]`, y después ejecuta `python image_bank.py build --only <ID>`.
- **Una ficha que no se debe tocar más:** `"manual": true`.
- **Una empresa con la categoría de Commons, el CEO o el nombre equivocados:** en `bank/universe.json`,
  corrige el campo y añade `"manual": ["commons_category"]` (o el campo que sea). Se mantiene en cada
  `universe`.
- **Una empresa que falta o sobra:** añádela o quítala en `extras.json`.

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
- **Enlaces.** Si una foto se borra de Commons, su enlace deja de funcionar. Repetir `build --redo` de vez en
  cuando renueva el banco.
