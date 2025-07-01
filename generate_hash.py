# generate_hash.py
from werkzeug.security import generate_password_hash
import getpass

# Este script te ayuda a generar un hash de contraseña seguro para añadir nuevos
# usuarios a la base de datos de Clinigramm.
# El hash generado es compatible con el que usa la aplicación Flask.

def create_password_hash():
    """
    Pide al usuario una contraseña de forma segura y genera su hash.
    """
    print("--- Generador de Hashes para Clinigramm ---")
    
    # getpass oculta la contraseña mientras se escribe para mayor seguridad.
    password = getpass.getpass("Introduce la nueva contraseña: ")
    password_confirm = getpass.getpass("Confirma la contraseña: ")

    if not password or not password_confirm:
        print("\nError: La contraseña no puede estar vacía.")
        return

    if password != password_confirm:
        print("\nError: Las contraseñas no coinciden.")
        return

    # Genera el hash usando el mismo método que la aplicación.
    # El método 'pbkdf2:sha256' es el predeterminado y es muy seguro.
    hashed_password = generate_password_hash(password)

    print("\n¡Hash generado con éxito!")
    print("Copia la siguiente línea completa y pégala en tu comando SQL en el campo 'password_hash':\n")
    print(hashed_password)
    print("\n-------------------------------------------------")


if __name__ == '__main__':
    create_password_hash()
