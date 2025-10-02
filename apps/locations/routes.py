# Assuming your blueprint is defined in an 'apps.locations' module 
# and aliased to 'locations_blueprint'
from apps.locations import blueprint 

from flask import render_template, request, redirect, url_for, flash, session
import mysql.connector
from werkzeug.utils import secure_filename
from mysql.connector import Error
from datetime import datetime
import os
import random
import logging
import re
from apps import get_db_connection
from jinja2 import TemplateNotFound


@blueprint.route('/locations') # Use the renamed blueprint
def locations():
    """Fetches all locations and renders the manage locations page."""
    connection = get_db_connection()
    cursor = connection.cursor(dictionary=True)

    # Fetch all locations from the database
    # The table name 'Locations' is correctly used from the database design
    cursor.execute('SELECT * FROM Locations ORDER BY LocationName ASC') 
    locations = cursor.fetchall()

    # Close the cursor and connection
    cursor.close()
    connection.close()

    # Renders the template specific to locations
    return render_template('locations/locations.html', locations=locations, segment='locations')









import re
# Assuming mysql.connector is imported or accessible

@blueprint.route('/add_location', methods=['GET', 'POST'])
def add_location():
    """Handles the adding of a new location."""
    if request.method == 'POST':
        # The location name is captured from the form field
        location_name = request.form.get('name') 

        # Validate input
        if not location_name:
            flash("Please fill out the form!", "warning")
        # Assuming location names can only contain letters, numbers, and spaces
        elif not re.match(r'^[A-Za-z0-9_ ]+$', location_name):
            flash('Location name must contain only letters and numbers!', "danger")
        else:
            connection = get_db_connection()
            cursor = connection.cursor(dictionary=True)

            try:
                # Check if the location already exists in the Locations table
                cursor.execute('SELECT * FROM Locations WHERE LocationName = %s', (location_name,))
                existing_location = cursor.fetchone()

                if existing_location:
                    flash("Location already exists!", "warning")
                else:
                    # Insert the new location into the Locations table
                    cursor.execute('INSERT INTO Locations (LocationName) VALUES (%s)', (location_name,))
                    connection.commit()
                    flash("Location successfully added!", "success")

            except mysql.connector.Error as err:
                flash(f"Database Error: {err}", "danger")
            except Exception as e:
                flash(f"An unexpected error occurred: {e}", "danger")
            finally:
                cursor.close()
                connection.close()
    
    # Renders the form for adding a location on GET request or after POST
    return render_template('locations/add_location.html', segment='add_location')




@blueprint.route('/edit_location/<int:location_id>', methods=['GET', 'POST'])
def edit_location(location_id):
    """Handles editing an existing location."""
    if request.method == 'POST':
        location_name = request.form['name']

        # NOTE: Input validation (like the regex check) should be added here as well for a complete solution.
        
        try:
            connection = get_db_connection()
            cursor = connection.cursor()

            # Update the LocationName in the Locations table based on LocationID
            cursor.execute("""
                UPDATE Locations
                SET LocationName = %s
                WHERE LocationID = %s
            """, (location_name, location_id))
            connection.commit()

            flash("Location updated successfully!", "success")
        except Exception as e:
            flash(f"Error: {str(e)}", "danger")
        finally:
            cursor.close()
            connection.close()

        # Assuming 'locations' is the function that renders the list of locations
        return redirect(url_for('locations_blueprint.locations'))

    elif request.method == 'GET':
        # Retrieve the location to pre-fill the form
        connection = get_db_connection()
        cursor = connection.cursor(dictionary=True)
        # Select from Locations table using the LocationID
        cursor.execute("SELECT LocationID, LocationName FROM Locations WHERE LocationID = %s", (location_id,))
        location = cursor.fetchone()
        cursor.close()
        connection.close()

        if location:
            # Pass the retrieved location object to the template
            return render_template('locations/edit_location.html', location=location, segment='locations')
        else:
            flash("Location not found.", "danger")
            return redirect(url_for('locations_blueprint.locations'))




@blueprint.route('/delete_location/<int:location_id>')
def delete_location(location_id):
    """Deletes a location from the database."""
    connection = get_db_connection()
    cursor = connection.cursor()

    try:
        # Delete the location from the Locations table
        cursor.execute('DELETE FROM Locations WHERE LocationID = %s', (location_id,))
        connection.commit()
        flash("Location deleted successfully.", "success")
        
        # NOTE: Database design should prevent deletion if assets are still linked (ON DELETE RESTRICT).
        # If the deletion fails due to a Foreign Key constraint, the Exception handler will catch it.
        
    except Exception as e:
        flash(f"Error: Cannot delete location. It may be linked to existing assets. ({str(e)})", "danger")
    finally:
        cursor.close()
        connection.close()

    # Assuming 'locations' is the function that renders the list of locations
    return redirect(url_for('locations_blueprint.locations'))