from flask import Flask, render_template, request, send_file, make_response
import os
from flask_cors import CORS

from procesador import procesar_excel
import tempfile
import io

app = Flask(__name__)
cors = CORS(app)

UPLOAD_FOLDER = "."

@app.route("/")
def index():
    return render_template("index.html")


@app.route("/procesar", methods=["POST"])
def procesar():
    file = request.files.get("file")
    if file is None:
        return "Error: no file uploaded", 400

    # Use a temporary directory so uploaded input is not persisted in the backend folder
    with tempfile.TemporaryDirectory() as tmpdir:
        input_path = os.path.join(tmpdir, "input.xlsx")
        output_path = os.path.join(tmpdir, "output.xlsx")

        # Guardar archivo temporalmente
        file.save(input_path)

        try:
            # Ejecutar tu script y obtener cuántas filas se procesaron/errores
            processed, errors = procesar_excel(input_path, output_path)

            # Leer el archivo de salida en memoria y devolverlo sin dejar ficheros en disco
            with open(output_path, "rb") as f:
                data = f.read()

            bio = io.BytesIO(data)
            bio.seek(0)

            response = make_response(send_file(bio, as_attachment=True, download_name="resultado.xlsx"))

            try:
                response.headers['X-Rows-Processed'] = str(int(processed))
            except Exception:
                response.headers['X-Rows-Processed'] = '0'

            try:
                response.headers['X-Rows-Errors'] = str(int(errors))
            except Exception:
                response.headers['X-Rows-Errors'] = '0'

            try:
                response.headers['X-Processing-Status'] = 'partial' if errors and int(errors) > 0 else 'completed'
            except Exception:
                response.headers['X-Processing-Status'] = 'completed'

            # Expose headers for CORS
            try:
                response.headers['Access-Control-Expose-Headers'] = 'X-Rows-Processed, X-Rows-Errors, X-Processing-Status'
            except Exception:
                pass

            return response

        except Exception as e:
            return f"Error: {str(e)}", 500


if __name__ == "__main__":
    app.run(debug=True)