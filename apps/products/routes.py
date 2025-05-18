import os
import random
import logging
from flask import render_template, request, redirect, url_for, flash,jsonify,current_app
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






@blueprint.route('/products')
def products():
    """Renders the 'products' page with category and subcategory info."""
    try:
        connection = get_db_connection()
        cursor = connection.cursor(dictionary=True)

        query = '''
            SELECT 
                p.*, 
                c.name AS category_name,
                COALESCE(sc.name, 'None') AS sub_category_name
            FROM product_list p
            INNER JOIN category_list c ON p.category_id = c.CategoryID
            LEFT JOIN sub_category sc ON p.sub_category_id = sc.sub_category_id
            ORDER BY p.name
        '''
        cursor.execute(query)
        products = cursor.fetchall()

    except Error as e:
        logging.error(f"Database error while fetching products: {e}")
        flash("An error occurred while fetching products.", "error")
        return render_template('products/page-500.html'), 500

    finally:
        if cursor:
            cursor.close()
        if connection:
            connection.close()

    return render_template('products/products.html', products=products, segment='products')



from flask import jsonify

@blueprint.route('/sub_category_data')
def sub_category_data():
    try:
        connection = get_db_connection()
        cursor = connection.cursor(dictionary=True)  # Ensure dictionary cursor
        cursor.execute('''
            SELECT 
                sc.sub_category_id,
                sc.name AS sub_category_name,
                sc.description AS sub_category_description,
                c.CategoryID AS category_id,
                c.name AS category_name,
                c.Description AS category_description
            FROM sub_category sc
            JOIN category_list c ON sc.category_id = c.CategoryID
            ORDER BY sc.name
        ''')
        sub_categories_data = cursor.fetchall()
        return jsonify(sub_categories_data)
    except Exception as e:
        return jsonify({'error': str(e)}), 500





# Route to add a new product
@blueprint.route('/add_product', methods=['GET', 'POST'])
def add_product():
    connection = get_db_connection()
    cursor = connection.cursor(dictionary=True)

    # Fetch categories and sub-categories
    cursor.execute('SELECT * FROM category_list ORDER BY name')
    categories = cursor.fetchall()

    cursor.execute('SELECT * FROM sub_category ORDER BY name')
    sub_categories = cursor.fetchall()

    # Generate a random SKU
    random_num = random.randint(1005540, 9978799)

    # Ensure the SKU is unique
    while True:
        cursor.execute('SELECT * FROM product_list WHERE sku = %s', (random_num,))
        if not cursor.fetchone():
            break
        random_num = random.randint(1005540, 9978799)

    if request.method == 'POST':
        # Retrieve form data
        category_id = request.form.get('category_id')
        sub_category_id = request.form.get('sub_category_id') or None
        sku = request.form.get('serial_no') or random_num
        name = request.form.get('name')
        unique_number = request.form.get('unique_number')
        description = request.form.get('description')
        quantity = 0  # default for new product

        # Check for duplicate product
        cursor.execute('SELECT * FROM product_list WHERE category_id = %s AND name = %s', (category_id, name))
        existing_product = cursor.fetchone()

        if existing_product:
            flash("This product already exists in the selected category!", "danger")
        else:
            # Handle image upload
            image_file = request.files.get('image')
            image_filename = None

            if image_file and allowed_file(image_file.filename):
                filename = secure_filename(image_file.filename)
                image_filename = f"{random_num}_{filename}"
                
                image_folder = os.path.join(current_app.config['UPLOAD_FOLDER'])
                os.makedirs(image_folder, exist_ok=True)

                image_path = os.path.join(image_folder, image_filename)
                image_file.save(image_path)

            # Insert product without price
            cursor.execute('''
                INSERT INTO product_list 
                (category_id, sub_category_id, sku, name, unique_number, description, quantity, image) 
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            ''', (category_id, sub_category_id, sku, name, unique_number, description, quantity, image_filename))
            
            connection.commit()
            flash("Product successfully added!", "success")

    cursor.close()
    connection.close()

    return render_template(
        'products/add_product.html',
        categories=categories,
        sub_categories=sub_categories,
        random_num=random_num,
        segment='add_product'
    )






@blueprint.route('/subc_data', methods=['GET'])
def subc_data():
    category_id = request.args.get('category_id')  # Get category_id from query params
    connection = get_db_connection()
    cursor = connection.cursor(dictionary=True)
    
    # Fetch sub-categories matching the category_id
    cursor.execute('SELECT * FROM sub_category WHERE category_id = %s ORDER BY name', (category_id,))
    sub_categories = cursor.fetchall()
    
    connection.close()
    return jsonify(sub_categories)





# Route to edit an existing product
@blueprint.route('/edit_product/<int:product_id>', methods=['GET', 'POST'])
def edit_product(product_id):
    connection = get_db_connection()
    cursor = connection.cursor(dictionary=True)

    # Fetch product data
    cursor.execute('SELECT * FROM product_list WHERE ProductID = %s', (product_id,))
    product = cursor.fetchone()

    if not product:
        flash("Product not found!", "danger")
        return redirect(url_for('products_blueprint.products'))

    # Fetch categories and sub-categories
    cursor.execute('SELECT * FROM category_list ORDER BY name')
    categories = cursor.fetchall()

    cursor.execute('SELECT * FROM sub_category ORDER BY name')
    sub_categories = cursor.fetchall()

    if request.method == 'POST':
        # Form data
        category_id = request.form.get('category_id')
        sub_category_id = request.form.get('sub_category_id') or None
        sku = request.form.get('serial_no')
        name = request.form.get('name')
        unique_number = request.form.get('unique_number')
        description = request.form.get('description')

        # Image handling
        image_filename = product['image']  # keep current if no new upload
        image_file = request.files.get('image')

        if image_file and allowed_file(image_file.filename):
            filename = secure_filename(image_file.filename)
            image_filename = f"{product_id}_{filename}"
            image_folder = os.path.join(current_app.config['UPLOAD_FOLDER'])
            os.makedirs(image_folder, exist_ok=True)
            image_path = os.path.join(image_folder, image_filename)
            image_file.save(image_path)

        # Update product data
        cursor.execute('''
            UPDATE product_list
            SET category_id = %s,
                sub_category_id = %s,
                sku = %s,
                name = %s,
                unique_number = %s,
                description = %s,
                image = %s,
                updated_at = CURRENT_TIMESTAMP
            WHERE ProductID = %s
        ''', (category_id, sub_category_id, sku, name, unique_number, description, image_filename, product_id))

        connection.commit()
        flash("Product updated successfully!", "success")
        return redirect(url_for('products_blueprint.products'))

    # Close connections
    cursor.close()
    connection.close()

    return render_template(
        'products/edit_product.html',
        product=product,
        categories=categories,
        sub_categories=sub_categories,
        segment='products/edit_product.html'
    )








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
