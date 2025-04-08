import os
import random
import logging
from flask import render_template, request, redirect, url_for, flash, current_app
from werkzeug.utils import secure_filename
from mysql.connector import Error
from apps import get_db_connection
from apps.products import blueprint
import mysql.connector


# Helper function to calculate formatted totals
def calculate_formatted_totals(products):
    total_sum = sum(product['total_price'] for product in products)
    total_price = sum(product['price'] for product in products)

    formatted_total_sum = "{:,.2f}".format(total_sum) if total_sum else '0.00'
    formatted_total_price = "{:,.2f}".format(total_price) if total_price else '0.00'

    for product in products:
        product['formatted_total_price'] = "{:,.2f}".format(product['total_price']) if product['total_price'] else '0.00'
        product['formatted_price'] = "{:,.2f}".format(product['price']) if product['price'] else '0.00'

    return formatted_total_sum, formatted_total_price


# Access the upload folder from the current Flask app configuration
def allowed_file(filename):
    """Check if the uploaded file has a valid extension."""
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in current_app.config['ALLOWED_EXTENSIONS']


# Route for the 'products' page
@blueprint.route('/products')
def products():
    """Renders the 'products' page."""
    connection = get_db_connection()
    cursor = connection.cursor(dictionary=True)

    try:
        cursor.execute(''' 
            SELECT *, (quantity * price) AS total_price
            FROM product_list
            ORDER BY name
        ''')
        products = cursor.fetchall()

        # Calculate totals and format them
        formatted_total_sum, formatted_total_price = calculate_formatted_totals(products)

    except Error as e:
        logging.error(f"Database error: {e}")
        flash("An error occurred while fetching products.", "error")
        return render_template('products/page-500.html'), 500

    finally:
        cursor.close()
        connection.close()

    return render_template('products/products.html',
                           formatted_total_price=formatted_total_price,
                           products=products,
                           formatted_total_sum=formatted_total_sum,
                           segment='products')


# Route to add a new product
@blueprint.route('/add_product', methods=['GET', 'POST'])
def add_product():
    connection = get_db_connection()
    cursor = connection.cursor(dictionary=True)

    # Fetch categories from the database
    cursor.execute('SELECT * FROM category_list')
    categories = cursor.fetchall()

    # Generate a random SKU
    random_num = random.randint(1005540, 9978799)

    # Ensure the SKU is unique
    while True:
        cursor.execute('SELECT * FROM product_list WHERE sku = %s', (random_num,))
        if not cursor.fetchone():
            break  # Unique SKU found
        random_num = random.randint(1005540, 9978799)

    if request.method == 'POST':
        # Retrieve form data
        category_id = request.form.get('category_id')
        sku = request.form.get('serial_no') or random_num
        price = request.form.get('price')
        name = request.form.get('name')
        description = request.form.get('description')
        quantity = 0
        reorder_level = request.form.get('reorder_level')

        # Check for existing product with the same name in the selected category
        cursor.execute('SELECT * FROM product_list WHERE category_id = %s AND name = %s', (category_id, name))
        existing_product = cursor.fetchone()

        if existing_product:
            flash("This product already exists in the selected category!", "danger")
        else:
            # Handle image upload
            image_file = request.files.get('image')
            image_filename = None  # Default if no image is uploaded

            if image_file and allowed_file(image_file.filename):
                filename = secure_filename(image_file.filename)
                image_filename = f"{random_num}_{filename}"  # Rename with SKU to avoid conflicts
                
                # Ensure the directory exists before saving the file
                image_folder = os.path.join(current_app.config['UPLOAD_FOLDER'])
                if not os.path.exists(image_folder):
                    os.makedirs(image_folder)  # Create the folder if it doesn't exist

                image_path = os.path.join(image_folder, image_filename)
                image_file.save(image_path)  # Save image

            # Insert new product into the database
            cursor.execute('''INSERT INTO product_list 
                (category_id, sku, price, name, description, quantity, reorder_level, image) 
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s)''',
                (category_id, sku, price, name, description, quantity, reorder_level, image_filename))
            
            connection.commit()
            flash("Product successfully added!", "success")

    cursor.close()
    connection.close()

    return render_template('products/add_product.html', random_num=random_num, categories=categories, segment='add_product')


