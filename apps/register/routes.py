from flask import (
    Blueprint, render_template, request, redirect,
    url_for, flash, session, jsonify, send_file,current_app
)
from werkzeug.utils import secure_filename
from datetime import datetime
from jinja2 import TemplateNotFound
from io import BytesIO
import os
import random
import re
import logging
import pandas as pd
import openpyxl
from openpyxl.worksheet.datavalidation import DataValidation
import mysql.connector
from mysql.connector import Error

from apps.register import blueprint
from apps import get_db_connection

import numpy as np


# Access the upload folder from the current Flask app configuration
def allowed_file(filename):
    """Check if the uploaded file has a valid extension."""
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in current_app.config['ALLOWED_EXTENSIONS']



@blueprint.route('/r_pupils')
def r_pupils():
    """Fetch and filter pupils by Reg No, Name, Class, Study Year, Term, and Stream."""
    connection = get_db_connection()
    cursor = connection.cursor(dictionary=True)

    # Fetch data for dropdowns
    cursor.execute('SELECT year_id, year_name AS study_year FROM study_year ORDER BY year_name')
    study_years = cursor.fetchall()

    cursor.execute('SELECT class_id, class_name FROM classes ORDER BY class_name')
    class_list = cursor.fetchall()

    cursor.execute('SELECT term_id, term_name FROM terms ORDER BY term_name')
    terms = cursor.fetchall()

    
    cursor.execute('''
    SELECT 
        s.stream_id,
        s.stream_name,
        c.class_id,
        c.class_name
    FROM stream s
    JOIN classes c ON s.class_id = c.class_id
    ORDER BY s.stream_name
    ''')
    streams = cursor.fetchall() 

    # Get filter values from request
    reg_no = request.args.get('reg_no', '').strip()
    name = request.args.get('name', '').strip()
    class_id = request.args.get('class_name', '').strip()
    study_year_id = request.args.get('study_year', '').strip()
    term_id = request.args.get('term', '').strip()
    stream_id = request.args.get('stream', '').strip()

    # Build filters
    filters = []
    params = {}

    if reg_no:
        filters.append("p.reg_no LIKE %(reg_no)s")
        params['reg_no'] = f"%{reg_no}%"

    if name:
        filters.append("(p.first_name LIKE %(name)s OR p.last_name LIKE %(name)s)")
        params['name'] = f"%{name}%"

    if class_id:
        filters.append("p.class_id = %(class_id)s")
        params['class_id'] = class_id

    if study_year_id:
        filters.append("p.year_id = %(study_year_id)s")
        params['study_year_id'] = study_year_id

    if term_id:
        filters.append("p.term_id = %(term_id)s")
        params['term_id'] = term_id

    if stream_id:
        filters.append("p.stream_id = %(stream_id)s")
        params['stream_id'] = stream_id

    # Fetch filtered pupil data
    pupils = []
    if filters:
        query = f'''
            SELECT 
                p.pupil_id,
                p.reg_no,
                CONCAT(p.first_name, ' ', p.last_name) AS full_name,
                p.gender,
                p.image,
                p.date_of_birth,
                sy.year_name AS study_year,
                c.class_name,
                t.term_name,
                s.stream_name
            FROM pupils p
            JOIN study_year sy ON p.year_id = sy.year_id
            JOIN classes c ON p.class_id = c.class_id
            JOIN terms t ON p.term_id = t.term_id
            LEFT JOIN stream s ON p.stream_id = s.stream_id
            WHERE {' AND '.join(filters)}
            ORDER BY p.last_name
        '''
        cursor.execute(query, params)
        pupils = cursor.fetchall()

    cursor.close()
    connection.close()

    return render_template(
        'register/r_pupils.html',
        pupils=pupils,
        segment='pupils',
        class_list=class_list,
        study_years=study_years,
        terms=terms,
        streams=streams,
        filters={
            'reg_no': reg_no,
            'name': name,
            'class_name': class_id,
            'study_year': study_year_id,
            'term': term_id,
            'stream': stream_id
        }
    )









@blueprint.route('/register_pupil', methods=['POST'])
def register_pupil():
    assigned_by = session['id']  # Current user's ID from session

    selected_pupil_ids = request.form.getlist('pupil_ids')
    term_id = request.form.get('term')
    class_id = request.form.get('class_name')  # Get class from form
    flash_messages = []

    if not selected_pupil_ids:
        flash('No pupils were selected.', 'warning')
        return redirect(url_for('register_blueprint.r_pupils'))

    if not term_id:
        flash('No term was selected.', 'warning')
        return redirect(url_for('register_blueprint.r_pupils'))

    connection = get_db_connection()
    cursor = connection.cursor(dictionary=True)

    try:
        for pupil_id in selected_pupil_ids:
            # Fetch current pupil data
            cursor.execute("SELECT term_id, class_id FROM pupils WHERE pupil_id = %s", (pupil_id,))
            result = cursor.fetchone()

            if not result:
                flash_messages.append(f'Pupil {pupil_id} not found in the database, skipping.')
                continue

            updates = []
            params = []

            # Check if term needs update
            if str(result['term_id']) != str(term_id):
                updates.append("term_id = %s")
                params.append(term_id)

            # Check if class_name was provided and needs update
            if class_id and str(result['class_id']) != str(class_id):
                updates.append("class_id = %s")
                params.append(class_id)

            if updates:
                update_query = f"UPDATE pupils SET {', '.join(updates)} WHERE pupil_id = %s"
                params.append(pupil_id)
                cursor.execute(update_query, tuple(params))
            else:
                flash_messages.append(f'Pupil {pupil_id} already has the selected term and class.')

        connection.commit()

        for message in flash_messages:
            flash(message, 'warning' if 'already' in message or 'skipping' in message else 'success')

        if not flash_messages or all('already' not in msg and 'skipping' not in msg for msg in flash_messages):
            flash(f'{len(selected_pupil_ids)} pupil(s) updated successfully.', 'success')

    except Exception as e:
        connection.rollback()
        flash(f'Error while updating pupils: {str(e)}', 'danger')

    finally:
        cursor.close()
        connection.close()

    return redirect(url_for('register_blueprint.r_pupils'))





















@blueprint.route('/<template>')
def route_template(template):

    try:

        if not template.endswith('.html'):
            template += '.html'

        # Detect the current page
        segment = get_segment(request)

        # Serve the file (if exists) from app/templates/home/FILE.html
        return render_template("pupils/" + template, segment=segment)

    except TemplateNotFound:
        return render_template('home/page-404.html'), 404

    except:
        return render_template('home/page-500.html'), 500


# Helper - Extract current page name from request
def get_segment(request):

    try:

        segment = request.path.split('/')[-1]

        if segment == '':
            segment = 'pupils'

        return segment

    except:
        return None
