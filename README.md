# Banco de imágenes de InvestIQ para carruseles

Un banco de fotos propio, reales y con licencia libre, para que el chat de Claude que hace los carruseles de
InvestIQ las use: 5 o 6 por cada gran empresa y por cada tema de mercado, ya recortadas a 4:5 y 1:1, con
el crédito de cada foto y un índice (`bank/index.json`) que el chat lee para encontrarlas. Cómo conectarlo al
chat: [`CAROUSEL_CHAT.md`](CAROUSEL_CHAT.md).

- **50 empresas** (297 tomas): AAPL, MSFT, NVDA, AMZN, GOOGL, META, TSLA, AVGO, ORCL, NFLX, PLTR, AMD, INTC,
  TSM, ASML, CRM, ADBE, IBM, MU, SPCX, BRK-B, JPM, V, MA, LLY, NVO, UNH, JNJ, PFE, WMT, COST, XOM, CVX, KO, PEP,
  MCD, NKE, DIS, SBUX, HD, BA, CAT, LMT, GE, GS, BAC, BLK, UBER, MSTR, COIN.
  Normalmente: sede, producto o fábrica, tienda o planta, evento, y su CEO o fundador.
- **29 temas** (171 tomas): Fed y tipos, inflación, recesión, empleo, Wall Street alcista, crash y volatilidad,
  IA, centros de datos y energía, semiconductores, bitcoin y cripto, oro, petróleo, aranceles, China, dólar,
  bonos y deuda, vivienda, temporada de resultados, salidas a bolsa, coches eléctricos, nuclear y uranio,
  defensa, consumo, bancos, invertir y jubilación, economía espacial, fármacos GLP-1, política de EE. UU.,
  Europa y BCE.

Qué muestra cada toma está en `catalog.json`. Para añadir una empresa o un tema, o cambiar una toma, se edita
ahí y después se ejecutan `python image_bank.py check` y `python image_bank.py build --only <ID>`.

## Construirlo

Hace falta Python 3.9 o superior, Pillow (`pip install pillow`) y acceso a `commons.wikimedia.org` y
`upload.wikimedia.org`.

```bash
python image_bank.py build
```

Tarda unos 20–30 minutos la primera vez. Si se corta, vuelve a ejecutarlo: solo hace lo que falta. Después,
sube los cambios a GitHub (`git add bank && git commit && git push`) para que el chat vea las fotos nuevas.

| Comando | Qué hace |
|---|---|
| `build` | busca y descarga las tomas que faltan, y genera el índice, los créditos, los prompts y la hoja de revisión |
| `build --only NVDA,gold` | repite esas empresas o temas (sirve el ID, el ticker o un alias) |
| `build --redo` | repite todas las tomas, menos las corregidas a mano |
| `build --no-sa` | descarta las fotos CC BY-SA (ver Licencias) |
| `build --formats 4x5,1x1,16x9,9x16` | recortes que se generan (por defecto 4x5 y 1x1; también hay 3x4 para TikTok) |
| `index --base-url URL` | vuelve a generar `index.json` con otra dirección pública (por defecto, la del repo en GitHub) |
| `list NVDA --format 1x1` | rutas y créditos de las fotos de una empresa o tema |
| `sheet` · `credits` · `prompts [--all]` | vuelve a generar solo la hoja de revisión, los créditos o los prompts |
| `check` | valida `catalog.json` |

## Qué genera (en `bank/`)

- `<ID>/<toma>.4x5.jpg` (1200×1500, diapositiva vertical de Instagram y documento de LinkedIn),
  `<toma>.1x1.jpg` (1200×1200, cuadrada) y `<toma>.thumb.jpg` (miniatura). Ejemplo: `bank/NVDA/leader.4x5.jpg`.
  Estos archivos van a Git (unos 250 MB en total) para que el chat los descargue por su enlace público.
  La foto a tamaño completo (`<toma>.jpg`, lado largo de 2560 px) se queda fuera de Git y sirve para hacer
  nuevos recortes.
