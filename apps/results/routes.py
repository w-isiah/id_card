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


@blueprint.route('/results')
def results():
    """Fetch and filter results by Reg No, Name, Class, and Study Year."""
    connection = get_db_connection()
    cursor = connection.cursor(dictionary=True)

    # Fetch all study years and classes for dropdowns
    cursor.execute('SELECT year_id, year_name AS study_year FROM study_year ORDER BY year_name')
    study_years = cursor.fetchall()

    cursor.execute('SELECT class_id, class_name FROM classes ORDER BY class_name')
    class_list = cursor.fetchall()

    # Get search filters from the request
    reg_no = request.args.get('reg_no', '').strip()
    name = request.args.get('name', '').strip()
    class_id = request.args.get('class_name', '').strip()
    study_year_id = request.args.get('study_year', '').strip()

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

    results = []

    # Only run the query if filters are applied
    if filters:
        query = '''
            SELECT 
                p.result_id,
                p.reg_no,
                CONCAT(p.first_name, ' ', p.last_name) AS full_name,
                p.gender,
                p.image,
                p.date_of_birth,
                sy.year_name AS study_year,
                c.class_name
            FROM results p
            JOIN study_year sy ON p.year_id = sy.year_id
            JOIN classes c ON p.class_id = c.class_id
            WHERE ''' + " AND ".join(filters) + " ORDER BY p.last_name"

        cursor.execute(query, params)
        results = cursor.fetchall()

    cursor.close()
    connection.close()

    return render_template(
        'results/results.html',
        results=results,
        segment='results',
        class_list=class_list,
        study_years=study_years,
        filters={
            'reg_no': reg_no,
            'name': name,
            'class_name': class_id,
            'study_year': study_year_id
        }
    )






# Route to add a new result
@blueprint.route('/add_result', methods=['GET', 'POST'])
def add_result():
    connection = get_db_connection()
    cursor = connection.cursor(dictionary=True)
    cursor.execute('SELECT * FROM study_year ORDER BY year_name')
    study_years = cursor.fetchall()
    cursor.execute('SELECT * FROM classes ORDER BY class_name')
    classes = cursor.fetchall()

    if request.method == 'POST':
        # Retrieve form data
        reg_no = request.form.get('reg_no')  # You can generate or get this as needed
        first_name = request.form.get('first_name')
        other_name = request.form.get('other_name')
        last_name = request.form.get('last_name')
        date_of_birth = request.form.get('date_of_birth')
        gender = request.form.get('gender')
        class_name = request.form.get('class_name')
        admission_date = request.form.get('admission_date')
        study_year = request.form.get('study_year')
        
        address = request.form.get('address')
        emergency_contact = request.form.get('emergency_contact')
        medical_info = request.form.get('medical_info')
        special_needs = request.form.get('special_needs')
        attendance_record = request.form.get('attendance_record')
        academic_performance = request.form.get('academic_performance')
        notes = request.form.get('notes')

        # Handle image upload
        image_file = request.files.get('image')
        image_filename = None  # Default if no image is uploaded

        if image_file and allowed_file(image_file.filename):
            filename = secure_filename(image_file.filename)
            #image_filename = f"{reg_no}_{filename}"  # Rename with reg_no to avoid conflicts
            image_filename = filename
            
            # Ensure the directory exists before saving the file
            image_folder = os.path.join(current_app.config['UPLOAD_FOLDER'])
            if not os.path.exists(image_folder):
                os.makedirs(image_folder)  # Create the folder if it doesn't exist

            image_path = os.path.join(image_folder, image_filename)
            image_file.save(image_path)  # Save image

        # Insert new result into the database
        cursor.execute('''INSERT INTO results 
            (reg_no, first_name, other_name, last_name, image, date_of_birth, gender, class, admission_date, study_year, address, emergency_contact, medical_info, special_needs, attendance_record, academic_performance, notes) 
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)''',
            (reg_no, first_name, other_name, last_name, image_filename, date_of_birth, gender, class_name, admission_date, study_year, address, emergency_contact, medical_info, special_needs, attendance_record, academic_performance, notes))
        
        connection.commit()
        flash("result successfully added!", "success")

    cursor.close()
    connection.close()

    return render_template('results/add_result.html',classes=classes, study_years=study_years,segment='add_result')







