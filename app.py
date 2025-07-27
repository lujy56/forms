from flask import Flask, render_template, request, redirect, url_for, flash, send_file, make_response
import uuid
import json
import os
from datetime import datetime
from flask_mail import Mail, Message
from reportlab.lib.pagesizes import letter, A4
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, Image
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.lib import colors
import tempfile
import base64
import io
from weasyprint import HTML

app = Flask(__name__)
app.secret_key = 'your_secret_key'  # Needed for flash messages

# Flask-Mail configuration (example for Gmail SMTP)
app.config['MAIL_SERVER'] = 'smtp.gmail.com'
app.config['MAIL_PORT'] = 587
app.config['MAIL_USE_TLS'] = True
app.config['MAIL_USERNAME'] = 'schindlerforms@gmail.com'
app.config['MAIL_PASSWORD'] = 'dgrpcbdbwosnxeqn'
app.config['MAIL_DEFAULT_SENDER'] = 'schindlerforms@gmail.com'

mail = Mail(app)

SUBMISSIONS_FILE = 'submissions.json'

# Helper to load submissions
def load_submissions():
    if not os.path.exists(SUBMISSIONS_FILE):
        return []
    with open(SUBMISSIONS_FILE, 'r') as f:
        return json.load(f)

# Helper to save submissions
def save_submissions(submissions):
    with open(SUBMISSIONS_FILE, 'w') as f:
        json.dump(submissions, f, indent=2)

# Helper to send email
def send_email(to, subject, body, reply_to=None):
    msg = Message(subject, recipients=[to], body=body)
    if reply_to:
        msg.reply_to = reply_to
    mail.send(msg)

