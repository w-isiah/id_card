from apps.dorms import blueprint
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



@blueprint.route('/dorms')
def dorms():
    """Fetches all dorms and renders the manage dorms page."""
    connection = get_db_connection()
    cursor = connection.cursor(dictionary=True)

    # Fetch all dorms from the database
    cursor.execute('SELECT * FROM dormitories')
    dorms = cursor.fetchall()

    # Close the cursor and connection
    cursor.close()
    connection.close()

    return render_template('dorms/dorms.html', dorms=dorms,segment='dorms')




@blueprint.route('/add_dorms', methods=['GET', 'POST'])
def add_dorms():
    """Handles the adding of a new dormitory."""
    if request.method == 'POST':
        name = request.form.get('name')
        gender = request.form.get('gender')
        capacity = request.form.get('capacity')
        description = request.form.get('description')
        dorm_master_id = request.form.get('dorm_master_id')

        # Validate required fields
        if not name or not gender or not capacity:
            flash("Please fill out all required fields!", "warning")
        elif not re.match(r'^\d+$', capacity):
            flash('Capacity must be a valid number!', "danger")
        elif dorm_master_id and not re.match(r'^\d+$', dorm_master_id):
            flash('Dorm Master ID must be numeric if provided!', "danger")
        else:
            connection = get_db_connection()
            cursor = connection.cursor(dictionary=True)

            try:
                # Check if dormitory with same name and gender already exists
                cursor.execute('SELECT * FROM dormitories WHERE name = %s AND gender = %s', (name, gender))
                existing_dorm = cursor.fetchone()

                if existing_dorm:
                    flash("Dormitory already exists with that name and gender!", "warning")
                else:
                    # Insert new dormitory
                    cursor.execute('''
                        INSERT INTO dormitories (name, gender, capacity, description, dorm_master_id)
                        VALUES (%s, %s, %s, %s, %s)
                    ''', (name, gender, int(capacity), description, dorm_master_id if dorm_master_id else None))

                    connection.commit()
                    flash("Dormitory successfully added!", "success")

            except mysql.connector.Error as err:
                flash(f"Database error: {err}", "danger")
            finally:
                cursor.close()
                connection.close()

    return render_template('dorms/add_dorms.html', segment='add_dorms')







@blueprint.route('/edit_dorms/<int:dorm_id>', methods=['GET', 'POST'])
def edit_dorms(dorm_id):
    """Handles editing an existing dormitory record."""
    if request.method == 'POST':
        # Get form data
        name = request.form.get('name', '').strip()
        gender = request.form.get('gender', '').strip()
        capacity = request.form.get('capacity', '').strip()
        description = request.form.get('description', '').strip()
        dorm_master_id = request.form.get('dorm_master_id', '').strip() or None

        # Validate required fields
        if not name or not gender or not capacity:
            flash("Please fill out all required fields!", "warning")
            return redirect(url_for('dorms_blueprint.edit_dorms', dorm_id=dorm_id))

        # Validate numeric fields
        if not capacity.isdigit():
            flash("Capacity must be a valid number.", "danger")
            return redirect(url_for('dorms_blueprint.edit_dorms', dorm_id=dorm_id))

        try:
            connection = get_db_connection()
            cursor = connection.cursor(dictionary=True)

            # Check for duplicate dorm name/gender (excluding current dorm)
            cursor.execute("""
                SELECT * FROM dormitories
                WHERE name = %s AND gender = %s AND dormitory_id != %s
            """, (name, gender, dorm_id))
            if cursor.fetchone():
                flash("A dormitory with the same name and gender already exists!", "warning")
                return redirect(url_for('dorms_blueprint.edit_dorms', dorm_id=dorm_id))

            # Update dormitory
            cursor.execute("""
                UPDATE dormitories
                SET name = %s, gender = %s, capacity = %s, description = %s, dorm_master_id = %s
                WHERE dormitory_id = %s
            """, (name, gender, int(capacity), description or None, dorm_master_id, dorm_id))
            connection.commit()
            flash("Dormitory updated successfully!", "success")

        except Exception as e:
            flash(f"An error occurred while updating the dormitory: {e}", "danger")

        finally:
            cursor.close()
            connection.close()

        return redirect(url_for('dorms_blueprint.dorms'))

    else:  # GET request
        try:
            connection = get_db_connection()
            cursor = connection.cursor(dictionary=True)

            cursor.execute("SELECT * FROM dormitories WHERE dormitory_id = %s", (dorm_id,))
            dorm = cursor.fetchone()

        except Exception as e:
            flash(f"Failed to retrieve dormitory: {e}", "danger")
            dorm = None

        finally:
            cursor.close()
            connection.close()

        if dorm:
            return render_template('dorms/edit_dorms.html', dorm=dorm, segment='dorms')
        else:
            flash("Dormitory not found.", "danger")
            return redirect(url_for('dorms_blueprint.dorms'))







@blueprint.route('/delete_dorms/<int:dormitory_id>')
def delete_dorms(dormitory_id):
    """Deletes a dormitory record from the database."""
    try:
        connection = get_db_connection()
        cursor = connection.cursor()

        # Check if the dormitory exists before deletion
        cursor.execute("SELECT * FROM dormitories WHERE dormitory_id = %s", (dormitory_id,))
        dorm = cursor.fetchone()

        if not dorm:
            flash("Dormitory not found.", "warning")
        else:
            cursor.execute("DELETE FROM dormitories WHERE dormitory_id = %s", (dormitory_id,))
            connection.commit()
            flash("Dormitory deleted successfully.", "success")

    except Exception as e:
        flash(f"An error occurred while deleting the dormitory: {e}", "danger")

    finally:
        if cursor: cursor.close()
        if connection: connection.close()

    return redirect(url_for('dorms_blueprint.dorms'))
   





@blueprint.route('/<template>')
def route_template(template):

    try:

        if not template.endswith('.html'):
            template += '.html'

        # Detect the current page
        segment = get_segment(request)

        # Serve the file (if exists) from app/templates/home/FILE.html
        return render_template("dorms/" + template, segment=segment)

    except TemplateNotFound:
        return render_template('home/page-404.html'), 404

    except:
        return render_template('home/page-500.html'), 500


# Helper - Extract current page name from request
def get_segment(request):

    try:

        segment = request.path.split('/')[-1]

        if segment == '':
            segment = 'dorms'

        return segment

    except:
        return None
