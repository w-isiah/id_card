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
import numpy as np 






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








@blueprint.route('/scores_reports', methods=['GET'])
def scores_reports():
    connection = get_db_connection()
    cursor = connection.cursor(dictionary=True)

    # Load dropdowns
    cursor.execute("SELECT * FROM classes")
    class_list = cursor.fetchall()
    cursor.execute("SELECT * FROM study_year")
    study_years = cursor.fetchall()
    cursor.execute("SELECT * FROM terms")
    terms = cursor.fetchall()
    cursor.execute("SELECT * FROM assessment")
    assessments = cursor.fetchall()

    # Get filters
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
        return render_template('reports/scores_reports.html',
            reports=[], subject_names=[], class_list=class_list,
            study_years=study_years, terms=terms, assessments=assessments,
            selected_class_id=None, selected_study_year_id=None,
            selected_term_id=None, selected_assessment_name=None, segment='reports'
        )

    # Query with filters
    query = """
    SELECT 
        p.reg_no,
        CONCAT_WS(' ', p.first_name, p.other_name, p.last_name) AS full_name,
        y.year_name,
        t.term_name,
        a.assessment_name,
        sub.subject_name,
        s.Mark,
        g.grade_letter,
        g.remark
    FROM scores s
    JOIN pupils p ON s.reg_no = p.reg_no
    JOIN assessment a ON s.assessment_id = a.assessment_id
    JOIN terms t ON s.term_id = t.term_id
    JOIN subjects sub ON s.subject_id = sub.subject_id
    JOIN study_year y ON s.year_id = y.year_id
    LEFT JOIN grades g ON s.Mark BETWEEN g.min_score AND g.max_score
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
    cursor.close()
    connection.close()

    # Process and pivot using NumPy
    subject_names = sorted({row['subject_name'] for row in raw_data})
    student_map = {}

    for row in raw_data:
        reg = row['reg_no']
        if reg not in student_map:
            student_map[reg] = {
                'reg_no': reg,
                'full_name': row['full_name'],
                'year_name': row['year_name'],
                'term_name': row['term_name'],
                'assessment_name': row['assessment_name'],
                'marks': {},
                'grades': {},
                'remarks': {}
            }
        subject = row['subject_name']
        mark = row['Mark']

        student_map[reg]['marks'][subject] = mark if mark is not None else np.nan
        student_map[reg]['grades'][subject] = row['grade_letter'] or ''
        student_map[reg]['remarks'][subject] = row['remark'] or ''

    # Calculate total and average using NumPy
    reports = []
    for student in student_map.values():
        marks_array = np.array([
            student['marks'].get(subject, np.nan) for subject in subject_names
        ], dtype=np.float64)

        total = np.nansum(marks_array)
        count = np.count_nonzero(~np.isnan(marks_array))
        avg = np.round(total / count, 2) if count > 0 else 0

        student['total_score'] = total
        student['average_score'] = avg
        reports.append(student)

    return render_template('reports/scores_reports.html',
        reports=reports, subject_names=subject_names,
        class_list=class_list, study_years=study_years,
        terms=terms, assessments=assessments,
        selected_class_id=class_id, selected_study_year_id=year_id,
        selected_term_id=term_id, selected_assessment_name=assessment_name,
        segment='reports'
    )




@blueprint.route('/scores_positions_reports', methods=['GET'])
def scores_positions_reports():
    connection = get_db_connection()
    cursor = connection.cursor(dictionary=True)

    # Load dropdown data
    cursor.execute("SELECT * FROM classes")
    class_list = cursor.fetchall()

    cursor.execute("SELECT * FROM study_year")
    study_years = cursor.fetchall()

    cursor.execute("SELECT * FROM terms")
    terms = cursor.fetchall()

    cursor.execute("SELECT * FROM assessment")
    assessments = cursor.fetchall()

    # Get filters from request
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

    # If no filters selected, render empty page
    if not any(filters.values()):
        return render_template('reports/scores_positions_reports.html',
            reports=[], subject_names=[], class_list=class_list,
            study_years=study_years, terms=terms, assessments=assessments,
            selected_class_id=None, selected_study_year_id=None,
            selected_term_id=None, selected_assessment_name=None, segment='reports'
        )

    # Build base SQL query
    query = """
    SELECT 
        p.reg_no,
        CONCAT_WS(' ', p.first_name, p.other_name, p.last_name) AS full_name,
        y.year_name,
        t.term_name,
        a.assessment_name,
        sub.subject_name,
        s.Mark,
        g.grade_letter,
        g.remark
    FROM scores s
    JOIN pupils p ON s.reg_no = p.reg_no
    JOIN assessment a ON s.assessment_id = a.assessment_id
    JOIN terms t ON s.term_id = t.term_id
    JOIN subjects sub ON s.subject_id = sub.subject_id
    JOIN study_year y ON s.year_id = y.year_id
    LEFT JOIN grades g ON s.Mark BETWEEN g.min_score AND g.max_score
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

    # Execute query
    cursor.execute(query, params)
    raw_data = cursor.fetchall()
    cursor.close()
    connection.close()

    # Extract subject names and initialize student mapping
    subject_names = sorted({row['subject_name'] for row in raw_data})
    student_map = {}

    for row in raw_data:
        reg = row['reg_no']
        if reg not in student_map:
            student_map[reg] = {
                'reg_no': reg,
                'full_name': row['full_name'],
                'year_name': row['year_name'],
                'term_name': row['term_name'],
                'assessment_name': row['assessment_name'],
                'marks': {},
                'grades': {},
                'remarks': {}
            }

        subject = row['subject_name']
        mark = row['Mark']

        student_map[reg]['marks'][subject] = mark if mark is not None else np.nan
        student_map[reg]['grades'][subject] = row['grade_letter'] or ''
        student_map[reg]['remarks'][subject] = row['remark'] or ''

    # Calculate totals, averages, and prepare for ranking
    reports = []
    for student in student_map.values():
        marks_array = np.array([
            student['marks'].get(subject, np.nan) for subject in subject_names
        ], dtype=np.float64)

        total = np.nansum(marks_array)
        count = np.count_nonzero(~np.isnan(marks_array))
        average = np.round(total / count, 2) if count > 0 else 0

        student['total_score'] = total
        student['average_score'] = average
        reports.append(student)

    # Sort and assign positions
    reports.sort(key=lambda x: x['average_score'], reverse=True)

    current_position = 1
    last_average = None
    for index, student in enumerate(reports):
        if student['average_score'] == last_average:
            student['position'] = current_position  # same position for tie
        else:
            current_position = index + 1
            student['position'] = current_position
            last_average = student['average_score']

    # Render template with results
    return render_template('reports/scores_positions_reports.html',
        reports=reports,
        subject_names=subject_names,
        class_list=class_list,
        study_years=study_years,
        terms=terms,
        assessments=assessments,
        selected_class_id=class_id,
        selected_study_year_id=year_id,
        selected_term_id=term_id,
        selected_assessment_name=assessment_name,
        segment='reports'
    )













