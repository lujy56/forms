from flask import Flask, render_template, request, redirect, url_for, flash
import uuid
import json
import os
from flask_mail import Mail, Message

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

@app.route('/', methods=['GET'])
def landing():
    return render_template('landing.html')

@app.route('/form', methods=['GET'])
def form():
    form_type = request.args.get('type', 'elevator')
    if form_type == 'escalator':
        return render_template('form.html', form_type='escalator')
    return render_template('form.html', form_type='elevator')

@app.route('/submit', methods=['POST'])
def submit():
    form_type = request.form.get('form_type', 'elevator')
    # Collect all form data
    data = dict(request.form)
    # Remove signature_data from form fields (will add separately)
    signature_data = data.pop('signature_data', None)
    # Generate unique ID
    submission_id = str(uuid.uuid4())[:8]
    # Save to JSON
    submission = {
        'id': submission_id,
        'form_type': form_type,
        'fields': data,
        'signature_data': signature_data,
        'approval_comments': ''
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
    return redirect(url_for('form', type=form_type))

@app.route('/review/<submission_id>', methods=['GET'])
def review(submission_id):
    submissions = load_submissions()
    submission = next((s for s in submissions if s['id'] == submission_id), None)
    if not submission:
        return 'Submission not found', 404
    form_type = submission.get('form_type', 'elevator')
    fields = submission.get('fields', {})
    signature_data = submission.get('signature_data', '')
    return render_template('review.html', submission_id=submission_id, form_type=form_type, fields=fields, signature_data=signature_data)

@app.route('/review/<submission_id>/submit', methods=['POST'])
def review_submit(submission_id):
    # Get updated data from PM
    form_type = request.form.get('form_type', 'elevator')
    data = dict(request.form)
    signature_data = data.pop('signature_data', None)
    # Load and update submission
    submissions = load_submissions()
    submission = next((s for s in submissions if s['id'] == submission_id), None)
    if not submission:
        return 'Submission not found', 404
    submission['form_type'] = form_type
    submission['fields'] = data
    submission['signature_data'] = signature_data
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
    return redirect(url_for('review', submission_id=submission_id))

if __name__ == '__main__':
    app.run(debug=True) 