# Route to edit an existing result
@blueprint.route('/edit_result/<int:result_id>', methods=['GET', 'POST'])
def edit_result(result_id):
    # Connect to the database
    connection = get_db_connection()
    cursor = connection.cursor(dictionary=True)

    # Fetch the result data from the database
    cursor.execute('SELECT * FROM results WHERE result_id = %s', (result_id,))
    result = cursor.fetchone()

    cursor.execute('SELECT * FROM study_year ORDER BY year_name')
    study_years = cursor.fetchall()
    cursor.execute('SELECT * FROM classes ORDER BY class_name')
    classes = cursor.fetchall()



    if not result:
        flash("result not found!")
        return redirect(url_for('results_blueprint.results'))  # Redirect to results list page or home

    if request.method == 'POST':
        # Get the form data
        first_name = request.form.get('first_name')
        other_name = request.form.get('other_name')
        last_name = request.form.get('last_name')
        date_of_birth = request.form.get('date_of_birth')
        gender = request.form.get('gender')
        class_name = request.form.get('class_name')  # Renamed 'class' to 'class_name' to avoid conflict with Python keyword
        study_year = request.form.get('study_year')
      
        address = request.form.get('address')
        emergency_contact = request.form.get('emergency_contact')
        medical_info = request.form.get('medical_info')
        special_needs = request.form.get('special_needs')
        attendance_record = request.form.get('attendance_record')
        academic_performance = request.form.get('academic_performance')
        notes = request.form.get('notes')

        # Handle image upload
        image_filename = result['image']  # Default to existing image if no new one is uploaded
        image_file = request.files.get('image')

        if image_file and allowed_file(image_file.filename):
            filename = secure_filename(image_file.filename)
            image_filename = f"{result_id}_{filename}"  # Rename with result ID to avoid conflicts
            
            # Ensure the directory exists before saving the file
            image_folder = os.path.join(current_app.config['UPLOAD_FOLDER'])
            if not os.path.exists(image_folder):
                os.makedirs(image_folder)  # Create the folder if it doesn't exist

            image_path = os.path.join(image_folder, image_filename)
            image_file.save(image_path)  # Save new image

        # Update the result data in the database
        cursor.execute(''' 
            UPDATE results
            SET first_name = %s, other_name = %s, last_name = %s, date_of_birth = %s, gender = %s,
                class_id = %s, year_id = %s,  address = %s, emergency_contact = %s,
                medical_info = %s, special_needs = %s, attendance_record = %s, academic_performance = %s,
                notes = %s, image = %s
            WHERE result_id = %s
        ''', (first_name, other_name, last_name, date_of_birth, gender, class_name, study_year, 
              address, emergency_contact, medical_info, special_needs, attendance_record, academic_performance,
              notes, image_filename, result_id))

        # Commit the transaction
        connection.commit()

        flash("result updated successfully!", "success")
        return redirect(url_for('results_blueprint.results'))  # Redirect to result list or home

    cursor.close()
    connection.close()

    return render_template('results/edit_result.html',classes=classes, study_years=study_years, result=result)











@blueprint.route('/pdownload_template', methods=['GET'])
def pdownload_template():
    class_id = request.args.get("class_name")
    year_id = request.args.get("study_year")

    if not class_id or not year_id:
        flash("Please select both Class and Study Year to download a template.", "warning")
        return redirect(url_for('results_blueprint.pupload_excel'))  # Redirect back to upload page to select filters

    # Connect to the database
    conn = get_db_connection()
    if not conn:
        return "Database connection failed", 500

    cursor = conn.cursor(dictionary=True)
    try:
        # Fetch names from IDs
        cursor.execute("SELECT class_name FROM classes WHERE class_id = %s", (class_id,))
        class_row = cursor.fetchone()
        class_name = class_row["class_name"] if class_row else "Unknown"

        cursor.execute("SELECT year_name FROM study_year WHERE year_id = %s", (year_id,))
        year_row = cursor.fetchone()
        study_year = year_row["year_name"] if year_row else "Unknown"

        cursor.execute("SELECT assessment_name FROM assessment ORDER BY assessment_name")
        assessments = [row["assessment_name"] for row in cursor.fetchall()]
    finally:
        cursor.close()
        conn.close()

    # Create Excel workbook
    wb = openpyxl.Workbook()
    ws_template = wb.active
    ws_template.title = "Results Template"

    headers = ["reg_no", "first_name", "other_name", "last_name", "class", "study_year", "assessment", "notes"]
    ws_template.append(headers)

    # Fill default class and year values in the first 99 rows
    for row in range(2, 101):
        ws_template[f"E{row}"] = class_name
        ws_template[f"F{row}"] = study_year

    # Add dropdowns for assessment only
    ws_dropdown = wb.create_sheet("drop_down_data")
    ws_dropdown.append(["assessments"])
    for a in assessments:
        ws_dropdown.append([a])
    wb.create_named_range("Assessments", ws_dropdown, f"$A$2:$A${len(assessments)+1}")

    dv = openpyxl.worksheet.datavalidation.DataValidation(type="list", formula1="=Assessments", allow_blank=True)
    ws_template.add_data_validation(dv)
    dv.add("G2:G100")

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
    # Load dropdown data
    conn = get_db_connection()
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

        # Save file securely
        filename = f"{uuid.uuid4()}_{secure_filename(file.filename)}"
        file_path = os.path.join(current_app.config['UPLOAD_FOLDER'], filename)
        file.save(file_path)

        try:
            # Read and process the Excel file
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

            # Insert valid records into the database
            insert_into_database(processed_data)
            flash(f"{len(processed_data)} record(s) uploaded successfully!", 'success')

        except pd.errors.EmptyDataError:
            flash('Uploaded file is empty.', 'danger')
        except Exception as e:
            flash(f'Error processing the file: {str(e)}', 'danger')
        finally:
            if os.path.exists(file_path):
                os.remove(file_path)

        return redirect(url_for('pupload_excel'))

    return render_template('results/upload_excel.html',
                           study_years=study_years,
                           class_list=class_list)








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