def create_pdf_content(submission_id, form_type, fields, approved, timestamps, version_history):
    """Create PDF content using reportlab"""
    story = []
    styles = getSampleStyleSheet()
    
    # Title
    title_style = ParagraphStyle(
        'CustomTitle',
        parent=styles['Heading1'],
        fontSize=18,
        spaceAfter=30,
        alignment=1,  # Center
        textColor=colors.HexColor('#b00')
    )
    story.append(Paragraph(f"Schindler Project Review Form", title_style))
    story.append(Paragraph(f"{form_type.title()} Project - ID: {submission_id}", styles['Heading2']))
    story.append(Spacer(1, 20))
    
    # Approval Status
    if approved:
        status_text = "✅ APPROVED"
        status_color = colors.HexColor('#28a745')
    else:
        status_text = "⏳ PENDING APPROVAL"
        status_color = colors.HexColor('#dc3545')
    
    status_style = ParagraphStyle(
        'Status',
        parent=styles['Normal'],
        fontSize=14,
        textColor=status_color,
        alignment=1,
        spaceAfter=20
    )
    story.append(Paragraph(status_text, status_style))
    
    # Contact Information
    story.append(Paragraph("Contact Information", styles['Heading2']))
    contact_data = [
        ['Salesman Email:', fields.get('salesman_email', 'N/A')],
        ['Project Manager Email:', fields.get('pm_email', 'N/A')]
    ]
    contact_table = Table(contact_data, colWidths=[2*inch, 4*inch])
    contact_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (0, -1), colors.HexColor('#f8f9fa')),
        ('TEXTCOLOR', (0, 0), (0, -1), colors.HexColor('#b00')),
        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
        ('FONTNAME', (0, 0), (-1, -1), 'Helvetica'),
        ('FONTSIZE', (0, 0), (-1, -1), 10),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
        ('GRID', (0, 0), (-1, -1), 1, colors.black)
    ]))
    story.append(contact_table)
    story.append(Spacer(1, 20))
    
    # Project Data
    story.append(Paragraph("Project Data", styles['Heading2']))
    if form_type == 'elevator':
        project_data = [
            ['Product line:', fields.get('product_line', 'N/A')],
            ['Process type:', fields.get('process_type', 'N/A')]
        ]
    else:
        project_data = [
            ['Color code:', fields.get('color_code', 'N/A')],
            ['Product line:', fields.get('product_line', 'N/A')],
            ['Process type:', fields.get('process_type', 'N/A')]
        ]
    
    project_table = Table(project_data, colWidths=[2*inch, 4*inch])
    project_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (0, -1), colors.HexColor('#f8f9fa')),
        ('TEXTCOLOR', (0, 0), (0, -1), colors.HexColor('#b00')),
        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
        ('FONTNAME', (0, 0), (-1, -1), 'Helvetica'),
        ('FONTSIZE', (0, 0), (-1, -1), 10),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
        ('GRID', (0, 0), (-1, -1), 1, colors.black)
    ]))
    story.append(project_table)
    story.append(Spacer(1, 20))
    
    # Form Questions with full text
    if form_type == 'elevator':
        # Customer Requirements
        story.append(Paragraph("Customer Requirements", styles['Heading2']))
        elevator_questions = [
            ('Unit used as construction elevator?', 'unit_construction_elevator', 'Charges approved by FF?'),
            ('Working time restrictions?', 'working_time_restrictions', ''),
            ('Special designated use of the elevator? (High traffic, Attica, Heavy loading, ...)', 'special_designated_use', ''),
            ('Special technical requirements? (Atmospheric exposure, steel structure, ...)', 'special_technical_requirements', ''),
            ('Installation dates, handover defined and achievable, Programme agreed with customer (lead time, resources, ...)?', 'installation_dates', 'Hand over Date agreed: ..........'),
            ('Site Office required / Priced?', 'site_office_required', ''),
            ('Special customer relation and/or installation relevant benefits communicated?', 'special_customer_relation', ''),
            ('Special work conditions (Temperature, dust, humidity, drilling restrictions, night shift, ...)?', 'special_work_conditions', '')
        ]
        
        for question, field_name, hint in elevator_questions:
            answer = fields.get(f'{field_name}_yn', 'N/A')
            comments = fields.get(f'{field_name}_comments', '')
            
            question_text = question
            if hint:
                question_text += f" - {hint}"
            
            story.append(Paragraph(f"<b>{question_text}</b>", styles['Normal']))
            story.append(Paragraph(f"Answer: {answer}", styles['Normal']))
            if comments:
                story.append(Paragraph(f"Comments: {comments}", styles['Italic']))
            story.append(Spacer(1, 8))
        
        # Project Scope
        story.append(Paragraph("Project Scope", styles['Heading2']))
        project_scope_questions = [
            ('Deliverables from MDC required/available?', 'deliverables_mdc', ''),
            ('Several units in the project? Divider Beam, Separator or Screen Considered. Balustrade height?', 'several_units', 'No of units... Configured?...'),
            ('New hoistway light required?', 'new_hoistway_light', ''),
            ('Metal works considered? Hoist Beam, Ladders etc.', 'metal_works', ''),
            ('If VF drive is PF1, RCCB Type budgeted?', 'vf_drive_pf1', ''),
            ('Painting works considered?', 'painting_works', ''),
            ('Electrical works considered?', 'electrical_works', ''),
            ('Civil works considered? Grouting, Fire Sealant', 'civil_works', ''),
            ('Full Shaft Separator Mesh required?', 'full_shaft_separator', ''),
            ('Glass elevator use checklist MAN-0213', 'glass_elevator_checklist', ''),
            ('3 way Intercom considered?', 'intercom', ''),
            ('GI trunking required?', 'gi_trunking', ''),
            ('Dismantling considered?', 'dismantling', ''),
            ('Handover dismantled material to customer?', 'handover_dismantled_material', ''),
            ('SAIS Package: Cwt screen, Machine/rotating equipment guard/Dividing screen/Pit ladder/platform/Shaft lighting 200 lux', 'sais_package', ''),
            ('Safety package: Hook certification/hoarding around landing doors/Finishes: Car lighting lux, Architraves or around landing doors, addl cwt fillers blocks.', 'safety_package', ''),
        ]
        
        for question, field_name, hint in project_scope_questions:
            answer = fields.get(f'{field_name}_yn', 'N/A')
            comments = fields.get(f'{field_name}_comments', '')
            
            question_text = question
            if hint:
                question_text += f" - {hint}"
            
            story.append(Paragraph(f"<b>{question_text}</b>", styles['Normal']))
            story.append(Paragraph(f"Answer: {answer}", styles['Normal']))
            if comments:
                story.append(Paragraph(f"Comments: {comments}", styles['Italic']))
            story.append(Spacer(1, 8))
        
        # Site Survey/IFC
        story.append(Paragraph("Site Survey/IFC", styles['Heading2']))
        site_survey_questions = [
            ('Incase of Accessible rooms beneath the hoistway, Cwt Safety Gear Included?', 'accessible_rooms_hoistway', ''),
            ('Additional fall protection required? (Landing doors / balustrade / trap doors / fix point for safety equipment, ...)', 'additional_fall_protection', ''),
            ('Building Tolerance considered as minimum +/-25mm?', 'building_tolerance', ''),
            ('Sufficient parking space provided nearby?', 'parking_space', ''),
            ('Building accessible (distance to unloading, stairs, MR access, 2.5m rails, ...)?', 'building_accessible', ''),
            ('Does the Power supply meet schindler requirement?', 'power_supply_schindler', ''),
            ('Does the flooring need special protection?', 'flooring_protection', ''),
            ('Keys required to access the building?', 'keys_required', '')
        ]
        
        for question, field_name, hint in site_survey_questions:
            answer = fields.get(f'{field_name}_yn', 'N/A')
            comments = fields.get(f'{field_name}_comments', '')
            
            question_text = question
            if hint:
                question_text += f" - {hint}"
            
            story.append(Paragraph(f"<b>{question_text}</b>", styles['Normal']))
            story.append(Paragraph(f"Answer: {answer}", styles['Normal']))
            if comments:
                story.append(Paragraph(f"Comments: {comments}", styles['Italic']))
            story.append(Spacer(1, 8))
        
        # Installation Requirements
        story.append(Paragraph("Installation Requirements", styles['Heading2']))
        installation_questions = [
            ('Installation method clear (INEX, scaffold, scaffoldless) Priced Accordingly?', 'installation_method', 'Single or 2/3 stage installation?...'),
            ('Structural building issues?', 'structural_building_issues', ''),
            ('Installation target hours correct, Local Installation Hours considered?', 'installation_target_hours', ''),
            ('Permanent lifting points for installation required and considered?', 'permanent_lifting_points', ''),
            ('Potential equalization existing?', 'potential_equalization', ''),
            ('Sufficient power supply provided?', 'sufficient_power_supply', ''),
            ('Sufficient venting of the hoistway and machine room existing?', 'sufficient_venting', ''),
            ('In case of chemical bolts: Are additional hours considered and charged to the customer?', 'chemical_bolts', ''),
            ('Storage room sufficient?', 'storage_room', ''),
            ('Truck unloading clarified (truck w/ crane required, forklift accessibility, crane cost, ...)?', 'truck_unloading', ''),
            ('Waste disposal site cleaning covered?', 'waste_disposal', ''),
            ('Met SMRA/USANADA Compliance? Necessary equipments priced to make CCTV operational?', 'smra_usanada_compliance', ''),
            ('Alternate fire recall considered?', 'alternate_fire_recall', ''),
            ('Transom Provided?', 'transom_provided', '')
        ]
        
        for question, field_name, hint in installation_questions:
            answer = fields.get(f'{field_name}_yn', 'N/A')
            comments = fields.get(f'{field_name}_comments', '')
            
            question_text = question
            if hint:
                question_text += f" - {hint}"
            
            story.append(Paragraph(f"<b>{question_text}</b>", styles['Normal']))
            story.append(Paragraph(f"Answer: {answer}", styles['Normal']))
            if comments:
                story.append(Paragraph(f"Comments: {comments}", styles['Italic']))
            story.append(Spacer(1, 8))
        
        # Financial & Contract Requirements
        story.append(Paragraph("Financial & Contract Requirements", styles['Heading2']))
        financial_questions = [
            ('Is this project a Turnkey?', 'turnkey', 'If Yes, ask for Subcon site check list/compliance'),
            ('Penalty agreed?', 'penalty_agreed', '...per day')
        ]
        
        for question, field_name, hint in financial_questions:
            answer = fields.get(f'{field_name}_yn', 'N/A')
            comments = fields.get(f'{field_name}_comments', '')
            
            question_text = question
            if hint:
                question_text += f" - {hint}"
            
            story.append(Paragraph(f"<b>{question_text}</b>", styles['Normal']))
            story.append(Paragraph(f"Answer: {answer}", styles['Normal']))
            if comments:
                story.append(Paragraph(f"Comments: {comments}", styles['Italic']))
            story.append(Spacer(1, 8))
        
        # Code Requirements
        story.append(Paragraph("Code Requirements", styles['Heading2']))
        code_questions = [
            ('Special code requirements (Seismic, fire rating, fire fighter, IP rating, local code, vandal proof, disability, ...)?', 'special_code_requirements', ''),
            ('Seismic completed?', 'seismic_completed', 'Zone ...'),
            ('Foreign installation in MR or hoistway? Mitigation?', 'foreign_installation', '')
        ]
        
        for question, field_name, hint in code_questions:
            answer = fields.get(f'{field_name}_yn', 'N/A')
            comments = fields.get(f'{field_name}_comments', '')
            
            question_text = question
            if hint:
                question_text += f" - {hint}"
            
            story.append(Paragraph(f"<b>{question_text}</b>", styles['Normal']))
            story.append(Paragraph(f"Answer: {answer}", styles['Normal']))
            if comments:
                story.append(Paragraph(f"Comments: {comments}", styles['Italic']))
            story.append(Spacer(1, 8))
    
    else:  # Escalator form
        # Customer Requirements
        story.append(Paragraph("Customer Requirements", styles['Heading2']))
        escalator_questions = [
            ('Working time restrictions?', 'working_time_restrictions', ''),
            ('Special designated use of the escalator/moving walk? (Public Transport, outdoor usage, ...)', 'special_designated_use', ''),
            ('Special technical requirements? (Delivery in multiple pieces, no intermediate support, sprinkler, parallel arrangement...)', 'special_technical_requirements', ''),
            ('Installation dates, handover defined and achievable (lead time, resources, ...)?', 'installation_dates', 'Date:'),
            ('Special Customer relation and/or installation relevant benefits communicated?', 'special_customer_relation', ''),
            ('Special work conditions (Temperature, dust, humidity, drilling restrictions, night shift, ...)?', 'special_work_conditions', '')
        ]
        
        for question, field_name, hint in escalator_questions:
            answer = fields.get(f'{field_name}_yn', 'N/A')
            comments = fields.get(f'{field_name}_comments', '')
            
            question_text = question
            if hint:
                question_text += f" - {hint}"
            
            story.append(Paragraph(f"<b>{question_text}</b>", styles['Normal']))
            story.append(Paragraph(f"Answer: {answer}", styles['Normal']))
            if comments:
                story.append(Paragraph(f"Comments: {comments}", styles['Italic']))
            story.append(Spacer(1, 8))
        
        # Project Scope
        story.append(Paragraph("Project Scope", styles['Heading2']))
        project_scope_questions = [
            ('Deliverables from MDC required/available?', 'deliverables_mdc', ''),
            ('Several units in the project?', 'several_units', ''),
            ('New building interface required?', 'new_building_interface', ''),
            ('Dismantling considered? Handover dismantled material to Customer?', 'dismantling', ''),
            ('Metal works considered?', 'metal_works', ''),
            ('Painting works considered?', 'painting_works', ''),
            ('Electrical works considered?', 'electrical_works', ''),
            ('Civil works considered?', 'civil_works', ''),
            ('Others works?', 'other_works', ''),
            ('Truck unloading clarified (truck/crane required, forklift accessibility, ...)?', 'truck_unloading', ''),
            ('Sprinkler pipes?', 'sprinkler_pipes', '')
        ]
        
        for question, field_name, hint in project_scope_questions:
            answer = fields.get(f'{field_name}_yn', 'N/A')
            comments = fields.get(f'{field_name}_comments', '')
            
            question_text = question
            if hint:
                question_text += f" - {hint}"
            
            story.append(Paragraph(f"<b>{question_text}</b>", styles['Normal']))
            story.append(Paragraph(f"Answer: {answer}", styles['Normal']))
            if comments:
                story.append(Paragraph(f"Comments: {comments}", styles['Italic']))
            story.append(Spacer(1, 8))
        
        # Site Survey (MOD)
        story.append(Paragraph("Site Survey (MOD)", styles['Heading2']))
        site_survey_questions = [
            ('Additional fall protection required? (balustrade/fix point for safety equipment, ...)', 'additional_fall_protection', ''),
            ('MTBC Performance: Components impacting MTBC identified and considered in offer scope', 'mtbc_performance', ''),
            ('Sufficient parking space provided nearby?', 'parking_space', ''),
            ('Building accessible (distance to unloading)', 'building_accessible', ''),
            ('Keys/special agreement required to access the building?', 'keys_required', '')
        ]
        
        for question, field_name, hint in site_survey_questions:
            answer = fields.get(f'{field_name}_yn', 'N/A')
            comments = fields.get(f'{field_name}_comments', '')
            
            question_text = question
            if hint:
                question_text += f" - {hint}"
            
            story.append(Paragraph(f"<b>{question_text}</b>", styles['Normal']))
            story.append(Paragraph(f"Answer: {answer}", styles['Normal']))
            if comments:
                story.append(Paragraph(f"Comments: {comments}", styles['Italic']))
            story.append(Spacer(1, 8))
        
        # Installation Requirements
        story.append(Paragraph("Installation Requirements", styles['Heading2']))
        installation_questions = [
            ('Installation method clear (scaffold, suspension points, ceiling plates, I beam)?', 'installation_method', ''),
            ('Structural building issues?', 'structural_building_issues', ''),
            ('Installation target hours correct?', 'installation_target_hours', ''),
            ('Permanent lifting points for installation required?', 'permanent_lifting_points', ''),
            ('Potential equalization existing?', 'potential_equalization', ''),
            ('Sufficient power supplies provided?', 'sufficient_power_supplies', ''),
            ('Storage room sufficient?', 'storage_room', ''),
            ('Maximum floor load discussed and considered?', 'max_floor_load', ''),
            ('Additional floor supports considered?', 'additional_floor_supports', ''),
            ('Waste disposal site cleaning covered?', 'waste_disposal', ''),
            ('Floor cover protection considered?', 'floor_cover_protection', '')
        ]
        
        for question, field_name, hint in installation_questions:
            answer = fields.get(f'{field_name}_yn', 'N/A')
            comments = fields.get(f'{field_name}_comments', '')
            
            question_text = question
            if hint:
                question_text += f" - {hint}"
            
            story.append(Paragraph(f"<b>{question_text}</b>", styles['Normal']))
            story.append(Paragraph(f"Answer: {answer}", styles['Normal']))
            if comments:
                story.append(Paragraph(f"Comments: {comments}", styles['Italic']))
            story.append(Spacer(1, 8))
        
        # Financial & Contract Requirements
        story.append(Paragraph("Financial & Contract Requirements", styles['Heading2']))
        financial_questions = [
            ('Penalty agreed?', 'penalty_agreed', '')
        ]
        
        for question, field_name, hint in financial_questions:
            answer = fields.get(f'{field_name}_yn', 'N/A')
            comments = fields.get(f'{field_name}_comments', '')
            
            question_text = question
            if hint:
                question_text += f" - {hint}"
            
            story.append(Paragraph(f"<b>{question_text}</b>", styles['Normal']))
            story.append(Paragraph(f"Answer: {answer}", styles['Normal']))
            if comments:
                story.append(Paragraph(f"Comments: {comments}", styles['Italic']))
            story.append(Spacer(1, 8))
        
        # Code Requirements
        story.append(Paragraph("Code Requirements", styles['Heading2']))
        code_questions = [
            ('Special code requirements (Earthquake, fire rating, fire fighter, IP rating, local code, ...)?', 'special_code_requirements', ''),
        ]
        
        for question, field_name, hint in code_questions:
            answer = fields.get(f'{field_name}_yn', 'N/A')
            comments = fields.get(f'{field_name}_comments', '')
            
            question_text = question
            if hint:
                question_text += f" - {hint}"
            
            story.append(Paragraph(f"<b>{question_text}</b>", styles['Normal']))
            story.append(Paragraph(f"Answer: {answer}", styles['Normal']))
            if comments:
                story.append(Paragraph(f"Comments: {comments}", styles['Italic']))
            story.append(Spacer(1, 8))
    
    # Signatures
    story.append(Paragraph("Signatures", styles['Heading2']))
    if form_type == 'elevator':
        signature_data = [
            ['Salesman Name:', fields.get('salesman_name', 'N/A')],
            ['Order Processing / Sales Engineering Name:', fields.get('order_processing_name', 'N/A')],
            ['Project Engineer / Manager Name:', fields.get('project_engineer_name', 'N/A')]
        ]
    else:
        signature_data = [
            ['Sales Representative Name:', fields.get('sales_rep_name', 'N/A')],
            ['Sales Assistant Name:', fields.get('sales_assistant_name', 'N/A')],
            ['Supervisor Name:', fields.get('supervisor_name', 'N/A')]
        ]
    
    signature_table = Table(signature_data, colWidths=[2.5*inch, 3.5*inch])
    signature_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (0, -1), colors.HexColor('#f8f9fa')),
        ('TEXTCOLOR', (0, 0), (0, -1), colors.HexColor('#b00')),
        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
        ('FONTNAME', (0, 0), (-1, -1), 'Helvetica'),
        ('FONTSIZE', (0, 0), (-1, -1), 10),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
        ('GRID', (0, 0), (-1, -1), 1, colors.black)
    ]))
    story.append(signature_table)
    story.append(Spacer(1, 20))
    
    # Timestamps
    if timestamps:
        story.append(Paragraph("Form Timeline", styles['Heading2']))
        if timestamps.get('initial_submission'):
            initial_date = timestamps['initial_submission'].split('T')[0]
            initial_time = timestamps['initial_submission'].split('T')[1][:5]
            story.append(Paragraph(f"Initial Submission: {initial_date} at {initial_time}", styles['Normal']))
        
        if timestamps.get('last_modified'):
            last_date = timestamps['last_modified'].split('T')[0]
            last_time = timestamps['last_modified'].split('T')[1][:5]
            story.append(Paragraph(f"Last Modified: {last_date} at {last_time}", styles['Normal']))
        
        story.append(Spacer(1, 20))
    
    # Version History
    if version_history:
        story.append(Paragraph("Complete Form Timeline", styles['Heading2']))
        story.append(Paragraph("Every adjustment and edit made to this form:", styles['Normal']))
        story.append(Spacer(1, 10))
        
        for i, version in enumerate(version_history):
            date = version['timestamp'].split('T')[0]
            time = version['timestamp'].split('T')[1][:5]
            action = version['action']
            approved_status = "✓ Approved" if version.get('approved') else ""
            
            # Create a more detailed version entry
            version_text = f"<b>Edit #{i+1}:</b> {action}"
            version_text += f"<br/>Date: {date} at {time}"
            
            if approved_status:
                version_text += f"<br/>Status: {approved_status}"
            
            story.append(Paragraph(version_text, styles['Normal']))
            story.append(Spacer(1, 8))
        
        # Add current PDF generation timestamp
        current_time = datetime.now()
        pdf_date = current_time.strftime('%Y-%m-%d')
        pdf_time = current_time.strftime('%H:%M')
        
        story.append(Paragraph(f"<b>PDF Generated:</b> {pdf_date} at {pdf_time}", styles['Normal']))
        story.append(Spacer(1, 10))
        
        # Summary
        total_edits = len(version_history)
        story.append(Paragraph(f"<b>Summary:</b> This form has been edited {total_edits} time(s) from initial submission to final PDF generation.", styles['Normal']))
        story.append(Spacer(1, 6))
    
    return story

