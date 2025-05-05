from flask import (
    Blueprint, g, render_template, request, redirect,
    url_for, flash, session, jsonify, send_file, current_app
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
import numpy as np
import openpyxl
from openpyxl import Workbook
from openpyxl.worksheet.datavalidation import DataValidation

import mysql.connector
from mysql.connector import Error

from apps.results import blueprint
from apps import get_db_connection



# Access the upload folder from the current Flask app configuration
def allowed_file(filename):
    """Check if the uploaded file has a valid extension."""
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in current_app.config['ALLOWED_EXTENSIONS']

















@blueprint.route('/pdownload_template', methods=['GET'])
def pdownload_template():
    # Extract filters from query parameters
    class_id = request.args.get('class_id')
    year_id = request.args.get('year_id')
    term_id = request.args.get('term_id')
    subject_id = request.args.get('subject_id')
    assessment_id = request.args.get('assessment_id')

    # Validate required inputs
    if not all([class_id, year_id, term_id, subject_id, assessment_id]):
        flash("Please select all required fields: class, study year, term, subject, and assessment.", "error")
        return redirect(url_for('results_blueprint.pupload_excel'))

    conn = get_db_connection()
    if not conn:
        flash("Failed to connect to the database.", "error")
        return redirect(url_for('results_blueprint.pupload_excel'))

    cursor = conn.cursor(dictionary=True)

    try:
        # Helper function to fetch list from a column
        def fetch_column(query, column):
            cursor.execute(query)
            return [row[column] for row in cursor.fetchall()]

        # Dropdown values for Excel validation
        classes = fetch_column("SELECT class_name FROM classes ORDER BY class_name", "class_name")
        study_years = fetch_column("SELECT year_name FROM study_year ORDER BY year_name", "year_name")
        assessments = fetch_column("SELECT assessment_name FROM assessment ORDER BY assessment_name", "assessment_name")
        terms = fetch_column("SELECT term_name FROM terms ORDER BY term_name", "term_name")
        subjects = fetch_column("SELECT subject_name FROM subjects ORDER BY subject_name", "subject_name")

        # Lookup names for selected IDs
        cursor.execute("SELECT class_name FROM classes WHERE class_id = %s", (class_id,))
        class_name = cursor.fetchone()
        cursor.execute("SELECT term_name FROM terms WHERE term_id = %s", (term_id,))
        term_name = cursor.fetchone()
        cursor.execute("SELECT assessment_name FROM assessment WHERE assessment_id = %s", (assessment_id,))
        assessment_name = cursor.fetchone()
        cursor.execute("SELECT year_name FROM study_year WHERE year_id = %s", (year_id,))
        year_name = cursor.fetchone()
        cursor.execute("SELECT subject_name FROM subjects WHERE subject_id = %s", (subject_id,))
        subject_name = cursor.fetchone()

        # Validate each result
        if not all([class_name, term_name, assessment_name, year_name, subject_name]):
            flash("Invalid selection detected. Please try again.", "error")
            return redirect(url_for('results_blueprint.pupload_excel'))

        # Unwrap dict results
        class_name = class_name['class_name']
        term_name = term_name['term_name']
        assessment_name = assessment_name['assessment_name']
        year_name = year_name['year_name']
        subject_name = subject_name['subject_name']

        # Fetch pupils for the selected filters
        cursor.execute("""
            SELECT reg_no, first_name, other_name, last_name
            FROM pupils
            WHERE class_id = %s AND year_id = %s AND term_id = %s
            ORDER BY last_name
        """, (class_id, year_id, term_id))
        pupils = cursor.fetchall()

    finally:
        cursor.close()
        conn.close()

    if not pupils:
        flash("No students found for the selected filters.", "error")
        return redirect(url_for('results_blueprint.pupload_excel'))

    # Create Excel workbook
    wb = Workbook()
    ws = wb.active
    ws.title = "Results Template"

    # Headers
    headers = [
        "reg_no", "first_name", "other_name", "last_name",
        "class", "term", "assessment", "study_year", "notes", "subject", "mark"
    ]
    ws.append(headers)

    # Populate rows with default data
    for pupil in pupils:
        ws.append([
            pupil['reg_no'],
            pupil['first_name'],
            pupil['other_name'],
            pupil['last_name'],
            class_name,
            term_name,
            assessment_name,
            year_name,
            "",  # Notes
            subject_name,
            ""   # Mark
        ])

    # Sheet for reference values
    dropdown_ws = wb.create_sheet("drop_down_data")
    dropdown_ws.append(["reg_nos", "classes", "study_years", "assessments", "terms", "subjects"])
    dropdown_ws.append([
        ", ".join([p['reg_no'] for p in pupils]),
        ", ".join(classes),
        ", ".join(study_years),
        ", ".join(assessments),
        ", ".join(terms),
        ", ".join(subjects)
    ])

    # Helper to safely format dropdown values
    def safe_join(values):
        # Ensure values are not empty and limit the result to 255 characters
        return ",".join([str(v).replace('"', "'") for v in values])[:255]

    # Add dropdown validations
    validations = [
        (DataValidation(type="list", formula1=f'"{safe_join(classes)}"', allow_blank=True), 'E'),
        (DataValidation(type="list", formula1=f'"{safe_join(terms)}"', allow_blank=True), 'F'),
        (DataValidation(type="list", formula1=f'"{safe_join(assessments)}"', allow_blank=True), 'G'),
        (DataValidation(type="list", formula1=f'"{safe_join(study_years)}"', allow_blank=True), 'H'),
        (DataValidation(type="list", formula1=f'"{safe_join(subjects)}"', allow_blank=True), 'J'),
    ]

    for dv, col in validations:
        ws.add_data_validation(dv)
        dv.add(f"{col}2:{col}{len(pupils) + 1}")

    # Return Excel file as a download
    output = BytesIO()
    wb.save(output)
    output.seek(0)

    return send_file(
        output,
        as_attachment=True,
        download_name="filtered_results_template.xlsx",
        mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )







@blueprint.route('/pupload_excel', methods=['GET', 'POST'])
def pupload_excel():
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    # Fetch dropdown data
    cursor.execute('SELECT year_id, year_name AS study_year FROM study_year ORDER BY year_name')
    study_years = cursor.fetchall()

    cursor.execute('SELECT class_id, class_name FROM classes ORDER BY class_name')
    class_list = cursor.fetchall()

    cursor.execute('SELECT term_id, term_name FROM terms ORDER BY term_name')
    terms = cursor.fetchall()

    cursor.execute('SELECT subject_id, subject_name FROM subjects ORDER BY subject_name')
    subjects = cursor.fetchall()

    cursor.execute('SELECT assessment_id, assessment_name FROM assessment ORDER BY assessment_name')
    assessments = cursor.fetchall()

    if request.method == 'POST':
        file = request.files.get('file')

        # Validate file
        if not file or file.filename == '':
            flash('No file selected.', 'danger')
            return redirect(request.url)

        if not allowed_file(file.filename):
            flash('Invalid file format. Please upload an Excel file.', 'danger')
            return redirect(request.url)

        # Save the uploaded file
        filename = secure_filename(file.filename)
        file_path = os.path.join(current_app.config['UPLOAD_FOLDER'], filename)
        file.save(file_path)

        try:
            # Read and validate Excel data
            df = pd.read_excel(file_path)
            processed_data, errors, existing_reg_nos, duplicate_reg_nos = validate_excel_data(df)

            # Handle validation errors
            if errors:
                flash('Errors encountered:\n' + '\n'.join(errors), 'danger')
                return redirect(request.url)

            # Handle duplicate reg_no
            if duplicate_reg_nos:
                flash(f"Duplicate reg_no(s) found: {', '.join(duplicate_reg_nos)}", 'danger')
                return redirect(request.url)

            # Handle existing records and skip insertion if found
            if existing_reg_nos:
                flash(f"Existing reg_no(s): {', '.join(existing_reg_nos)} (skipped).", 'warning')
                return redirect(url_for('results_blueprint.pupload_excel'))

            # If there are no errors or existing records, insert data into the database
            if processed_data:
                insert_scores_into_database(processed_data)  # Ensure the insert function is correct
                flash(f"{len(processed_data)} score record(s) uploaded successfully!", 'success')
            else:
                flash('No new records to insert.', 'info')

            return redirect(url_for('results_blueprint.pupload_excel'))

        except pd.errors.EmptyDataError:
            flash('Uploaded file is empty.', 'danger')
        except Exception as e:
            flash(f'Error processing the file: {str(e)}', 'danger')

        return redirect(url_for('results_blueprint.pupload_excel'))

    # GET request: render upload page with dropdowns
    return render_template(
        'results/upload_excel.html',
        study_years=study_years,
        class_list=class_list,
        terms=terms,
        assessments=assessments,
        subjects=subjects
    )














def validate_excel_data(df):
    processed_data = []
    errors = []
    existing_reg_nos = []
    seen_keys = set()

    # Normalize column names
    df.columns = df.columns.str.lower()

    # Required columns
    required_columns = {'reg_no', 'class', 'study_year', 'term', 'assessment', 'subject', 'mark'}
    missing_columns = required_columns - set(df.columns)
    if missing_columns:
        raise ValueError(f"Missing required columns: {', '.join(missing_columns)}")

    # Get current user ID from session
    user_id = session.get('id')
    if not user_id:
        raise ValueError("Missing or invalid user session ID.")

    try:
        with get_db_connection() as connection:
            cursor = connection.cursor()

            # Get mapping dictionaries from DB
            mapping_queries = {
                'classes': "SELECT class_name, class_id FROM classes",
                'study_year': "SELECT year_name, year_id FROM study_year",
                'terms': "SELECT term_name, term_id FROM terms",
                'assessment': "SELECT assessment_name, assessment_id FROM assessment",
                'subjects': "SELECT subject_name, subject_id FROM subjects",
            }

            mappings = {}
            for key, query in mapping_queries.items():
                cursor.execute(query)
                mappings[key] = {row[0].strip(): row[1] for row in cursor.fetchall()}

            # Load existing score keys
            cursor.execute("""
                SELECT reg_no, class_id, year_id, term_id, assessment_id, subject_id FROM scores
            """)
            existing_score_keys = {
                (row[0], row[1], row[2], row[3], row[4], row[5]) for row in cursor.fetchall()
            }

    except Exception as e:
        errors.append(f"Database error: {str(e)}")
        return processed_data, errors, existing_reg_nos, []

    for index, row in df.iterrows():
        if row.isnull().all():
            continue

        reg_no = str(row.get('reg_no')).strip()
        class_name = str(row.get('class')).strip()
        year_name = str(row.get('study_year')).strip()
        term_name = str(row.get('term')).strip()
        assessment_name = str(row.get('assessment')).strip()
        subject_name = str(row.get('subject')).strip()
        mark = row.get('mark')
        notes = row.get('notes') if 'notes' in row else None

        # Check for missing values (including mark)
        if pd.isna(mark):
            errors.append(f"Row {index + 2}: 'Mark' value is missing.")
            continue

        if not all([reg_no, class_name, year_name, term_name, assessment_name, subject_name]):
            errors.append(f"Row {index + 2}: Missing required fields.")
            continue

        # Convert to IDs
        class_id = mappings['classes'].get(class_name)
        year_id = mappings['study_year'].get(year_name)
        term_id = mappings['terms'].get(term_name)
        assessment_id = mappings['assessment'].get(assessment_name)
        subject_id = mappings['subjects'].get(subject_name)

        row_errors = []
        if not class_id:
            row_errors.append(f"Class '{class_name}' not found.")
        if not year_id:
            row_errors.append(f"Year '{year_name}' not found.")
        if not term_id:
            row_errors.append(f"Term '{term_name}' not found.")
        if not assessment_id:
            row_errors.append(f"Assessment '{assessment_name}' not found.")
        if not subject_id:
            row_errors.append(f"Subject '{subject_name}' not found.")

        if row_errors:
            errors.append(f"Row {index + 2}: " + "; ".join(row_errors))
            continue

        key = (reg_no, class_id, year_id, term_id, assessment_id, subject_id)
        if key in existing_score_keys:
            existing_reg_nos.append(reg_no)
            continue

        data = {
            'user_id': user_id,
            'reg_no': reg_no,
            'class_id': class_id,
            'year_id': year_id,
            'term_id': term_id,
            'assessment_id': assessment_id,
            'subject_id': subject_id,
            'Mark': mark,
            'notes': None if pd.isna(notes) else notes
        }

        processed_data.append(data)

    if processed_data:
        try:
            insert_scores_into_database(processed_data)
        except Exception as e:
            errors.append(f"Failed to insert data: {str(e)}")

    return processed_data, errors, existing_reg_nos, []








def insert_scores_into_database(processed_data):
    if not processed_data:
        print("⚠️ No score data to insert.")
        return

    if not isinstance(processed_data, list) or not all(isinstance(item, dict) for item in processed_data):
        raise ValueError("❌ processed_data must be a list of dictionaries.")

    for idx, data in enumerate(processed_data):
        if 'Mark' not in data or pd.isna(data['Mark']):
            raise ValueError(f"❌ 'Mark' is missing or null in record at index {idx}: {data}")
        data['notes'] = None if pd.isna(data.get('notes')) else data.get('notes')

    insert_query = """
        INSERT INTO scores (
            user_id, reg_no, class_id, term_id, year_id,
            assessment_id, subject_id, Mark, notes
        ) VALUES (
            %(user_id)s, %(reg_no)s, %(class_id)s, %(term_id)s, %(year_id)s,
            %(assessment_id)s, %(subject_id)s, %(Mark)s, %(notes)s
        )
    """

    check_existing_query = """
        SELECT COUNT(*) FROM scores
        WHERE reg_no = %(reg_no)s
        AND class_id = %(class_id)s
        AND year_id = %(year_id)s
        AND term_id = %(term_id)s
        AND assessment_id = %(assessment_id)s
        AND subject_id = %(subject_id)s
    """

    try:
        with get_db_connection() as connection:
            with connection.cursor() as cursor:
                inserted_count = 0

                for data in processed_data:
                    cursor.execute(check_existing_query, {
                        'reg_no': data['reg_no'],
                        'class_id': data['class_id'],
                        'year_id': data['year_id'],
                        'term_id': data['term_id'],
                        'assessment_id': data['assessment_id'],
                        'subject_id': data['subject_id']
                    })
                    existing_count = cursor.fetchone()[0]

                    if existing_count == 0:
                        cursor.execute(insert_query, data)
                        inserted_count += 1

                connection.commit()
                print(f"✅ Successfully inserted {inserted_count} record(s).")
    except Exception as e:
        print(f"❌ Error inserting data: {e}")
        raise










  
@blueprint.route('/delete_result/<int:results_id>')
def delete_result(results_id):
    """Deletes a results from the database."""
    connection = get_db_connection()
    cursor = connection.cursor()

    try:
        # Delete the results with the specified ID
        cursor.execute('DELETE FROM results WHERE result_id = %s', (results_id,))
        connection.commit()
        flash("results deleted successfully.", "success")
    except Exception as e:
        flash(f"Error: {str(e)}", "danger")
    finally:
        cursor.close()
        connection.close()

    return redirect(url_for('results_blueprint.results'))




@blueprint.route('/<template>')
def route_template(template):

    try:

        if not template.endswith('.html'):
            template += '.html'

        # Detect the current page
        segment = get_segment(request)

        # Serve the file (if exists) from app/templates/home/FILE.html
        return render_template("results/" + template, segment=segment)

    except TemplateNotFound:
        return render_template('home/page-404.html'), 404

    except:
        return render_template('home/page-500.html'), 500


# Helper - Extract current page name from request
def get_segment(request):

    try:

        segment = request.path.split('/')[-1]

        if segment == '':
            segment = 'results'

        return segment

    except:
        return None
