from apps.eot_reports import blueprint
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












from datetime import datetime
import pytz


def get_kampala_time():
    kampala = pytz.timezone("Africa/Kampala")
    return datetime.now(kampala)









@blueprint.route('/scores_positions_eot_reports', methods=['GET'])
def scores_positions_eot_reports():
    connection = get_db_connection()
    cursor = connection.cursor(dictionary=True)

    # Load dropdown data
    cursor.execute("SELECT * FROM classes WHERE class_id IN (4, 30, 31, 32)")
    class_list = cursor.fetchall()
    cursor.execute("SELECT * FROM study_year")
    study_years = cursor.fetchall()
    cursor.execute("SELECT * FROM terms")
    terms = cursor.fetchall()
    cursor.execute("SELECT * FROM assessment")
    assessments = cursor.fetchall()
    cursor.execute("SELECT * FROM stream")
    streams = cursor.fetchall()

    # Read filters
    class_id = request.args.get('class_id', type=int)
    year_id = request.args.get('year_id', type=int)
    term_id = request.args.get('term_id', type=int)
    assessment_name = request.args.get('assessment_name', type=str)
    stream_id = request.args.get('stream_id', type=int)

    if not all([class_id, year_id, term_id, assessment_name]):
        cursor.close()
        connection.close()
        return render_template(
            'eot_reports/scores_positions_eot_reports.html',
            eot_reports=[],
            subject_names=[],
            class_list=class_list,
            study_years=study_years,
            terms=terms,
            assessments=assessments,
            streams=streams,
            selected_stream_id=stream_id,
            selected_class_id=class_id,
            selected_study_year_id=year_id,
            selected_term_id=term_id,
            selected_assessment_name=assessment_name,
            segment='eot_reports'
        )

    core_subjects = ['MTC', 'ENGLISH', 'SST', 'SCIE']

    # Fetch scores and related data
    sql = """
        SELECT 
            p.reg_no, p.stream_id, p.class_id,
            CONCAT_WS(' ', p.last_name, p.first_name, p.other_name) AS full_name,
            y.year_name, y.year_id,
            t.term_name, t.term_id,
            a.assessment_name,
            sub.subject_name,
            s.Mark,
            g.grade_letter,
            g.weight,
            st.stream_name
        FROM scores s
        JOIN pupils p ON s.reg_no = p.reg_no
        JOIN assessment a ON s.assessment_id = a.assessment_id
        JOIN terms t ON s.term_id = t.term_id
        JOIN study_year y ON s.year_id = y.year_id
        JOIN subjects sub ON s.subject_id = sub.subject_id
        JOIN stream st ON p.stream_id = st.stream_id
        LEFT JOIN grades g ON s.Mark BETWEEN g.min_score AND g.max_score
        WHERE p.class_id = %s AND s.year_id = %s AND s.term_id = %s AND a.assessment_name = %s
    """
    args = [class_id, year_id, term_id, assessment_name]

    if stream_id:
        sql += " AND p.stream_id = %s"
        args.append(stream_id)

    cursor.execute(sql, args)
    rows = cursor.fetchall()

    subject_names = sorted({row['subject_name'] for row in rows})

    # Build student data map
    student_map = {}
    for row in rows:
        reg_no = row['reg_no']
        if reg_no not in student_map:
            student_map[reg_no] = {
                'reg_no': reg_no,
                'full_name': row['full_name'],
                'class_id': row['class_id'],
                'stream_id': row['stream_id'],
                'stream_name': row['stream_name'],
                'year_id': row['year_id'],
                'term_id': row['term_id'],
                'year_name': row['year_name'],
                'term_name': row['term_name'],
                'assessment_name': row['assessment_name'],
                'marks': {},
                'grades': {},
                'weights': {}
            }
        student_map[reg_no]['marks'][row['subject_name']] = row['Mark']
        student_map[reg_no]['grades'][row['subject_name']] = row['grade_letter'] or ''
        student_map[reg_no]['weights'][row['subject_name']] = row['weight'] or 0

    # Calculate totals, averages, aggregate, division
    for student in student_map.values():
        core_marks = [student['marks'].get(sub) for sub in core_subjects]

        # Replace missing marks with zero for total and average calculation
        marks_values = [m if m is not None else 0 for m in core_marks]
        total_score = sum(marks_values)

        # Average is always divided by total number of core subjects (4)
        avg_score = round(total_score / len(core_subjects), 2)

        incomplete = any(m is None for m in core_marks)
        if incomplete:
            aggregate = 'X'
            division = 'X'
        else:
            aggregate = sum(student['weights'].get(sub, 0) for sub in core_subjects)
            cursor.execute("""
                SELECT division_name FROM division
                WHERE %s BETWEEN min_score AND max_score LIMIT 1
            """, (aggregate,))
            div_row = cursor.fetchone()
            division = div_row['division_name'] if div_row else 'N/A'

        student.update({
            'total_score': total_score,
            'average_score': avg_score,
            'aggregate': aggregate,
            'division': division
        })

    students = list(student_map.values())

    def assign_positions(student_list, pos_key):
        # Sort students: aggregate 'X' last, others by descending average_score
        student_list.sort(key=lambda s: (float('inf') if s['aggregate'] == 'X' else -s['average_score'], s['reg_no']))
        prev_score = None
        prev_position = 0
        for idx, student in enumerate(student_list, start=1):
            # Assign numeric position regardless of 'X' aggregate
            if student['aggregate'] == 'X':
                student[pos_key] = idx
            else:
                if student['average_score'] != prev_score:
                    prev_position = idx
                student[pos_key] = prev_position
                prev_score = student['average_score']

    # Assign class positions
    assign_positions(students, 'class_position')

    # Assign stream positions
    from collections import defaultdict
    stream_groups = defaultdict(list)
    for student in students:
        stream_groups[student['stream_id']].append(student)

    for group in stream_groups.values():
        assign_positions(group, 'stream_position')

    cursor.close()
    connection.close()

    return render_template(
        'eot_reports/scores_positions_eot_reports.html',
        eot_reports=students,
        subject_names=subject_names,
        class_list=class_list,
        study_years=study_years,
        terms=terms,
        assessments=assessments,
        streams=streams,
        selected_class_id=class_id,
        selected_study_year_id=year_id,
        selected_term_id=term_id,
        selected_assessment_name=assessment_name,
        selected_stream_id=stream_id,
        segment='eot_reports'
    )