@blueprint.route('/assessment_report', methods=['GET'])
def assessment_report():
    connection = get_db_connection()
    cursor = connection.cursor(dictionary=True)

    # Load dropdown data
    cursor.execute("SELECT * FROM classes")
    class_list = cursor.fetchall()

    cursor.execute("SELECT * FROM study_year")
    study_years = cursor.fetchall()

    cursor.execute("SELECT * FROM terms")
    terms = cursor.fetchall()

    cursor.execute("SELECT * FROM assessment")
    assessments = cursor.fetchall()

    # Get filters from request
    class_id = request.args.get('class_id', type=int)
    year_id = request.args.get('year_id', type=int)
    term_id = request.args.get('term_id', type=int)
    assessment_name = request.args.get('assessment_name')  # NEW

    filters = {
        'class_id': class_id,
        'year_id': year_id,
        'term_id': term_id,
        'assessment_name': assessment_name
    }

    # If no filters selected, render empty page
    if not any(filters.values()):
        return render_template('reports/assessment_report.html',
            reports=[], pivoted_columns=[],
            class_list=class_list,
            study_years=study_years,
            terms=terms,
            assessments=assessments,
            selected_class_id=None,
            selected_study_year_id=None,
            selected_term_id=None,
            selected_assessment_name=None,
            segment='reports'
        )

    # Query with filters
    query = """
    SELECT 
        p.reg_no,
        CONCAT_WS(' ', p.first_name, p.other_name, p.last_name) AS full_name,
        y.year_name,
        t.term_name,
        a.assessment_name,
        sub.subject_name,
        s.Mark
    FROM scores s
    JOIN pupils p ON s.reg_no = p.reg_no
    JOIN assessment a ON s.assessment_id = a.assessment_id
    JOIN terms t ON s.term_id = t.term_id
    JOIN subjects sub ON s.subject_id = sub.subject_id
    JOIN study_year y ON s.year_id = y.year_id
    WHERE 1=1
    """

    params = []
    if class_id:
        query += " AND p.class_id = %s"
        params.append(class_id)
    if year_id:
        query += " AND s.year_id = %s"
        params.append(year_id)
    if term_id:
        query += " AND s.term_id = %s"
        params.append(term_id)
    if assessment_name:
        query += " AND a.assessment_name = %s"
        params.append(assessment_name)

    cursor.execute(query, params)
    raw_data = cursor.fetchall()
    cursor.close()
    connection.close()

    # Pivot and structure data
    subject_names = sorted({row['subject_name'] for row in raw_data})
    assessment_names = sorted({row['assessment_name'] for row in raw_data})
    pivoted_columns = sorted({f"{subject} ({assessment})" for subject in subject_names for assessment in assessment_names})

    student_map = {}
    for row in raw_data:
        reg = row['reg_no']
        if reg not in student_map:
            student_map[reg] = {
                'reg_no': reg,
                'full_name': row['full_name'],
                'year_name': row['year_name'],
                'term_name': row['term_name'],
                'marks': {}
            }

        key = f"{row['subject_name']} ({row['assessment_name']})"
        student_map[reg]['marks'][key] = row['Mark']

    # Final formatting
    reports = []
    for student in student_map.values():
        total = 0
        count = 0
        for col in pivoted_columns:
            mark = student['marks'].get(col)
            if mark is not None:
                total += mark
                count += 1
        student['total_score'] = total
        student['average_score'] = round(total / count, 2) if count else 0
        reports.append(student)

    # Sort and rank
    reports.sort(key=lambda x: x['average_score'], reverse=True)
    current_rank = 1
    last_avg = None
    for index, student in enumerate(reports):
        if student['average_score'] == last_avg:
            student['position'] = current_rank
        else:
            current_rank = index + 1
            student['position'] = current_rank
            last_avg = student['average_score']

    return render_template('reports/assessment_report.html',
        reports=reports,
        pivoted_columns=pivoted_columns,
        class_list=class_list,
        study_years=study_years,
        terms=terms,
        assessments=assessments,
        selected_class_id=class_id,
        selected_study_year_id=year_id,
        selected_term_id=term_id,
        selected_assessment_name=assessment_name,
        segment='reports'
    )















