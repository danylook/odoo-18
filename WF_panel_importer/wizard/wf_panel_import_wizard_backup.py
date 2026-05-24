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
            self._notify_user(
                title="Importación finalizada",
                message=f"Pipeline completado en {pipeline_elapsed:.2f}s.",
                notif_type="success",
            )
        except import_steps.PipelineExecutionError as err:
            _logger.error(
                "❌ Error en pipeline después de %.2fs: %s",
                time.time() - pipeline_start,
                err,
            )
            raise Exception(f"Error ejecutando el pipeline de SVG: {err}")

# hasta aca procesa con python los SVGs generados
#------------------------------------------------------------------------------#








    #     # 4. (Opcional) Procesar el PDF como antes para crear paneles, etc.
    #     _logger.info("📖 Procesando contenido del PDF...")
    #     processing_start = time.time()
        
    #     with pdfplumber.open(BytesIO(base64.b64decode(self.pdf_file))) as pdf:
    #         full_text = "\n".join([page.extract_text() or '' for page in pdf.pages])
    #         panel_blocks = [block for block in re.split(r'(?=Panel:\s*)', full_text) if block.strip()]
    #         created_panels = []
    #         total_panels_detected = len(panel_blocks)

    #         _logger.info("🔍 Encontrados %d bloques de panel para procesar", total_panels_detected)

    #         for idx, block in enumerate(panel_blocks, start=1):
    #             # Mostrar progreso cada panel a partir del segundo
    #             if idx > 1 and total_panels_detected:
    #                 progress = (idx / total_panels_detected) * 100
    #                 elapsed_processing = time.time() - processing_start
    #                 _logger.info(
    #                     "⏳ Procesando panel %d/%d (%.1f%%) - %.2fs transcurridos",
    #                     idx,
    #                     total_panels_detected,
    #                     progress,
    #                     elapsed_processing,
    #                 )
                
    #             match_panel = re.search(r'Panel:\s*(.+)', block)
    #             if match_panel:
    #                 panel_line = match_panel.group(1).replace('Elevation Report', '').strip()
    #                 if '  ' in panel_line:
    #                     panel_name = panel_line.split('  ')[0].strip()
    #                 else:
    #                     panel_name = panel_line.strip()
    #             else:
    #                 panel_name = None
    #             header_match = re.search(r'Job: (.*?)\nModel:(.*?) Page:.*?\nSite Address:(.*?) Date: (.*?)\nDesigner:(.*?)\n', block, re.DOTALL)
    #             project_data = {}
    #             if header_match:
    #                 project_val = header_match.group(1).replace('Elevation Report', '').strip()
    #                 if '  ' in project_val:
    #                     project_val = project_val.split('  ')[0].strip()
    #                 project_data['project'] = project_val
    #                 project_data['model'] = header_match.group(2).strip()
    #                 project_data['site_address'] = header_match.group(3).strip()
    #                 project_data['date'] = header_match.group(4).strip()
    #                 project_data['designer'] = header_match.group(5).strip()
    #             if 'date' in project_data:
    #                 date_full = project_data['date']
    #                 date_only = date_full.split()[0] if ' ' in date_full else date_full
    #                 project_data['date'] = date_only
    #             level_val = None
    #             match_level = re.search(r'Level:\s*(.+)', block, re.IGNORECASE)
    #             if match_level:
    #                 level_line = match_level.group(1).strip()
    #                 import re as _re
    #                 cut_patterns = [r'\t', r'\s{2,}', r'Bundle', r'BUNDLE', r'GAR', r'\d+/\d+']
    #                 min_idx = len(level_line)
    #                 for pat in cut_patterns:
    #                     m = re.search(pat, level_line)
    #                     if m:
    #                         min_idx = min(min_idx, m.start())
    #                 level_val = level_line[:min_idx].strip()
    #                 project_data['level'] = level_val
    #             else:
    #                 project_data['level'] = None
    #             if panel_name:
    #                 project_data['panel_name'] = panel_name
    #             else:
    #                 project_data['panel_name'] = project_data.get('project')
    #             bom_lines = []
    #             if 'Cutting List' in block:
    #                 bom_lines += self._parse_cutting_list(block)
    #             if bom_lines:
    #                 panel_name_final = project_data['panel_name']
    #                 existing_panel = self.env['wf.panel'].search([('name', '=', panel_name_final)], limit=1)
    #                 remaining_panels = max(total_panels_detected - idx, 0)
    #                 if existing_panel:
    #                     if not self.force_reload:
    #                         return {
    #                             'type': 'ir.actions.act_window',
    #                             'res_model': 'wf.panel.import.wizard',
    #                             'view_mode': 'form',
    #                             'res_id': self.id,
    #                             'target': 'new',
    #                             'context': dict(self.env.context, force_reload_prompt=True),
    #                             'name': f'El panel {panel_name_final}({idx}/{total_panels_detected}). ya existe. ¿Sobrescribir?',
    #                         }

            
                
    #                 return {
    #                     'type': 'ir.actions.act_window',
    #                     'res_model': 'wf.panel.import.wizard',
    #                     'view_mode': 'form',
    #                     'res_id': self.id,
    #                     'target': 'new',
    #                     'context': dict(self.env.context, force_reload_prompt=True),
    #                     'name': f'El panel {panel_name_final}({idx}/{total_panels_detected}), faltan {remaining_panels}',
    #                 }
                       

    #         if created_panels:
    #             if len(created_panels) == 1:
    #                 return {
    #                     'type': 'ir.actions.act_window',
    #                     'res_model': 'wf.panel',
    #                     'view_mode': 'form',
    #                     'res_id': created_panels[0],
    #                     'target': 'current',
    #                     'name': 'Panel importado correctamente',
    #                     'context': self.env.context,
    #                 }
    #             else:
    #                 return {
    #                     'type': 'ir.actions.act_window',
    #                     'res_model': 'wf.panel',
    #                     'view_mode': 'tree,form',
    #                     'domain': [('id', 'in', created_panels)],
    #                     'target': 'current',
    #                     'name': 'Paneles importados correctamente',
    #                     'context': self.env.context,
    #                 }
            
    #     # Resumen final con tiempo total
    #     processing_elapsed = time.time() - processing_start
    #     total_elapsed = time.time() - start_time
    #     _logger.info(
    #         "🎉 ¡Importación completada! Total: %.2fs | Procesamiento: %.2fs | Paneles creados: %d",
    #         total_elapsed,
    #         processing_elapsed,
    #         len(created_panels),
    #     )
        
    #     # Si no hay paneles creados o ya terminó, cerrar el wizard
    #     return {'type': 'ir.actions.act_window_close'}
    
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

    # def _split_member_description(self, combined_parts_list):
    #     member_words = []
    #     description_words = []
    #     desc_started = False
    #     common_materials = ["SPF", "OSB", "LVL", "PINE", "FIR", "SYP", "TREATED", "CLADMATE"]
    #     for part in combined_parts_list:
    #         if desc_started:
    #             description_words.append(part)
    #             continue
    #         is_dimension_start = False
    #         if part and part[0].isdigit():
    #             if (
    #                 ('x' in part and part.count('x') == 1 and part.index('x') > 0)
    #                 or part.endswith('"')
    #                 or part.endswith("'")
    #                 or (
    #                     '/' in part
    #                     and part.replace('/', '').isdigit()
    #                     and sum(c.isdigit() for c in part) > sum(c == '/' for c in part)
    #                 )
    #             ):
    #                 is_dimension_start = True
    #         if is_dimension_start:
    #             desc_started = True
    #             description_words.append(part)
    #         elif member_words and part.upper() in common_materials:
    #             desc_started = True
    #             description_words.append(part)
    #         else:
    #             member_words.append(part)
    #     return " ".join(member_words), " ".join(description_words)
    
    # def _parse_cutting_list(self, text_block):
    #     bom_lines = []
    #     lines = text_block.splitlines()
    #     data_lines_started = False

    #     for line_str_full in lines:
    #         line_str = line_str_full.strip()
    #         if not line_str:
    #             continue

    #         token_set = {token.lower() for token in line_str.split()}
    #         if not data_lines_started and {"label", "member", "description", "qty"}.issubset(token_set):
    #             data_lines_started = True
    #             continue

    #         if not data_lines_started:
    #             continue

    #         parts = line_str.split()
    #         if not parts or parts[0].lower().startswith("total") or len(parts) < 4:
    #             continue

    #         qty_candidate = parts[-3]
    #         length_candidate = parts[-2]
    #         width_candidate = parts[-1]

    #         normalized_qty = qty_candidate.replace('(', '').replace(')', '')
    #         qty_is_number = normalized_qty.replace('.', '', 1).isdigit()
    #         length_is_number = length_candidate.replace('.', '', 1).replace('-', '', 1).isdigit()
    #         width_is_number = width_candidate.replace('.', '', 1).replace('-', '', 1).isdigit()

    #         if not (qty_is_number and length_is_number and width_is_number):
    #             continue

    #         combined_member_desc_parts = parts[1:-3]
    #         if not combined_member_desc_parts:
    #             continue

    #         member, description = self._split_member_description(combined_member_desc_parts)
    #         bom_lines.append({
    #             'label': parts[0],
    #             'member': member,
    #             'description': description,
    #             'qty': normalized_qty,
    #             'length': length_candidate,
    #             'width': width_candidate,
    #         })

    #     return bom_lines

    # def _parse_date_to_odoo(self, date_str):
    #     from datetime import datetime
    #     if not date_str:
    #         return False
    #     for fmt in ('%d/%m/%Y', '%Y-%m-%d', '%m/%d/%Y'):
    #         try:
    #             date_obj = datetime.strptime(date_str, fmt)
    #             return date_obj.strftime('%Y-%m-%d')
    #         except Exception:
    #             continue
    #     return False

    # def _create_panel_and_lines(self, project_data, bom_lines, force_reload=False):
    #     panel_name = project_data.get('panel_name') or project_data.get('project')
    #     existing_panel = self.env['wf.panel'].search([('name', '=', panel_name)], limit=1)
    #     if existing_panel:
    #         if not force_reload:
    #             return existing_panel
    #         existing_panel.line_ids.unlink()
    #         if existing_panel.production_id:
    #             if existing_panel.production_id.state not in ('cancel', 'done'):
    #                 existing_panel.production_id.action_cancel()
    #             existing_panel.production_id.unlink()
    #         if existing_panel.bom_id:
    #             existing_panel.bom_id.unlink()
    #         panel = existing_panel
    #         date_final = self._parse_date_to_odoo(project_data.get('date'))
    #         panel.write({
    #             'project': project_data.get('project'),
    #             'model': project_data.get('model'),
    #             'site_address': project_data.get('site_address'),
    #             'date': date_final,
    #             'designer': project_data.get('designer'),
    #             'level': project_data.get('level'),
    #         })
    #     else:
    #         date_final = self._parse_date_to_odoo(project_data.get('date'))
    #         panel = self.env['wf.panel'].create({
    #             'name': panel_name,
    #             'project': project_data.get('project'),
    #             'model': project_data.get('model'),
    #             'site_address': project_data.get('site_address'),
    #             'date': date_final,
    #             'designer': project_data.get('designer'),
    #             'level': project_data.get('level'),
    #         })
    #     for line in bom_lines:
    #         self.env['wf.panel.line'].create({
    #             'panel_id': panel.id,
    #             'label': line['label'],
    #             'member': line['member'],
    #             'description': line['description'],
    #             'qty': float(line['qty']) if str(line['qty']).replace('.','',1).isdigit() else 1.0,
    #             'length': line['length'],
    #             'width': line['width'],
    #         })
    #     product_panel_name = f"{panel.project} - {panel.name}"
    #     product_panel = self.env['product.product'].search([
    #         ('name', '=', product_panel_name)
    #     ], limit=1)
    #     if not product_panel:
    #         product_panel = self.env['product.product'].create({
    #             'name': product_panel_name,
    #             'type': 'product',
    #         })
    #     existing_bom = self.env['mrp.bom'].search([
    #         ('product_tmpl_id', '=', product_panel.product_tmpl_id.id),
    #         ('type', '=', 'normal')
    #     ], limit=1)
    #     if not existing_bom:
    #         bom = self.env['mrp.bom'].create({
    #             'product_tmpl_id': product_panel.product_tmpl_id.id,
    #             'type': 'normal',
    #             'code': product_panel_name,
    #             'product_qty': 1,
    #         })
    #     else:
    #         bom = existing_bom
    #     panel.bom_id = bom.id
    #     for line in bom_lines:
    #         material = self.env['product.product'].search([
    #             ('name', '=', line['description'])
    #         ], limit=1)
    #         if not material:
    #             material = self.env['product.product'].create({
    #                 'name': line['description'],
    #                 'type': 'product',
    #             })
    #         self.env['mrp.bom.line'].create({
    #             'bom_id': bom.id,
    #             'product_id': material.id,
    #             'product_qty': float(line['qty']) if str(line['qty']).replace('.','',1).isdigit() else 1.0,
    #             'product_uom_id': material.uom_id.id,
    #         })
    #     existing_production = self.env['mrp.production'].search([
    #         ('product_id', '=', product_panel.id),
    #         ('state', 'not in', ['done', 'cancel'])
    #     ], limit=1)
    #     if not existing_production:
    #         production = self.env['mrp.production'].create({
    #             'product_id': product_panel.id,
    #             'product_qty': 1,
    #             'bom_id': bom.id,
    #             'origin': product_panel_name,
    #         })
    #         panel.production_id = production.id
    #     else:
    #         panel.production_id = existing_production.id
    #     return panel
