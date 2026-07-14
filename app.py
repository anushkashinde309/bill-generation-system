"""
Bill Generation System - Flask Application
A professional bill generation system with PDF export capability
"""

from flask import Flask, render_template, request, jsonify, send_file
from datetime import datetime
import json
from io import BytesIO
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_RIGHT, TA_LEFT
import uuid

app = Flask(__name__)
app.config['JSON_SORT_KEYS'] = False

# Store bills in memory (in production, use a database)
bills_storage = {}


@app.route('/')
def index():
    """Render the main page"""
    return render_template('index.html')


@app.route('/api/generate-bill', methods=['POST'])
def generate_bill():
    """Generate a new bill"""
    try:
        data = request.json
        
        # Validate input
        if not data.get('billTo') or not data.get('items'):
            return jsonify({'error': 'Missing required fields'}), 400
        
        if len(data['items']) == 0:
            return jsonify({'error': 'Bill must contain at least one item'}), 400
        
        # Create bill object
        bill_id = str(uuid.uuid4())[:8].upper()
        bill = {
            'id': bill_id,
            'billNumber': f'BILL-{bill_id}',
            'date': datetime.now().strftime('%Y-%m-%d'),
            'dueDate': data.get('dueDate', ''),
            'billFrom': {
                'company': data.get('billFrom', {}).get('company', 'Your Company'),
                'address': data.get('billFrom', {}).get('address', ''),
                'email': data.get('billFrom', {}).get('email', ''),
                'phone': data.get('billFrom', {}).get('phone', '')
            },
            'billTo': data.get('billTo', {}),
            'items': data.get('items', []),
            'notes': data.get('notes', ''),
            'taxRate': float(data.get('taxRate', 0)),
            'subtotal': 0,
            'tax': 0,
            'total': 0
        }
        
        # Calculate totals
        subtotal = 0
        for item in bill['items']:
            item_total = float(item['quantity']) * float(item['price'])
            item['total'] = item_total
            subtotal += item_total
        
        bill['subtotal'] = round(subtotal, 2)
        bill['tax'] = round(subtotal * (bill['taxRate'] / 100), 2)
        bill['total'] = round(bill['subtotal'] + bill['tax'], 2)
        
        # Store bill
        bills_storage[bill_id] = bill
        
        return jsonify(bill), 201
    
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/bills', methods=['GET'])
def get_bills():
    """Get all bills"""
    try:
        return jsonify(list(bills_storage.values())), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/bill/<bill_id>', methods=['GET'])
def get_bill(bill_id):
    """Get a specific bill"""
    try:
        if bill_id not in bills_storage:
            return jsonify({'error': 'Bill not found'}), 404
        
        return jsonify(bills_storage[bill_id]), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/bill/<bill_id>', methods=['DELETE'])
def delete_bill(bill_id):
    """Delete a bill"""
    try:
        if bill_id not in bills_storage:
            return jsonify({'error': 'Bill not found'}), 404
        
        del bills_storage[bill_id]
        return jsonify({'message': 'Bill deleted successfully'}), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/bill/<bill_id>/pdf', methods=['GET'])