@blueprint.route('/term_report_card/<string:reg_no>', methods=['GET'])
def term_report_card(reg_no):
    connection = get_db_connection()
    cursor = connection.cursor(dictionary=True)

    # Fetch pupil details
    cursor.execute("""
        SELECT p.reg_no, CONCAT(p.first_name, ' ', p.other_name, ' ', p.last_name) AS full_name,
               p.image, p.gender, p.dorm_id, p.stream_id, p.year_id, p.term_id,
               y.year_name, t.term_name, s.stream_name, c.class_name, c.class_id
        FROM pupils p
        JOIN stream s ON p.stream_id = s.stream_id
        JOIN classes c ON s.class_id = c.class_id
        JOIN study_year y ON p.year_id = y.year_id
        JOIN terms t ON p.term_id = t.term_id
        WHERE p.reg_no = %s
    """, (reg_no,))
    pupil = cursor.fetchone()
    if not pupil:
        return "Pupil not found", 404

    # Load grade scale
    cursor.execute("SELECT * FROM grades ORDER BY weight")
    grade_scale = cursor.fetchall()

    def get_grade(score):
        for g in grade_scale:
            if g['min_score'] <= score <= g['max_score']:
                return g['grade_letter'], g['remark']
        return '-', '-'

    # Get all scores
    cursor.execute("""
        SELECT a.assessment_name, sub.subject_name, s.Mark
        FROM scores s
        JOIN assessment a ON s.assessment_id = a.assessment_id
        JOIN subjects sub ON s.subject_id = sub.subject_id
        WHERE s.reg_no = %s
        ORDER BY sub.subject_name, a.assessment_id
    """, (reg_no,))
    results = cursor.fetchall()

    # Process assessment data
    subject_scores = {}
    assessment_names = set()

    for row in results:
        subject = row['subject_name']
        assess = row['assessment_name']
        mark = float(row['Mark']) if row['Mark'] is not None else None
        assessment_names.add(assess)

        if subject not in subject_scores:
            subject_scores[subject] = {}
        subject_scores[subject][assess] = mark

    assessment_list = sorted(assessment_names)

    subjects_data = []
    overall_total = 0
    subject_count = 0

    for subject, scores in subject_scores.items():
        total = sum([m for m in scores.values() if m is not None])
        count = sum([1 for m in scores.values() if m is not None])
        average = round(total / count, 2) if count else 0
        grade_letter, remark = get_grade(average)
        subject_entry = {
            'subject': subject,
            'marks': [],
            'total': total,
            'average': average,
            'grade': grade_letter,
            'remark': remark
        }

        for assessment in assessment_list:
            mark = scores.get(assessment)
            if mark is not None:
                g, r = get_grade(mark)
                subject_entry['marks'].append({'mark': mark, 'grade': g, 'remark': r})
            else:
                subject_entry['marks'].append({'mark': '-', 'grade': '-', 'remark': '-'})
        
        subjects_data.append(subject_entry)
        overall_total += average
        subject_count += 1

    overall_average = round(overall_total / subject_count, 2) if subject_count else 0
    overall_grade, overall_remark = get_grade(overall_average)

    # Stream and class position
    cursor.execute("""
        SELECT p.reg_no, AVG(s.Mark) AS avg
        FROM scores s
        JOIN pupils p ON s.reg_no = p.reg_no
        WHERE p.stream_id = %s AND p.term_id = %s AND p.year_id = %s
        GROUP BY p.reg_no ORDER BY avg DESC
    """, (pupil['stream_id'], pupil['term_id'], pupil['year_id']))
    stream_position = next((i+1 for i, r in enumerate(cursor.fetchall()) if r['reg_no'] == reg_no), None)

    cursor.execute("""
        SELECT p.reg_no, AVG(s.Mark) AS avg
        FROM scores s
        JOIN pupils p ON s.reg_no = p.reg_no
        JOIN stream strm ON p.stream_id = strm.stream_id
        WHERE strm.class_id = %s AND p.term_id = %s AND p.year_id = %s
        GROUP BY p.reg_no ORDER BY avg DESC
    """, (pupil['class_id'], pupil['term_id'], pupil['year_id']))
    class_position = next((i+1 for i, r in enumerate(cursor.fetchall()) if r['reg_no'] == reg_no), None)

    cursor.close()
    connection.close()

    return render_template("reports/term_report_card.html",
        pupil=pupil,
        subjects=subjects_data,
        assessments=assessment_list,
        overall_average=overall_average,
        overall_grade=overall_grade,
        overall_remark=overall_remark,
        stream_position=stream_position,
        class_position=class_position,
        print_date=datetime.now()
    )



