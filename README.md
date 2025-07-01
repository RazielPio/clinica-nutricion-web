# Clinigramm - Sistema de Gestión para Clínica de Nutrición

Bienvenido a **Clinigramm**, una herramienta web desarrollada en Flask para la gestión integral de pacientes y su seguimiento nutricional, ideal para clínicas y profesionales de la salud.


## 📝 Características

- 👥 Gestión de Roles: Perfiles de Administrador, Recepción y Nutriólogo con distintos permisos.

- 🖥️ Dashboard de Administración: Gestión de usuarios (activar/desactivar) y registro de inicios de sesión.

- 🚪 Portal de Recepción: Registro de nuevos pacientes y captura de mediciones corporales.

- 📂 Expediente de Paciente: Visualización detallada del historial de mediciones, gráficas de evolución y análisis segmental.

- 📋 Historial Clínico: Formulario detallado para registrar el historial clínico-nutricional del paciente.

- 📄 Reportes en PDF: Generación de reportes profesionales con el logo de la clínica para los pacientes.

## 🛠️ Instalación y Ejecución Local
<details>
<summary> 🗺️ Guía de instalación</summary>

Sigue estos pasos para instalar y ejecutar el proyecto en un entorno local.
Prerrequisitos

    Python 3.8 o superior.

    Un servidor de base de datos MySQL. (Se recomienda usar XAMPP, ya que incluye un servidor MySQL y una interfaz gráfica fácil de usar como phpMyAdmin).

1. Clonar el Repositorio
 ```
 git clone https://github.com/RazielPio/clinica-nutricion-web.git
 cd clinica-nutricion-web
```

2. Crear y Activar un Entorno Virtual

Es una buena práctica aislar las dependencias del proyecto.

En Windows:

```python
python -m venv venv
.\venv\Scripts\activate
```
En macOS / Linux:
```python
python3 -m venv venv
source venv/bin/activate
```
3. Instalar Dependencias

Instala todas las librerías necesarias con el siguiente comando:
```python
pip install -r requirements.txt
```
4. Configuración de la Base de Datos con XAMPP

Necesitas crear la base de datos y las tablas necesarias.

a. Inicia XAMPP:
Abre el panel de control de XAMPP y asegúrate de que los módulos de Apache y MySQL estén iniciados.

b. Crea la Base de Datos:

    Ve a http://localhost/phpmyadmin en tu navegador.

    Haz clic en la pestaña "Bases de datos".

    En el campo "Crear base de datos", escribe clinigramm_db.

    En el campo de cotejamiento, selecciona utf8mb4_unicode_ci y haz clic en "Crear".

c. Crea las Tablas y el Usuario Administrador:

    Una vez creada la base de datos, selecciónala en la barra lateral izquierda.

    Ve a la pestaña "SQL".

    Copia y pega el contenido del siguiente script y haz clic en "Continuar". Este script creará todas las tablas y un usuario admin para que puedas iniciar sesión inmediatamente.


<details>
<summary>Click para ver el Script SQL de configuración</summary>

