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

from apps.results import blueprint
from apps import get_db_connection

import numpy as np


# Access the upload folder from the current Flask app configuration
def allowed_file(filename):
    """Check if the uploaded file has a valid extension."""
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in current_app.config['ALLOWED_EXTENSIONS']

















@blueprint.route('/pdownload_template', methods=['GET'])
def pdownload_template():
    import openpyxl
    from openpyxl.worksheet.datavalidation import DataValidation
    from io import BytesIO

    class_id = request.args.get('class_id')
    year_id = request.args.get('year_id')
    term_id = request.args.get('term_id')

    if not all([class_id, year_id, term_id]):
        flash("Please select class, study year, and term.", "error")
        return redirect(url_for('results_blueprint.pupload_excel'))

    conn = get_db_connection()
    if not conn:
        flash("Failed to connect to the database.", "error")
        return redirect(url_for('results_blueprint.pupload_excel'))

    cursor = conn.cursor(dictionary=True)

    try:
        def fetch_column(query, column):
            cursor.execute(query)
            return [row[column] for row in cursor.fetchall()]

        # Dropdown values
        classes = fetch_column("SELECT class_name FROM classes ORDER BY class_name", "class_name")
        study_years = fetch_column("SELECT year_name FROM study_year ORDER BY year_name", "year_name")
        assessments = fetch_column("SELECT assessment_name FROM assessment ORDER BY assessment_name", "assessment_name")
        terms = fetch_column("SELECT term_name FROM terms ORDER BY term_name", "term_name")

        # Get class and term names
        cursor.execute("SELECT class_name FROM classes WHERE class_id = %s", (class_id,))
        class_row = cursor.fetchone()
        if not class_row:
            flash("Invalid class selected.", "error")
            return redirect(url_for('results_blueprint.pupload_excel'))
        class_name = class_row['class_name']

        cursor.execute("SELECT term_name FROM terms WHERE term_id = %s", (term_id,))
        term_row = cursor.fetchone()
        if not term_row:
            flash("Invalid term selected.", "error")
            return redirect(url_for('results_blueprint.pupload_excel'))
        term_name = term_row['term_name']

        # Get pupils in selected class, year, term
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

    # === Excel Generation ===
    wb = openpyxl.Workbook()
    ws1 = wb.active
    ws1.title = "Results Template"

    # Define headers
    headers = ["reg_no", "first_name", "other_name", "last_name", "class", "term", "assessment", "study_year", "notes",
               "Math", "English", "Science", "Social Studies", "R.E", "Computer"]
    ws1.append(headers)

    # Add student data
    for pupil in pupils:
        ws1.append([
            pupil['reg_no'],
            pupil['first_name'],
            pupil['other_name'],
            pupil['last_name'],
            class_name,
            term_name,
            "",  # assessment
            "",  # study_year
            "",  # notes
            "", "", "", "", "", ""  # subjects
        ])

    # Helper to safely format dropdown options
    def safe_join(values):
        return ",".join(str(v).replace('"', "'") for v in values)[:255]

    # Add second sheet with dropdown backup values
    ws2 = wb.create_sheet("drop_down_data")
    ws2.append(["reg_nos", "classes", "study_years", "assessments", "terms"])
    ws2.append([
        ", ".join([p['reg_no'] for p in pupils]),
        ", ".join(classes),
        ", ".join(study_years),
        ", ".join(assessments),
        ", ".join(terms)
    ])

    # Data validation setup
    dv_class = DataValidation(type="list", formula1=f'"{safe_join(classes)}"', allow_blank=True)
    dv_term = DataValidation(type="list", formula1=f'"{safe_join(terms)}"', allow_blank=True)
    dv_assessment = DataValidation(type="list", formula1=f'"{safe_join(assessments)}"', allow_blank=True)
    dv_year = DataValidation(type="list", formula1=f'"{safe_join(study_years)}"', allow_blank=True)

    for dv, col in zip([dv_class, dv_term, dv_assessment, dv_year], ['E', 'F', 'G', 'H']):
        ws1.add_data_validation(dv)
        dv.add(f"{col}2:{col}{len(pupils) + 1}")

    # Prepare file for download
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

    # Fetch all dropdown data
    cursor.execute('SELECT year_id, year_name AS study_year FROM study_year ORDER BY year_name')
    study_years = cursor.fetchall()

    cursor.execute('SELECT class_id, class_name FROM classes ORDER BY class_name')
    class_list = cursor.fetchall()

    cursor.execute('SELECT term_id, term_name FROM terms ORDER BY term_name')
    terms = cursor.fetchall()

    cursor.execute('SELECT assessment_id, assessment_name FROM assessment ORDER BY assessment_name')
    assessments = cursor.fetchall()

    if request.method == 'POST':
        file = request.files.get('file')

        if not file or file.filename == '':
            flash('No file selected.', 'danger')
            return redirect(request.url)

        if not allowed_file(file.filename):
            flash('Invalid file format. Please upload an Excel file.', 'danger')
            return redirect(request.url)

        filename = secure_filename(file.filename)
        file_path = os.path.join(current_app.config['UPLOAD_FOLDER'], filename)
        file.save(file_path)

        try:
            df = pd.read_excel(file_path)
            processed_data, errors, existing_reg_nos, duplicate_reg_nos = validate_excel_data(df)

            if duplicate_reg_nos:
                flash(f"Duplicate reg_no(s) found: {', '.join(duplicate_reg_nos)}", 'danger')
                return redirect(request.url)

            if errors:
                flash('Errors encountered:\n' + '\n'.join(errors), 'danger')
                return redirect(request.url)

            if existing_reg_nos:
                flash(f"Existing reg_no(s): {', '.join(existing_reg_nos)} (skipped).", 'warning')

            insert_scores_into_database(processed_data)

            flash(f"{len(processed_data)} score record(s) uploaded successfully!", 'success')
            return redirect(url_for('results_blueprint.pupload_excel'))

        except pd.errors.EmptyDataError:
            flash('Uploaded file is empty.', 'danger')
        except Exception as e:
            flash(f'Error processing the file: {str(e)}', 'danger')

        return redirect(url_for('results_blueprint.pupload_excel'))

    return render_template(
        'results/upload_excel.html',
        study_years=study_years,
        class_list=class_list,
        terms=terms,
        assessments=assessments
    )






