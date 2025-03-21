import pymssql
from flask import Flask, jsonify, request
import pyodbc
import os
from Crypto.Cipher import AES
from Crypto.Util.Padding import unpad
import base64
from dotenv import load_dotenv
from flask_cors import CORS
from datetime import datetime, time, timedelta
import logging

# Configuración de la aplicación Flask
app = Flask(__name__)
CORS(app)  # Habilita CORS para toda la aplicación

# Configuración de logs
logging.basicConfig(level=logging.DEBUG)

# Cargar variables de entorno
load_dotenv()
ENCRYPTION_KEY = os.getenv("ENCRYPTION_KEY").encode()

# Función para desencriptar nombres
def decrypt_name(encrypted_name):
    try:
        encrypted_data = base64.b64decode(encrypted_name)
        iv = encrypted_data[:16]
        encrypted_bytes = encrypted_data[16:]
        cipher = AES.new(ENCRYPTION_KEY, AES.MODE_CBC, iv)
        return unpad(cipher.decrypt(encrypted_bytes), AES.block_size).decode()
    except Exception as e:
        logging.error(f"Error desencriptando nombre: {e}")
        return encrypted_name

# Función para convertir objetos `time` a string
def time_to_string(t):
    if isinstance(t, time):
        return t.strftime('%H:%M:%S')  # Formato de hora (por ejemplo, '15:30:00')
    return t

# Función para convertir el formato de hora de la base de datos a un objeto time
def convert_db_time(db_time):
    try:
        # Si db_time ya es un objeto time, devolverlo directamente
        if isinstance(db_time, time):
            return db_time
        
        # Si db_time es una cadena de texto, convertirla a objeto time
        if isinstance(db_time, str):
            # Convertir el formato "HH.MM.SS.0000000" a "HH:MM:SS"
            time_str = db_time.split('.')[0]  # Tomar solo la parte "HH.MM.SS"
            return datetime.strptime(time_str, "%H.%M.%S").time()
        
        # Si no es ni time ni str, devolver None
        return None
    except Exception as e:
        logging.error(f"Error convirtiendo hora de la base de datos: {e}")
        return None

# Función para determinar el tipo de turno
def determinar_turno(entradas, salidas):
    if not entradas or not salidas:
        return "Sin turno definido"
    
    # Convertir las horas a objetos datetime para calcular la duración
    primera_entrada = datetime.strptime(entradas[0], "%H:%M:%S")
    ultima_salida = datetime.strptime(salidas[-1], "%H:%M:%S")
    
    # Calcular la duración total del turno
    duracion_turno = ultima_salida - primera_entrada
    
    # Verificar si el turno es de 8 horas con almuerzo
    if len(entradas) == 2 and len(salidas) == 2:
        entrada_manana = datetime.strptime(entradas[0], "%H:%M:%S")
        salida_manana = datetime.strptime(salidas[0], "%H:%M:%S")
        entrada_tarde = datetime.strptime(entradas[1], "%H:%M:%S")
        salida_tarde = datetime.strptime(salidas[1], "%H:%M:%S")
        
        # Verificar si el horario coincide con un turno de 8 horas con almuerzo
        if (entrada_manana.time() == datetime.strptime("08:30:00", "%H:%M:%S").time() and
            salida_manana.time() == datetime.strptime("12:30:00", "%H:%M:%S").time() and
            entrada_tarde.time() == datetime.strptime("14:30:00", "%H:%M:%S").time() and
            salida_tarde.time() == datetime.strptime("18:30:00", "%H:%M:%S").time()):
            return "8 horas con almuerzo"
    
    # Determinar el tipo de turno basado en la duración
    if duracion_turno >= timedelta(hours=24):
        return "24 horas"
    elif timedelta(hours=7) <= duracion_turno <= timedelta(hours=9):
        return "8 horas"
    else:
        return f"Otro turno ({duracion_turno})"

# Ruta para obtener la lista de empleados y sus registros de asistencia
@app.route("/empleados", methods=["GET"])
def get_empleados():
    try:
        logging.debug("Iniciando la conexión a la base de datos")
        # Conexión usando pyodbc en lugar de pymssql
        conn = pymssql.connect(server="DESKTOP-P03JJMU\\SQLEXPRESS", user="sa", password="univalle", database="DbOrco")
        cursor = conn.cursor()

        # Obtener los empleados
        logging.debug("Ejecutando la consulta para obtener empleados")
        cursor.execute("SELECT id, nombre FROM empleados")
        empleados = [
            {"id": row[0], "nombre": decrypt_name(row[1])}
            for row in cursor.fetchall()
        ]
        logging.debug(f"Empleados obtenidos: {empleados}")

        # Obtener los registros de asistencia
        logging.debug("Ejecutando la consulta para obtener registros de asistencia")
        cursor.execute("SELECT empleado_id, fecha, hora, tipo FROM [DbOrco].[dbo].[registro_asistencia]")
        registros = cursor.fetchall()
        logging.debug(f"Registros de asistencia obtenidos: {registros}")

        # Formatear los registros para el frontend
        registros_formateados = {}
        for reg in registros:
            empleado_id, fecha, hora, tipo = reg
            hora_time = convert_db_time(hora)  # Convertir la hora de la base de datos
            if not hora_time:
                continue  # Si la conversión falla, omitir este registro

            hora_str = time_to_string(hora_time)  # Convertir la hora a string

            if empleado_id not in registros_formateados:
                registros_formateados[empleado_id] = {}

            if fecha not in registros_formateados[empleado_id]:
                registros_formateados[empleado_id][fecha] = {
                    "Fecha": fecha,
                    "Entradas": [],  # Lista de todas las entradas
                    "Salidas": []    # Lista de todas las salidas
                }

            # Agregar la hora a la lista correspondiente (Entradas o Salidas)
            if tipo == "Entrada":
                registros_formateados[empleado_id][fecha]["Entradas"].append(hora_str)
            elif tipo == "Salida":
                registros_formateados[empleado_id][fecha]["Salidas"].append(hora_str)

        logging.debug(f"Registros de asistencia formateados: {registros_formateados}")

        # Cerrar la conexión
        conn.close()
        logging.debug("Conexión cerrada")

        # Combinar empleados y registros
        respuesta = []
        for emp in empleados:
            registros_empleado = []
            if emp["id"] in registros_formateados:
                for fecha, registro in registros_formateados[emp["id"]].items():
                    # Determinar el tipo de turno
                    tipo_turno = determinar_turno(registro["Entradas"], registro["Salidas"])
                    registro["turno"] = tipo_turno
                    registros_empleado.append(registro)
            respuesta.append({
                "id": emp["id"],
                "nombre": emp["nombre"],
                "registros": registros_empleado
            })
        logging.debug(f"Respuesta final: {respuesta}")

        # Devolver la respuesta en formato JSON
        return jsonify(respuesta)

    except Exception as e:
        logging.error(f"Error en la base de datos: {e}", exc_info=True)
        return jsonify({"error": f"Error en la base de datos: {str(e)}"}), 500

# Iniciar la aplicación Flask
if __name__ == "__main__":
    app.run(debug=True)