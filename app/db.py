# db.py — Enrutador dinámico de Base de Datos para FOLAX DTC
# Dependiendo de la variable de entorno DB_BACKEND, expone la implementación de SQLite o MySQL.

from app.config import DB_BACKEND

if DB_BACKEND == "mysql":
    from app.db_mysql import *
else:
    from app.db_sqlite import *