- `index.json`: lo que lee el chat de carruseles. Por cada foto: qué muestra, si sale una persona real, el
  enlace de cada recorte, el crédito y la fuente, más las reglas de uso.
- `manifest.json`: el detalle completo de cada toma (archivo de Commons, autor, licencia, año, avisos y tres
  alternativas).
- `CREDITS.md` y `credits.csv`: el crédito de cada foto.
- `review.html`: todas las tomas de un vistazo. Las que conviene revisar salen en naranja.
- `prompts.jsonl`: un prompt de imagen con IA para cada toma sin foto. Nunca incluye tomas de personas reales.

## Panel

`python dashboard.py salida.html` genera una página con todas las tomas: su estado, su foto (cuando está
descargada), su crédito, el enlace a Commons y el prompt de IA. Está publicada en
https://claude.ai/artifact/GH9JEo598mzHkmJkjAmc1e. Las miniaturas se publican junto a la página
(`dashboard.thumb_files()`).

## Cómo elige cada foto

Busca en Wikimedia Commons con la consulta de la toma y, si salen menos de tres fotos válidas, con las
alternativas. Solo acepta fotos que cumplen todo esto:

- licencia libre: CC0, dominio público, CC BY o CC BY-SA;
- al menos 1600 px de lado largo y 1000 px de lado corto;
- un nombre de archivo que no indique logo, mapa, gráfico, diagrama, captura o ilustración;
- que no la use ya otra toma.

Puntúan mejor las fotos destacadas o de calidad de Commons, las que recortan bien a 4:5 y 1:1 (las
panorámicas puntúan peor), las recientes (salvo en tomas históricas) y las de licencia más libre. En las
fotos de personas, el recorte se centra en el tercio superior, donde suele estar la cara.

## Revisar y corregir a mano

Se abre `bank/review.html` y, para cada toma que no convenza, se edita la toma en `bank/manifest.json`. Hay
que listar en `"manual"` el campo que se cambia. Los cambios se mantienen en cada `build`.

- `"exclude": ["File:…"], "manual": ["exclude"]`: no usar nunca esas fotos (pasa a la siguiente).
- `"prefer": "File:…", "manual": ["prefer"]`: usar esa foto (por ejemplo, una de las alternativas).
- `"focus": [0.3, 0.4], "manual": ["focus"]`: el punto que conservan los recortes (0–1, de izquierda a
  derecha y de arriba abajo).
- `"manual": true`: no tocar nunca esa toma.

Después: `python image_bank.py build --only <ID>`.

## Licencias

- **Crédito.** CC BY y CC BY-SA obligan a citar al autor y la licencia. El texto está listo en el campo
  `credit` de cada foto, por ejemplo: «Daniel L. Lu, CC BY-SA 4.0, via Wikimedia Commons». En un carrusel
  basta con ponerlo en letra pequeña en la diapositiva o en una diapositiva final de créditos.
- **CC BY-SA.** Se discute si un carrusel que incluye una foto CC BY-SA tiene que publicarse con esa misma
  licencia. Para evitar la duda, usa `--no-sa`: solo deja CC0, dominio público y CC BY, a cambio de menos
  fotos.
- **Personas y marcas.** Las fotos de personas (los CEO) sirven para un uso informativo, no para dar a
  entender que la persona respalda InvestIQ. Los logos y los productos que salen en las fotos siguen siendo
  marcas de sus dueños. El manifiesto avisa cuando Commons marca una foto con restricciones
  (`personality`, `trademarked`).
- **CEO.** Comprueba el cargo antes de publicar. El catálogo nombra a quien sale en la foto, pero los cargos
  cambian.
- **Repo público.** Para que el chat descargue las fotos, el repo tiene que ser público. Solo contiene el
  código, el catálogo y fotos con licencia libre con sus créditos.