def validate_excel_data(df):
    processed_data = []
    errors = []
    existing_reg_nos = []
    duplicate_reg_nos = []
    seen_reg_nos = set()

    required_columns = {'reg_no', 'class', 'study_year', 'term', 'assessment'}
    missing_columns = required_columns - set(df.columns)
    if missing_columns:
        raise ValueError(f"Missing required columns: {', '.join(missing_columns)}")

    with get_db_connection() as connection:
        cursor = connection.cursor()

        # Fetch mappings
        cursor.execute("SELECT class_name, class_id FROM classes")
        class_map = {row[0].strip(): row[1] for row in cursor.fetchall()}

        cursor.execute("SELECT year_name, year_id FROM study_year")
        year_map = {row[0].strip(): row[1] for row in cursor.fetchall()}

        cursor.execute("SELECT term_name, term_id FROM terms")
        term_map = {row[0].strip(): row[1] for row in cursor.fetchall()}

        cursor.execute("SELECT assessment_name, assessment_id FROM assessment")
        assessment_map = {row[0].strip(): row[1] for row in cursor.fetchall()}

        cursor.execute("SELECT reg_no, class_id, year_id, term_id, assessment_id FROM scores")
        existing_score_keys = {
            (row[0], row[1], row[2], row[3], row[4]) for row in cursor.fetchall()
        }

        for index, row in df.iterrows():
            if row.isnull().all():
                continue

            reg_no = str(row.get('reg_no')).strip()
            class_name = str(row.get('class')).strip()
            year_name = str(row.get('study_year')).strip()
            term_name = str(row.get('term')).strip()
            assessment_name = str(row.get('assessment')).strip()

            if not reg_no or not class_name or not year_name or not term_name or not assessment_name:
                errors.append(f"Row {index + 2}: Missing required fields.")
                continue

            if reg_no in seen_reg_nos:
                duplicate_reg_nos.append(reg_no)
                continue
            seen_reg_nos.add(reg_no)

            class_id = class_map.get(class_name)
            year_id = year_map.get(year_name)
            term_id = term_map.get(term_name)
            assessment_id = assessment_map.get(assessment_name)

            if not class_id:
                errors.append(f"Row {index + 2}: Class '{class_name}' not found.")
            if not year_id:
                errors.append(f"Row {index + 2}: Study year '{year_name}' not found.")
            if not term_id:
                errors.append(f"Row {index + 2}: Term '{term_name}' not found.")
            if not assessment_id:
                errors.append(f"Row {index + 2}: Assessment '{assessment_name}' not found.")

            if class_id and year_id and term_id and assessment_id:
                key = (reg_no, class_id, year_id, term_id, assessment_id)
                if key in existing_score_keys:
                    existing_reg_nos.append(reg_no)
                    continue

                data = {
                    'reg_no': reg_no,
                    'class_id': class_id,
                    'year_id': year_id,
                    'term_id': term_id,
                    'assessment_id': assessment_id,
                    'math': row.get('Math'),
                    'english': row.get('English'),
                    'science': row.get('Science'),
                    'social_studies': row.get('Social Studies'),
                    're': row.get('R.E'),
                    'computer': row.get('Computer'),
                    'notes': row.get('notes')
                }

                # Clean up NaN to None
                for k, v in data.items():
                    if pd.isna(v):
                        data[k] = None

                processed_data.append(data)

    return processed_data, errors, existing_reg_nos, duplicate_reg_nos








def insert_scores_into_database(processed_data):
    if not processed_data:
        print("No score data to insert.")
        return

    insert_query = """
        INSERT INTO `scores` (
            `reg_no`, `class_id`, `term_id`, `year_id`, `assessment_id`,
            `math`, `english`, `science`, `social_studies`, `re`, `computer`, `notes`
        ) VALUES (
            %(reg_no)s, %(class_id)s, %(term_id)s, %(year_id)s, %(assessment_id)s,
            %(math)s, %(english)s, %(science)s, %(social_studies)s, %(re)s, %(computer)s, %(notes)s
        )
    """

    try:
        with get_db_connection() as connection:
            cursor = connection.cursor()

            for data in processed_data:
                # Convert any NaNs to None (already handled earlier but double-check)
                for field in ['math', 'english', 'science', 'social_studies', 're', 'computer', 'notes']:
                    if isinstance(data.get(field), float) and pd.isna(data[field]):
                        data[field] = None

                cursor.execute(insert_query, data)

            connection.commit()
            print(f"{len(processed_data)} score record(s) inserted into database.")

    except Exception as e:
        print("❌ Error inserting score data:", e)








  
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