# Route to edit an existing pupil
@blueprint.route('/edit_pupil/<int:pupil_id>', methods=['GET', 'POST'])
def edit_pupil(pupil_id):
    # Connect to the database
    connection = get_db_connection()
    cursor = connection.cursor(dictionary=True)

    # Fetch the pupil data from the database
    cursor.execute('SELECT * FROM pupils WHERE pupil_id = %s', (pupil_id,))
    pupil = cursor.fetchone()

    if not pupil:
        flash("Pupil not found!")
        return redirect(url_for('pupils_blueprint.pupils'))  # Redirect to pupils list page or home

    if request.method == 'POST':
        # Get the form data
        first_name = request.form.get('first_name')
        other_name = request.form.get('other_name')
        last_name = request.form.get('last_name')
        date_of_birth = request.form.get('date_of_birth')
        gender = request.form.get('gender')
        class_name = request.form.get('class')  # Renamed 'class' to 'class_name' to avoid conflict with Python keyword
        study_year = request.form.get('study_year')
        contact_number = request.form.get('contact_number')
        address = request.form.get('address')
        emergency_contact = request.form.get('emergency_contact')
        medical_info = request.form.get('medical_info')
        special_needs = request.form.get('special_needs')
        attendance_record = request.form.get('attendance_record')
        academic_performance = request.form.get('academic_performance')
        notes = request.form.get('notes')

        # Handle image upload
        image_filename = pupil['image']  # Default to existing image if no new one is uploaded
        image_file = request.files.get('image')

        if image_file and allowed_file(image_file.filename):
            filename = secure_filename(image_file.filename)
            image_filename = f"{pupil_id}_{filename}"  # Rename with pupil ID to avoid conflicts
            
            # Ensure the directory exists before saving the file
            image_folder = os.path.join(current_app.config['UPLOAD_FOLDER'])
            if not os.path.exists(image_folder):
                os.makedirs(image_folder)  # Create the folder if it doesn't exist

            image_path = os.path.join(image_folder, image_filename)
            image_file.save(image_path)  # Save new image

        # Update the pupil data in the database
        cursor.execute(''' 
            UPDATE pupils
            SET first_name = %s, other_name = %s, last_name = %s, date_of_birth = %s, gender = %s,
                class = %s, study_year = %s, contact_number = %s, address = %s, emergency_contact = %s,
                medical_info = %s, special_needs = %s, attendance_record = %s, academic_performance = %s,
                notes = %s, image = %s, updated_at = CURRENT_TIMESTAMP
            WHERE pupil_id = %s
        ''', (first_name, other_name, last_name, date_of_birth, gender, class_name, study_year, contact_number,
              address, emergency_contact, medical_info, special_needs, attendance_record, academic_performance,
              notes, image_filename, pupil_id))

        # Commit the transaction
        connection.commit()

        flash("Pupil updated successfully!")
        return redirect(url_for('pupils_blueprint.pupils'))  # Redirect to pupil list or home

    cursor.close()
    connection.close()

    return render_template('pupils/edit_pupil.html', pupil=pupil)







@blueprint.route('/delete_product/<string:get_id>')
def delete_product(get_id):
    connection = get_db_connection()
    cursor = connection.cursor(dictionary=True)
    cursor.execute('DELETE FROM product_list WHERE ProductID = %s', (get_id,))
    connection.commit()
    cursor.close()
    connection.close()
    return redirect(url_for('products_blueprint.products'))


@blueprint.route('/<template>')
def route_template(template):
    try:
        # Ensure the template ends with '.html' for correct render
        if not template.endswith('.html'):
            template += '.html'

        segment = get_segment(request)

        return render_template("products/" + template, segment=segment)

    except TemplateNotFound:
        return render_template('products/page-404.html'), 404

    except Exception as e:
        return render_template('products/page-500.html'), 500


def get_segment(request):
    """Extracts the last part of the URL path to identify the current page."""
    try:
        segment = request.path.split('/')[-1]
        if segment == '':
            segment = 'products'
        return segment

    except Exception as e:
        return None