@app.route('/', methods=['GET'])
def landing():
    return render_template('landing.html')

@app.route('/form', methods=['GET'])
def form():
    form_type = request.args.get('type', 'elevator')
    if form_type == 'escalator':
        return render_template('form.html', form_type='escalator')
    return render_template('form.html', form_type='elevator')

@app.route('/confirmation', methods=['GET'])
def confirmation():
    message = request.args.get('message', 'Your form has been submitted.')
    submission_id = request.args.get('submission_id', None)
    review_submission = request.args.get('review_submission', 'False').lower() == 'true'
    return render_template('confirmation.html', message=message, submission_id=submission_id, review_submission=review_submission)

@app.route('/submit', methods=['POST'])
def submit():
    form_type = request.form.get('form_type', 'elevator')
    data = dict(request.form)
    # Save doodle signature
    signature_doodle_data = data.get('signature_doodle_data', '')
    # Generate unique ID
    submission_id = str(uuid.uuid4())[:8]
    # Add timestamp for initial submission
    current_time = datetime.now().isoformat()
    # Save to JSON
    submission = {
        'id': submission_id,
        'form_type': form_type,
        'fields': data,
        'signature_doodle_data': signature_doodle_data,
        'initial_signature': signature_doodle_data,  # Save initial signature separately
        'review_signature': '',  # Initialize review signature as empty
        'approval_comments': '',
        'approved': False,
        'timestamps': {
            'initial_submission': current_time,
            'last_modified': current_time
        },
        'version_history': [{
            'timestamp': current_time,
            'action': 'Initial submission by salesman',
            'fields': data.copy()
        }]
    }
    submissions = load_submissions()
    submissions.append(submission)
    save_submissions(submissions)
    # Generate review link
    review_link = url_for('review', submission_id=submission_id, _external=True)
    # Send email to PM (get PM email from form fields)
    pm_email = data.get('pm_email') or data.get('order_processing_name') or data.get('sales_assistant_name')
    salesman_email = data.get('salesman_email') or data.get('sales_rep_name')
    subject = f"Project Review Request: {form_type.title()}"
    body = f"Hello,\n\nA new {form_type} project submission requires your review.\n\nPlease review and approve at: {review_link}\n\nThank you."
    try:
        if pm_email:
            send_email(pm_email, subject, body, reply_to=salesman_email)
        flash('Submission successful! Project manager has been notified.', 'success')
    except Exception as e:
        flash(f'Submission saved, but failed to send email: {e}', 'error')
    return redirect(url_for('confirmation', message='Your form has been submitted.'))