```sql
USE clinigramm_db;

-- Tabla de Usuarios
CREATE TABLE `usuarios` (
  `id` int NOT NULL AUTO_INCREMENT,
  `nombre` varchar(100) NOT NULL,
  `email` varchar(100) NOT NULL,
  `password_hash` varchar(255) NOT NULL,
  `rol` enum('admin','nutriologo','recepcion') NOT NULL,
  `estado` enum('activo','inactivo') NOT NULL DEFAULT 'activo',
  PRIMARY KEY (`id`),
  UNIQUE KEY `email` (`email`)
) ENGINE=InnoDB;

-- Tabla de Pacientes
CREATE TABLE `pacientes` (
  `id` int NOT NULL AUTO_INCREMENT,
  `nombre_completo` varchar(255) NOT NULL,
  `fecha_nacimiento` date DEFAULT NULL,
  `estatura_cm` decimal(5,1) DEFAULT NULL,
  `telefono` varchar(20) DEFAULT NULL,
  `email` varchar(100) DEFAULT NULL,
  `id_nutriologo_asignado` int DEFAULT NULL,
  PRIMARY KEY (`id`),
  KEY `id_nutriologo_asignado` (`id_nutriologo_asignado`),
  CONSTRAINT `pacientes_ibfk_1` FOREIGN KEY (`id_nutriologo_asignado`) REFERENCES `usuarios` (`id`) ON DELETE SET NULL
) ENGINE=InnoDB;

-- Tabla de Historial Clínico
CREATE TABLE `historial_clinico` (
  `id` int NOT NULL AUTO_INCREMENT,
  `id_paciente` int NOT NULL,
  `edad` int DEFAULT NULL,
  `objetivo_principal` text,
  `actividad_diaria` text,
  `tiempo_entrenamiento` varchar(100) DEFAULT NULL,
  `enfermedades_condiciones` text,
  `alergias` text,
  `condiciones_cardiovasculares` text,
  `cirugias_lesiones` text,
  `experiencia_deportiva` text,
  `estres_psicologico` int DEFAULT NULL,
  `horas_sueno` decimal(4,1) DEFAULT NULL,
  `estres_fisico` int DEFAULT NULL,
  `medicacion_actual` text,
  `suplementos_uso` text,
  `farmacologia_deportiva_uso` text,
  `num_comidas_dia` int DEFAULT NULL,
  `preferencias_alimentarias` varchar(255) DEFAULT NULL,
  `frecuencia_proteinas` varchar(50) DEFAULT NULL,
  `frecuencia_verduras` varchar(50) DEFAULT NULL,
  `frecuencia_cereales` varchar(50) DEFAULT NULL,
  `frecuencia_azucares` varchar(50) DEFAULT NULL,
  `frecuencia_lacteos` varchar(50) DEFAULT NULL,
  `alimentos_preferidos` text,
  `alimentos_no_preferidos` text,
  `alimentos_evitados` text,
  PRIMARY KEY (`id`),
  UNIQUE KEY `id_paciente` (`id_paciente`),
  CONSTRAINT `historial_clinico_ibfk_1` FOREIGN KEY (`id_paciente`) REFERENCES `pacientes` (`id`) ON DELETE CASCADE
) ENGINE=InnoDB;

-- Tabla de Mediciones
CREATE TABLE `mediciones` (
  `id` int NOT NULL AUTO_INCREMENT,
  `id_paciente` int NOT NULL,
  `fecha_medicion` datetime NOT NULL,
  `peso` decimal(5,2) DEFAULT NULL,
  `altura` decimal(3,2) DEFAULT NULL,
  `imc` decimal(4,2) DEFAULT NULL,
  `grasa_corporal_pct` decimal(4,1) DEFAULT NULL,
  `masa_muscular_pct` decimal(4,1) DEFAULT NULL,
  `agua_corporal_pct` decimal(4,1) DEFAULT NULL,
  `masa_osea_kg` decimal(4,2) DEFAULT NULL,
  `tmb_kcal` int DEFAULT NULL,
  `get_kcal` int DEFAULT NULL,
  `grasa_visceral` int DEFAULT NULL,
  `masa_muscular_kg` decimal(5,2) DEFAULT NULL,
  `grasa_tronco_pct` decimal(4,1) DEFAULT NULL,
  `musculo_tronco_pct` decimal(4,1) DEFAULT NULL,
  `grasa_brazo_der_pct` decimal(4,1) DEFAULT NULL,
  `musculo_brazo_der_pct` decimal(4,1) DEFAULT NULL,
  `grasa_brazo_izq_pct` decimal(4,1) DEFAULT NULL,
  `musculo_brazo_izq_pct` decimal(4,1) DEFAULT NULL,
  `grasa_pierna_der_pct` decimal(4,1) DEFAULT NULL,
  `musculo_pierna_der_pct` decimal(4,1) DEFAULT NULL,
  `grasa_pierna_izq_pct` decimal(4,1) DEFAULT NULL,
  `musculo_pierna_izq_pct` decimal(4,1) DEFAULT NULL,
  `grasa_tronco_kg` decimal(5,2) DEFAULT NULL,
  `musculo_tronco_kg` decimal(5,2) DEFAULT NULL,
  `grasa_brazo_der_kg` decimal(5,2) DEFAULT NULL,
  `musculo_brazo_der_kg` decimal(5,2) DEFAULT NULL,
  `grasa_brazo_izq_kg` decimal(5,2) DEFAULT NULL,
  `musculo_brazo_izq_kg` decimal(5,2) DEFAULT NULL,
  `grasa_pierna_der_kg` decimal(5,2) DEFAULT NULL,
  `musculo_pierna_der_kg` decimal(5,2) DEFAULT NULL,
  `grasa_pierna_izq_kg` decimal(5,2) DEFAULT NULL,
  `musculo_pierna_izq_kg` decimal(5,2) DEFAULT NULL,
  `observaciones` text,
  PRIMARY KEY (`id`),
  KEY `id_paciente` (`id_paciente`),
  CONSTRAINT `mediciones_ibfk_1` FOREIGN KEY (`id_paciente`) REFERENCES `pacientes` (`id`) ON DELETE CASCADE
) ENGINE=InnoDB;

-- Tabla de Logs de Sesiones
CREATE TABLE `log_sesiones` (
  `id` int NOT NULL AUTO_INCREMENT,
  `id_usuario` int NOT NULL,
  `fecha_hora` datetime NOT NULL,
  `ip_address` varchar(45) DEFAULT NULL,
  PRIMARY KEY (`id`),
  KEY `id_usuario` (`id_usuario`),
  CONSTRAINT `log_sesiones_ibfk_1` FOREIGN KEY (`id_usuario`) REFERENCES `usuarios` (`id`) ON DELETE CASCADE
) ENGINE=InnoDB;

-- Insertar usuario administrador inicial
-- Contraseña: admin
INSERT INTO `usuarios` (`nombre`, `email`, `password_hash`, `rol`, `estado`) VALUES
('Admin', 'admin@clinica.com', 'pbkdf2:sha256:600000$o7qjLzVdEmrBTEIl$d5138834418f4a14a93cb33b3b401c6e61122a5781a95a89849c5a7732159f6f', 'admin', 'activo');
```
</details>

