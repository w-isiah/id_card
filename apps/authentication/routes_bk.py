@blueprint.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']

        try:
            # Get DB connection using context manager
            with get_db_connection() as connection:
                with connection.cursor(dictionary=True) as cursor:
                    # Retrieve the user by username
                    cursor.execute("SELECT * FROM users WHERE username = %s", (username,))
                    user = cursor.fetchone()

                    if user:
                        # If the user exists, check the password hash
                        if check_password_hash(user['password'], password):
                            try:
                                # Insert a new login record in the user_activity table
                                cursor.execute("INSERT INTO user_activity (user_id, login_time) VALUES (%s, %s)", 
                                               (user['id'], datetime.utcnow()))
                            
                                # Set user as online (update `is_online` field to 1)
                                cursor.execute("UPDATE users SET is_online = 1 WHERE id = %s", (user['id'],))
                                connection.commit()  # Commit the changes to the database

                                # Storing user session data
                                session.update({
                                    'loggedin': True,
                                    'id': user['id'],
                                    'username': user['username'],
                                    'profile_image': user['profile_image'],
                                    'first_name': user['first_name'],
                                    'role': user['role'],
                                    'last_activity': datetime.utcnow()
                                })
                                session.permanent = True  # Make the session permanent

                                flash('Login successful!', 'success')
                                return redirect(url_for('home_blueprint.index'))  # Redirect to home page after successful login
                            except Exception as e:
                                # Log the error to the console
                                print(f"Error during session handling or user activity logging: {str(e)}")
                                flash('An error occurred during the login process. Please try again later.', 'danger')
                                return redirect(url_for('authentication_blueprint.login'))  # Redirect back to login page in case of error

                        else:
                            flash('Incorrect password.', 'danger')
                            return redirect(url_for('authentication_blueprint.login'))  # Redirect to login if password is incorrect
                    else:
                        flash('Username not found.', 'danger')
                        return redirect(url_for('authentication_blueprint.login'))  # Redirect to login if username is not found

        except Exception as e:
            flash(f"An error occurred: {str(e)}", 'danger')  # Handle any database or other errors

    return render_template('accounts/login.html')  # Render the login page on GET request