@app.route('/review/<submission_id>', methods=['GET'])
def review(submission_id):
    submissions = load_submissions()
    submission = next((s for s in submissions if s['id'] == submission_id), None)
    if not submission:
        return 'Submission not found', 404
    form_type = submission.get('form_type', 'elevator')
    fields = submission.get('fields', {})
    signature_doodle_data = submission.get('signature_doodle_data', '')
    approved = submission.get('approved', False)
    timestamps = submission.get('timestamps', {})
    return render_template('review.html', 
                         submission_id=submission_id, 
                         form_type=form_type, 
                         fields=fields, 
                         signature_doodle_data=signature_doodle_data,
                         approved=approved,
                         timestamps=timestamps)

@app.route('/review/<submission_id>/submit', methods=['POST'])
def review_submit(submission_id):
    # Get updated data from PM
    form_type = request.form.get('form_type', 'elevator')
    data = dict(request.form)
    signature_doodle_data = data.get('signature_doodle_data', '')
    approved = 'approved' in request.form
    
    # Load and update submission
    submissions = load_submissions()
    submission = next((s for s in submissions if s['id'] == submission_id), None)
    if not submission:
        return 'Submission not found', 404
    
    current_time = datetime.now().isoformat()
    
    # Preserve original signature if no new signature is provided
    original_signature = submission.get('signature_doodle_data', '')
    if not signature_doodle_data or signature_doodle_data == '':
        signature_doodle_data = original_signature
    
    # Store both signatures separately
    initial_signature = submission.get('initial_signature', original_signature)
    review_signature = signature_doodle_data if signature_doodle_data != original_signature else ''
    
    # Update submission
    submission['form_type'] = form_type
    submission['fields'] = data
    submission['signature_doodle_data'] = signature_doodle_data
    submission['initial_signature'] = initial_signature
    submission['review_signature'] = review_signature
    submission['approved'] = approved
    submission['timestamps']['last_modified'] = current_time
    
    # Add to version history
    if 'version_history' not in submission:
        submission['version_history'] = []
    
    submission['version_history'].append({
        'timestamp': current_time,
        'action': 'Updated by project manager',
        'fields': data.copy(),
        'approved': approved
    })
    
    save_submissions(submissions)
    
    # Send confirmation email to salesman
    salesman_email = data.get('salesman_email') or data.get('sales_rep_name')
    subject = f"Project Reviewed: {form_type.title()}"
    body = f"Hello,\n\nYour {form_type} project submission has been reviewed and updated by the project manager.\n\nYou can view the updated submission at: {url_for('review', submission_id=submission_id, _external=True)}\n\nThank you."
    try:
        if salesman_email:
            send_email(salesman_email, subject, body)
        flash('Review submitted and salesman notified.', 'success')
    except Exception as e:
        flash(f'Review saved, but failed to send email: {e}', 'error')
    return redirect(url_for('confirmation', message='Your form has been submitted.', submission_id=submission_id, review_submission=True))

