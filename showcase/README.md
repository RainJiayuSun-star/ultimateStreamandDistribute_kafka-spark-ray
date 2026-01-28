# Showcase Website

Standalone static website that showcases the **Ultimate Stream and Distribute** project: system architecture, tech stack, data sources, ML models, service endpoints, and references.

## Viewing the site

- **Option 1:** Open `index.html` directly in a browser (`file:///.../showcase/index.html`).
- **Option 2:** Serve the directory with a static server, then open the given URL (e.g. `http://localhost:8080`):

  ```bash
  cd showcase
  python3 -m http.server 8080
  ```

  Then visit `http://localhost:8080`.

## Contents

- Project overview and Lambda Architecture summary
- Detailed system architecture (ingestion → Spark → Ray → serving)
- Tech stack and resource allocation
- Data sources (Open-Meteo, Kaggle) and ML models
- Service endpoints (Dashboard, API, Spark, Ray, Kafka)
- References (APIs, frameworks, course)
