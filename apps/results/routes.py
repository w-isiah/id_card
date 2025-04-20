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
    class_id = request.args.get('class_id')
    year_id = request.args.get('year_id')

    if not class_id or not year_id:
        flash("Missing class or study year selection", "error")
        return redirect(url_for('results_blueprint.pupload_excel'))  # Redirect to a route where the message can be shown

    conn = get_db_connection()
    if not conn:
        flash("Database connection failed", "error")
        return redirect(url_for('results_blueprint.pupload_excel'))  # Redirect to appropriate route

    cursor = conn.cursor(dictionary=True)

    try:
        # Fetch helper
        def fetch_column_values(query, column_name):
            cursor.execute(query)
            return [row[column_name] for row in cursor.fetchall()]

        # Dropdown values
        classes = fetch_column_values("SELECT class_name FROM classes ORDER BY class_name", "class_name")
        study_years = fetch_column_values("SELECT year_name FROM study_year ORDER BY year_name", "year_name")
        assessments = fetch_column_values("SELECT assessment_name FROM assessment ORDER BY assessment_name", "assessment_name")
        terms = fetch_column_values("SELECT term_name FROM terms ORDER BY term_name", "term_name")

        # Get the class name based on class_id
        cursor.execute("""
            SELECT class_name FROM classes WHERE class_id = %s
        """, (class_id,))
        class_name = cursor.fetchone()
        if not class_name:
            flash("Class not found", "error")
            return redirect(url_for('results_blueprint.pupload_excel'))  # Redirect to appropriate route
        class_name = class_name['class_name']

        # Filtered pupils
        cursor.execute("""
            SELECT reg_no, first_name, other_name, last_name
            FROM pupils
            WHERE class_id = %s AND year_id = %s
            ORDER BY last_name
        """, (class_id, year_id))
        pupils = cursor.fetchall()

    finally:
        cursor.close()
        conn.close()

    # If no pupils are found, flash an error message
    if not pupils:
        flash("There are no students in this class for the selected year", "error")
        return redirect(url_for('results_blueprint.pupload_excel'))  # Redirect to appropriate route

    # Workbook setup
    wb = openpyxl.Workbook()
    ws1 = wb.active
    ws1.title = "Results Template"

    headers = [
        "reg_no", "first_name", "other_name", "last_name",
        "class", "term", "assessment", "study_year", "notes",
        "Math", "English", "Science", "Social Studies", "R.E", "Computer"
    ]
    ws1.append(headers)

    # Add pupil rows
    for pupil in pupils:
        ws1.append([
            pupil['reg_no'],
            pupil['first_name'],
            pupil['other_name'],
            pupil['last_name'],
            class_name,  # Fill the class name
            "", "", "", "", "", "", "", "", "", "", "", ""
        ])

    # Dropdown helper
    def safe_join(values):
        return ",".join(str(v).replace('"', "'") for v in values)[:255]  # Excel limit

    # Create second sheet for dropdown backup
    ws2 = wb.create_sheet("drop_down_data")
    ws2.append(["reg_nos", "classes", "study_years", "assessments", "terms"])
    ws2.append([
        ", ".join([p['reg_no'] for p in pupils]),
        ", ".join(classes),
        ", ".join(study_years),
        ", ".join(assessments),
        ", ".join(terms)
    ])

    # Data Validations
    dv_class = DataValidation(type="list", formula1=f'"{safe_join(classes)}"', allow_blank=True)
    dv_term = DataValidation(type="list", formula1=f'"{safe_join(terms)}"', allow_blank=True)
    dv_assessment = DataValidation(type="list", formula1=f'"{safe_join(assessments)}"', allow_blank=True)
    dv_year = DataValidation(type="list", formula1=f'"{safe_join(study_years)}"', allow_blank=True)

    ws1.add_data_validation(dv_class)
    ws1.add_data_validation(dv_term)
    ws1.add_data_validation(dv_assessment)
    ws1.add_data_validation(dv_year)

    row_count = len(pupils) + 1  # Include header row
    if row_count > 1:  # Only add data validation if there are pupils
        dv_class.add(f"E2:E{row_count}")
        dv_term.add(f"F2:F{row_count}")
        dv_assessment.add(f"G2:G{row_count}")
        dv_year.add(f"H2:H{row_count}")

    # Export to BytesIO
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
    # Fetch all study years and classes for dropdowns
    cursor = conn.cursor(dictionary=True)
    cursor.execute('SELECT year_id, year_name AS study_year FROM study_year ORDER BY year_name')
    study_years = cursor.fetchall()

    cursor.execute('SELECT class_id, class_name FROM classes ORDER BY class_name')
    class_list = cursor.fetchall()

    if request.method == 'POST':
        file = request.files.get('file')

        if not file or file.filename == '':
            flash('No file selected', 'danger')
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

            insert_into_database(processed_data)

            flash(f"{len(processed_data)} record(s) uploaded successfully!", 'success')
            return redirect(url_for('results_blueprint.upload_excel'))

        except pd.errors.EmptyDataError:
            flash('Uploaded file is empty.', 'danger')
        except Exception as e:
            flash(f'Error processing the file: {str(e)}', 'danger')

        return redirect(url_for('results_blueprint.upload_excel'))

    return render_template('results/upload_excel.html',study_years=study_years,class_list=class_list)






