from apps.classes import blueprint
from flask import render_template, request, redirect, url_for, flash, session
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



@blueprint.route('/classes')
def classes():
    """Fetches all classes and renders the manage classes page."""
    connection = get_db_connection()
    cursor = connection.cursor(dictionary=True)

    # Fetch all classes from the database
    cursor.execute('SELECT * FROM classes')
    classes = cursor.fetchall()

    # Close the cursor and connection
    cursor.close()
    connection.close()

    return render_template('classes/classes.html', classes=classes,segment='classes')




@blueprint.route('/add_classes', methods=['GET', 'POST'])
def add_classes():
    """Handles the adding of a new class."""
    if request.method == 'POST':
        class_name = request.form.get('class_name')
        year = request.form.get('year')
        teacher_in_charge = request.form.get('teacher_in_charge')
        room_number = request.form.get('room_number')

        # Validate input
        if not class_name or not year:
            flash("Please fill out all required fields!", "warning")
        #elif not re.match(r'^[A-Za-z0-9_ ]+$', class_name):
        #    flash('Class name must contain only letters, numbers, and spaces!', "danger")
        elif not re.match(r'^[0-9]+$', year):  # Ensuring year is numeric (you can modify the pattern as needed)
            flash('Year must be a valid number!', "danger")
        else:
            connection = get_db_connection()
            cursor = connection.cursor(dictionary=True)

            try:
                # Check if the class already exists
                cursor.execute('SELECT * FROM classes WHERE class_name = %s AND year = %s', (class_name, year))
                existing_class = cursor.fetchone()

                if existing_class:
                    flash("Class already exists for the given year!", "warning")
                else:
                    # Insert the new class into the database
                    cursor.execute('''
                        INSERT INTO classes (class_name, year, teacher_in_charge, room_number)
                        VALUES (%s, %s, %s, %s)
                    ''', (class_name, year, teacher_in_charge, room_number))
                    connection.commit()
                    flash("Class successfully added!", "success")

            except mysql.connector.Error as err:
                flash(f"Error: {err}", "danger")
            finally:
                cursor.close()
                connection.close()

    return render_template('classes/add_classes.html', segment='add_classes')







@blueprint.route('/edit_classes/<int:class_id>', methods=['GET', 'POST'])
def edit_classes(class_id):
    """Handles editing an existing class."""
    if request.method == 'POST':
        # Retrieve the form data
        class_name = request.form['class_name']
        year = request.form['year']
        teacher_in_charge = request.form['teacher_in_charge']
        room_number = request.form['room_number']

        # Validate the input
        if not class_name or not year:
            flash("Please fill out all required fields!", "warning")
            return redirect(url_for('classes_blueprint.edit_classes', class_id=class_id))
        
        #if not re.match(r'^[A-Za-z0-9_ ]+$', class_name):
        #    flash("Class name must contain only letters, numbers, and spaces!", "danger")
        #    return redirect(url_for('classes_blueprint.edit_classes', class_id=class_id))

        if not re.match(r'^[0-9]+$', year):
            flash("Year must be a valid number!", "danger")
            return redirect(url_for('classes_blueprint.edit_classes', class_id=class_id))

        try:
            connection = get_db_connection()
            cursor = connection.cursor()

            # Check if the class name already exists in the database for the same year
            cursor.execute("""
                SELECT * FROM classes 
                WHERE class_name = %s AND year = %s AND class_id != %s
            """, (class_name, year, class_id))
            existing_class = cursor.fetchone()

            if existing_class:
                flash("A class with the same name already exists for this year!", "warning")
                return redirect(url_for('classes_blueprint.edit_classes', class_id=class_id))

            # Update the class details in the database
            cursor.execute("""
                UPDATE classes
                SET class_name = %s, year = %s, teacher_in_charge = %s, room_number = %s
                WHERE class_id = %s
            """, (class_name, year, teacher_in_charge, room_number, class_id))
            connection.commit()

            flash("Class updated successfully!", "success")

        except Exception as e:
            flash(f"Error: {str(e)}", "danger")
        finally:
            cursor.close()
            connection.close()

        return redirect(url_for('classes_blueprint.classes'))

    elif request.method == 'GET':
        # Retrieve the class to pre-fill the form
        connection = get_db_connection()
        cursor = connection.cursor(dictionary=True)
        cursor.execute("SELECT * FROM classes WHERE class_id = %s", (class_id,))
        class_data = cursor.fetchone()
        cursor.close()
        connection.close()

        if class_data:
            return render_template('classes/edit_classes.html', classes=class_data, segment='classes')
        else:
            flash("Class not found.", "danger")
            return redirect(url_for('classes_blueprint.classes'))







@blueprint.route('/delete_classes/<int:class_id>')
def delete_classes(class_id):
    """Deletes a classes from the database."""
    connection = get_db_connection()
    cursor = connection.cursor()

    try:
        # Delete the classes with the specified ID
        cursor.execute('DELETE FROM classes WHERE class_id = %s', (class_id,))
        connection.commit()
        flash("class deleted successfully.", "success")
    except Exception as e:
        flash(f"Error: {str(e)}", "danger")
    finally:
        cursor.close()
        connection.close()

    return redirect(url_for('classes_blueprint.classes'))




@blueprint.route('/<template>')
def route_template(template):

    try:

        if not template.endswith('.html'):
            template += '.html'

        # Detect the current page
        segment = get_segment(request)

        # Serve the file (if exists) from app/templates/home/FILE.html
        return render_template("classes/" + template, segment=segment)

    except TemplateNotFound:
        return render_template('home/page-404.html'), 404

    except:
        return render_template('home/page-500.html'), 500


# Helper - Extract current page name from request
def get_segment(request):

    try:

        segment = request.path.split('/')[-1]

        if segment == '':
            segment = 'classes'

        return segment

    except:
        return None
