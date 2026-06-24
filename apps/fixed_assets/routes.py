from apps.fixed_assets import blueprint
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

# --- HELPER FUNCTION TO FETCH LOOKUP DATA ---
def fetch_lookup_data(cursor):
    """Fetches locations, suppliers, categories, and users for dropdowns."""
    data = {}

    # 1. Locations
    cursor.execute('SELECT LocationID, LocationName FROM locations ORDER BY LocationName')
    data['locations'] = cursor.fetchall()

    # 2. Suppliers
    cursor.execute('SELECT SupplierID, Name FROM Suppliers ORDER BY Name')
    data['suppliers'] = cursor.fetchall()

    # 3. Categories (Using 'category_list')
    cursor.execute('SELECT CategoryID, Name FROM category_list ORDER BY Name')
    data['categories'] = cursor.fetchall()

    # 4. Users (for Custodians)
    cursor.execute('SELECT id, username, first_name, last_name FROM users ORDER BY last_name')
    data['users'] = cursor.fetchall()

    return data


# ---


# LIST ASSETS (FIXED ASSETS REGISTER)
@blueprint.route('/assets')
def assets():
    """Fetches all fixed assets and renders the main register page."""
    connection = get_db_connection()
    cursor = connection.cursor(dictionary=True)

    try:
        # Fetch all assets, including names from linked tables and new accounting metrics
        cursor.execute("""
            SELECT
                fa.AssetID, 
                fa.IdentificationNumber, 
                fa.SerialNumber,
                fa.AssetDescription, 
                fa.AssetCondition,
                fa.AssetStatus,
                fa.quantity,
                fa.AcquisitionDate, 
                fa.CostValuation, 
                fa.ResidualValue,
                fa.UsefulLife_Years,
                fa.DepreciationMethod,
                fa.AccumulatedDepreciation,
                (fa.CostValuation - fa.AccumulatedDepreciation) AS NetBookValue,
                fa.OwnershipStatus,
                loc.LocationName, 
                cat.Name AS CategoryName,
                sup.Name AS SupplierName,
                CONCAT(u.first_name, ' ', u.last_name) AS CustodianName
            FROM fixed_assets fa
            JOIN locations loc ON fa.LocationID = loc.LocationID
            JOIN category_list cat ON fa.CategoryID = cat.CategoryID
            LEFT JOIN Suppliers sup ON fa.SupplierID = sup.SupplierID
            LEFT JOIN users u ON fa.CustodianID = u.id
            ORDER BY fa.IdentificationNumber ASC
        """)
        assets_list = cursor.fetchall()

    except Exception as e:
        logging.error(f"Database error fetching assets: {e}")
        flash("Could not fetch assets due to a database error. Please verify database table constraints.", "danger")
        assets_list = []

    finally:
        cursor.close()
        connection.close()

    # Renders the template specific to assets
    return render_template('assets/assets.html', assets=assets_list, segment='assets')

# ---

# ADD ASSET (FIXED ASSETS)




