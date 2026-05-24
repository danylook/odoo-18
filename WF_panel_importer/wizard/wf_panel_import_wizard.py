from odoo import models, fields
#import pdfplumber
import re
from io import BytesIO
import os
import logging
import time

from . import import_steps

_logger = logging.getLogger(__name__)


class WFPanelImportWizard(models.TransientModel):
    _name = 'wf.panel.import.wizard'
    _description = 'Import WF Panel from PDF'

    pdf_file = fields.Binary('PDF File', required=True)
    filename = fields.Char('Filename')
    force_reload = fields.Boolean('Sobrescribir si existe', default=False, help='Si está activo, sobrescribe los datos del panel si ya existe.')


    def action_import_pdf(self):
        if not self.pdf_file:
            return

        start_time = time.time()
        _logger.info("🔄 Iniciando importación de PDF...")
        
        # 1. Preparar directorio temporal y guardar el PDF original
        svg_pages_dir, used_default_dir = import_steps.prepare_workspace(self.env)
        if used_default_dir:
            self._notify_user(
                title="Directorio de importación no configurado",
                message=(
                    "No se definió el parámetro wf_panel_importer.svg_temp_dir. "
                    f"Se continuará usando el directorio por defecto del módulo: {svg_pages_dir}."
                ),
                notif_type="warning",
            )
        pdf_path = import_steps.save_pdf(
            pdf_binary=self.pdf_file,
            svg_pages_dir=svg_pages_dir,
            base_filename=self.filename,
            fallback_id=self.id,
        )

        elapsed = time.time() - start_time
        _logger.info("⏱️  PDF guardado (%.2fs transcurridos)", elapsed)

        # Ejecutar el pipeline de generación de SVGs usando el PDF y el directorio temporal
        _logger.info("🔄 Ejecutando pipeline de generación SVG...")
        pipeline_start = time.time()
        script_dir = os.path.dirname(os.path.abspath(__file__))
        python_exec = import_steps.resolve_python_executable(script_dir)
        try:
            pipeline_elapsed = import_steps.run_pipeline(
                script_dir=script_dir,
                pdf_path=pdf_path,
                svg_pages_dir=svg_pages_dir,
                python_exec=python_exec,
            )
            total_elapsed = time.time() - start_time
            _logger.info("✅ Pipeline completado (%.2fs) - Total: %.2fs", pipeline_elapsed, total_elapsed)
            project_map = import_steps.sync_projects_from_metadata(self.env, svg_pages_dir)
            import_steps.sync_panels_from_svg(self.env, svg_pages_dir, project_map)
            self._notify_user(
                title="Importación finalizada",
                message=f"Pipeline completado en {pipeline_elapsed:.2f}s.",
                notif_type="success",
            )
            return {
                "type": "ir.actions.client",
                "tag": "reload",
            }
        except import_steps.PipelineExecutionError as err:
            _logger.error(
                "❌ Error en pipeline después de %.2fs: %s",
                time.time() - pipeline_start,
                err,
            )
            raise Exception(f"Error ejecutando el pipeline de SVG: {err}")

# hasta aca procesa con python los SVGs generados
#------------------------------------------------------------------------------#

    def _notify_user(self, title, message, notif_type="info", sticky=False):
        """Envía una notificación ligera al usuario sin detener el flujo."""
        partner = self.env.user.partner_id
        if not partner:
            return
        payload = {
            "type": notif_type,
            "title": title,
            "message": message,
            "sticky": sticky,
        }
        try:
            self.env['bus.bus']._sendone(partner, 'notification', payload)
        except Exception as err:
            _logger.debug("No se pudo enviar notificación de progreso: %s", err)

   