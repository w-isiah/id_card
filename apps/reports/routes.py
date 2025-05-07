from apps.reports import blueprint
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






@blueprint.route('/reports', methods=['GET'])
def reports():
    """Fetches pupil marks per subject for a given assessment and renders the reports page."""
    connection = get_db_connection()
    cursor = connection.cursor(dictionary=True)

    # Fetch available filters (for dropdowns)
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




    # Retrieve query parameters with default values (for applied filters)
    class_id = request.args.get('class_id', type=int)
    year_id = request.args.get('year_id', type=int)
    term_id = request.args.get('term_id', type=int)
    subject_id = request.args.get('subject_id', type=int)
    assessment_name = request.args.get('assessment_name', type=str)

    filters = {
        'class_id': class_id,
        'year_id': year_id,
        'term_id': term_id,
        'subject_id': subject_id,
        'assessment_name': assessment_name
    }

    # If no filters are applied, return an empty list immediately
    if not any(filters.values()):
        demo_data = []  # No filters applied, return an empty list
        cursor.close()
        connection.close()
        return render_template(
            'reports/reports.html',
            reports=demo_data,
            class_list=class_list,
            study_years=study_years,
            terms=terms,
            subjects=subjects,
            assessments=assessments,
            selected_class_id=None,
            selected_study_year_id=None,
            selected_term_id=None,
            selected_assessment_name=None,
            segment='reports'
        )

    # Base query to fetch the report data
    query = """
    SELECT 
        p.reg_no,
        TRIM(CONCAT(p.first_name, ' ', COALESCE(p.other_name, ''), ' ', p.last_name)) AS full_name,
        t.term_name,
        a.assessment_name,
        sub.subject_name,
        s.Mark,
        p.pupil_id,
        y.year_name

    FROM 
        scores s
    JOIN 
        pupils p ON s.reg_no = p.reg_no
    JOIN 
        assessment a ON s.assessment_id = a.assessment_id
    JOIN 
        terms t ON s.term_id = t.term_id
    JOIN 
        subjects sub ON s.subject_id = sub.subject_id
    JOIN 
        study_year y ON s.year_id = y.year_id
    WHERE 1=1
    """

    # Add filters to query
    if class_id:
        query += f" AND p.class_id = {class_id}"
    if year_id:
        query += f" AND p.year_id = {year_id}"
    if term_id:
        query += f" AND s.term_id = {term_id}"
    if subject_id:
        query +=f" AND s.subject_id = {subject_id}"
    if assessment_name:
        query += f" AND a.assessment_name = '{assessment_name}'"
    
    cursor.execute(query)
    reports = cursor.fetchall()
    
    cursor.close()
    connection.close()

    return render_template(
        'reports/reports.html',
        reports=reports,
        class_list=class_list,
        study_years=study_years,
        terms=terms,
        subjects=subjects,
        assessments=assessments,
        selected_class_id=class_id,
        selected_study_year_id=year_id,
        selected_term_id=term_id,
        selected_assessment_name=assessment_name,
        segment='reports'
    )














@blueprint.route('/report_card/<string:reg_no>', methods=['GET'])
def report_card(reg_no):
    """Generates a detailed report card for a pupil grouped by assessments."""
    connection = get_db_connection()
    cursor = connection.cursor(dictionary=True)

    query = """
        SELECT 
            p.reg_no,
            CONCAT(p.first_name, ' ', p.other_name, ' ', p.last_name) AS full_name,
            a.assessment_name,
            s.math,
            s.english,
            s.science,
            s.social_studies,
            s.re,
            s.computer
        FROM 
            scores s
        JOIN 
            pupils p ON s.reg_no = p.reg_no
        JOIN 
            assessment a ON s.assessment_id = a.assessment_id
        WHERE 
            p.reg_no = %s
        ORDER BY 
            a.assessment_id
    """
    cursor.execute(query, (reg_no,))
    records = cursor.fetchall()
    cursor.close()
    connection.close()

    if not records:
        return "No report card found for this pupil.", 404

    pupil_name = records[0]['full_name']
    assessments = []  # Will hold structured per-assessment info
    overall_total = 0
    overall_count = 0

    for row in records:
        subjects = {
            'Math': row['math'],
            'English': row['english'],
            'Science': row['science'],
            'Social Studies': row['social_studies'],
            'RE': row['re'],
            'Computer': row['computer']
        }
        assessment_total = sum(score for score in subjects.values() if score is not None)
        assessment_count = sum(1 for score in subjects.values() if score is not None)

        assessments.append({
            'name': row['assessment_name'],
            'scores': subjects,
            'total': assessment_total,
            'average': round(assessment_total / assessment_count, 2) if assessment_count else 0
        })

        overall_total += assessment_total
        overall_count += assessment_count

    overall_average = round(overall_total / overall_count, 2) if overall_count else 0

    return render_template(
        'reports/report_card.html',
        student_name=pupil_name,
        assessments=assessments,
        overall_total=overall_total,
        overall_average=overall_average
    )