def export_pdf(bill_id):
    """Export bill as PDF"""
    try:
        if bill_id not in bills_storage:
            return jsonify({'error': 'Bill not found'}), 404
        
        bill = bills_storage[bill_id]
        
        # Create PDF in memory
        pdf_buffer = BytesIO()
        doc = SimpleDocTemplate(pdf_buffer, pagesize=letter,
                               rightMargin=0.5*inch, leftMargin=0.5*inch,
                               topMargin=0.5*inch, bottomMargin=0.5*inch)
        
        # Container for PDF elements
        elements = []
        
        # Define styles
        styles = getSampleStyleSheet()
        title_style = ParagraphStyle(
            'CustomTitle',
            parent=styles['Heading1'],
            fontSize=24,
            textColor=colors.HexColor('#1e3c72'),
            spaceAfter=10,
            alignment=TA_CENTER
        )
        
        heading_style = ParagraphStyle(
            'CustomHeading',
            parent=styles['Heading2'],
            fontSize=12,
            textColor=colors.HexColor('#2a5298'),
            spaceAfter=8,
            spaceBefore=8
        )
        
        normal_style = ParagraphStyle(
            'CustomNormal',
            parent=styles['Normal'],
            fontSize=10,
            spaceAfter=4
        )
        
        # Title
        elements.append(Paragraph("INVOICE", title_style))
        elements.append(Spacer(1, 0.2*inch))
        
        # Bill info table
        bill_info_data = [
            ['Bill Number:', bill['billNumber'], 'Bill Date:', bill['date']],
            ['Due Date:', bill['dueDate'], '', '']
        ]
        
        bill_info_table = Table(bill_info_data, colWidths=[1.5*inch, 1.5*inch, 1.5*inch, 1.5*inch])
        bill_info_table.setStyle(TableStyle([
            ('FONT', (0, 0), (-1, -1), 'Helvetica', 9),
            ('TEXTCOLOR', (0, 0), (-1, -1), colors.black),
            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
            ('VALIGN', (0, 0), (-1, -1), 'TOP'),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.lightgrey),
        ]))
        
        elements.append(bill_info_table)
        elements.append(Spacer(1, 0.2*inch))
        
        # Bill From and To
        bill_details_data = [
            [Paragraph("<b>FROM:</b>", heading_style), Paragraph("<b>BILL TO:</b>", heading_style)],
            [
                Paragraph(format_address(bill['billFrom']), normal_style),
                Paragraph(format_address(bill['billTo']), normal_style)
            ]
        ]
        
        bill_details_table = Table(bill_details_data, colWidths=[3.5*inch, 3.5*inch])
        bill_details_table.setStyle(TableStyle([
            ('VALIGN', (0, 0), (-1, -1), 'TOP'),
            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
        ]))
        
        elements.append(bill_details_table)
        elements.append(Spacer(1, 0.2*inch))
        
        # Items table
        items_data = [['Item', 'Description', 'Quantity', 'Price', 'Total']]
        
        for item in bill['items']:
            items_data.append([
                item.get('name', ''),
                item.get('description', ''),
                str(item['quantity']),
                f"${float(item['price']):.2f}",
                f"${item.get('total', 0):.2f}"
            ])
        
        items_table = Table(items_data, colWidths=[1*inch, 2*inch, 1*inch, 1.2*inch, 1.2*inch])
        items_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#1e3c72')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 11),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
            ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
            ('GRID', (0, 0), (-1, -1), 1, colors.black),
            ('FONT', (0, 1), (-1, -1), 'Helvetica', 9),
            ('ALIGN', (3, 1), (-1, -1), 'RIGHT'),
            ('ALIGN', (2, 1), (2, -1), 'CENTER'),
        ]))
        
        elements.append(items_table)
        elements.append(Spacer(1, 0.2*inch))
        
        # Totals
        totals_data = [
            ['', '', '', 'Subtotal:', f"${bill['subtotal']:.2f}"],
            ['', '', '', 'Tax ({0}%)'.format(bill['taxRate']), f"${bill['tax']:.2f}"],
            ['', '', '', 'TOTAL:', f"${bill['total']:.2f}"]
        ]
        
        totals_table = Table(totals_data, colWidths=[1*inch, 2*inch, 1*inch, 1.2*inch, 1.2*inch])
        totals_table.setStyle(TableStyle([
            ('ALIGN', (0, 0), (2, -1), 'LEFT'),
            ('ALIGN', (3, 0), (-1, -1), 'RIGHT'),
            ('FONT', (3, 0), (-1, 1), 'Helvetica', 9),
            ('FONT', (3, 2), (-1, 2), 'Helvetica-Bold'),
            ('FONTSIZE', (3, 2), (-1, 2), 12),
            ('BACKGROUND', (3, 2), (-1, 2), colors.HexColor('#1e3c72')),
            ('TEXTCOLOR', (3, 2), (-1, 2), colors.whitesmoke),
            ('TOPPADDING', (3, 2), (-1, 2), 8),
            ('BOTTOMPADDING', (3, 2), (-1, 2), 8),
        ]))
        
        elements.append(totals_table)
        
        if bill.get('notes'):
            elements.append(Spacer(1, 0.2*inch))
            elements.append(Paragraph("<b>Notes:</b>", heading_style))
            elements.append(Paragraph(bill['notes'], normal_style))
        
        # Build PDF
        doc.build(elements)
        pdf_buffer.seek(0)
        
        return send_file(
            pdf_buffer,
            mimetype='application/pdf',
            as_attachment=True,
            download_name=f"Bill-{bill_id}.pdf"
        )
    
    except Exception as e:
        return jsonify({'error': str(e)}), 500


def format_address(address_dict):
    """Format address for display"""
    lines = []
    if address_dict.get('name'):
        lines.append(address_dict['name'])
    if address_dict.get('company'):
        lines.append(address_dict['company'])
    if address_dict.get('address'):
        lines.append(address_dict['address'])
    if address_dict.get('city'):
        city_line = address_dict['city']
        if address_dict.get('state'):
            city_line += f", {address_dict['state']}"
        if address_dict.get('zip'):
            city_line += f" {address_dict['zip']}"
        lines.append(city_line)
    if address_dict.get('email'):
        lines.append(f"Email: {address_dict['email']}")
    if address_dict.get('phone'):
        lines.append(f"Phone: {address_dict['phone']}")
    
    return '<br/>'.join(lines)


@app.errorhandler(404)
def not_found(error):
    """Handle 404 errors"""
    return jsonify({'error': 'Not found'}), 404


@app.errorhandler(500)
def internal_error(error):
    """Handle 500 errors"""
    return jsonify({'error': 'Internal server error'}), 500


if __name__ == '__main__':
    app.run(debug=True, host='localhost', port=5000)