# ADD ASSET (FIXED ASSETS)
@blueprint.route('/add_asset', methods=['GET', 'POST'])
def add_asset():
    """Handles the adding of a new fixed asset."""
    connection = get_db_connection()
    cursor = connection.cursor(dictionary=True)
    lookup_data = fetch_lookup_data(cursor)  # Get lookup data for GET/POST failure
    cursor.close()
    connection.close()

    if request.method == 'POST':
        # 1. Capture MANDATORY form data (Mapped directly to your HTML form names)
        identification_number = request.form.get('identification_number')
        asset_description = request.form.get('asset_description')
        acquisition_date = request.form.get('acquisition_date')
        cost_valuation = request.form.get('cost_valuation')
        location_id = request.form.get('location_id')
        category_id = request.form.get('category_id')
        ownership_status = request.form.get('ownership_status')
        asset_condition = request.form.get('asset_condition')
        asset_status = request.form.get('asset_status')
        quantity = request.form.get('quantity')

        # 2. Capture OPTIONAL/ACCOUNTING form data
        serial_number = request.form.get('serial_number') or None
        residual_value = request.form.get('residual_value') or '0.00'
        useful_life_years = request.form.get('useful_life_years') or None
        depreciation_method = request.form.get('depreciation_method') or 'Straight Line'
        depreciation_start_date = request.form.get('depreciation_start_date') or None
        supplier_id = request.form.get('supplier_id') or None
        custodian_id = request.form.get('custodian_id') or None

        # Simple Mandatory Field Validation
        if not all([identification_number, asset_description, acquisition_date, cost_valuation, 
                    location_id, category_id, ownership_status, asset_condition, asset_status, quantity]):
            flash("Please fill in all mandatory fields.", "warning")
            connection_fail = get_db_connection()
            cursor_fail = connection_fail.cursor(dictionary=True)
            lookup_data_fail = fetch_lookup_data(cursor_fail)
            cursor_fail.close()
            connection_fail.close()
            return render_template('assets/add_asset.html', **lookup_data_fail, segment='add_asset')

        # Database connection for validation and insertion
        connection = get_db_connection()
        cursor = connection.cursor()

        try:
            # Check if IdentificationNumber already exists
            cursor.execute('SELECT AssetID FROM fixed_assets WHERE IdentificationNumber = %s', (identification_number,))
            if cursor.fetchone():
                flash(f"Asset with ID '{identification_number}' already exists!", "warning")
                connection_fail = get_db_connection()
                cursor_fail = connection_fail.cursor(dictionary=True)
                lookup_data_fail = fetch_lookup_data(cursor_fail)
                cursor_fail.close()
                connection_fail.close()
                return render_template('assets/add_asset.html', **lookup_data_fail, segment='add_asset')

            # Clean and parse numerical values safely
            try:
                cost = float(cost_valuation)
                residual = float(residual_value)
                qty = int(quantity)
                useful_life = int(useful_life_years) if useful_life_years else None
            except ValueError:
                flash("Cost, Residual Value, Quantity, and Useful Life must contain valid numeric configurations.", "danger")
                connection_fail = get_db_connection()
                cursor_fail = connection_fail.cursor(dictionary=True)
                lookup_data_fail = fetch_lookup_data(cursor_fail)
                cursor_fail.close()
                connection_fail.close()
                return render_template('assets/add_asset.html', **lookup_data_fail, segment='add_asset')

            # Insert the new asset into the fixed_assets table matching your exact MariaDB columns
            cursor.execute("""
                INSERT INTO fixed_assets (
                    IdentificationNumber, SerialNumber, AssetDescription, CategoryID, 
                    AcquisitionDate, DepreciationStartDate, CostValuation, ResidualValue, 
                    LocationID, SupplierID, CustodianID, OwnershipStatus, 
                    AssetCondition, AssetStatus, UsefulLife_Years, DepreciationMethod, quantity
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """, (
                identification_number, serial_number, asset_description, category_id,
                acquisition_date, depreciation_start_date, cost, residual,
                location_id, supplier_id, custodian_id, ownership_status,
                asset_condition, asset_status, useful_life, depreciation_method, qty
            ))
            
            connection.commit()
            flash(f"Asset '{asset_description}' successfully added!", "success")
            return redirect(url_for('fixed_assets_blueprint.assets'))

        except mysql.connector.Error as err:
            logging.error(f"Database Error adding asset: {err}")
            flash(f"Database Error: Could not add asset. {err}", "danger")
            connection_fail = get_db_connection()
            cursor_fail = connection_fail.cursor(dictionary=True)
            lookup_data_fail = fetch_lookup_data(cursor_fail)
            cursor_fail.close()
            connection_fail.close()
            return render_template('assets/add_asset.html', **lookup_data_fail, segment='add_asset')

        except Exception as e:
            logging.error(f"Unexpected error adding asset: {e}")
            flash(f"An unexpected error occurred: {e}", "danger")
            connection_fail = get_db_connection()
            cursor_fail = connection_fail.cursor(dictionary=True)
            lookup_data_fail = fetch_lookup_data(cursor_fail)
            cursor_fail.close()
            connection_fail.close()
            return render_template('assets/add_asset.html', **lookup_data_fail, segment='add_asset')

        finally:
            cursor.close()
            connection.close()

    # GET request execution
    return render_template('assets/add_asset.html', **lookup_data, segment='add_asset')



    
# ---

