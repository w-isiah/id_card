from apps.sub_categories import blueprint
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







@blueprint.route('/sub_categories')
def sub_categories():
    """
    Fetch all sub-categories with their associated category names.
    Render the management page for sub-categories.
    """
    sub_categories = []
    try:
        connection = get_db_connection()
        cursor = connection.cursor(dictionary=True)
        
        query = """
            SELECT 
                sc.sub_category_id,
                sc.name AS sub_category_name,
                sc.description AS sub_category_description,
                cl.CategoryID,
                cl.name AS category_name
            FROM sub_category sc
            JOIN category_list cl ON sc.category_id = cl.CategoryID
        """
        cursor.execute(query)
        sub_categories = cursor.fetchall()
        
    except Exception as e:
        flash(f"Error fetching sub-categories: {str(e)}", "danger")
    finally:
        if cursor: cursor.close()
        if connection: connection.close()

    return render_template(
        'sub_categories/sub_categories.html',
        sub_categories=sub_categories,
        segment='sub_categories'
    )



@blueprint.route('/add_sub_category', methods=['GET', 'POST'])
def add_sub_category():
    """Handles the adding of a new sub_category."""
    connection = get_db_connection()
    cursor = connection.cursor(dictionary=True)
    cursor.execute("SELECT * FROM category_list")
    categories = cursor.fetchone()
    if request.method == 'POST':
        name = request.form.get('name')

        # Validate input
        if not name:
            flash("Please fill out the form!", "warning")
        elif not re.match(r'^[A-Za-z0-9_ ]+$', name):

            flash('sub_category name must contain only letters and numbers!', "danger")
        else:
            connection = get_db_connection()
            cursor = connection.cursor(dictionary=True)

            try:
                # Check if the sub_category already exists
                cursor.execute('SELECT * FROM sub_category_list WHERE name = %s', (name,))
                existing_sub_category = cursor.fetchone()

                if existing_sub_category:
                    flash("sub_category already exists!", "warning")
                else:
                    # Insert the new sub_category into the database
                    cursor.execute('INSERT INTO sub_category (name) VALUES (%s)', (name,))
                    connection.commit()
                    flash("sub_category successfully added!", "success")

            except mysql.connector.Error as err:
                flash(f"Error: {err}", "danger")
            finally:
                cursor.close()
                connection.close()

    return render_template('sub_categories/add_sub_category.html',categories=categories, segment='add_sub_category')




    


@blueprint.route('/edit_sub_category/<int:sub_category_id>', methods=['GET', 'POST'])
def edit_sub_category(sub_category_id):
    """Handles editing an existing sub_category."""
    if request.method == 'POST':
        name = request.form['name']

        try:
            connection = get_db_connection()
            cursor = connection.cursor()

            # Update sub_category in the database
            cursor.execute("""
                UPDATE sub_category_list
                SET name = %s
                WHERE sub_categoryID = %s
            """, (name, sub_category_id))
            connection.commit()

            flash("sub_category updated successfully!", "success")
        except Exception as e:
            flash(f"Error: {str(e)}", "danger")
        finally:
            cursor.close()
            connection.close()

        return redirect(url_for('sub_categories_blueprint.sub_categories'))

    elif request.method == 'GET':
        # Retrieve the sub_category to pre-fill the form
        connection = get_db_connection()
        cursor = connection.cursor(dictionary=True)
        cursor.execute("SELECT * FROM sub_category_list WHERE sub_categoryID = %s", (sub_category_id,))
        sub_category = cursor.fetchone()
        cursor.close()
        connection.close()

        if sub_category:
            return render_template('sub_categories/edit_sub_category.html', sub_category=sub_category,segment='sub_categories')
        else:
            flash("sub_category not found.", "danger")
            return redirect(url_for('sub_categories_blueprint.sub_categories'))


@blueprint.route('/delete_sub_category/<int:sub_category_id>')
def delete_sub_category(sub_category_id):
    """Deletes a sub_category from the database."""
    connection = get_db_connection()
    cursor = connection.cursor()

    try:
        # Delete the sub_category with the specified ID
        cursor.execute('DELETE FROM sub_category_list WHERE sub_categoryID = %s', (sub_category_id,))
        connection.commit()
        flash("sub_category deleted successfully.", "success")
    except Exception as e:
        flash(f"Error: {str(e)}", "danger")
    finally:
        cursor.close()
        connection.close()

    return redirect(url_for('sub_categories_blueprint.sub_categories'))




@blueprint.route('/<template>')
def route_template(template):

    try:

        if not template.endswith('.html'):
            template += '.html'

        # Detect the current page
        segment = get_segment(request)

        # Serve the file (if exists) from app/templates/home/FILE.html
        return render_template("sub_categories/" + template, segment=segment)

    except TemplateNotFound:
        return render_template('home/page-404.html'), 404

    except:
        return render_template('home/page-500.html'), 500


# Helper - Extract current page name from request
def get_segment(request):

    try:

        segment = request.path.split('/')[-1]

        if segment == '':
            segment = 'sub_categories'

        return segment

    except:
        return None
