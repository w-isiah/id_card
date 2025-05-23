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





@blueprint.route('/o_sales', methods=['GET'])
def o_sales():
    try:
        user_id = session.get('id')
        if not user_id:
            flash("Please log in to view sales.", "warning")
            return render_template('auth/login.html')

        connection = get_db_connection()
        cursor = connection.cursor(dictionary=True)

        # Fetch customer data
        cursor.execute('SELECT * FROM customer_list ORDER BY name')
        customers = cursor.fetchall()

        # Fetch ONLY products the user is allowed to see via sub_category/other_roles
        cursor.execute('''
            SELECT 
                p.*, 
                c.name AS category_name, 
                c.description AS category_description
            FROM product_list p
            INNER JOIN category_list c ON p.category_id = c.CategoryID
            INNER JOIN other_roles orl ON orl.sub_category_id = p.sub_category_id
            WHERE orl.user_id = %s
            ORDER BY p.name
        ''', (user_id,))
        products = cursor.fetchall()

    except mysql.connector.Error as e:
        current_app.logger.error(f"Database error: {e}")
        return "Database error", 500
    finally:
        if cursor:
            cursor.close()
        if connection:
            connection.close()

    return render_template(
        'sales/o_sale.html',
        customers=customers,
        products=products,
        segment='o_sales'
    )  

















@blueprint.route('/save_sale', methods=['POST'])
def save_sale():
    connection = None
    cursor = None
    try:
        # Safe access to session
        user_id = session.get('id')
        if not user_id:
            return jsonify({'message': 'You must be logged in to make a sale.'}), 401

        data = request.get_json()
        customer_id = data.get('customer_id')
        items = data.get('cart_items')

        current_app.logger.debug(f"Received data: {data}")

        if not customer_id or not items or len(items) == 0:
            return jsonify({'message': 'Customer ID and cart items are required.'}), 400

        # DB connection
        connection = get_db_connection()
        cursor = connection.cursor(dictionary=True)

        # Begin transaction
        connection.start_transaction()

        for item in items:
            product_id = item.get('product_id')
            quantity = item.get('quantity')

            current_app.logger.debug(f"Processing item: {item}")

            if not product_id or not quantity or quantity <= 0:
                return jsonify({'message': f'Invalid item or quantity for product ID {product_id}.'}), 400

            # Insert into sales (include user)
            cursor.execute("""
                INSERT INTO sales (ProductID, customer_id, qty, user_id)
                VALUES (%s, %s, %s, %s)
            """, (product_id, customer_id, quantity, user_id))

            # Update product quantity
            cursor.execute("""
                UPDATE product_list
                SET quantity = quantity - %s
                WHERE ProductID = %s
            """, (quantity, product_id))

            # Fetch updated current quantity
            cursor.execute("""
                SELECT quantity FROM product_list WHERE ProductID = %s
            """, (product_id,))
            result = cursor.fetchone()
            current_quantity = result['quantity'] if result else None

            # Insert inventory log with current quantity
            cursor.execute("""
                INSERT INTO inventory_logs (
                    product_id, quantity_change, current_quantity, reason, log_date, user_id
                ) VALUES (%s, %s, %s, %s, NOW(), %s)
            """, (
                product_id, -quantity, current_quantity, 'sale', user_id
            ))

        connection.commit()
        return jsonify({'message': 'Sale recorded and inventory updated successfully.'}), 201

    except Exception as e:
        if connection:
            connection.rollback()
        current_app.logger.error(f"Error occurred: {e}")
        current_app.logger.error(traceback.format_exc())
        return jsonify({'message': 'Error occurred: ' + str(e)}), 500

    finally:
        if cursor:
            cursor.close()
        if connection:
            connection.close()













@blueprint.route('/sales_view', methods=['GET', 'POST'])
def sales_view():
    from datetime import datetime
    from flask import request, render_template

    start_date = datetime.now().strftime('%Y-%m-%d')
    end_date = datetime.now().strftime('%Y-%m-%d')

    if request.method == 'POST':
        start_date = request.form.get('start_date') or start_date
        end_date = request.form.get('end_date') or end_date

    connection = get_db_connection()
    cursor = connection.cursor(dictionary=True)

    # Get sales details including user (staff) name
    query_sales_details = """
        SELECT 
            s.salesID, 
            p.name AS product_name, 
            c.name AS customer_name,  
            s.qty, 
            s.date_updated,
            CONCAT(u.first_name, ' ', u.last_name) AS sold_by
        FROM 
            sales s
        INNER JOIN 
            product_list p ON s.ProductID = p.ProductID
        INNER JOIN 
            customer_list c ON s.customer_id = c.CustomerID
        LEFT JOIN 
            users u ON s.user_id = u.id
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










@blueprint.route('/o_sales_view', methods=['GET', 'POST'])
def o_sales_view():
    user_id = session.get('id')
    if not user_id:
        flash("Please log in to view sales history.", "warning")
        return render_template('auth/login.html')

    start_date = datetime.now().strftime('%Y-%m-%d')
    end_date = datetime.now().strftime('%Y-%m-%d')

    if request.method == 'POST':
        start_date = request.form.get('start_date') or start_date
        end_date = request.form.get('end_date') or end_date

    try:
        connection = get_db_connection()
        cursor = connection.cursor(dictionary=True)

        # Filtered sales details including user name
        query_sales_details = """
            SELECT 
                s.salesID, 
                p.name AS product_name, 
                c.name AS customer_name,  
                s.qty, 
                s.date_updated,
                CONCAT(u.first_name, ' ', u.last_name) AS sold_by
            FROM 
                sales s
            INNER JOIN 
                product_list p ON s.ProductID = p.ProductID
            INNER JOIN 
                customer_list c ON s.customer_id = c.CustomerID 
            INNER JOIN 
                other_roles orl ON orl.sub_category_id = p.sub_category_id
            LEFT JOIN 
                users u ON s.user_id = u.id
            WHERE 
                DATE(s.date_updated) BETWEEN %s AND %s
                AND orl.user_id = %s
        """

        # Filtered quantity summary
        query_sales_quantity = """
            SELECT 
                SUM(s.qty) AS total_quantity
            FROM 
                sales s
            INNER JOIN 
                product_list p ON s.ProductID = p.ProductID
            INNER JOIN 
                other_roles orl ON orl.sub_category_id = p.sub_category_id
            WHERE 
                DATE(s.date_updated) BETWEEN %s AND %s
                AND orl.user_id = %s
        """

        cursor.execute(query_sales_details, (start_date, end_date, user_id))
        sales = cursor.fetchall()

        cursor.execute(query_sales_quantity, (start_date, end_date, user_id))
        total_quantity = cursor.fetchone()['total_quantity']

        formatted_total_quantity = "{:,}".format(total_quantity) if total_quantity else '0'

    except mysql.connector.Error as e:
        current_app.logger.error(f"Database error in o_sales_view: {e}")
        flash("A database error occurred while loading sales data.", "danger")
        sales = []
        formatted_total_quantity = '0'

    finally:
        if cursor:
            cursor.close()
        if connection:
            connection.close()

    return render_template(
        'sales/o_sales_view.html',
        sales=sales,
        total_quantity=formatted_total_quantity,
        start_date=start_date,
        end_date=end_date,
        segment='o_sales_view'
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