@blueprint.route('/term_reports', methods=['GET'])
def term_reports():
    connection = get_db_connection()
    cursor = connection.cursor(dictionary=True)

    # Fetch dropdowns
    cursor.execute("SELECT * FROM classes")
    class_list = cursor.fetchall()

    cursor.execute("SELECT * FROM study_year")
    study_years = cursor.fetchall()

    cursor.execute("SELECT * FROM terms")
    terms = cursor.fetchall()

    cursor.execute("SELECT * FROM assessment")
    assessments = cursor.fetchall()

    # Filters
    class_id = request.args.get('class_id', type=int)
    year_id = request.args.get('year_id', type=int)
    term_id = request.args.get('term_id', type=int)
    assessment_name = request.args.get('assessment_name', type=str)

    filters = {
        'class_id': class_id,
        'year_id': year_id,
        'term_id': term_id,
        'assessment_name': assessment_name
    }

    if not any(filters.values()):
        return render_template(
            'reports/term_reports.html',
            reports=[],
            subject_names=[],
            class_list=class_list,
            study_years=study_years,
            terms=terms,
            subjects=[],  # Empty since we’re filtering
            assessments=assessments,
            selected_class_id=None,
            selected_study_year_id=None,
            selected_term_id=None,
            selected_assessment_name=None,
            segment='reports'
        )

    # Main query to fetch data with grades
    query = """
    SELECT 
        p.reg_no,
        TRIM(CONCAT(p.first_name, ' ', COALESCE(p.other_name, ''), ' ', p.last_name)) AS full_name,
        t.term_name,
        a.assessment_name,
        sub.subject_name,
        s.Mark,
        g.grade_letter,
        g.remark,
        p.pupil_id,
        y.year_name
    FROM 
        scores s
    JOIN pupils p ON s.reg_no = p.reg_no
    JOIN assessment a ON s.assessment_id = a.assessment_id
    JOIN terms t ON s.term_id = t.term_id
    JOIN subjects sub ON s.subject_id = sub.subject_id
    JOIN study_year y ON s.year_id = y.year_id
    JOIN grades g ON s.Mark BETWEEN g.min_score AND g.max_score
    WHERE 1=1
    """

    params = []
    if class_id:
        query += " AND p.class_id = %s"
        params.append(class_id)
    if year_id:
        query += " AND p.year_id = %s"
        params.append(year_id)
    if term_id:
        query += " AND s.term_id = %s"
        params.append(term_id)
    if assessment_name:
        query += " AND a.assessment_name = %s"
        params.append(assessment_name)

    cursor.execute(query, params)
    raw_data = cursor.fetchall()

    # Identify only used subjects
    subject_names = sorted(set(row['subject_name'] for row in raw_data))

    # Pivot logic
    pivoted = {}
    for row in raw_data:
        key = row['reg_no']
        if key not in pivoted:
            pivoted[key] = {
                'reg_no': row['reg_no'],
                'full_name': row['full_name'],
                'term_name': row['term_name'],
                'assessment_name': row['assessment_name'],
                'year_name': row['year_name'],
                'marks': {sub: '' for sub in subject_names},
                'grades': {sub: '' for sub in subject_names},
                'remarks': {sub: '' for sub in subject_names}
            }
        pivoted[key]['marks'][row['subject_name']] = row['Mark']
        pivoted[key]['grades'][row['subject_name']] = row['grade_letter']
        pivoted[key]['remarks'][row['subject_name']] = row['remark']

    reports = list(pivoted.values())

    cursor.close()
    connection.close()

    return render_template(
        'reports/term_reports.html',
        reports=reports,
        subject_names=subject_names,
        class_list=class_list,
        study_years=study_years,
        terms=terms,
        subjects=[],  # not needed for table display
        assessments=assessments,
        selected_class_id=class_id,
        selected_study_year_id=year_id,
        selected_term_id=term_id,
        selected_assessment_name=assessment_name,
        segment='reports'
    )