@blueprint.route('/scores_p_reports', methods=['GET'])
def scores_p_reports():
    connection = get_db_connection()
    cursor = connection.cursor(dictionary=True)

    # Load dropdown data
    cursor.execute("SELECT * FROM classes")
    class_list = cursor.fetchall()

    cursor.execute("SELECT * FROM study_year")
    study_years = cursor.fetchall()

    cursor.execute("SELECT * FROM terms")
    terms = cursor.fetchall()

    cursor.execute("SELECT * FROM assessment")
    assessments = cursor.fetchall()

    # Get filters from request
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

    # If no filters selected, render empty page
    if not any(filters.values()):
        return render_template('reports/scores_p_reports.html',
            reports=[], subject_names=[], class_list=class_list,
            study_years=study_years, terms=terms, assessments=assessments,
            selected_class_id=None, selected_study_year_id=None,
            selected_term_id=None, selected_assessment_name=None, segment='reports'
        )

    # Build base SQL query
    query = """
    SELECT 
        p.reg_no,
        CONCAT_WS(' ', p.first_name, p.other_name, p.last_name) AS full_name,
        y.year_name,
        t.term_name,
        a.assessment_name,
        sub.subject_name,
        s.Mark,
        g.grade_letter,
        g.remark
    FROM scores s
    JOIN pupils p ON s.reg_no = p.reg_no
    JOIN assessment a ON s.assessment_id = a.assessment_id
    JOIN terms t ON s.term_id = t.term_id
    JOIN subjects sub ON s.subject_id = sub.subject_id
    JOIN study_year y ON s.year_id = y.year_id
    LEFT JOIN grades g ON s.Mark BETWEEN g.min_score AND g.max_score
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

    # Execute query
    cursor.execute(query, params)
    raw_data = cursor.fetchall()
    cursor.close()
    connection.close()

    # Extract subject names and initialize student mapping
    subject_names = sorted({row['subject_name'] for row in raw_data})
    student_map = {}

    for row in raw_data:
        reg = row['reg_no']
        if reg not in student_map:
            student_map[reg] = {
                'reg_no': reg,
                'full_name': row['full_name'],
                'year_name': row['year_name'],
                'term_name': row['term_name'],
                'assessment_name': row['assessment_name'],
                'marks': {},
                'grades': {},
                'remarks': {}
            }

        subject = row['subject_name']
        mark = row['Mark']

        student_map[reg]['marks'][subject] = mark if mark is not None else np.nan
        student_map[reg]['grades'][subject] = row['grade_letter'] or ''
        student_map[reg]['remarks'][subject] = row['remark'] or ''

    # Calculate totals, averages, and prepare for ranking
    reports = []
    for student in student_map.values():
        marks_array = np.array([
            student['marks'].get(subject, np.nan) for subject in subject_names
        ], dtype=np.float64)

        total = np.nansum(marks_array)
        count = np.count_nonzero(~np.isnan(marks_array))
        average = np.round(total / count, 2) if count > 0 else 0

        student['total_score'] = total
        student['average_score'] = average
        reports.append(student)

    # Sort and assign positions
    reports.sort(key=lambda x: x['average_score'], reverse=True)

    current_position = 1
    last_average = None
    for index, student in enumerate(reports):
        if student['average_score'] == last_average:
            student['position'] = current_position  # same position for tie
        else:
            current_position = index + 1
            student['position'] = current_position
            last_average = student['average_score']

    # Render template with results
    return render_template('reports/scores_p_reports.html',
        reports=reports,
        subject_names=subject_names,
        class_list=class_list,
        study_years=study_years,
        terms=terms,
        assessments=assessments,
        selected_class_id=class_id,
        selected_study_year_id=year_id,
        selected_term_id=term_id,
        selected_assessment_name=assessment_name,
        segment='reports'
    )
