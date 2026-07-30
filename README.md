# Resultados de admisión UNAM — datos y dashboard

## Contexto

Este proyecto se creó para poder analizar, de forma independiente y con datos públicos,
los resultados del Concurso de Selección de Licenciatura de la UNAM (Escolarizado, SUAYED
y SUAYED Noviembre), a raíz de las denuncias reportadas en El Universal sobre
irregularidades en el examen de admisión:

> ["Aspirantes revelan irregularidades en examen de admisión a la UNAM: vigilancia con IA
> fue insuficiente y laxa, dicen"](https://www.eluniversal.com.mx/nacion/aspirantes-revelan-irregularidades-en-examen-de-admision-a-la-unam-vigilancia-con-ia-fue-insuficiente-y-laxa-dicen/)
> — aspirantes rechazados denuncian que la vigilancia con IA durante el examen a distancia
> fue fácil de evadir (puntos ciegos de cámara, celulares fuera de encuadre), que las
> alertas del sistema fueron inconsistentes (algunos recibían advertencias por movimientos
> mínimos, mientras otros hacían cosas evidentemente irregulares sin consecuencia), y
> mencionan el caso de un aspirante que intentó deliberadamente que le cancelaran el
> examen y aun así obtuvo 120 aciertos sin ninguna advertencia.


Los datos son públicos (los publica la propia DGAE-UNAM en su sitio de resultados);
este proyecto solo los descarga, limpia y visualiza para facilitar su análisis.

## El dashboard (`dashboard/`)

Dashboard estático (sin build, sin backend con estado) con **tres páginas**, una por
convocatoria/modalidad, todas con el mismo tipo de análisis:

| Página | Convocatoria | Años con datos |
|---|---|---|
| `index.html` | Licenciatura Escolarizado | 2021–2026 |
| `suayed.html` | SUAYED regular (a distancia) | 2021–2026 |
| `suayed_noviembre.html` | SUAYED convocatoria extraordinaria de noviembre | 2021–2025 |

Cada página tiene:

- **Filtros** de carrera, plantel y año (aplican a todas las secciones salvo donde se
  indica lo contrario).
- **KPIs**: aspirantes, aceptados, tasa aceptados/presentaron y mediana de aciertos del
  último año con datos, con su variación contra el año anterior.
- **Distribución de aciertos**: histograma superpuesto por año, caja y bigotes por año, y
  tabla de estadísticos descriptivos (media, mediana, desviación estándar, cuartiles).
- **Mayor cambio en la distribución de aciertos** entre los dos años más recientes con
  datos: ranking por distancia de Wasserstein-1 (mide qué tanto cambió la forma completa
  de la distribución, no solo la media/mediana) por combinación carrera+plantel, más un
  scatter de examinandos del año más reciente vs. cambio en mediana. Solo incluye
  combinaciones con al menos 50 aspirantes en ambos años, para que combinaciones chicas no
  dominen el ranking por puro ruido muestral.
- **Carreras-plantel con más aspirantes de aciertos muy bajos (< 5 de 120)**: aciertos por
  debajo de lo esperable solo por azar: puede servir como proxy de aspirantes que no
  presentaron en condiciones normales (fallas técnicas, abandono del examen, etc.), no
  necesariamente de fraude.

### Cómo verlo

```bash
cd ~/Documents/UNAM_RESULTS/dashboard
PORT=8123 node server.js
# abre http://localhost:8123/index.html (y /suayed.html, /suayed_noviembre.html)
```


