import pymssql
import os
import re
import base64
from datetime import datetime
from Crypto.Cipher import AES
from Crypto.Util.Padding import pad, unpad
from dotenv import load_dotenv

# Cargar variables de entorno
load_dotenv()
ENCRYPTION_KEY = os.getenv("ENCRYPTION_KEY").encode()

# Funciones para encriptar y desencriptar nombres
def encrypt_name(name):
    try:
        cipher = AES.new(ENCRYPTION_KEY, AES.MODE_CBC)
        iv = cipher.iv
        encrypted_bytes = cipher.encrypt(pad(name.encode(), AES.block_size))
        return base64.b64encode(iv + encrypted_bytes).decode()
    except Exception as e:
        print(f"Error encriptando nombre: {e}")
        return name

def decrypt_name(encrypted_name):
    try:
        encrypted_data = base64.b64decode(encrypted_name)
        iv = encrypted_data[:16]
        encrypted_bytes = encrypted_data[16:]
        cipher = AES.new(ENCRYPTION_KEY, AES.MODE_CBC, iv)
        return unpad(cipher.decrypt(encrypted_bytes), AES.block_size).decode()
    except Exception as e:
        print(f"Error desencriptando nombre: {e}")
        return encrypted_name

def create_database():
    try:
        conn = pymssql.connect(server="DESKTOP-P03JJMU\\SQLEXPRESS", user="sa", password="univalle")
        cursor = conn.cursor()
        cursor.execute("IF NOT EXISTS (SELECT * FROM sys.databases WHERE name = 'DbOrco') CREATE DATABASE DbOrco")
        conn.commit()
        conn.close()
    except Exception as e:
        print(f"Error al crear la base de datos: {e}")
        return
    
    try:
        conn = pymssql.connect(server="DESKTOP-P03JJMU\\SQLEXPRESS", user="sa", password="univalle", database="DbOrco")
        cursor = conn.cursor()
        cursor.execute('''
            IF NOT EXISTS (SELECT * FROM sysobjects WHERE name='empleados' AND xtype='U')
            CREATE TABLE empleados (
                id INT PRIMARY KEY,
                nombre NVARCHAR(255),
                departamento NVARCHAR(50)
            )
        ''')
        cursor.execute('''
            IF NOT EXISTS (SELECT * FROM sysobjects WHERE name='registro_asistencia' AND xtype='U')
            CREATE TABLE registro_asistencia (
                id INT IDENTITY PRIMARY KEY,
                empleado_id INT,
                fecha DATE,
                hora TIME,
                tipo NVARCHAR(10),  
                FOREIGN KEY (empleado_id) REFERENCES empleados(id)
            )
        ''')
        conn.commit()
        conn.close()
    except Exception as e:
        print(f"Error al crear las tablas: {e}")

def parse_txt_file(file_path):
    with open(file_path, "r", encoding="utf-8") as file:
        lines = file.readlines()
    
    employees = {}
    records = []
    
    for line in lines:
        line = line.strip()
        name_match = re.search(r"ID\s*,(\d+),Nombre\s*,\s*,(.*?),\s*,Departamento\s*,\s*,(.*?)\s*,", line)
        if name_match:
            emp_id, name, dept = name_match.groups()
            employees[emp_id] = (emp_id, encrypt_name(name.strip()), dept.strip())
            continue
        
        matches = re.findall(r"(\d{2}/\d{2}/\d{4})\s+(\d{2}:\d{2})\s*,\s*(Entrada|Salida)", line)
        for match in matches:
            fecha, hora, tipo = match
            fecha = datetime.strptime(fecha, "%d/%m/%Y").strftime("%Y-%m-%d")
            records.append((emp_id, fecha, hora, tipo))
    
    return employees, records

def insert_into_db(employees, records):
    try:
        conn = pymssql.connect(server="DESKTOP-P03JJMU\\SQLEXPRESS", user="sa", password="univalle", database="DbOrco")
        cursor = conn.cursor()
        
        for emp_id, (id, nombre, dept) in employees.items():
            cursor.execute('''
                IF NOT EXISTS (SELECT 1 FROM empleados WHERE id = %s)
                INSERT INTO empleados (id, nombre, departamento)
                VALUES (%s, %s, %s)
            ''', (id, id, nombre, dept))
        
        for record in records:
            cursor.execute('''
                INSERT INTO registro_asistencia (empleado_id, fecha, hora, tipo)
                VALUES (%s, %s, %s, %s)
            ''', record)
        
        conn.commit()
        conn.close()
    except Exception as e:
        print(f"Error insertando en la base de datos: {e}")

def process_all_txt_files(directory):
    if not os.path.exists(directory):
        print(f"Error: La carpeta '{directory}' no existe")
        return
    
    txt_files = [f for f in os.listdir(directory) if f.endswith(".txt")]
    if not txt_files:
        print(f"No se encontraron archivos TXT en la carpeta '{directory}'")
        return
    
    print(f"Procesando {len(txt_files)} archivos TXT...")
    
    for filename in txt_files:
        file_path = os.path.join(directory, filename)
        try:
            employees, records = parse_txt_file(file_path)
            insert_into_db(employees, records)
            print(f"{len(records)} registros insertados desde {filename}")
        except Exception as e:
            print(f"Error procesando archivo {filename}: {e}")

if __name__ == "__main__":
    try:
        create_database()
        repository_path = "Repository"
        process_all_txt_files(repository_path)
        print("Proceso completado.")
    except Exception as e:
        print(f"Error: {e}")
