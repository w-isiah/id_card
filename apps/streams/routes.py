from apps.streams import blueprint
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


@blueprint.route('/streams')
def streams():
    """Fetches all streams with class names, room names, and renders the manage streams page."""
    try:
        connection = get_db_connection()
        cursor = connection.cursor(dictionary=True)

        # Join streams with classes and rooms to get class_name and room_name
        cursor.execute("""
            SELECT 
                stream.stream_id,
                stream.stream_name,
                stream.description,
                stream.created_at,
                stream.updated_at,
                stream.class_id,
                classes.class_name,
                rooms.room_name  -- Adding room_name from rooms table
            FROM stream
            JOIN classes ON stream.class_id = classes.class_id
            JOIN rooms ON stream.room_id = rooms.room_id  -- Joining the rooms table
        """)
        streams = cursor.fetchall()

    except Exception as e:
        print(f"Database error: {e}")
        streams = []

    finally:
        cursor.close()
        connection.close()

    return render_template('streams/streams.html', streams=streams, segment='streams')





@blueprint.route('/add_stream', methods=['GET', 'POST'])
def add_stream():
    """Handles adding a new stream to the database."""
    connection = get_db_connection()
    cursor = connection.cursor(dictionary=True)

    # Fetch the list of classes for the dropdown
    cursor.execute('SELECT class_id, class_name FROM classes')
    classes = cursor.fetchall()

    # Fetch the list of rooms for the dropdown
    cursor.execute('SELECT room_id, room_name FROM rooms')
    rooms = cursor.fetchall()

    if request.method == 'POST':
        stream_name = request.form.get('stream_name')
        class_id = request.form.get('class_id')
        description = request.form.get('description')
        room_id = request.form.get('room_id')  # Room ID from form
        user_id = session.get('id')  # Get the user ID from the session

        # Validate inputs
        if not stream_name or not class_id or not room_id:
            flash("Please fill out all required fields!", "warning")
        elif not re.match(r'^[A-Za-z0-9_ ]+$', stream_name):
            flash("Stream name must contain only letters, numbers, and spaces!", "danger")
        else:
            try:
                # Check if the stream already exists for this class
                cursor.execute(
                    'SELECT * FROM stream WHERE stream_name = %s AND class_id = %s',
                    (stream_name, class_id)
                )
                existing_stream = cursor.fetchone()

                if existing_stream:
                    flash("Stream already exists for this class!", "warning")
                else:
                    # Check if the room is already assigned (for any class or stream)
                    cursor.execute(
                        'SELECT * FROM room_assignment WHERE room_id = %s',
                        (room_id,)
                    )
                    existing_assignment = cursor.fetchone()

                    if existing_assignment:
                        flash("Room is already assigned!", "warning")
                        return redirect(url_for('streams_blueprint.add_stream'))
                    else:
                        # Insert the new stream into the database
                        cursor.execute(
                            'INSERT INTO stream (stream_name, class_id, description, room_id) VALUES (%s, %s, %s, %s)',
                            (stream_name, class_id, description, room_id)
                        )
                        connection.commit()

                        # Insert into room_assignment
                        stream_id = cursor.lastrowid
                        cursor.execute(
                            'INSERT INTO room_assignment (room_id, user_id, assigned_to_type, assigned_to_id) VALUES (%s, %s, %s, %s)',
                            (room_id, user_id, 'stream', stream_id)
                        )
                        connection.commit()

                        flash("Stream successfully added!", "success")
                        return redirect(url_for('streams_blueprint.streams'))

            except Exception as err:
                flash(f"Error: {err}", "danger")

    # Close the cursor and connection
    cursor.close()
    connection.close()

    # Render the template with the classes and rooms for the dropdown
    return render_template('streams/add_stream.html', classes=classes, rooms=rooms, segment='streams')







