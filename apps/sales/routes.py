from flask import render_template, request, jsonify, current_app,session
from datetime import datetime
import mysql.connector
import traceback
from apps import get_db_connection
from apps.sales import blueprint
import traceback


@blueprint.route('/sales', methods=['GET'])
def sales():
    try:
        connection = get_db_connection()
        cursor = connection.cursor(dictionary=True)

        # Fetch customer data
        cursor.execute('SELECT * FROM customer_list ORDER BY name')
        customers = cursor.fetchall()

        # Fetch product data with category information using a JOIN
        cursor.execute('''
            SELECT p.*, c.name AS category_name, c.description AS category_description
            FROM product_list p
            INNER JOIN category_list c ON p.category_id = c.CategoryID
            ORDER BY name
        ''')
        products = cursor.fetchall()

    except mysql.connector.Error as e:
        current_app.logger.error(f"Database error: {e}")
        return "Database error", 500
    finally:
        if cursor:
            cursor.close()
        if connection:
            connection.close()

    return render_template('sales/sale.html', customers=customers, products=products, segment='sales')










@blueprint.route('/save_sale', methods=['POST'])
def save_sale():
    connection = None
    cursor = None
    try:
        # Ensure the user is logged in
        if 'id' not in session:
            return jsonify({'message': 'You must be logged in to make a sale.'}), 401

        user_id = session['id']
        data = request.get_json()
        customer_id = data.get('customer_id')
        items = data.get('cart_items')

        current_app.logger.debug(f"Received data: {data}")

        # Validate input
        if not customer_id or not items or len(items) == 0:
            return jsonify({'message': 'Customer ID and cart items are required.'}), 400

        # Establish DB connection
        connection = get_db_connection()
        cursor = connection.cursor(dictionary=True)

        # Start transaction
        connection.start_transaction()

        # Process each cart item
        for item in items:
            product_id = item.get('product_id')
            quantity = item.get('quantity')

            current_app.logger.debug(f"Processing item: {item}")

            if not product_id or not quantity or quantity <= 0:
                return jsonify({'message': f'Invalid item or quantity for product ID {product_id}.'}), 400

            # Insert into sales table
            cursor.execute(
                'INSERT INTO sales (ProductID, customer_id, qty) VALUES (%s, %s, %s)',
                (product_id, customer_id, quantity)
            )

            # Update product stock
            cursor.execute(
                'UPDATE product_list SET quantity = quantity - %s WHERE ProductID = %s',
                (quantity, product_id)
            )

            # Log inventory change
            cursor.execute("""
                INSERT INTO inventory_logs (product_id, quantity_change, reason, log_date, user_id)
                VALUES (%s, %s, %s, NOW(), %s)
            """, (product_id, -quantity, 'sale', user_id))

        # Commit all changes
        connection.commit()
        return jsonify({'message': 'Stock out recorded and inventory updated successfully.'}), 201

    except Exception as e:
        if connection:
            connection.rollback()

        current_app.logger.error(f"Error: {e}")
        current_app.logger.error(traceback.format_exc())
        return jsonify({'message': 'Error occurred: ' + str(e)}), 500

    finally:
        if cursor:
            cursor.close()
        if connection:
            connection.close()








@blueprint.route('/sales_view', methods=['GET', 'POST'])
def sales_view():
    start_date = datetime.now().strftime('%Y-%m-%d')
    end_date = datetime.now().strftime('%Y-%m-%d')

    if request.method == 'POST':
        start_date = request.form.get('start_date') or start_date
        end_date = request.form.get('end_date') or end_date

    connection = get_db_connection()
    cursor = connection.cursor(dictionary=True)

    # Get sales details (excluding price/discount)
    query_sales_details = """
        SELECT 
            s.salesID, 
            p.name AS product_name, 
            c.name AS customer_name,  
            s.qty, 
            s.date_updated
        FROM 
            sales s
        INNER JOIN 
            product_list p ON s.ProductID = p.ProductID
        INNER JOIN 
            customer_list c ON s.customer_id = c.CustomerID 
        WHERE 
            DATE(s.date_updated) BETWEEN %s AND %s
    """

    # Get total quantity sold
    query_sales_quantity = """
        SELECT 
            SUM(s.qty) AS total_quantity
        FROM 
            sales s
        INNER JOIN 
            product_list p ON s.ProductID = p.ProductID
        WHERE 
            DATE(s.date_updated) BETWEEN %s AND %s
    """

    cursor.execute(query_sales_details, (start_date, end_date))
    sales = cursor.fetchall()

    cursor.execute(query_sales_quantity, (start_date, end_date))
    total_quantity = cursor.fetchone()['total_quantity']

    formatted_total_quantity = "{:,}".format(total_quantity) if total_quantity else '0'

    cursor.close()
    connection.close()

    return render_template(
        'sales/sales_view.html',
        sales=sales,
        total_quantity=formatted_total_quantity,
        start_date=start_date,
        end_date=end_date,
        segment='sales_view'
    )






@blueprint.route('/discount_percentage', methods=['GET', 'POST'])
def discount_percentage():
    if request.method == 'POST':
        try:
            original_price = float(request.form['original_price'])
            discounted_price = float(request.form['discounted_price'])

            if original_price <= 0 or discounted_price < 0:
                raise ValueError("Prices must be positive numbers.")

            discount_amount = original_price - discounted_price
            discount_percentage = (discount_amount / original_price) * 100

            return render_template('sales/discount_percentage.html',
                                   original_price=original_price, 
                                   discounted_price=discounted_price,
                                   discount_amount=discount_amount,
                                   discount_percentage=discount_percentage)
        except (ValueError, TypeError):
            error = "Please enter valid numeric values."
            return render_template('sales/discount_percentage.html',  error=error)

    return render_template('sales/discount_percentage.html')


@blueprint.route('/<template>')
def route_template(template):
    """Renders a dynamic template page."""
    try:
        if not template.endswith('.html'):
            template += '.html'

        segment = get_segment(request)

        return render_template(f"sales/{template}", segment=segment)

    except TemplateNotFound:
        return render_template('home/page-404.html'), 404

    except Exception as e:
        return render_template('home/page-500.html'), 500


def get_segment(request):
    """Extracts the last part of the URL to determine the current page."""
    try:
        segment = request.path.split('/')[-1]
        return segment if segment else 'sales'
    except Exception:
        return None