def validate_excel_data(df):
    processed_data = []
    errors = []
    existing_reg_nos = []
    duplicate_reg_nos = []
    seen_reg_nos = set()

    # Required columns
    required_columns = {'reg_no', 'class', 'study_year'}
    missing_columns = required_columns - set(df.columns)
    if missing_columns:
        raise ValueError(f"Missing required columns: {', '.join(missing_columns)}")

    with get_db_connection() as connection:
        cursor = connection.cursor()

        # Fetch mappings
        cursor.execute("SELECT `class_name`, `class_id` FROM `classes`")
        class_map = {str(row[0]).strip(): int(row[1]) for row in cursor.fetchall()}

        cursor.execute("SELECT `year_name`, `year_id` FROM `study_year`")
        year_map = {str(row[0]).strip(): int(row[1]) for row in cursor.fetchall()}

        cursor.execute("SELECT `reg_no` FROM `results`")
        existing_db_reg_nos = {str(row[0]).strip() for row in cursor.fetchall()}

        for index, row in df.iterrows():
            if row.isnull().all():
                continue  # Skip empty rows

            reg_no = str(row.get('reg_no')).strip() if pd.notna(row.get('reg_no')) else ''
            class_name = str(row.get('class')).strip() if pd.notna(row.get('class')) else ''
            year_name = str(row.get('study_year')).strip() if pd.notna(row.get('study_year')) else ''

            if not reg_no or not class_name or not year_name:
                errors.append(f"Row {index + 2}: Missing required fields (reg_no: '{reg_no}')")
                continue

            if reg_no in seen_reg_nos:
                duplicate_reg_nos.append(reg_no)
                continue
            seen_reg_nos.add(reg_no)

            if reg_no in existing_db_reg_nos:
                existing_reg_nos.append(reg_no)
                continue

            class_id = class_map.get(class_name)
            year_id = year_map.get(year_name)

            if not class_id:
                errors.append(f"Row {index + 2}: Class '{class_name}' not found.")
            if not year_id:
                errors.append(f"Row {index + 2}: Study year '{year_name}' not found.")

            if class_id and year_id:
                data = {
                    'reg_no': reg_no,
                    'first_name': row.get('first_name'),
                    'other_name': row.get('other_name'),
                    'last_name': row.get('last_name'),
                    'date_of_birth': row.get('date_of_birth'),
                    'gender': row.get('gender'),
                    'class_id': class_id,
                    'admission_date': row.get('admission_date'),
                    'year_id': year_id,
                    'address': row.get('address'),
                    'emergency_contact': row.get('emergency_contact'),
                    'medical_info': row.get('medical_info'),
                    'special_needs': row.get('special_needs'),
                    'attendance_record': row.get('attendance_record'),
                    'academic_performance': row.get('academic_performance'),
                    'notes': row.get('notes')
                }

                # Convert NaN to None
                for k, v in data.items():
                    if isinstance(v, float) and pd.isna(v):
                        data[k] = None

                processed_data.append(data)

    return processed_data, errors, existing_reg_nos, duplicate_reg_nos








def insert_into_database(processed_data):
    if not processed_data:
        print("No data to insert.")
        return

    insert_query = """
        INSERT INTO `results` (
            `reg_no`, `first_name`, `other_name`, `last_name`,
            `date_of_birth`, `gender`, `class_id`, `admission_date`,
            `year_id`, `address`, `emergency_contact`, `medical_info`,
            `special_needs`, `attendance_record`, `academic_performance`, `notes`
        ) VALUES (
            %(reg_no)s, %(first_name)s, %(other_name)s, %(last_name)s,
            %(date_of_birth)s, %(gender)s, %(class_id)s, %(admission_date)s,
            %(year_id)s, %(address)s, %(emergency_contact)s, %(medical_info)s,
            %(special_needs)s, %(attendance_record)s, %(academic_performance)s, %(notes)s
        )
    """

    try:
        with get_db_connection() as connection:
            cursor = connection.cursor()

            for data in processed_data:
                # Convert pandas Timestamp to date
                for date_field in ['date_of_birth', 'admission_date']:
                    if isinstance(data[date_field], pd.Timestamp):
                        data[date_field] = data[date_field].date()

                cursor.execute(insert_query, data)

            connection.commit()
            print(f"{len(processed_data)} records successfully inserted.")

    except Exception as e:
        print(" Error inserting data:", e)








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