@app.route('/download/<submission_id>', methods=['GET'])
def download_pdf(submission_id):
    submissions = load_submissions()
    submission = next((s for s in submissions if s['id'] == submission_id), None)
    if not submission:
        return 'Submission not found', 404

    form_type = submission.get('form_type', 'elevator')
    fields = submission.get('fields', {})
    signature_doodle_data = submission.get('signature_doodle_data', '')
    initial_signature = submission.get('initial_signature', '')
    review_signature = submission.get('review_signature', '')
    approved = submission.get('approved', False)
    
    # Check if signature data is in fields dictionary
    if not signature_doodle_data and 'signature_doodle_data' in fields:
        signature_doodle_data = fields['signature_doodle_data']
    
    # Debug: Print signature data info
    print(f"PDF Generation Debug:")
    print(f"Submission ID: {submission_id}")
    print(f"Initial signature length: {len(initial_signature) if initial_signature else 0}")
    print(f"Review signature length: {len(review_signature) if review_signature else 0}")
    print(f"Approved status: {approved}")
    print(f"Initial signature preview: {initial_signature[:50] if initial_signature else 'None'}")
    print(f"Review signature preview: {review_signature[:50] if review_signature else 'None'}")

    # Choose the correct template
    if form_type == 'elevator':
        template_name = 'form_elevator.html'
    else:
        template_name = 'form_escalator.html'

    # Render the filled form as HTML
    html = render_template(
        template_name,
        fields=fields,
        signature_doodle_data=signature_doodle_data,
        initial_signature=initial_signature,
        review_signature=review_signature,
        approved=approved,
        pdf_mode=True  # Optional: use this in template to hide buttons/scripts
    )

    # Generate PDF from HTML
    pdf = HTML(string=html, base_url=request.host_url).write_pdf()
    response = make_response(pdf)
    response.headers['Content-Type'] = 'application/pdf'
    response.headers['Content-Disposition'] = f'attachment; filename=schindler_form_{submission_id}.pdf'
    return response

if __name__ == '__main__':
    app.run(debug=True) 