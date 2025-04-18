from apps.pupils import blueprint
from flask import render_template, request, redirect, url_for, flash, current_app
import mysql.connector
from werkzeug.utils import secure_filename
from mysql.connector import Error
from datetime import datetime
import os
import random
import logging
import re  # <-- Add this line
from apps import get_db_connection
from jinja2 import TemplateNotFound



# Access the upload folder from the current Flask app configuration
def allowed_file(filename):
    """Check if the uploaded file has a valid extension."""
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in current_app.config['ALLOWED_EXTENSIONS']


@blueprint.route('/pupils')
def pupils():
    """Fetch and filter pupils by Reg No, Name, Class, and Study Year."""
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
    class_id = request.args.get('class_name', '').strip()  # using class_id in filter
    study_year_id = request.args.get('study_year', '').strip()  # using year_id in filter

    # Build SQL query dynamically
    query = '''
        SELECT 
            p.pupil_id,
            p.reg_no,
            CONCAT(p.first_name, ' ', p.last_name) AS full_name,
            p.gender,
            p.image,
            p.date_of_birth,
            sy.year_name AS study_year,
            c.class_name
        FROM pupils p
        JOIN study_year sy ON p.year_id = sy.year_id
        JOIN classes c ON p.class_id = c.class_id
        WHERE 1 = 1
    '''

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

    if filters:
        query += " AND " + " AND ".join(filters)

    query += " ORDER BY p.last_name"

    cursor.execute(query, params)
    pupils = cursor.fetchall()

    cursor.close()
    connection.close()

    return render_template(
        'pupils/pupils.html',
        pupils=pupils,
        segment='pupils',
        class_list=class_list,
        study_years=study_years,
        filters={
            'reg_no': reg_no,
            'name': name,
            'class_name': class_id,
            'study_year': study_year_id
        }
    )






# Route to add a new pupil
@blueprint.route('/add_pupil', methods=['GET', 'POST'])
def add_pupil():
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

        # Insert new pupil into the database
        cursor.execute('''INSERT INTO pupils 
            (reg_no, first_name, other_name, last_name, image, date_of_birth, gender, class, admission_date, study_year, address, emergency_contact, medical_info, special_needs, attendance_record, academic_performance, notes) 
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)''',
            (reg_no, first_name, other_name, last_name, image_filename, date_of_birth, gender, class_name, admission_date, study_year, address, emergency_contact, medical_info, special_needs, attendance_record, academic_performance, notes))
        
        connection.commit()
        flash("Pupil successfully added!", "success")

    cursor.close()
    connection.close()

    return render_template('pupils/add_pupil.html',classes=classes, study_years=study_years,segment='add_pupil')







# Route to edit an existing pupil
@blueprint.route('/edit_pupil/<int:pupil_id>', methods=['GET', 'POST'])
def edit_pupil(pupil_id):
    # Connect to the database
    connection = get_db_connection()
    cursor = connection.cursor(dictionary=True)

    # Fetch the pupil data from the database
    cursor.execute('SELECT * FROM pupils WHERE pupil_id = %s', (pupil_id,))
    pupil = cursor.fetchone()

    cursor.execute('SELECT * FROM study_year ORDER BY year_name')
    study_years = cursor.fetchall()
    cursor.execute('SELECT * FROM classes ORDER BY class_name')
    classes = cursor.fetchall()



    if not pupil:
        flash("Pupil not found!")
        return redirect(url_for('pupils_blueprint.pupils'))  # Redirect to pupils list page or home

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
        image_filename = pupil['image']  # Default to existing image if no new one is uploaded
        image_file = request.files.get('image')

        if image_file and allowed_file(image_file.filename):
            filename = secure_filename(image_file.filename)
            image_filename = f"{pupil_id}_{filename}"  # Rename with pupil ID to avoid conflicts
            
            # Ensure the directory exists before saving the file
            image_folder = os.path.join(current_app.config['UPLOAD_FOLDER'])
            if not os.path.exists(image_folder):
                os.makedirs(image_folder)  # Create the folder if it doesn't exist

            image_path = os.path.join(image_folder, image_filename)
            image_file.save(image_path)  # Save new image

        # Update the pupil data in the database
        cursor.execute(''' 
            UPDATE pupils
            SET first_name = %s, other_name = %s, last_name = %s, date_of_birth = %s, gender = %s,
                class_id = %s, year_id = %s,  address = %s, emergency_contact = %s,
                medical_info = %s, special_needs = %s, attendance_record = %s, academic_performance = %s,
                notes = %s, image = %s
            WHERE pupil_id = %s
        ''', (first_name, other_name, last_name, date_of_birth, gender, class_name, study_year, 
              address, emergency_contact, medical_info, special_needs, attendance_record, academic_performance,
              notes, image_filename, pupil_id))

        # Commit the transaction
        connection.commit()

        flash("Pupil updated successfully!", "success")
        return redirect(url_for('pupils_blueprint.pupils'))  # Redirect to pupil list or home

    cursor.close()
    connection.close()

    return render_template('pupils/edit_pupil.html',classes=classes, study_years=study_years, pupil=pupil)









@blueprint.route('/delete_pupil/<int:pupils_id>')
def delete_pupil(pupils_id):
    """Deletes a pupils from the database."""
    connection = get_db_connection()
    cursor = connection.cursor()

    try:
        # Delete the pupils with the specified ID
        cursor.execute('DELETE FROM pupils WHERE pupil_id = %s', (pupils_id,))
        connection.commit()
        flash("pupils deleted successfully.", "success")
    except Exception as e:
        flash(f"Error: {str(e)}", "danger")
    finally:
        cursor.close()
        connection.close()

    return redirect(url_for('pupils_blueprint.pupils'))




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
