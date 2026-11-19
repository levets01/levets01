# Mantenimiento del perfil de Stevel Iglesias

El perfil se publica con el README y los SVG de `assets/generated/`. GitHub selecciona la imagen de cada `<picture>` según el ancho de la ventana. La variante móvil entra hasta los 760 px.

## Regenerar desde la raíz

Usa Python 3.12. El primer script necesita acceso a GitHub. Para trabajar con la última captura guardada en `data/github_stats.json`, puedes empezar directamente por `generate_cards.py`.

```sh
python -m pip install -r requirements.txt
python scripts/fetch_github_data.py
python -m unittest discover -s tests -v
python scripts/generate_cards.py
python scripts/validate_profile.py
```

| Archivo | Dónde editar | Qué se regenera |
| --- | --- | --- |
| Foto y retrato | `assets/IMG_2087.jpg` y `scripts/generate_portrait.py` | Retrato animado, retrato estático y geometría del retrato dentro de ambos hero |
| Terminal, tarjetas y tecnologías | `scripts/generate_cards.py` y `assets/technology-logos.json` | SVG de escritorio y móvil, incluidas las tarjetas de los proyectos seleccionados |
| Datos públicos | `scripts/fetch_github_data.py` | `data/github_stats.json` |
| Presentación, navegación y contacto | `README.md` | El generador solo sustituye los bloques delimitados por los comentarios de `activity`, `stack` y `projects` |

Las tecnologías se editan en `STACK`. Cada nombre tiene un trazado de 24 × 24 unidades en el catálogo local. El generador lo incorpora al SVG junto a su etiqueta y distribuye las filas según el espacio disponible. Los logotipos proceden de [Simple Icons 11.15.0](https://github.com/simple-icons/simple-icons/tree/11.15.0).

## Ajustar el retrato

Pillow identifica el JPEG de 341 × 481 píxeles, aplica la orientación EXIF y separa el fondo claro conectado a los bordes. El encuadre se calcula a partir de la silueta del cabello y conserva los hombros. El muestreo Lanczos, el contraste en el entorno de cada punto y la detección de bordes conservan las diferencias entre piel, pelo y rasgos. Los tonos se interpolan entre las anclas de la paleta. El verde neón acentúa los bordes. Las zonas de detalle reciben más muestras.

```sh
python scripts/generate_portrait.py assets/IMG_2087.jpg .preview/retrato.svg --width 264 --height 292 --focus 0.5 0.38 --density 1
python scripts/generate_portrait.py --source assets/IMG_2087.jpg --output .preview/retrato-estatico.svg --palette "#14532D,#647D73,#00FF88,#A7F3D0,#F0FFF4" --static
python scripts/generate_cards.py --static --output .preview/estatico
```

`--density` multiplica las muestras por unidad de área. El hero móvil usa 0.60 para que los puntos se distingan al reducir la imagen. `--focus` acepta dos valores de 0 a 1. La paleta predeterminada se llama `hologram`. La alternativa personalizada recibe cinco colores en el orden del ejemplo.

Los puntos se agrupan por fase y tono en trazados de extremos redondos. Primero aparecen partículas tenues. Después se forma la silueta desde el cabello hasta los hombros y se definen los bordes del rostro. Al final, un pequeño grupo de puntos varía suavemente de intensidad dos veces. Tanto la construcción como la escritura de `whoami` y el calendario usan CSS dentro de su propio SVG. Si el visor omite las animaciones o el usuario prefiere movimiento reducido, se muestra la composición completa. El README también enlaza el retrato estático.

## Procedencia y recuperación de datos

- El perfil y los repositorios públicos aportan el número de repositorios, los seguidores, las estrellas y los lenguajes. Las estrellas se suman sobre los repositorios propios que no son forks. El gráfico de lenguajes usa como denominador los repositorios propios con lenguaje identificado. [API del perfil](https://api.github.com/users/levets01) · [Repositorios públicos](https://api.github.com/users/levets01/repos?type=owner)
- El calendario conserva las fechas, los niveles diarios y el total del periodo que muestra GitHub. Un día activo tiene nivel mayor que cero. La mejor racha cuenta días activos consecutivos dentro del intervalo mostrado. [Calendario público](https://github.com/users/levets01/contributions)
- Las tarjetas usan el nombre, la URL, las estrellas y el lenguaje principal de los repositorios que devuelve la API. `FEATURED` contiene la selección, las etiquetas de stack y una descripción editorial para repositorios con la descripción de GitHub vacía. La actividad resume los eventos públicos recientes. [Eventos públicos](https://api.github.com/users/levets01/events/public)
- Si una fuente falla, se conserva la última captura de esa fuente. El proceso se detiene si falta la captura inicial. Los errores de red y los fallos transitorios del servidor tienen reintentos limitados. Cuando GitHub indica una espera larga por cuota, se conserva la captura y la siguiente ejecución vuelve a consultar.

## GitHub Actions

El workflow se ejecuta a las 11:23 UTC cada día, admite ejecución manual y responde a cambios en la foto, los generadores, los logotipos, las pruebas y su configuración. Utiliza el token temporal de Actions para la API y requiere permiso `contents: write` para publicar en la rama predeterminada. Una política de protección de rama que impida ese push quedará reflejada como un error en el paso de publicación.

La tarea ejecuta las pruebas, regenera desde las fuentes versionadas y valida las referencias locales del README y los SVG. Solo crea un commit si el contenido cambió. Las pruebas locales pueden ejecutar esas mismas etapas hasta la validación.

La referencia de diseño fue el uso de SVG autónomos y actualización desde GitHub en el [perfil de Avi Vashishta](https://github.com/AVIVASHISHTA29/AVIVASHISHTA29/tree/a5fc82b23b6549e360e30382609e1547df535f75).
