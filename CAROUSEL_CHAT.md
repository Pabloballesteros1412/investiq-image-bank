# Conectar el banco al chat de carruseles

El chat de Claude que hace los carruseles de InvestIQ encuentra las fotos en un índice público
(`bank/index.json`). Para conectarlo:

1. **Haz público el repo** `investiq-image-bank`: en GitHub, Settings → General → Danger Zone → Change
   visibility. Sin eso, los enlaces del índice no funcionan.
2. **Pega este bloque en las instrucciones del proyecto** de Claude que hace los carruseles:

```
Banco de imágenes de InvestIQ
- Índice: https://raw.githubusercontent.com/Pabloballesteros1412/investiq-image-bank/main/bank/index.json
- Antes de elegir fotos para un carrusel, lee el índice. Busca la empresa por ticker o nombre, o el tema por
  alias (por ejemplo "fed", "inflation", "gold", "ai"), y elige por lo que muestra cada foto ("shows").
- Usa "4x5" (1200×1500) para diapositivas verticales y "1x1" (1200×1200) para cuadradas. Mira "thumb" si
  necesitas ver la foto antes de elegir.
- Usa solo fotos del banco, nunca imágenes de otras webs.
- Pon el crédito de cada foto que uses tal cual aparece en "credit", en letra pequeña en la diapositiva o en
  una diapositiva final de créditos.
- Solo recortar: no retoques, no redibujes y no generes imágenes parecidas. En las fotos de personas reales
  ("person": true) no des a entender que esa persona respalda InvestIQ.
- Si no hay foto para lo que necesitas, dilo y propón la más parecida del banco.
```

3. **Prueba:** pide al chat «lee el índice del banco y dime qué fotos hay de Nvidia».

Si el chat crea las diapositivas con código y no consigue descargar las fotos, en los ajustes de claude.ai
permite el dominio `raw.githubusercontent.com` en el acceso a internet de la ejecución de código.

Cada vez que se añadan o cambien fotos (`python image_bank.py build` y `git push`), el chat las ve en el
siguiente carrusel. No hace falta cambiar nada en el proyecto.