# EDIT ASSET (FIXED ASSETS)
@blueprint.route('/edit_asset/<int:asset_id>', methods=['GET', 'POST'])
def edit_asset(asset_id):
    """Handles editing an existing fixed asset."""

    # Internal helper function to avoid repeating asset query steps across failure blocks
    def get_current_asset():
        conn = get_db_connection()
        curr = conn.cursor(dictionary=True)
        curr.execute("SELECT * FROM fixed_assets WHERE AssetID = %s", (asset_id,))
        record = curr.fetchone()
        curr.close()
        conn.close()
        return record

    # Fetch fresh drops lookup configurations
    connection_lookup = get_db_connection()
    cursor_lookup = connection_lookup.cursor(dictionary=True)
    lookup_data = fetch_lookup_data(cursor_lookup)
    cursor_lookup.close()
    connection_lookup.close()

    if request.method == 'POST':
        # 1. Capture Form Parameters (Synced perfectly with updated form definitions)
        identification_number = request.form.get('identification_number')
        asset_description = request.form.get('asset_description')
        acquisition_date = request.form.get('acquisition_date')
        cost_valuation = request.form.get('cost_valuation')
        location_id = request.form.get('location_id')
        category_id = request.form.get('category_id')
        ownership_status = request.form.get('ownership_status')
        asset_condition = request.form.get('asset_condition')
        asset_status = request.form.get('asset_status')
        quantity = request.form.get('quantity')

        # 2. Capture Optional / Financial Parameters
        serial_number = request.form.get('serial_number') or None
        residual_value = request.form.get('residual_value') or '0.00'
        useful_life_years = request.form.get('useful_life_years') or None
        depreciation_method = request.form.get('depreciation_method') or 'Straight Line'
        depreciation_start_date = request.form.get('depreciation_start_date') or None
        supplier_id = request.form.get('supplier_id') or None
        custodian_id = request.form.get('custodian_id') or None

        # Mandatory Request Validation Checks
        if not all([identification_number, asset_description, acquisition_date, cost_valuation, 
                    location_id, category_id, ownership_status, asset_condition, asset_status, quantity]):
            flash('Invalid or missing mandatory asset details.', "danger")
            return render_template('assets/edit_asset.html', asset=get_current_asset(), **lookup_data, segment='assets')

        try:
            # Typecasting configurations cleanly
            cost = float(cost_valuation)
            residual = float(residual_value)
            qty = int(quantity)
            useful_life = int(useful_life_years) if useful_life_years else None
        except ValueError:
            flash("Cost, Residual, Quantity, and Useful Life must contain valid metric formats.", "danger")
            return render_template('assets/edit_asset.html', asset=get_current_asset(), **lookup_data, segment='assets')

        try:
            connection = get_db_connection()
            cursor = connection.cursor()

            # Execute transactional UPDATE statement mapping exactly to database constraints
            cursor.execute("""
                UPDATE fixed_assets
                SET IdentificationNumber = %s, SerialNumber = %s, AssetDescription = %s,
                    CategoryID = %s, AcquisitionDate = %s, DepreciationStartDate = %s, 
                    CostValuation = %s, ResidualValue = %s, LocationID = %s, 
                    SupplierID = %s, CustodianID = %s, OwnershipStatus = %s, 
                    AssetCondition = %s, AssetStatus = %s, UsefulLife_Years = %s, 
                    DepreciationMethod = %s, quantity = %s
                WHERE AssetID = %s
            """, (
                identification_number, serial_number, asset_description, category_id, 
                acquisition_date, depreciation_start_date, cost, residual, location_id, 
                supplier_id, custodian_id, ownership_status, asset_condition, asset_status, 
                useful_life, depreciation_method, qty, asset_id
            ))
            connection.commit()

            flash("Asset details updated successfully!", "success")
            return redirect(url_for('fixed_assets_blueprint.assets'))

        except Exception as e:
            logging.error(f"Database/Runtime error processing modification update trace: {e}")
            flash(f"Error Processing Update request: {e}", "danger")
            return render_template('assets/edit_asset.html', asset=get_current_asset(), **lookup_data, segment='assets')

        finally:
            if 'connection' in locals() and connection.is_connected():
                cursor.close()
                connection.close()

    elif request.method == 'GET':
        asset = get_current_asset()
        if asset:
            return render_template('assets/edit_asset.html', asset=asset, **lookup_data, segment='assets')
        else:
            flash("Requested ledger record asset not found.", "danger")
            return redirect(url_for('fixed_assets_blueprint.assets'))
# ---

# DELETE ASSET (FIXED ASSETS)
@blueprint.route('/delete_asset/<int:asset_id>')
def delete_asset(asset_id):
    """Deletes a fixed asset from the database."""
    connection = get_db_connection()
    cursor = connection.cursor()

    try:
        # Get asset description for flash message before deleting
        cursor.execute('SELECT AssetDescription FROM fixed_assets WHERE AssetID = %s', (asset_id,))
        asset_info = cursor.fetchone()
        asset_description = asset_info[0] if asset_info else "the asset"

        # Delete the asset
        cursor.execute('DELETE FROM fixed_assets WHERE AssetID = %s', (asset_id,))
        connection.commit()
        flash(f"Asset '{asset_description}' deleted successfully.", "success")

    except Exception as e:
        # Handle Foreign Key errors if the asset is linked to other audit/disposal logs
        flash(f"Error: Cannot delete asset. It may be linked to audit history or other records. ({str(e)})", "danger")
    finally:
        cursor.close()
        connection.close()

    # Redirect to the assets list
    return redirect(url_for('fixed_assets_blueprint.assets'))
