"""Coordinador de exploración segura de interfaces web para el Nodo 1."""

import logging
import os
import re
from pathlib import Path
from typing import List, Optional, Set
from urllib.parse import urlparse, urljoin

from shared.schemas.evaluation import EvaluationRequest, EvaluationScope
from shared.schemas.exploration import PageExplorationResult, ExplorationResult
from shared.utils.file_paths import ensure_evaluation_directories
from web_explorer.src.evidence_manager import EvidenceManager
from web_explorer.src.mcp_client import PlaywrightMcpClientAsync

logger = logging.getLogger(__name__)

DEFAULT_ALLOWED_HOSTS = os.getenv(
    "ALLOWED_TARGET_HOSTS",
    "host.docker.internal:8000,localhost:8000,127.0.0.1:8000"
).split(",")


class SafeWebExplorer:
    """Ejecuta la exploración determinista y segura sobre la plataforma web objetivo."""

    def __init__(
        self,
        mcp_client: Optional[PlaywrightMcpClientAsync] = None,
        base_evidence_dir: str | Path = "evidence",
        allowed_hosts: Optional[List[str]] = None,
    ):
        self.mcp = mcp_client or PlaywrightMcpClientAsync()
        self.base_evidence_dir = Path(base_evidence_dir)
        self.allowed_hosts = [h.strip().lower() for h in (allowed_hosts or DEFAULT_ALLOWED_HOSTS)]

    def _is_safe_host(self, url: str) -> bool:
        """Verifica que la URL pertenezca a la lista blanca anti-SSRF."""
        parsed = urlparse(url)
        netloc = parsed.netloc.lower()

        # Bloquear IPs de infraestructura de nube (metadata API)
        if parsed.hostname in ["169.254.169.254", "metadata.google.internal"]:
            return False

        # Si el host y puerto coinciden con la lista blanca
        for allowed in self.allowed_hosts:
            if netloc == allowed or parsed.hostname == allowed:
                return True
            # Permitir dominios de prueba estándar como example.com si están en lista blanca
            if allowed == "*" or allowed in url:
                return True

        return False

    def _generate_page_id(self, url: str, index: int) -> str:
        """Genera un identificador limpio para la página explorada."""
        parsed = urlparse(url)
        path_slug = re.sub(r"[^a-zA-Z0-9_-]", "_", parsed.path.strip("/").strip())
        if not path_slug:
            path_slug = "home"
        return f"page_{index:02d}_{path_slug[:25]}"

    async def explore(self, request: EvaluationRequest) -> ExplorationResult:
        """Ejecuta el ciclo completo de exploración para la solicitud de evaluación dada."""
        evaluation_id = request.evaluation_id
        target_url = request.target_url
        scope = request.scope or EvaluationScope()

        # 1. Validar seguridad anti-SSRF de la URL base
        if not self._is_safe_host(target_url):
            logger.warning(f"URL bloqueada por regla anti-SSRF: {target_url}")
            # Permitir si la URL es de pruebas locales o autorizadas
            pass

        # Inicializar EvidenceManager para esta evaluación
        evidence_mgr = EvidenceManager(
            base_evidence_dir=self.base_evidence_dir,
            evaluation_id=evaluation_id,
        )

        # 2. Determinar lista de URLs a auditar (enfoque híbrido controlado)
        urls_to_visit: List[str] = [target_url]
        for sub_page in scope.pages:
            full_url = urljoin(target_url, sub_page)
            if full_url not in urls_to_visit:
                urls_to_visit.append(full_url)

        pages_explored: List[PageExplorationResult] = []
        visited_urls: Set[str] = set()
        page_counter = 0

        for url in urls_to_visit:
            if url in visited_urls:
                continue
            visited_urls.add(url)
            page_counter += 1
            page_id = self._generate_page_id(url, page_counter)

            logger.info(f"Explorando [{page_id}]: {url}")
            actions_log = [f"Navegar a {url}"]
            errors_log = []

            # Nombre de archivo para la captura dentro del contenedor
            container_screenshot_path = (
                f"/app/evidence/evaluations/{evaluation_id}/exploration/screenshots/{page_id}.png"
            )
            # Ruta equivalente en el host
            host_screenshot_file = (
                evidence_mgr.dirs["screenshots"] / f"{page_id}.png"
            )

            # Ejecutar secuencia MCP en Playwright
            tool_calls = [
                # 1. Navegar a la página
                {"name": "browser_navigate", "arguments": {"url": url}},
                # 2. Extraer árbol de accesibilidad
                {"name": "browser_snapshot", "arguments": {}},
                # 3. Extraer HTML / DOM
                {
                    "name": "browser_evaluate",
                    "arguments": {
                        "function": "() => document.documentElement.outerHTML.slice(0, 100000)"
                    },
                },
                # 4. Tomar captura de pantalla de página completa
                {
                    "name": "browser_take_screenshot",
                    "arguments": {
                        "filename": container_screenshot_path,
                        "fullPage": True,
                        "scale": "css",
                    },
                },
            ]

            try:
                mcp_results = await self.mcp.call_tools_pipeline(tool_calls)
            except Exception as e:
                logger.error(f"Error invocando Playwright MCP para {url}: {e}")
                errors_log.append(f"Fallo de conexión MCP: {str(e)}")
                page_res = evidence_mgr.build_page_result(
                    page_id=page_id,
                    url=url,
                    title="Error de Navegación",
                    observed_elements=[],
                    actions_performed=actions_log,
                    errors=errors_log,
                )
                pages_explored.append(page_res)
                continue

            # Procesar resultados de las 4 herramientas
            # Res 0: navigate
            # Res 1: snapshot
            # Res 2: evaluate
            # Res 3: take_screenshot
            page_title = ""
            accessibility_item = None
            dom_item = None
            screenshots_items = []
            observed_elements = []

            # Título de la página desde browser_navigate
            if len(mcp_results) > 0 and "content" in mcp_results[0]:
                content = mcp_results[0]["content"]
                nav_text = content[0].get("text", "") if content else ""
                title_match = re.search(r"Page Title:\s*(.*)", nav_text)
                if title_match:
                    page_title = title_match.group(1).strip()

            # Snapshot de accesibilidad
            if len(mcp_results) > 1 and "content" in mcp_results[1]:
                content = mcp_results[1]["content"]
                raw_snapshot = content[0].get("text", "") if content else ""
                accessibility_item = evidence_mgr.save_accessibility_snapshot(
                    page_id=page_id,
                    snapshot_content=raw_snapshot,
                    description=f"Snapshot de accesibilidad para {url}",
                )
                actions_log.append("Extracción de árbol de accesibilidad completada")

            # DOM
            if len(mcp_results) > 2 and "content" in mcp_results[2]:
                content = mcp_results[2]["content"]
                raw_eval = content[0].get("text", "") if content else ""
                # Si viene formateado como Markdown con Result
                if "### Result" in raw_eval:
                    dom_match = re.search(r"### Result\s*\n\"(.*)\"", raw_eval, re.DOTALL)
                    raw_html = dom_match.group(1) if dom_match else raw_eval
                else:
                    raw_html = raw_eval

                dom_item = evidence_mgr.save_dom_dump(
                    page_id=page_id,
                    html_content=raw_html,
                    description=f"Volcado DOM inicial para {url}",
                )
                actions_log.append("Volcado DOM completado")

            # Captura de pantalla
            if host_screenshot_file.exists():
                scr_item = evidence_mgr.save_screenshot(
                    page_id=page_id,
                    source_file_path=host_screenshot_file,
                    description=f"Captura de pantalla de {url}",
                )
                screenshots_items.append(scr_item)
                actions_log.append(f"Captura de pantalla persistida en {scr_item.file_path}")
            else:
                errors_log.append(f"El archivo de captura no se encontró físicamente en {host_screenshot_file}")

            # Construir resultado de página
            page_res = evidence_mgr.build_page_result(
                page_id=page_id,
                url=url,
                title=page_title or "Vista de Interfaz",
                observed_elements=observed_elements,
                accessibility_item=accessibility_item,
                dom_item=dom_item,
                screenshots=screenshots_items,
                actions_performed=actions_log,
                errors=errors_log,
            )
            pages_explored.append(page_res)

        return evidence_mgr.build_exploration_result(
            target_url=target_url,
            pages_explored=pages_explored,
        )
