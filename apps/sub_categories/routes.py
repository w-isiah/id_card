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
    connection = get_db_connection()
    cursor = connection.cursor(dictionary=True)

    # Load all categories for the dropdown
    cursor.execute("SELECT * FROM category_list")
    categories = cursor.fetchall()

    if request.method == 'POST':
        name = request.form.get('name', '').strip()
        category_id = request.form.get('category_id', '').strip()
        description = request.form.get('description', '').strip()
        print(name,category_id,description)

        # Validate inputs
        if not name or not category_id or not description:
            flash("All fields are required!", "warning")
        elif not re.match(r'^[A-Za-z0-9 _-]+$', name):
            flash("Sub-category name must contain only letters, numbers, spaces, dashes, or underscores.", "danger")
        else:
            try:
                # Check for duplicate sub-category under the same category
                check_query = "SELECT * FROM sub_category WHERE name = %s AND category_id = %s"
                cursor.execute(check_query, (name, category_id))
                existing = cursor.fetchone()

                if existing:
                    flash("Sub-category already exists for this category.", "warning")
                else:
                    # Insert the new sub-category with description
                    insert_query = "INSERT INTO sub_category (name, category_id, description) VALUES (%s, %s, %s)"
                    cursor.execute(insert_query, (name, category_id, description))
                    connection.commit()
                    flash("Sub-category successfully added!", "success")
                    return redirect(url_for('sub_categories_blueprint.add_sub_category'))

            except mysql.connector.Error as err:
                flash(f"Database error: {err}", "danger")
            finally:
                cursor.close()
                connection.close()

    return render_template("sub_categories/add_sub_category.html", categories=categories)







    

@blueprint.route('/edit_sub_category/<int:sub_category_id>', methods=['GET', 'POST'])
def edit_sub_category(sub_category_id):
    """Handles editing an existing sub-category, including changing its category_id."""
    connection = get_db_connection()
    cursor = connection.cursor(dictionary=True)

    # Fetch all categories for dropdown
    cursor.execute("SELECT * FROM category_list")
    categories = cursor.fetchall()

    # Retrieve current sub-category
    cursor.execute("SELECT * FROM sub_category WHERE sub_category_id = %s", (sub_category_id,))
    sub_category = cursor.fetchone()

    if not sub_category:
        cursor.close()
        connection.close()
        flash("Sub-category not found.", "danger")
        return redirect(url_for('sub_categories_blueprint.sub_categories'))

    if request.method == 'POST':
        name = request.form.get('name', '').strip()
        description = request.form.get('description', '').strip()
        category_id = request.form.get('category_id')

        print(name,category_id)

        if not name or not category_id:
            flash("Name and category are required!", "warning")
        else:
            try:
                cursor.execute("""
                    UPDATE sub_category
                    SET name = %s, description = %s, category_id = %s
                    WHERE sub_category_id = %s
                """, (name, description, category_id, sub_category_id))
                connection.commit()
                flash("Sub-category updated successfully!", "success")
                return redirect(url_for('sub_categories_blueprint.sub_categories'))
            except mysql.connector.Error as e:
                flash(f"Database error: {str(e)}", "danger")

    cursor.close()
    connection.close()

    return render_template(
        'sub_categories/edit_sub_category.html',
        categories=categories,
        sub_category=sub_category,
        segment='sub_categories'
    )




@blueprint.route('/delete_sub_category/<int:sub_category_id>')
def delete_sub_category(sub_category_id):
    """Deletes a sub-category from the database by its ID."""
    connection = get_db_connection()
    cursor = connection.cursor()

    try:
        # Ensure the sub-category exists before attempting deletion (optional but safe)
        cursor.execute('SELECT * FROM sub_category WHERE sub_category_id = %s', (sub_category_id,))
        result = cursor.fetchone()
        if not result:
            flash("Sub-category not found.", "warning")
        else:
            # Delete the sub-category
            cursor.execute('DELETE FROM sub_category WHERE sub_category_id = %s', (sub_category_id,))
            connection.commit()
            flash("Sub-category deleted successfully.", "success")
    except Exception as e:
        flash(f"Error deleting sub-category: {str(e)}", "danger")
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
