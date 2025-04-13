from apps.gen_ids import blueprint
from flask import render_template, request, redirect, url_for, flash, session
from flask import Flask
import mysql.connector
from werkzeug.utils import secure_filename
from mysql.connector import Error
from datetime import datetime
import os
import random
import logging
from apps import get_db_connection


# Start of gen_id handling
@blueprint.route('/gen_ids')
def gen_ids():
    connection = get_db_connection()
    cursor = connection.cursor(dictionary=True)

    cursor.execute("""
        SELECT 
            -- Pupil Info
            p.pupil_id,
            p.reg_no,
            p.first_name AS pupil_first_name,
            p.other_name AS pupil_other_name,
            p.last_name AS pupil_last_name,
            p.gender,
            p.date_of_birth,
            p.class,
            p.study_year,
            p.image AS pupil_image,

            -- Father's Info
            f.first_name AS father_first_name,
            f.other_name AS father_other_name,
            f.last_name AS father_last_name,
            f.image AS father_image,
            f.sign_image AS father_sign,

            -- Mother's Info
            m.first_name AS mother_first_name,
            m.other_name AS mother_other_name,
            m.last_name AS mother_last_name,
            m.image AS mother_image,
            m.sign_image AS mother_sign,

            -- Guardian's Info
            g.first_name AS guardian_first_name,
            g.other_name AS guardian_other_name,
            g.last_name AS guardian_last_name,
            g.relationship,
            g.contact_number,
            g.image AS guardian_image,
            g.sign_image AS guardian_sign,

            -- Class Info
            c.class_name,
            c.year,
            c.teacher_in_charge,
            c.room_number

        FROM pupils p
        LEFT JOIN fathers f ON p.pupil_id = f.pupil_id
        LEFT JOIN mothers m ON p.pupil_id = m.pupil_id
        LEFT JOIN guardians g ON p.pupil_id = g.pupil_id
        LEFT JOIN classes c ON p.class = c.class_name
    """)

    gen_id = cursor.fetchall()
    cursor.close()
    connection.close()

    return render_template('gen_ids/gen_ids.html', gen_id=gen_id, segment='gen_ids')



@blueprint.route('/add_gen_id', methods=['GET', 'POST'])
def add_gen_id():
    if request.method == 'POST':
        name = request.form.get('gen_id_name')
        contact = request.form.get('contact')
        address = request.form.get('address')
        
        # Ensure the form data is filled
        if not name or not contact or not address:
            flash("Please fill out the form!")
            return render_template('gen_id/add_gen_id.html',segment='add_gen_id')

        # Check if gen_id already exists
        connection = get_db_connection()
        cursor = connection.cursor(dictionary=True)
        cursor.execute('SELECT * FROM gen_id WHERE name = %s', (name,))
        gen_id = cursor.fetchone()

        if gen_id:
            flash("gen_id already exists!")
        else:
            # Insert the new gen_id
            cursor.execute('INSERT INTO gen_id (name, contact, address) VALUES (%s, %s, %s)', 
                           (name, contact, address))
            connection.commit()
            flash("You have successfully registered a gen_id!")
        
        cursor.close()
        connection.close()
        return render_template('gen_ids/add_gen_id.html',segment='add_gen_id')
    
    # Handle GET request (no action needed for this part)
    return render_template('gen_ids/add_gen_id.html',segment='add_gen_id')


@blueprint.route('/edit_gen_id/<int:gen_id_id>', methods=['POST', 'GET'])
def edit_gen_id(gen_id_id):
    if request.method == 'POST':
        # Get data from the form
        name = request.form['name']
        contact = request.form['contact']
        address = request.form['address']
        loyaltypoints = request.form.get('loyaltypoints')  # Optional field, may be NULL

        try:
            # Create connection and execute the update query
            connection = get_db_connection()
            cursor = connection.cursor()
            cursor.execute("""
                UPDATE gen_id 
                SET name=%s, contact=%s, address=%s, loyaltypoints=%s 
                WHERE gen_idID=%s
            """, (name, contact, address, loyaltypoints, gen_id_id))
            connection.commit()
            
            # Flash success message
            flash("gen_id Data Updated Successfully", "success")
        except Exception as e:
            # Flash error message if any exception occurs
            flash(f"Error: {str(e)}", "danger")
        finally:
            # Close the cursor and connection
            cursor.close()
            connection.close()
            return redirect(url_for('gen_ids_blueprint.gen_ids'))

    elif request.method == 'GET':
        # Retrieve gen_id data to pre-fill the form (if needed)
        connection = get_db_connection()
        cursor = connection.cursor(dictionary=True)
        cursor.execute("SELECT * FROM gen_id WHERE gen_idID = %s", (gen_id_id,))
        gen_id = cursor.fetchone()
        cursor.close()
        connection.close()
        
        # If gen_id exists, render an edit form
        if gen_id:
            return render_template('gen_ids/edit_gen_id.html', gen_id=gen_id)
        else:
            flash("gen_id not found.", "danger")
            return redirect(url_for('gen_ids_blueprint.gen_ids'))





@blueprint.route('/delete_gen_id/<string:get_id>')
def delete_gen_id(get_id):
    connection = get_db_connection()
    cursor = connection.cursor()
    
    # Using a parameterized query to prevent SQL injection
    cursor.execute('DELETE FROM gen_id WHERE gen_idID = %s', (get_id,))
    
    # Commit the transaction to apply the changes
    connection.commit()
    
    # Close the cursor and connection
    cursor.close()
    connection.close()

    # Redirect to the 'manage_gen_id' route
    return redirect(url_for('gen_ids_blueprint.gen_ids'))



    

# Dynamic route for rendering other templates
@blueprint.route('/<template>')
def route_template(template):
    try:
        # Ensure the template ends with '.html' for correct render
        if not template.endswith('.html'):
            template += '.html'

        segment = get_segment(request)

        return render_template("home/" + template, segment=segment)

    except TemplateNotFound:
        return render_template('home/page-404.html'), 404

    except Exception as e:
        return render_template('home/page-500.html'), 500


def get_segment(request):
    """Extracts the last part of the URL path to identify the current page."""
    try:
        segment = request.path.split('/')[-1]
        if segment == '':
            segment = 'gen_ids'
        return segment

    except Exception as e:
        return None
