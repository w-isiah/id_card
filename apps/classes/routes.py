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
    """Handles the adding of a new classes."""
    if request.method == 'POST':
        name = request.form.get('name')

        # Validate input
        if not name:
            flash("Please fill out the form!", "warning")
        elif not re.match(r'^[A-Za-z0-9_ ]+$', name):

            flash('classes name must contain only letters and numbers!', "danger")
        else:
            connection = get_db_connection()
            cursor = connection.cursor(dictionary=True)

            try:
                # Check if the classes already exists
                cursor.execute('SELECT * FROM classes WHERE name = %s', (name,))
                existing_classes = cursor.fetchone()

                if existing_classes:
                    flash("classes already exists!", "warning")
                else:
                    # Insert the new classes into the database
                    cursor.execute('INSERT INTO classes (name) VALUES (%s)', (name,))
                    connection.commit()
                    flash("classes successfully added!", "success")

            except mysql.connector.Error as err:
                flash(f"Error: {err}", "danger")
            finally:
                cursor.close()
                connection.close()

    return render_template('classes/add_classes.html',segment='add_classes')


@blueprint.route('/edit_classes/<int:classes_id>', methods=['GET', 'POST'])
def edit_classes(classes_id):
    """Handles editing an existing classes."""
    if request.method == 'POST':
        name = request.form['name']

        try:
            connection = get_db_connection()
            cursor = connection.cursor()

            # Update classes in the database
            cursor.execute("""
                UPDATE classes
                SET name = %s
                WHERE classesID = %s
            """, (name, classes_id))
            connection.commit()

            flash("classes updated successfully!", "success")
        except Exception as e:
            flash(f"Error: {str(e)}", "danger")
        finally:
            cursor.close()
            connection.close()

        return redirect(url_for('classes_blueprint.classes'))

    elif request.method == 'GET':
        # Retrieve the classes to pre-fill the form
        connection = get_db_connection()
        cursor = connection.cursor(dictionary=True)
        cursor.execute("SELECT * FROM classes WHERE classesID = %s", (classes_id,))
        classes = cursor.fetchone()
        cursor.close()
        connection.close()

        if classes:
            return render_template('classes/edit_classes.html', classes=classes,segment='classes')
        else:
            flash("classes not found.", "danger")
            return redirect(url_for('classes_blueprint.classes'))


@blueprint.route('/delete_classes/<int:classes_id>')
def delete_classes(classes_id):
    """Deletes a classes from the database."""
    connection = get_db_connection()
    cursor = connection.cursor()

    try:
        # Delete the classes with the specified ID
        cursor.execute('DELETE FROM classes WHERE classesID = %s', (classes_id,))
        connection.commit()
        flash("classes deleted successfully.", "success")
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
