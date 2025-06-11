from apps.results_update import blueprint
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
import numpy as np 





@blueprint.route('/results_update', methods=['GET'])
def results_update():
    """Fetches pupil marks per subject for a given assessment and renders the results_update page,
       including pupils without marks for the chosen assessment."""
    connection = get_db_connection()
    cursor = connection.cursor(dictionary=True)

    # Fetch dropdown filter data
    cursor.execute("SELECT * FROM classes")
    class_list = cursor.fetchall()

    cursor.execute("SELECT * FROM study_year")
    study_years = cursor.fetchall()

    cursor.execute("SELECT * FROM terms")
    terms = cursor.fetchall()

    cursor.execute("SELECT * FROM assessment")
    assessments = cursor.fetchall()

    cursor.execute("SELECT * FROM subjects")
    subjects = cursor.fetchall()

    cursor.execute("SELECT * FROM stream")
    streams = cursor.fetchall()

    cursor.execute("SELECT * FROM pupils")
    pupils = cursor.fetchall()

    # Retrieve query parameters
    class_id = request.args.get('class_id', type=int)
    year_id = request.args.get('year_id', type=int)
    term_id = request.args.get('term_id', type=int)
    subject_id = request.args.get('subject_id', type=int)
    assessment_name = request.args.get('assessment_name', type=str)
    stream_id = request.args.get('stream_id', type=int)
    pupil_name = request.args.get('pupil_name', type=str)
    reg_no = request.args.get('reg_no', type=str)

    filters = {
        'class_id': class_id,
        'year_id': year_id,
        'term_id': term_id,
        'subject_id': subject_id,
        'assessment_name': assessment_name,
        'stream_id': stream_id,
        'pupil_name': pupil_name,
        'reg_no': reg_no
    }

    if not any(filters.values()):
        cursor.close()
        connection.close()
        return render_template(
            'results_update/results_update.html',
            results_update=[],
            class_list=class_list,
            study_years=study_years,
            terms=terms,
            subjects=subjects,
            assessments=assessments,
            streams=streams,
            pupils=pupils,
            selected_class_id=None,
            selected_study_year_id=None,
            selected_term_id=None,
            selected_assessment_name=None,
            selected_subject_id=None,
            selected_stream_id=None,
            selected_pupil_name=None,
            entered_reg_no=None,
            segment='results_update'
        )

    # Construct the query
    query = """
    SELECT 
        p.reg_no,
        TRIM(CONCAT(p.first_name, ' ', COALESCE(p.other_name, ''), ' ', p.last_name)) AS full_name,
        t.term_name,
        a.assessment_name,
        sub.subject_name,
        s.Mark,
        p.pupil_id,
        y.year_name,
        str.stream_name,
        s.score_id
    FROM 
        pupils p
    LEFT JOIN 
        scores s ON p.reg_no = s.reg_no
    LEFT JOIN 
        assessment a ON s.assessment_id = a.assessment_id
    LEFT JOIN 
        terms t ON s.term_id = t.term_id
    LEFT JOIN 
        subjects sub ON s.subject_id = sub.subject_id
    LEFT JOIN 
        study_year y ON s.year_id = y.year_id
    LEFT JOIN
        stream str ON p.stream_id = str.stream_id
    WHERE 1=1
    """

    if class_id:
        query += f" AND p.class_id = {class_id}"
    if stream_id:
        query += f" AND p.stream_id = {stream_id}"
    if year_id:
        query += f" AND (y.year_id = {year_id} OR y.year_id IS NULL)"
    if term_id:
        query += f" AND (t.term_id = {term_id} OR t.term_id IS NULL)"
    if subject_id:
        query += f" AND (sub.subject_id = {subject_id} OR sub.subject_id IS NULL)"
    if assessment_name:
        query += f" AND (a.assessment_name = '{assessment_name}' OR a.assessment_name IS NULL)"
    if pupil_name:
        query += f" AND TRIM(CONCAT(p.first_name, ' ', COALESCE(p.other_name, ''), ' ', p.last_name)) LIKE '%{pupil_name}%'"
    if reg_no:
        query += f" AND p.reg_no = '{reg_no}'"

    query += " ORDER BY p.last_name, p.first_name, p.other_name"

    cursor.execute(query)
    results_update = cursor.fetchall()

    cursor.close()
    connection.close()

    return render_template(
        'results_update/results_update.html',
        results_update=results_update,
        class_list=class_list,
        study_years=study_years,
        terms=terms,
        subjects=subjects,
        assessments=assessments,
        streams=streams,
        pupils=pupils,
        selected_class_id=class_id,
        selected_study_year_id=year_id,
        selected_term_id=term_id,
        selected_assessment_name=assessment_name,
        selected_subject_id=subject_id,
        selected_stream_id=stream_id,
        selected_pupil_name=pupil_name,
        entered_reg_no=reg_no,
        segment='results_update'
    )











from datetime import datetime
import pytz


def get_kampala_time():
    kampala = pytz.timezone("Africa/Kampala")
    return datetime.now(kampala)

@blueprint.route('/delete_scores', methods=['POST'])
def delete_scores():
    """Deletes selected scores and logs them with optional notes."""

    score_ids = request.form.getlist('score_ids')
    print(score_ids)


    deletion_notes = request.form.get('deletion_notes', '').strip()  # get notes from form (optional)

    if not score_ids:
        flash('No scores selected for deletion.', 'warning')
        return redirect(url_for('results_update_blueprint.results_update'))

    try:
        connection = get_db_connection()
        cursor = connection.cursor(dictionary=True)

        # Fetch rows to log
        format_strings = ','.join(['%s'] * len(score_ids))
        cursor.execute(f"SELECT * FROM scores WHERE score_id IN ({format_strings})", score_ids)
        rows_to_log = cursor.fetchall()

        # Prepare insert query for logs (includes notes and deleted_at)
        log_query = """
            INSERT INTO scores_del_logs
            (score_id, user_id, reg_no, class_id, stream_id, term_id, year_id, assessment_id, subject_id, Mark, notes, deleted_at)
            VALUES (%(score_id)s, %(user_id)s, %(reg_no)s, %(class_id)s, %(stream_id)s, %(term_id)s, %(year_id)s,
                    %(assessment_id)s, %(subject_id)s, %(Mark)s, %(notes)s, %(deleted_at)s)
        """

        kampala_time = get_kampala_time()

        # Insert each deleted row into the logs table with your deletion notes
        for row in rows_to_log:
            row['deleted_at'] = kampala_time
            # Use deletion notes from form; if none provided, fallback to existing notes or NULL
            row['notes'] = deletion_notes if deletion_notes else row.get('notes', None)
            cursor.execute(log_query, row)

        # Now delete from scores table
        cursor.execute(f"DELETE FROM scores WHERE score_id IN ({format_strings})", score_ids)

        connection.commit()

        flash(f"{cursor.rowcount} score(s) deleted and logged successfully.", 'success')

    except Error as e:
        flash(f"An error occurred: {e}", 'danger')

    finally:
        if cursor:
            cursor.close()
        if connection:
            connection.close()

    return redirect(url_for('results_update_blueprint.results_update'))







