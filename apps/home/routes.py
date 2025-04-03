from apps.home import blueprint
from flask import render_template, request, session, flash
from jinja2 import TemplateNotFound
from apps import get_db_connection
import logging

@blueprint.route('/index')
def index():
    """
    Renders the 'index' page of the home section.
    """
    connection = get_db_connection()
    try:
        with connection.cursor(dictionary=True) as cursor:
            # Query for total sales today
            cursor.execute('''
                SELECT SUM(total_price) AS total_sales_today
                FROM sales
                WHERE DATE(date_updated) = CURDATE();
            ''')
            total_sales_today = cursor.fetchone()  # Fetch the result for today

            # Query for total sales yesterday
            cursor.execute('''
                SELECT SUM(total_price) AS total_sales_yesterday
                FROM sales
                WHERE DATE(date_updated) = CURDATE() - INTERVAL 1 DAY;
            ''')
            total_sales_yesterday = cursor.fetchone()  # Fetch the result for yesterday

            # Query for products that need to be reordered
            cursor.execute('SELECT * FROM product_list WHERE reorder_level > quantity ORDER BY name')
            products_to_reorder = cursor.fetchall()  # Fetch all results for reorder products

    finally:
        connection.close()  # Ensure the connection is closed after use

    # Format the sales values to UGX
    def format_to_ugx(amount):
        if amount is None:
            return "UGX 0"
        return f"UGX {amount:,.2f}"

    formatted_sales_today = format_to_ugx(total_sales_today['total_sales_today'] if total_sales_today['total_sales_today'] else 0)
    formatted_sales_yesterday = format_to_ugx(total_sales_yesterday['total_sales_yesterday'] if total_sales_yesterday['total_sales_yesterday'] else 0)

    return render_template('home/index.html', 
                           total_sales_today=formatted_sales_today,
                           total_sales_yesterday=formatted_sales_yesterday,
                           products_to_reorder=products_to_reorder, 
                           segment='index')






@blueprint.route('/<template>')
def route_template(template):
    """
    Renders dynamic templates from the 'home' folder.
    """
    try:
        if not template.endswith('.html'):
            template += '.html'
        
        segment = get_segment(request)
        return render_template("home/" + template, segment=segment)

    except TemplateNotFound:
        logging.error(f"Template {template} not found")
        return render_template('home/page-404.html', segment=segment), 404

    except Exception as e:
        logging.error(f"Error rendering template {template}: {str(e)}")
        return render_template('home/page-500.html', segment=segment), 500

def get_segment(request):
    """
    Extracts the last part of the URL path to identify the current page.
    """
    segment = request.path.strip('/').split('/')[-1]
    if not segment:
        segment = 'index'
    return segment