@blueprint.route('/edit_stream/<int:stream_id>', methods=['GET', 'POST'])
def edit_stream(stream_id):
    """Handles editing an existing stream."""
    connection = get_db_connection()
    cursor = connection.cursor(dictionary=True)

    if request.method == 'POST':
        # Retrieve the form data
        stream_name = request.form['stream_name']
        description = request.form['description']
        room_id = request.form['room']  # room_id instead of room name

        try:
            # Fetch existing stream data to get class_id
            cursor.execute("SELECT * FROM stream WHERE stream_id = %s", (stream_id,))
            stream_data = cursor.fetchone()

            if not stream_data:
                flash("Stream not found.", "danger")
                return redirect(url_for('streams_blueprint.streams'))

            class_id = stream_data['class_id']
            current_room_id = stream_data['room_id']

            # Input validation
            if not stream_name:
                flash("Stream name is required!", "warning")
                return redirect(url_for('streams_blueprint.edit_stream', stream_id=stream_id))

            if not re.match(r'^[A-Za-z0-9_ ]+$', stream_name):
                flash("Stream name must contain only letters, numbers, and spaces!", "danger")
                return redirect(url_for('streams_blueprint.edit_stream', stream_id=stream_id))

            # Check for duplicate stream name in the same class
            cursor.execute(
                'SELECT * FROM stream WHERE stream_name = %s AND class_id = %s AND stream_id != %s',
                (stream_name, class_id, stream_id)
            )
            existing_stream = cursor.fetchone()
            if existing_stream:
                flash("A stream with this name already exists in the class!", "warning")
                return redirect(url_for('streams_blueprint.edit_stream', stream_id=stream_id))

            # Check if the room is already assigned elsewhere (excluding current assignment)
            cursor.execute("""
                SELECT * FROM room_assignment
                WHERE room_id = %s AND NOT (assigned_to_type = 'stream' AND assigned_to_id = %s)
            """, (room_id, stream_id))
            existing_assignment = cursor.fetchone()

            if existing_assignment:
                flash("Room is already assigned!", "warning")
                return redirect(url_for('streams_blueprint.edit_stream', stream_id=stream_id))

            # Update stream record
            cursor.execute(
                'UPDATE stream SET stream_name = %s, description = %s, room_id = %s WHERE stream_id = %s',
                (stream_name, description, room_id, stream_id)
            )
            connection.commit()

            # Update room_assignment
            cursor.execute("""
                UPDATE room_assignment
                SET room_id = %s
                WHERE assigned_to_type = 'stream' AND assigned_to_id = %s
            """, (room_id, stream_id))
            connection.commit()

            flash("Stream updated successfully!", "success")

        except Exception as e:
            flash(f"Error: {str(e)}", "danger")
        finally:
            cursor.close()
            connection.close()

        return redirect(url_for('streams_blueprint.streams'))

    else:
        # GET method
        cursor.execute("""
            SELECT s.*, c.class_name, c.year, c.teacher_in_charge, r.room_name
            FROM stream s
            JOIN classes c ON s.class_id = c.class_id
            LEFT JOIN rooms r ON s.room_id = r.room_id
            WHERE s.stream_id = %s
        """, (stream_id,))
        stream_data = cursor.fetchone()
        cursor.close()
        connection.close()

        if stream_data:
            connection = get_db_connection()
            cursor = connection.cursor(dictionary=True)
            cursor.execute("SELECT * FROM rooms")
            rooms = cursor.fetchall()
            cursor.close()
            connection.close()

            return render_template('streams/edit_streams.html', stream=stream_data, rooms=rooms, segment='streams')
        else:
            flash("Stream not found.", "danger")
            return redirect(url_for('streams_blueprint.streams'))







@blueprint.route('/delete_stream/<int:stream_id>', methods=['GET'])
def delete_stream(stream_id):
    """Deletes a stream from the database."""
    connection = get_db_connection()
    cursor = connection.cursor()

    try:
        # Delete the stream with the given ID
        cursor.execute('DELETE FROM stream WHERE stream_id = %s', (stream_id,))
        connection.commit()
        flash("Stream deleted successfully.", "success")
    except Exception as e:
        flash(f"Error while deleting stream: {str(e)}", "danger")
    finally:
        cursor.close()
        connection.close()

    return redirect(url_for('streams_blueprint.streams'))




@blueprint.route('/<template>')
def route_template(template):

    try:

        if not template.endswith('.html'):
            template += '.html'

        # Detect the current page
        segment = get_segment(request)

        # Serve the file (if exists) from app/templates/home/FILE.html
        return render_template("streams/" + template, segment=segment)

    except TemplateNotFound:
        return render_template('home/page-404.html'), 404

    except:
        return render_template('home/page-500.html'), 500


# Helper - Extract current page name from request
def get_segment(request):

    try:

        segment = request.path.split('/')[-1]

        if segment == '':
            segment = 'streams'

        return segment

    except:
        return None
