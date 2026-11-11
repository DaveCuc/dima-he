# Política de Seguridad (Security Policy)

## 1. Compromiso de Seguridad

El proyecto **DIMA-HE** (*Distributed Multi-Agent Heuristic Evaluator*) está diseñado siguiendo principios de seguridad por diseño (*Security by Design*) para prevenir vulnerabilidades derivadas de la ejecución de agentes autónomos y la automatización de navegadores web.

---

## 2. Guardrails y Medidas de Protección Implementadas

### 2.1. Protección Anti-SSRF (Server-Side Request Forgery)
* El Nodo 1 (**Web Explorer**) cuenta con un mecanismo estricto de filtrado que intercepta toda solicitud de navegación previa a su transmisión al servidor Playwright MCP.
* Solo se permite la navegación hacia los dominios y hosts declarados explícitamente en la variable de entorno `ALLOWED_TARGET_HOSTS` (ejemplo: `host.docker.internal:8000,localhost:8000`).
* Queda **terminantemente bloqueada** cualquier petición hacia:
  * Segmentos de red de metadatos de proveedores en la nube (`169.254.169.254`).
  * Subredes privadas internas no autorizadas (`10.0.0.0/8`, `172.16.0.0/12`, `192.168.0.0/16`).
  * Esquemas de URI no estándar (`file://`, `gopher://`, `data:`).

### 2.2. Restricción de Acciones Destructivas
* El explorador autónomo opera bajo restricciones estrictas de solo lectura e interacción no destructiva.
* Se prohíbe la ejecución de operaciones de borrado (`DELETE`), pagos, compras, envíos masivos de formularios o acciones que alteren de manera permanente el estado o la base de datos de la aplicación bajo auditoría.

### 2.3. Aislamiento de Red y Contenedores
* El puerto del servidor Playwright MCP (`8931`) opera exclusivamente en la red interna de Docker (`usability_net`) y **nunca debe ser expuesto al host o a redes públicas**.
* Los 4 microservicios evaluadores heurísticos (Nodos 2 al 5) montan el volumen de evidencias en modo **solo lectura (`:ro`)**, impidiendo cualquier modificación o inyección de artefactos no autorizados.

### 2.4. Gestión de Credenciales y Secretos
* Queda estrictamente prohibido versionar claves de API (`GOOGLE_API_KEY`), tokens de autenticación o contraseñas en el código fuente o en el repositorio Git.
* Toda variable sensible se consume en tiempo de ejecución a través de variables de entorno controladas (`.env`).
* En entornos de pruebas públicas o CI/CD, el sistema activa de forma segura el motor determinista de respaldo sin requerir claves de API.

### 2.5. Prohibición de Base64 en Red A2A
* Para evitar ataques de denegación de servicio por agotamiento de memoria (*Memory Exhaustion DoS*), ninguna carga útil A2A transmite imágenes en Base64. Toda evidencia física se almacena en el sistema de archivos local y se referencia por rutas relativas verificables.

---

## 3. Notificación de Vulnerabilidades

Si identificas una vulnerabilidad de seguridad en este proyecto:
1. **No abras un issue público en GitHub.**
2. Envía un reporte confidencial y detallado al desarrollador principal a través de los canales de contacto de la Universidad Tecnológica de la Mixteca o mediante un reporte de seguridad privado en GitHub (*Security Advisory*).
3. Incluye los pasos necesarios para reproducir el hallazgo y el impacto estimado.
4. Se proporcionará acuse de recibo en un plazo no mayor a 48 horas y un plan de mitigación en caso de confirmarse la vulnerabilidad.
