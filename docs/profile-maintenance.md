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
rostro. Cada muestra del retrato se dibuja con una pequeña barra vertical en escala de
grises. Las 120 filas aparecen de arriba abajo. La generación conserva los bytes del original.

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

El workflow corre a las 11:23 UTC y también permite ejecución manual desde Actions.
Usa el token de GitHub que aporta el workflow. Para publicar, sube el cambio a la
rama predeterminada del perfil. Si aplicas protección de rama, la política de esa rama
debe permitir el commit automatizado para que la actualización diaria pueda publicarse.
`README.backup.md` conserva el README anterior.