@blueprint.route('/vd_eot_reports', methods=['GET'])
def vd_eot_reports():
    from collections import defaultdict
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    # --- Dropdown options ---
    cursor.execute("SELECT * FROM classes WHERE class_id IN (4,30,31,32,33)")
    class_list = cursor.fetchall()
    cursor.execute("SELECT * FROM study_year")
    study_years = cursor.fetchall()
    cursor.execute("SELECT * FROM terms")
    terms = cursor.fetchall()
    cursor.execute("SELECT * FROM assessment")
    assessments = cursor.fetchall()
    cursor.execute("SELECT * FROM stream")
    streams = cursor.fetchall()

    # --- Query parameters ---
    class_id = request.args.get('class_id', type=int)
    stream_id = request.args.get('stream_id', type=int)
    year_id = request.args.get('year_id', type=int)
    term_id = request.args.get('term_id', type=int)
    assessment_names = request.args.getlist('assessment_name')

    if not all([class_id, stream_id, year_id, term_id, assessment_names]):
        cursor.close()
        conn.close()
        return render_template('eot_reports/vd_eot_reports.html',
            reports=[], subject_names=[],
            class_list=class_list, study_years=study_years,
            terms=terms, assessments=assessments,
            streams=streams,
            selected_class_id=class_id,
            selected_stream_id=stream_id,
            selected_study_year_id=year_id,
            selected_term_id=term_id,
            selected_assessment_name=assessment_names,
            segment='vd_eot_reports'
        )

    # --- Class teacher info ---
    cursor.execute("""
        SELECT CONCAT(u.first_name, ' ', u.last_name) AS teacher_name, u.sign_image
        FROM classteacher_assignment cta
        JOIN users u ON cta.user_id = u.id
        WHERE cta.stream_id = %s AND cta.year_id = %s AND cta.term_id = %s
        ORDER BY cta.id DESC LIMIT 1
    """, (stream_id, year_id, term_id))
    cte = cursor.fetchone()
    class_teacher = cte['teacher_name'] if cte else 'Not Assigned'
    class_teacher_sign_image = cte['sign_image'] if cte and cte.get('sign_image') else None

    # --- Headmaster signature ---
    cursor.execute("SELECT sign_image FROM users WHERE role = 'headteacher' ORDER BY id DESC LIMIT 1")
    hme = cursor.fetchone()
    headmaster_sign_image = hme['sign_image'] if hme and hme.get('sign_image') else None

    # --- Main scores query ---
    placeholders = ','.join(['%s'] * len(assessment_names))
    sql = f"""
        SELECT s.reg_no, p.stream_id, p.class_id, p.index_number,
               CONCAT_WS(' ', p.last_name, p.first_name, p.other_name) AS full_name,
               p.image, c.class_name, st.stream_name,
               y.year_name, t.term_name, a.assessment_name,
               sub.subject_id, sub.subject_name, s.Mark,
               g.grade_letter, g.weight,
               cc.total_class_size, sc.total_stream_size
        FROM scores s
        JOIN pupils p USING (reg_no)
        JOIN classes c ON p.class_id = c.class_id
        JOIN stream st ON p.stream_id = st.stream_id
        JOIN study_year y ON s.year_id = y.year_id
        JOIN terms t ON s.term_id = t.term_id
        JOIN assessment a ON s.assessment_id = a.assessment_id
        JOIN subjects sub ON s.subject_id = sub.subject_id
        LEFT JOIN grades g ON s.Mark BETWEEN g.min_score AND g.max_score
        JOIN (SELECT class_id, COUNT(*) total_class_size FROM pupils GROUP BY class_id) cc ON cc.class_id = p.class_id
        JOIN (SELECT class_id, stream_id, COUNT(*) total_stream_size FROM pupils GROUP BY class_id, stream_id) sc
             ON sc.class_id = p.class_id AND sc.stream_id = p.stream_id
        WHERE p.class_id = %s AND s.year_id = %s AND s.term_id = %s AND a.assessment_name IN ({placeholders})
        ORDER BY p.last_name, p.first_name, p.other_name
    """
    params = [class_id, year_id, term_id] + assessment_names
    cursor.execute(sql, params)
    rows = cursor.fetchall()

    core_subjects = ['MTC', 'ENGLISH', 'SST', 'SCIE']
    grouped = {}
    subject_names = set()
    subject_ranks_data = defaultdict(lambda: defaultdict(list))

    for r in rows:
        key = (r['reg_no'], r['assessment_name'])
        subject_names.add(r['subject_name'])
        subject_ranks_data[r['assessment_name']][r['subject_name']].append({
            'reg_no': r['reg_no'], 'Mark': r['Mark']
        })
        if key not in grouped:
            grouped[key] = {
                'reg_no': r['reg_no'],
                'index_number': r['index_number'],
                'full_name': r['full_name'],
                'image': r['image'],
                'class_name': r['class_name'],
                'stream_name': r['stream_name'],
                'assessment_name': r['assessment_name'],
                'marks': {}, 'grades': {}, 'weights': {},
                'subject_comments': {},
                'class_teacher': class_teacher,
                'total_class_size': r['total_class_size'],
                'total_stream_size': r['total_stream_size'],
                'stream_id': r['stream_id'],
                'class_teacher_sign_image': class_teacher_sign_image,
                'headmaster_sign_image': headmaster_sign_image
            }
        stu = grouped[key]
        stu['marks'][r['subject_name']] = r['Mark']
        stu['grades'][r['subject_name']] = r['grade_letter']
        stu['weights'][r['subject_name']] = r['weight'] or 0

        # Subject comment
        if r['Mark'] is not None:
            cursor.execute("""
                SELECT sc.comment, u.name_sf
                FROM subject_comments sc
                LEFT JOIN users u ON sc.user_id = u.id
                WHERE sc.subject_id = %s AND sc.stream_id = %s AND %s BETWEEN sc.min_score AND sc.max_score
                ORDER BY sc.updated_at DESC LIMIT 1
            """, (r['subject_id'], r['stream_id'], r['Mark']))
            cm = cursor.fetchone()
            stu['subject_comments'][r['subject_name']] = {
                'text': cm['comment'] if cm else '',
                'by': cm['name_sf'] if cm else ''
            }

    # --- Subject ranks ---
    subject_ranks = defaultdict(lambda: defaultdict(dict))
    for asmt, subjmap in subject_ranks_data.items():
        for subj, entries in subjmap.items():
            entries.sort(key=lambda e: -e['Mark'] if e['Mark'] is not None else float('-inf'))
            prev = None
            rank = 0
            for idx, e in enumerate(entries):
                if e['Mark'] != prev:
                    rank = idx + 1
                subject_ranks[asmt][subj][e['reg_no']] = rank
                prev = e['Mark']

    # --- Reports list (per-assessment) ---
    reports_list = []
    student_subject_marks = defaultdict(lambda: defaultdict(list))
    for stu in grouped.values():
        core = [stu['marks'].get(s) for s in core_subjects if stu['marks'].get(s) is not None]
        total = sum(core)
        avg = round(total / len(core), 2) if core else 0
        agg = sum(stu['weights'].get(s, 0) for s in core_subjects) if core else 0

        cursor.execute("SELECT division_name FROM division WHERE %s BETWEEN min_score AND max_score LIMIT 1", (agg,))
        dv = cursor.fetchone()
        division = dv['division_name'] if dv else 'N/A'

        # Headmaster and class teacher comments
        cursor.execute("SELECT comment FROM headmaster_comments WHERE %s BETWEEN min_score AND max_score ORDER BY updated_at DESC LIMIT 1", (avg,))
        ht = cursor.fetchone()

        cursor.execute("""
            SELECT cc.comment, u.name_sf
            FROM classteacher_comments cc
            LEFT JOIN users u ON cc.user_id = u.id
            WHERE cc.stream_id = %s AND %s BETWEEN cc.min_score AND cc.max_score
            ORDER BY cc.updated_at DESC LIMIT 1
        """, (stu['stream_id'], avg))
        ctcm = cursor.fetchone()

        stu.update({
            'total_score': total,
            'average_score': avg,
            'aggregate': agg,
            'division': division,
            'headteacher_comment': ht['comment'] if ht else '',
            'classteacher_comment': ctcm['comment'] if ctcm else '',
            'classteacher_comment_by': ctcm['name_sf'] if ctcm else '',
            'subject_ranks': {subj: subject_ranks[stu['assessment_name']].get(subj, {}).get(stu['reg_no']) for subj in subject_names}
        })

        reports_list.append(stu)

        # Store marks for overall averaging
        for subject, mark in stu['marks'].items():
            if mark is not None:
                student_subject_marks[stu['reg_no']][subject].append(mark)

    # --- Overall per-student performance ---
    overall_map = {}
    for stu in reports_list:
        reg = stu['reg_no']
        if reg not in overall_map:
            overall_map[reg] = {
                'reg_no': reg,
                'full_name': stu['full_name'],
                'index_number': stu['index_number'],
                'image': stu['image'],
                'class_name': stu['class_name'],
                'stream_name': stu['stream_name'],
                'stream_id': stu['stream_id'],
                'total_class_size': stu['total_class_size'],
                'total_stream_size': stu['total_stream_size'],
                'class_teacher': stu['class_teacher'],
                'class_teacher_sign_image': stu['class_teacher_sign_image'],
                'headmaster_sign_image': stu['headmaster_sign_image'],
                'subject_averages': {},
                'subject_weights': {}
            }

        for subject in subject_names:
            marks = student_subject_marks[reg][subject]
            if marks:
                avg = int(round(sum(marks) / len(marks)))

                overall_map[reg]['subject_averages'][subject] = avg
                # Find the grade weight for this average
                cursor.execute(
                    "SELECT weight, grade_letter FROM grades WHERE %s BETWEEN min_score AND max_score LIMIT 1",
                    (avg,)
                )
                grade = cursor.fetchone()
                overall_map[reg]['subject_weights'][subject] = grade['weight'] if grade else 0
                # ADD THIS:
                if 'subject_average_grades' not in overall_map[reg]:
                    overall_map[reg]['subject_average_grades'] = {}
                overall_map[reg]['subject_average_grades'][subject] = grade['grade_letter'] if grade else ''

    for stu in overall_map.values():
        avgs = list(stu['subject_averages'].values())
        weights = list(stu['subject_weights'].values())
        if avgs:
            stu['overall_total'] = round(sum(avgs), 2)
            stu['overall_subject_average'] = round(sum(avgs) / len(avgs), 2)
            stu['aggregate'] = sum(weights)
        else:
            stu['overall_total'] = 0
            stu['overall_subject_average'] = 0
            stu['aggregate'] = 0

        # Division
        cursor.execute(
            "SELECT division_name FROM division WHERE %s BETWEEN min_score AND max_score LIMIT 1",
            (stu['aggregate'],)
        )
        dv = cursor.fetchone()
        stu['division'] = dv['division_name'] if dv else 'N/A'

        # --- Add overall class teacher and head teacher comments based on overall average ---
        # Class teacher comment
        cursor.execute("""
            SELECT cc.comment, u.name_sf
            FROM classteacher_comments cc
            LEFT JOIN users u ON cc.user_id = u.id
            WHERE cc.stream_id = %s AND %s BETWEEN cc.min_score AND cc.max_score
            ORDER BY cc.updated_at DESC LIMIT 1
        """, (stu['stream_id'], stu['overall_subject_average']))
        ctcm = cursor.fetchone()
        stu['classteacher_comment'] = ctcm['comment'] if ctcm else ''
        stu['classteacher_comment_by'] = ctcm['name_sf'] if ctcm else ''

        # Head teacher comment
        cursor.execute("""
            SELECT comment FROM headmaster_comments
            WHERE %s BETWEEN min_score AND max_score
            ORDER BY updated_at DESC LIMIT 1
        """, (stu['overall_subject_average'],))
        ht = cursor.fetchone()
        stu['headteacher_comment'] = ht['comment'] if ht else ''

    # --- Ranking ---
    overall_students = list(overall_map.values())
    overall_students.sort(key=lambda x: (-x['overall_subject_average'], x['full_name']))
    for idx, stu in enumerate(overall_students, 1):
        stu['class_position'] = idx

    by_stream = defaultdict(list)
    for stu in overall_students:
        by_stream[stu['stream_id']].append(stu)
    for group in by_stream.values():
        group.sort(key=lambda x: -x['overall_subject_average'])
        for idx, stu in enumerate(group, 1):
            stu['stream_position'] = idx

    # --- Assign class and stream positions for each assessment ---
    from collections import defaultdict

    # Group reports by assessment
    assessment_groups = defaultdict(list)
    for stu in reports_list:
        assessment_groups[stu['assessment_name']].append(stu)

    def assign_positions(students, pos_key):
        students.sort(key=lambda s: (-s['average_score'], s['full_name']))
        prev_score = None
        prev_position = 0
        for idx, student in enumerate(students, 1):
            if student['average_score'] != prev_score:
                prev_position = idx
            student[pos_key] = prev_position
            prev_score = student['average_score']

    for assessment, students in assessment_groups.items():
        # Assign class positions for this assessment
        assign_positions(students, 'class_position_assessment')

        # Assign stream positions for this assessment
        stream_groups = defaultdict(list)
        for stu in students:
            stream_groups[stu['stream_id']].append(stu)
        for group in stream_groups.values():
            assign_positions(group, 'stream_position_assessment')

    cursor.execute("SELECT grade_letter, min_score, max_score FROM grades ORDER BY weight ASC")
    grade_scale = cursor.fetchall()

    cursor.close()
    conn.close()

    return render_template(
        'eot_reports/vd_eot_reports.html',
        reports=reports_list,
        subject_names=sorted(subject_names),
        class_list=class_list,
        study_years=study_years,
        terms=terms,
        assessments=assessments,
        streams=streams,
        selected_class_id=class_id,
        selected_stream_id=stream_id,
        selected_study_year_id=year_id,
        selected_term_id=term_id,
        selected_assessment_name=assessment_names,
        segment='vd_eot_reports',
        overall_results=overall_students,
        grade_scale=grade_scale,
    )





from collections import defaultdict
from flask import request, render_template
