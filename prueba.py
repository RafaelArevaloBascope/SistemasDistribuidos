import pyodbc

try:
    print("Intentando conectar con pyodbc...")
    conn_string = "DRIVER={ODBC Driver 17 for SQL Server};SERVER=localhost\\SQLEXPRESS;DATABASE=DbOrco;UID=sa;PWD=Univalle"
    conn = pyodbc.connect(conn_string)
    print("¡Conexión exitosa!")
    cursor = conn.cursor()
    cursor.execute("SELECT @@version")
    row = cursor.fetchone()
    print("Versión de SQL Server:", row[0])
    conn.close()
except Exception as e:
    print("Error de conexión:", e)