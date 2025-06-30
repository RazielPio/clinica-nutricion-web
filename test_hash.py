from werkzeug.security import generate_password_hash

# Generamos el hash para la contraseña 'password123'
# El método 'scrypt' es el que usa nuestra app
hashed_password = generate_password_hash('password123', method='scrypt')

print("Copia y pega este hash:")
print(hashed_password)