# Conectar el banco al chat de carruseles

El chat de Claude que hace los carruseles de InvestIQ encuentra las fotos en un índice público
(`bank/index.json`). Las fotos están en Wikimedia Commons y el chat las recorta a la diapositiva.

1. **El repo tiene que ser público** (ya lo es).
2. **Pega este bloque en las instrucciones del proyecto** de Claude que hace los carruseles:

```
Banco de imágenes de InvestIQ
- Índice: https://raw.githubusercontent.com/Pabloballesteros1412/investiq-image-bank/main/bank/index.json
- Antes de elegir fotos para un carrusel, lee el índice y sus reglas ("rules"). Busca la empresa por ticker o
  nombre, el tema por alias (por ejemplo "fed", "inflation", "gold", "ai") o el sector, y abre el archivo de
  esa ficha (su "file"): tiene hasta 10 fotos.
- Elige por lo que muestra cada foto ("shows"); mira "preview" si necesitas verla antes de elegir.
- Recorta "url" a la diapositiva: 4:5 (1200×1500) o 1:1 (1200×1200), centrada en "focus" [x, y]
  (en HTML: object-fit: cover; object-position: x% y%).
- Usa solo fotos del banco, nunca imágenes de otras webs.
- Pon el crédito de cada foto que uses tal cual aparece en "credit", en letra pequeña en la diapositiva o en
  una diapositiva final de créditos.
- Solo recortar: no retoques, no redibujes y no generes imágenes parecidas. En las fotos de personas reales
  ("person": true) no des a entender que esa persona respalda InvestIQ. Los cargos (CEO, presidente...) pueden
  estar desfasados: compruébalos antes de nombrarlos.
- Si una empresa tiene "fill_from", sus fotos propias no llegan a 10: puedes completar con las de ese
  sector, pero son genéricas y nunca las presentes como de la empresa.
```

3. **Prueba:** pide al chat «lee el índice del banco y enséñame las fotos de Nvidia».

Si el chat crea las diapositivas con código y no consigue leer el índice o descargar las fotos, en los
ajustes de claude.ai permite los dominios `raw.githubusercontent.com` y `upload.wikimedia.org` en el acceso a
internet de la ejecución de código.

Cada vez que se rehace el banco (`build` y `git push`), el chat ve los cambios en el siguiente carrusel. No
hace falta cambiar nada en el proyecto.
