import csv
import io
from odoo import http
from odoo.http import request
from odoo.addons.portal.controllers.portal import CustomerPortal


def _get_partner_ids(partner):
    ids = [partner.id]
    if partner.parent_id:
        ids.append(partner.parent_id.id)
    return ids


class Tpl3plPortal(CustomerPortal):

    # ------------------------------------------------------------------
    # Home portal values (counter for sidebar badge)
    # ------------------------------------------------------------------
    def _prepare_home_portal_values(self, counters):
        values = super()._prepare_home_portal_values(counters)
        if 'tpl_stock_count' in counters:
            partner_ids = _get_partner_ids(request.env.user.partner_id)
            quants = request.env['stock.quant'].sudo().search([
                ('owner_id', 'in', partner_ids),
                ('location_id.usage', '=', 'internal'),
                ('quantity', '>', 0),
            ])
            values['tpl_stock_count'] = len(quants)
        return values

    # ------------------------------------------------------------------
    # /my  → redirect portal users to 3PL dashboard
    # ------------------------------------------------------------------
    @http.route('/my', type='http', auth='user', website=True)
    def home(self, **kwargs):
        if request.env.user.has_group('base.group_portal'):
            return request.redirect('/my/3pl/dashboard')
        return super().home(**kwargs)


    # ------------------------------------------------------------------
    # Language switcher
    # ------------------------------------------------------------------
    @http.route("/my/3pl/set_lang", type="http", auth="user", website=True, csrf=False)
    def set_lang(self, lang, redirect_to="/my/3pl/dashboard", **kwargs):
        lang_ok = request.env["res.lang"].sudo().search(
            [("code", "=", lang), ("active", "=", True)], limit=1)
        if lang_ok:
            request.env.user.sudo().partner_id.lang = lang
            request.update_context(lang=lang)
        resp = request.redirect(redirect_to or "/my/3pl/dashboard")
        resp.set_cookie("frontend_lang", lang)
        return resp

    # ------------------------------------------------------------------
    # My Profile
    # ------------------------------------------------------------------
    @http.route('/my/3pl/profile', type='http', auth='user', website=True)
    def portal_3pl_profile(self, **kwargs):
        partner = request.env.user.partner_id
        return request.render('tpl_3pl_logistic.portal_tpl_profile', {
            'partner': partner,
            'page_name': 'tpl_profile',
        })

    # ------------------------------------------------------------------
    # Dashboard
    # ------------------------------------------------------------------
    @http.route('/my/3pl/dashboard', type='http', auth='user', website=True)
    def portal_3pl_dashboard(self, **kwargs):
        partner = request.env.user.partner_id
        partner_ids = _get_partner_ids(partner)

        quants = request.env['stock.quant'].sudo().search([
            ('owner_id', 'in', partner_ids),
            ('location_id.usage', '=', 'internal'),
            ('quantity', '>', 0),
        ])
        total_units = sum(quants.mapped('quantity'))
        product_count = len(set(quants.mapped('product_id').ids))

        open_pickings = request.env['stock.picking'].sudo().search([
            ('partner_id', 'in', partner_ids),
            ('state', 'in', ['confirmed', 'assigned', 'waiting']),
        ])
        open_invoices = request.env['account.move'].sudo().search([
            ('partner_id', 'in', partner_ids),
            ('move_type', '=', 'out_invoice'),
            ('state', '=', 'posted'),
            ('payment_state', 'in', ['not_paid', 'partial']),
        ])

        inbound_count = request.env['stock.picking'].sudo().search_count([
            ('partner_id', 'in', partner_ids),
            ('picking_type_id.code', '=', 'incoming'),
            ('state', 'not in', ['done', 'cancel']),
        ])
        outbound_count = request.env['stock.picking'].sudo().search_count([
            ('partner_id', 'in', partner_ids),
            ('picking_type_id.code', '=', 'outgoing'),
            ('state', 'not in', ['done', 'cancel']),
        ])

        message = kwargs.get('message', '')
        return request.render('tpl_3pl_logistic.portal_3pl_dashboard', {
            'partner': partner,
            'total_units': int(total_units),
            'product_count': product_count,
            'open_orders': len(open_pickings),
            'open_invoices': len(open_invoices),
            'inbound_count': inbound_count,
            'outbound_count': outbound_count,
            'page_name': 'tpl_dashboard',
            'message': message,
        })

    # ------------------------------------------------------------------
    # Stock list
    # ------------------------------------------------------------------
    @http.route('/my/3pl/stock', type='http', auth='user', website=True)
    def portal_my_stock(self, **kwargs):
        partner_ids = _get_partner_ids(request.env.user.partner_id)
        quants = request.env['stock.quant'].sudo().search([
            ('owner_id', 'in', partner_ids),
            ('location_id.usage', '=', 'internal'),
            ('quantity', '>', 0),
        ])
        message = kwargs.get('message')
        return request.render('tpl_3pl_logistic.portal_my_3pl_stock', {
            'quants': quants,
            'page_name': 'tpl_stock',
            'message': message,
        })

    # ------------------------------------------------------------------
    # All orders (combined)
    # ------------------------------------------------------------------
    @http.route('/my/3pl/orders', type='http', auth='user', website=True)
    def portal_my_orders(self, **kwargs):
        partner_ids = _get_partner_ids(request.env.user.partner_id)
        pickings = request.env['stock.picking'].sudo().search([
            ('partner_id', 'in', partner_ids),
        ], order='id desc', limit=100)
        return request.render('tpl_3pl_logistic.portal_my_3pl_orders', {
            'pickings': pickings,
            'page_name': 'tpl_orders',
            'filter_type': 'all',
        })

    # ------------------------------------------------------------------
    # Inbound orders
    # ------------------------------------------------------------------
    @http.route('/my/3pl/orders/inbound', type='http', auth='user', website=True)
    def portal_inbound_orders(self, **kwargs):
        partner_ids = _get_partner_ids(request.env.user.partner_id)
        pickings = request.env['stock.picking'].sudo().search([
            ('partner_id', 'in', partner_ids),
            ('picking_type_id.code', '=', 'incoming'),
        ], order='id desc', limit=100)
        message = kwargs.get('message', '')
        return request.render('tpl_3pl_logistic.portal_my_3pl_orders', {
            'pickings': pickings,
            'page_name': 'tpl_inbound',
            'filter_type': 'inbound',
            'message': message,
        })

    # ------------------------------------------------------------------
    # Outbound orders
    # ------------------------------------------------------------------
    @http.route('/my/3pl/orders/outbound', type='http', auth='user', website=True)
    def portal_outbound_orders(self, **kwargs):
        partner_ids = _get_partner_ids(request.env.user.partner_id)
        pickings = request.env['stock.picking'].sudo().search([
            ('partner_id', 'in', partner_ids),
            ('picking_type_id.code', '=', 'outgoing'),
        ], order='id desc', limit=100)
        message = kwargs.get('message', '')
        return request.render('tpl_3pl_logistic.portal_my_3pl_orders', {
            'pickings': pickings,
            'page_name': 'tpl_outbound',
            'filter_type': 'outbound',
            'message': message,
        })


    # ------------------------------------------------------------------
    # Order detail
    # ------------------------------------------------------------------
    @http.route('/my/3pl/order/<int:order_id>', type='http', auth='user', website=True)
    def portal_order_detail(self, order_id, **kwargs):
        partner_ids = _get_partner_ids(request.env.user.partner_id)
        picking = request.env['stock.picking'].sudo().search([
            ('id', '=', order_id),
            ('partner_id', 'in', partner_ids),
        ], limit=1)
        if not picking:
            return request.redirect('/my/3pl/orders')
        filter_type = 'inbound' if picking.picking_type_id.code == 'incoming' else 'outbound'
        page_name = 'tpl_inbound' if filter_type == 'inbound' else 'tpl_outbound'
        return request.render('tpl_3pl_logistic.portal_3pl_order_detail', {
            'picking': picking,
            'page_name': page_name,
            'filter_type': filter_type,
        })

    # ------------------------------------------------------------------
    # My Invoices
    # ------------------------------------------------------------------
    @http.route('/my/3pl/invoices/<int:invoice_id>', type='http', auth='user', website=True)
    def portal_3pl_invoice_detail(self, invoice_id, **kwargs):
        partner = request.env.user.partner_id
        partner_ids = _get_partner_ids(partner)
        invoice = request.env['account.move'].sudo().search([
            ('id', '=', invoice_id),
            ('partner_id', 'in', partner_ids),
            ('move_type', '=', 'out_invoice'),
            ('state', '=', 'posted'),
        ], limit=1)
        if not invoice:
            return request.redirect('/my/3pl/invoices')
        return request.render('tpl_3pl_logistic.portal_tpl_invoice_detail', {
            'invoice': invoice,
            'page_name': 'tpl_invoices',
        })

    @http.route('/my/3pl/invoices', type='http', auth='user', website=True)
    def portal_3pl_invoices(self, **kwargs):
        partner = request.env.user.partner_id
        partner_ids = _get_partner_ids(partner)
        invoices = request.env['account.move'].sudo().search([
            ('partner_id', 'in', partner_ids),
            ('move_type', '=', 'out_invoice'),
            ('state', '=', 'posted'),
        ], order='invoice_date desc, id desc')
        return request.render('tpl_3pl_logistic.portal_tpl_my_invoices', {
            'invoices': invoices,
            'page_name': 'tpl_invoices',
        })

    # ------------------------------------------------------------------
    # New order form
    # ------------------------------------------------------------------
    @http.route('/my/3pl/order/new', type='http', auth='user', website=True)
    def portal_new_order(self, type='out', **kwargs):
        partner = request.env.user.partner_id
        partner_ids = _get_partner_ids(partner)

        quant_product_ids = request.env['stock.quant'].sudo().search([
            ('owner_id', 'in', partner_ids),
            ('location_id.usage', '=', 'internal'),
            ('quantity', '>', 0),
        ]).mapped('product_id.product_tmpl_id').ids

        tmpl_product_ids = request.env['product.template'].sudo().search([
            ('owner_id', 'in', partner_ids),
            ('is_storable', '=', True),
        ]).ids

        all_product_ids = list(set(quant_product_ids + tmpl_product_ids))
        owned_products = request.env['product.template'].sudo().browse(all_product_ids)

        delivery_addresses = request.env['res.partner'].sudo().search([
            '|',
            '&', ('parent_id', 'in', partner_ids), ('type', 'in', ['delivery', 'contact']),
            ('tpl_client_owner_id', 'in', partner_ids),
        ])

        return request.render('tpl_3pl_logistic.portal_3pl_create_order', {
            'order_type': type,
            'owned_products': owned_products,
            'partner': partner,
            'delivery_addresses': delivery_addresses,
            'page_name': 'tpl_new_order',
        })

    # ------------------------------------------------------------------
    # Submit order
    # ------------------------------------------------------------------
    @http.route('/my/3pl/order/submit', type='http', auth='user', website=True, methods=['POST'])
    def portal_submit_order(self, **post):
        partner = request.env.user.partner_id
        order_type = post.get('order_type', 'out')
        scheduled_date = post.get('scheduled_date')
        partner_ref = post.get('partner_ref', '')
        note = post.get('note', '')
        product_ids = request.httprequest.form.getlist('product_id[]')
        quantities = request.httprequest.form.getlist('quantity[]')

        if not product_ids:
            return request.redirect('/my/3pl/dashboard')

        warehouse = request.env['stock.warehouse'].sudo().search([
            ('company_id', '=', request.env.company.id),
        ], limit=1)
        if order_type == 'in':
            picking_type = warehouse.in_type_id
        elif warehouse.delivery_steps != 'ship_only':
            picking_type = warehouse.pick_type_id
        else:
            picking_type = warehouse.out_type_id

        if not picking_type:
            return request.redirect('/my/3pl/dashboard')

        delivery_note = ''
        if order_type == 'out':
            delivery_partner_id = post.get('delivery_partner_id')
            if delivery_partner_id:
                dp = request.env['res.partner'].sudo().browse(int(delivery_partner_id))
                delivery_note = 'Deliver to: %s' % dp.display_name
                if dp.street:
                    delivery_note += ', %s' % dp.street
                if dp.city:
                    delivery_note += ', %s' % dp.city
            else:
                parts = [
                    post.get('delivery_name', ''),
                    post.get('delivery_street', ''),
                    post.get('delivery_zip', ''),
                    post.get('delivery_city', ''),
                    post.get('delivery_country', ''),
                ]
                addr = ', '.join(p.strip() for p in parts if p.strip())
                if addr:
                    delivery_note = 'Deliver to: ' + addr

        contact_note = ''
        if order_type == 'out':
            contact_partner_id = post.get('contact_partner_id')
            if contact_partner_id:
                try:
                    cp = request.env['res.partner'].sudo().browse(int(contact_partner_id))
                    contact_note = 'Contact: %s' % cp.name
                    if cp.phone or cp.mobile:
                        contact_note += ' (%s)' % (cp.phone or cp.mobile)
                except Exception:
                    pass
            else:
                c_name = post.get('contact_name', '').strip()
                c_phone = post.get('contact_phone', '').strip()
                if c_name or c_phone:
                    parts = [p for p in [c_name, c_phone] if p]
                    contact_note = 'Contact: ' + ', '.join(parts)
        full_note = '\n'.join(filter(None, [delivery_note, contact_note, note]))

        move_lines = []
        for i, pid in enumerate(product_ids):
            try:
                qty = float(quantities[i]) if i < len(quantities) else 0
            except (ValueError, IndexError):
                qty = 0
            if not pid or qty <= 0:
                continue
            product = request.env['product.template'].sudo().browse(int(pid))
            move_lines.append((0, 0, {
                'product_id': product.product_variant_id.id,
                'product_uom_qty': qty,
                'product_uom': product.uom_id.id,
                'name': product.display_name,
            }))

        if not move_lines:
            return request.redirect('/my/3pl/dashboard')

        picking_vals = {
            'picking_type_id': picking_type.id,
            'partner_id': partner.id,
            'origin': 'Portal: ' + partner_ref if partner_ref else 'Portal Order',
            'note': full_note,
            'move_ids': move_lines,
        }
        if scheduled_date:
            if len(scheduled_date) == 10:
                scheduled_date += " 12:00:00"
            picking_vals['scheduled_date'] = scheduled_date

        request.env['stock.picking'].sudo().create(picking_vals)
        redirect = '/my/3pl/orders/inbound' if order_type == 'in' else '/my/3pl/orders/outbound'
        return request.redirect(redirect + '?message=order_submitted')

    # ==================================================================
    # CSV IMPORT — Products
    # ==================================================================
    @http.route('/my/3pl/import/products', type='http', auth='user', website=True)
    def portal_import_products_form(self, **kwargs):
        message = kwargs.get('message', '')
        errors = kwargs.get('errors', '')
        return request.render('tpl_3pl_logistic.portal_import_products', {
            'page_name': 'tpl_import',
            'message': message,
            'errors': errors,
        })

    @http.route('/my/3pl/import/products/submit', type='http', auth='user',
                website=True, methods=['POST'])
    def portal_import_products_submit(self, **post):
        partner = request.env.user.partner_id
        upload = request.httprequest.files.get('import_file')
        if not upload:
            return request.redirect('/my/3pl/import/products?message=no_file')

        errors = []
        created = 0
        try:
            content = upload.read().decode('utf-8-sig')
            reader = csv.DictReader(io.StringIO(content))
            for row_num, row in enumerate(reader, start=2):
                name = (row.get('name') or row.get('Name') or '').strip()
                ref = (row.get('internal_reference') or row.get('Internal Reference') or '').strip()
                price = (row.get('sales_price') or row.get('Sales Price') or '0').strip()
                weight = (row.get('weight') or row.get('Weight') or '0').strip()
                barcode = (row.get('barcode') or row.get('Barcode') or '').strip()
                if not name:
                    errors.append('Row %d: name is required' % row_num)
                    continue
                try:
                    price_val = float(price) if price else 0.0
                    weight_val = float(weight) if weight else 0.0
                except ValueError:
                    errors.append('Row %d: invalid price or weight' % row_num)
                    continue
                vals = {
                    'name': name,
                    'is_storable': True,
                    'owner_id': partner.id,
                    'list_price': price_val,
                    'weight': weight_val,
                }
                if ref:
                    vals['default_code'] = ref
                if barcode:
                    vals['barcode'] = barcode
                request.env['product.template'].sudo().create(vals)
                created += 1
        except Exception as e:
            errors.append('File error: %s' % str(e))

        msg = 'imported_%d' % created
        if errors:
            import urllib.parse
            err_str = urllib.parse.quote('|'.join(errors[:10]))
            return request.redirect('/my/3pl/import/products?message=%s&errors=%s' % (msg, err_str))
        return request.redirect('/my/3pl/import/products?message=%s' % msg)

    # ==================================================================
    # CSV IMPORT — Inbound Orders
    # ==================================================================
    @http.route('/my/3pl/import/inbound', type='http', auth='user', website=True)
    def portal_import_inbound_form(self, **kwargs):
        message = kwargs.get('message', '')
        errors = kwargs.get('errors', '')
        return request.render('tpl_3pl_logistic.portal_import_orders', {
            'page_name': 'tpl_import',
            'import_type': 'inbound',
            'message': message,
            'errors': errors,
        })

    @http.route('/my/3pl/import/inbound/submit', type='http', auth='user',
                website=True, methods=['POST'])
    def portal_import_inbound_submit(self, **post):
        return self._process_order_import(order_type='in')

    # ==================================================================
    # CSV IMPORT — Outbound Orders
    # ==================================================================
    @http.route('/my/3pl/import/outbound', type='http', auth='user', website=True)
    def portal_import_outbound_form(self, **kwargs):
        message = kwargs.get('message', '')
        errors = kwargs.get('errors', '')
        partner = request.env.user.partner_id
        partner_ids = _get_partner_ids(partner)
        delivery_addresses = request.env['res.partner'].sudo().search([
            '|',
            '&', ('parent_id', 'in', partner_ids), ('type', 'in', ['delivery', 'contact']),
            ('tpl_client_owner_id', 'in', partner_ids),
        ])
        return request.render('tpl_3pl_logistic.portal_import_orders', {
            'page_name': 'tpl_import',
            'import_type': 'outbound',
            'message': message,
            'errors': errors,
            'delivery_addresses': delivery_addresses,
        })

    @http.route('/my/3pl/import/outbound/submit', type='http', auth='user',
                website=True, methods=['POST'])
    def portal_import_outbound_submit(self, **post):
        return self._process_order_import(order_type='out')

    def _process_order_import(self, order_type):
        import urllib.parse
        partner = request.env.user.partner_id
        partner_ids = _get_partner_ids(partner)
        upload = request.httprequest.files.get('import_file')
        base_url = '/my/3pl/import/inbound' if order_type == 'in' else '/my/3pl/import/outbound'

        if not upload:
            return request.redirect(base_url + '?message=no_file')

        warehouse = request.env['stock.warehouse'].sudo().search([
            ('company_id', '=', request.env.company.id),
        ], limit=1)
        if order_type == 'in':
            picking_type = warehouse.in_type_id
        elif warehouse.delivery_steps != 'ship_only':
            picking_type = warehouse.pick_type_id
        else:
            picking_type = warehouse.out_type_id
        if not picking_type:
            return request.redirect(base_url + '?message=no_picking_type')

        errors = []
        created = 0
        # Group rows by order_ref so multiple lines become one picking
        orders = {}
        try:
            content = upload.read().decode('utf-8-sig')
            reader = csv.DictReader(io.StringIO(content))
            for row_num, row in enumerate(reader, start=2):
                def col(*keys):
                    for k in keys:
                        v = (row.get(k) or '').strip()
                        if v:
                            return v
                    return ''

                order_ref = col('order_ref', 'Order Reference', 'order_reference') or ('ROW%d' % row_num)
                product_ref = col('product_ref', 'Product Reference', 'product_internal_ref')
                product_name = col('product_name', 'Product Name')
                qty_str = col('quantity', 'Quantity', 'qty')
                scheduled = col('scheduled_date', 'Scheduled Date', 'date')
                note = col('note', 'Note', 'notes')
                delivery_addr = col('delivery_address', 'Delivery Address') if order_type == 'out' else ''

                # Resolve product
                product = None
                if product_ref:
                    tmpl = request.env['product.template'].sudo().search(
                        [('default_code', '=', product_ref)], limit=1)
                    if tmpl:
                        product = tmpl.product_variant_id
                if not product and product_name:
                    tmpl = request.env['product.template'].sudo().search(
                        [('name', 'ilike', product_name)], limit=1)
                    if tmpl:
                        product = tmpl.product_variant_id
                if not product:
                    errors.append('Row %d: product not found (ref=%s, name=%s)' % (
                        row_num, product_ref, product_name))
                    continue

                try:
                    qty = float(qty_str) if qty_str else 0
                except ValueError:
                    errors.append('Row %d: invalid quantity "%s"' % (row_num, qty_str))
                    continue
                if qty <= 0:
                    errors.append('Row %d: quantity must be > 0' % row_num)
                    continue

                if order_ref not in orders:
                    # Build contact note once per order (from POST form fields)
                    contact_note = ''
                    if order_type == 'out':
                        cpid = request.httprequest.form.get('contact_partner_id', '').strip()
                        if cpid:
                            try:
                                cp = request.env['res.partner'].sudo().browse(int(cpid))
                                contact_note = 'Contact: %s' % cp.name
                                if cp.phone or cp.mobile:
                                    contact_note += ' (%s)' % (cp.phone or cp.mobile)
                            except Exception:
                                pass
                        else:
                            c_name = request.httprequest.form.get('contact_name', '').strip()
                            c_phone = request.httprequest.form.get('contact_phone', '').strip()
                            if c_name or c_phone:
                                contact_note = 'Contact: ' + ', '.join(p for p in [c_name, c_phone] if p)
                    orders[order_ref] = {
                        'scheduled': scheduled,
                        'note': note,
                        'delivery_addr': delivery_addr,
                        'contact_note': contact_note,
                        'lines': [],
                    }
                orders[order_ref]['lines'].append({
                    'product': product,
                    'qty': qty,
                })
        except Exception as e:
            errors.append('File error: %s' % str(e))

        for ref, data in orders.items():
            move_lines = [(0, 0, {
                'product_id': l['product'].id,
                'product_uom_qty': l['qty'],
                'product_uom': l['product'].uom_id.id,
                'name': l['product'].display_name,
            }) for l in data['lines']]

            note_parts = []
            if data['delivery_addr']:
                note_parts.append('Deliver to: ' + data['delivery_addr'])
            if data.get('contact_note'):
                note_parts.append(data['contact_note'])
            if data['note']:
                note_parts.append(data['note'])

            vals = {
                'picking_type_id': picking_type.id,
                'partner_id': partner.id,
                'origin': 'Import: ' + ref,
                'note': '\n'.join(note_parts),
                'move_ids': move_lines,
            }
            if data['scheduled']:
                sched = data['scheduled'].strip()
                if len(sched) == 10:
                    sched += " 12:00:00"
                vals['scheduled_date'] = sched
            request.env['stock.picking'].sudo().create(vals)
            created += 1

        msg = 'imported_%d' % created
        if errors:
            err_str = urllib.parse.quote('|'.join(errors[:10]))
            return request.redirect('%s?message=%s&errors=%s' % (base_url, msg, err_str))
        return request.redirect(base_url + '?message=' + msg)

    # ------------------------------------------------------------------
    # Download sample CSV files
    # ------------------------------------------------------------------
    @http.route('/my/3pl/import/sample/<string:import_type>', type='http', auth='user', website=True)
    def portal_download_sample(self, import_type, **kwargs):
        samples = {
            'products': (
                'name,internal_reference,sales_price,weight,barcode\n'
                'Widget A,WGT-001,12.50,0.5,1234567890123\n'
                'Box B,BOX-002,5.00,1.2,\n'
            ),
            'inbound': (
                'order_ref,product_ref,product_name,quantity,scheduled_date,note\n'
                'PO-2026-001,WGT-001,,100,2026-05-20,Handle with care\n'
                'PO-2026-001,BOX-002,,50,2026-05-20,\n'
                'PO-2026-002,,Widget A,200,2026-05-21,\n'
            ),
            'outbound': (
                'order_ref,product_ref,product_name,quantity,scheduled_date,delivery_address,note\n'
                'SO-2026-001,WGT-001,,30,2026-05-22,123 Main St, City,\n'
                'SO-2026-002,BOX-002,,10,2026-05-23,456 Oak Ave, Town,Fragile\n'
            ),
        }
        if import_type not in samples:
            return request.redirect('/my/3pl/dashboard')
        content = samples[import_type]
        filename = 'sample_%s_import.csv' % import_type
        return request.make_response(
            content,
            headers=[
                ('Content-Type', 'text/csv; charset=utf-8'),
                ('Content-Disposition', 'attachment; filename="%s"' % filename),
            ]
        )

    # ------------------------------------------------------------------
    # Serve the import guide HTML document
    # ------------------------------------------------------------------
    @http.route('/my/3pl/import/guide', type='http', auth='user', website=True)
    def portal_import_guide(self, **kwargs):
        import os
        addon_path = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        guide_path = os.path.join(addon_path, 'static', 'src', 'import_guide.html')
        with open(guide_path, 'r', encoding='utf-8') as f:
            content = f.read()
        return request.make_response(
            content,
            headers=[('Content-Type', 'text/html; charset=utf-8')]
        )

    # ==================================================================
    # PORTAL REPORTS
    # ==================================================================
    @http.route('/my/3pl/reports/inbound', type='http', auth='user', website=True)
    def portal_report_inbound(self, **kwargs):
        partner_ids = _get_partner_ids(request.env.user.partner_id)
        pickings = request.env['stock.picking'].sudo().search([
            ('partner_id', 'in', partner_ids),
            ('picking_type_id.code', '=', 'incoming'),
        ], order='id desc', limit=200)
        return request.render('tpl_3pl_logistic.portal_tpl_report_inbound', {
            'pickings': pickings,
            'page_name': 'tpl_report_inbound',
        })

    @http.route('/my/3pl/reports/outbound', type='http', auth='user', website=True)
    def portal_report_outbound(self, **kwargs):
        partner_ids = _get_partner_ids(request.env.user.partner_id)
        pickings = request.env['stock.picking'].sudo().search([
            ('partner_id', 'in', partner_ids),
            ('picking_type_id.code', '=', 'outgoing'),
        ], order='id desc', limit=200)
        return request.render('tpl_3pl_logistic.portal_tpl_report_outbound', {
            'pickings': pickings,
            'page_name': 'tpl_report_outbound',
        })

    @http.route('/my/3pl/reports/delivery', type='http', auth='user', website=True)
    def portal_report_delivery(self, **kwargs):
        partner_ids = _get_partner_ids(request.env.user.partner_id)
        pickings = request.env['stock.picking'].sudo().search([
            ('partner_id', 'in', partner_ids),
            ('picking_type_id.code', '=', 'outgoing'),
            ('carrier_id', '!=', False),
        ], order='id desc', limit=200)
        return request.render('tpl_3pl_logistic.portal_tpl_report_delivery', {
            'pickings': pickings,
            'page_name': 'tpl_report_delivery',
        })

    @http.route('/my/3pl/reports/stock_age', type='http', auth='user', website=True)
    def portal_report_stock_age(self, **kwargs):
        partner_ids = _get_partner_ids(request.env.user.partner_id)
        stock_ages = request.env['tpl.stock.age'].sudo().search([
            ('owner_id', 'in', partner_ids),
        ], order='days_in_stock desc', limit=200)
        return request.render('tpl_3pl_logistic.portal_tpl_report_stock_age', {
            'stock_ages': stock_ages,
            'page_name': 'tpl_report_stock_age',
        })