d. Configura la Conexión en el Código:
Abre el archivo app.py. La configuración por defecto de XAMPP suele ser user: 'root' y password: '' (vacía), por lo que la configuración actual debería funcionar. Si has cambiado la contraseña de MySQL, actualízala aquí.
```sql
DB_CONFIG = {
  'host': 'localhost',
  'user': 'root',
  'password': '', # Tu contraseña de MySQL aquí (si tienes una)
  'database': 'clinigramm_db'
}
```
5. Ejecutar la Aplicación

Finalmente, ejecuta la aplicación con el siguiente comando:
```
python app.py
```
Abre tu navegador y ve a http://127.0.0.1:5001. Podrás iniciar sesión con:

Email:

```admin@clinica.com```

Contraseña:

```admin```

</details>

## ⚙️ Gestión de Usuarios
<details>
<summary>🧑‍💻 Guía para añadir un nuevo usuario</summary>

Añadir Nuevos Usuarios (Nutriólogos, Recepción, etc.)

Para añadir un nuevo usuario al sistema, sigue estos pasos:

1. Generar la Contraseña Segura:
Abre una terminal en la carpeta del proyecto (con el entorno virtual activado) y ejecuta el script que hemos creado:
```python
python generate_hash.py
```
El script te pedirá que introduzcas y confirmes la nueva contraseña de forma segura. Al final, te mostrará el password_hash generado. Copia esta línea completa.

2. Insertar el Usuario en la Base de Datos:
Ve a phpMyAdmin, selecciona la base de datos clinigramm_db y abre la pestaña "SQL". Usa la siguiente plantilla para crear tu usuario.

- Reemplaza 'Nombre del Usuario', 'email@clinica.com' y 'ROL' con los datos correctos.

- Pega el password_hash que copiaste del script.

- El rol puede ser 'nutriologo' o 'recepcion'.

```sql
INSERT INTO `usuarios` (`nombre`, `email`, `password_hash`, `rol`, `estado`) VALUES
('Nombre del Usuario', 'email@clinica.com', 'PEGA_AQUI_EL_HASH_GENERADO', 'ROL', 'activo');
```

Ejemplo para un nutriólogo:

```sql
INSERT INTO `usuarios` (`nombre`, `email`, `password_hash`, `rol`, `estado`) VALUES
('Dr. Juan Pérez', 'juan.perez@clinica.com', 'pbkdf2:sha256:600000$abc...xyz', 'nutriologo', 'activo');
```
Haz clic en "Continuar" para ejecutar el comando y ¡listo! El nuevo usuario ya podrá iniciar sesión con la contraseña que definiste.
