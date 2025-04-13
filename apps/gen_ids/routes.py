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











@blueprint.route('/generate_id/<int:pupil_id>')
def generate_id(pupil_id):
    connection = get_db_connection()
    cursor = connection.cursor(dictionary=True)

    cursor.execute("""
        SELECT 
            p.first_name AS pupil_first_name,
            p.other_name,
            p.last_name AS pupil_last_name,
            p.reg_no,
            p.class,
            f.first_name AS father_first_name,
            f.last_name AS father_last_name,
            m.first_name AS mother_first_name,
            m.last_name AS mother_last_name,
            p.image AS pupil_image,
            f.image AS father_image,
            m.image AS mother_image
        FROM pupils p
        LEFT JOIN fathers f ON p.pupil_id = f.pupil_id
        LEFT JOIN mothers m ON p.pupil_id = m.pupil_id
        WHERE p.pupil_id = %s
    """, (pupil_id,))
    
    row = cursor.fetchone()
    cursor.close()
    connection.close()

    if not row:
        flash("Pupil not found", "danger")
        return redirect(url_for('blueprint.gen_ids'))

    # Compose names
    full_name = f"{row['pupil_first_name']} {row['other_name']} {row['pupil_last_name']}"
    mother_name = f"{row['mother_first_name']} {row['mother_last_name']}"
    father_name = f"{row['father_first_name']} {row['father_last_name']}"
    reg_no = row['reg_no']
    class_name = row['class']
    issue_date = datetime.now().strftime("%Y-%m-%d")

    # Generate ID Card
    generate_id_card(
        name=full_name,
        id_number="N/A",  # Not used in template? Else pass it
        class_name=class_name,
        reg_number=reg_no,
        mother_name=mother_name,
        father_name=father_name,
        issue_date=issue_date,
        profile_pic_filename=row['pupil_image'],
        extra_image_filename=row['mother_image'],
        third_image_filename=row['father_image'],
        output_filename=f"id_{pupil_id}.png"
    )

    flash("ID card generated successfully!", "success")
    return redirect(url_for('blueprint.gen_ids'))




    

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
