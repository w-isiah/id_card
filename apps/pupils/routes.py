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
    """Fetches all pupils with their study year and class info, and renders the manage pupils page."""
    connection = get_db_connection()
    cursor = connection.cursor(dictionary=True)

    # Join pupils with year_id and class_id
    query = '''
        SELECT 
            p.pupil_id,
            p.reg_no,
            p.first_name,
            p.last_name,
            p.gender,
            p.image,
            p.date_of_birth,
            sy.year_name AS study_year,
            sy.level,
            c.class_name,
            c.teacher_in_charge,
            c.room_number
        FROM 
            pupils p
        JOIN 
            study_year sy ON p.year_id = sy.year_id  -- Updated column name
        JOIN 
            classes c ON p.class_id = c.class_id    -- Updated column name
        ORDER BY 
            p.last_name
    '''
    
    cursor.execute(query)
    pupils = cursor.fetchall()

    # Close the cursor and connection
    cursor.close()
    connection.close()

    return render_template('pupils/pupils.html', pupils=pupils, segment='pupils')




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
                class = %s, study_year = %s,  address = %s, emergency_contact = %s,
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

    return render_template('pupils/edit_pupil.html', pupil=pupil)









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
