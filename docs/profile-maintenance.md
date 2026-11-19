# Mantenimiento del perfil

Instala las dependencias con Python 3.12 y ejecuta los comandos desde la raíz.

```sh
python -m pip install -r requirements.txt
python scripts/fetch_github_data.py
python scripts/generate_cards.py
python scripts/validate_profile.py
python -m unittest discover -s tests -v
```

## Retrato y vista estática

El generador busca la foto original en `asset/` y `assets/`, incluidas sus subcarpetas,
por el nombre base `IMG_2087` con su extensión real.
Pillow verifica el formato por el contenido, corrige la orientación EXIF, encuadra y ajusta
el contraste. En `assets/IMG_2087.jpg`, un JPEG de 341 × 481 píxeles, el generador aísla
el fondo claro conectado al borde y usa la silueta superior para encuadrar el cabello y el
rostro. Las filas alternas desplazan medio punto el muestreo. Los puntos tienen un diámetro
uniforme y cambian de luminosidad con la foto. El recorte desvanece la camiseta en el borde
inferior. Cada punto es el carácter ASCII `.` en una posición explícita del SVG.
Se compararon rejillas de 64, 84 y 104 columnas a tamaño de presentación. La rejilla
de escritorio tiene 84 columnas y 92 filas. En móvil se compararon 48, 60, 72 y 84
columnas con el mismo encuadre. La versión móvil usa 60 columnas y 66 filas para mantener
separados los puntos a esa escala. `portrait-static.svg` contiene la versión estática.

Para ajustar visualmente el encuadre, abre variantes estáticas del retrato. Los valores
de `--focus` recorren el margen de recorte desde 0 hasta 1 en cada eje. Si encuentras un
encuadre mejor, actualiza el par de valores de `make_rows` en `scripts/generate_cards.py`.

```sh
python scripts/generate_portrait.py assets/IMG_2087.jpg portrait-preview.svg --focus 0.5 0.38 --static
python scripts/generate_cards.py --static --output .preview
```

El README usa imágenes SVG autónomas, CSS interno y una variante del hero para pantallas
estrechas. Las animaciones se desactivan con `prefers-reduced-motion`. El modo
`--static` produce tarjetas en su estado final para inspección local.

## Datos y publicación

La API REST pública de GitHub aporta el perfil, los repositorios propios y los eventos
públicos recientes. Las estrellas se suman en repositorios propios que no son forks.
Los lenguajes se ordenan por número de repositorios donde son el lenguaje principal.
El calendario reutiliza las intensidades de la página pública de GitHub. Si GitHub
cambia ese HTML o falla alguna consulta, se conserva el último valor válido de esa fuente.
La selección de proyectos vive en `FEATURED` y solo se muestran repositorios que la API devuelve.

El workflow corre a las 11:23 UTC, admite ejecución manual y se activa cuando llegan
cambios a `main` en el generador, las pruebas, la foto, las dependencias o el propio workflow.
Usa el token de GitHub que aporta el workflow. Para publicar, sube el cambio a la
rama predeterminada del perfil. Si aplicas protección de rama, la política de esa rama
debe permitir el commit automatizado para que la actualización diaria pueda publicarse.
`README.backup.md` conserva el README anterior.

## Referencia técnica

La referencia consultada fue la revisión `a5fc82b`. El workflow del autor lee el calendario
público, guarda días y agregados en JSON, renderiza los SVG y versiona los cambios.
El retrato independiente revela filas mediante recortes SMIL. El hero extrae sus filas de texto
y aplica CSS. La tarjeta de estadísticas usa elementos SMIL `set` para mostrar fotogramas
numéricos. En los metadatos y el árbol consultados no figuraba una licencia general.
El perfil de Stevel usa una implementación independiente. [Archivos de referencia](https://github.com/AVIVASHISHTA29/AVIVASHISHTA29/tree/a5fc82b23b6549e360e30382609e1547df535f75)

En este repositorio, `scripts/fetch_github_data.py` obtiene los datos de GitHub y
`scripts/generate_cards.py` convierte el snapshot en texto, barras y celdas SVG. El heatmap usa
el nivel diario que devuelve GitHub. SMIL revela las celdas con un barrido breve. CSS controla
el retrato, la terminal y las barras. El gráfico de lenguajes divide el recuento de cada lenguaje
principal entre los repositorios públicos propios, sin forks, que tienen lenguaje identificado.
