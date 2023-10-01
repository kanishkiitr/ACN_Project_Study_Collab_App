import sqlite3

# Connect to the database (or create it if it doesn't exist)
conn = sqlite3.connect('user_credentials.db')

# Create a cursor object to execute SQL commands
cursor = conn.cursor()

# Define the SQL command to create the table
create_table_sql = '''
CREATE TABLE IF NOT EXISTS user_credentials (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT NOT NULL UNIQUE,
    password TEXT NOT NULL,
    email TEXT NOT NULL,
    activation BOOLEAN
);
'''

# Execute the SQL command to create the table# Define the SQL command to create the table
create_table_sql = '''
CREATE TABLE IF NOT EXISTS user_credentials (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT NOT NULL UNIQUE,
    password TEXT NOT NULL,
    email TEXT NOT NULL,
    activation BOOLEAN
);
'''

# Execute the SQL command to create the table
cursor.execute(create_table_sql)
# cursor.execute("Insert into user_credentials (username, password, email, activation) values ()")
cursor.execute("select * from user_credentials")
# Commit the changes and close the database connection
conn.commit()
conn.close()

print("Database and table created successfully.")