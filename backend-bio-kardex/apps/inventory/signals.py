from django.db import DEFAULT_DB_ALIAS, connections

TABLA = "inventory_movimientokardex"

SENTENCIAS = [
    """
    CREATE OR REPLACE FUNCTION kardex_inalterable() RETURNS trigger AS $$
    BEGIN
        RAISE EXCEPTION 'El Kardex es inalterable: % no permitido', TG_OP;
    END;
    $$ LANGUAGE plpgsql
    """,
    f"DROP TRIGGER IF EXISTS trg_kardex_inalterable ON {TABLA}",
    f"""
    CREATE TRIGGER trg_kardex_inalterable
    BEFORE UPDATE OR DELETE ON {TABLA}
    FOR EACH ROW EXECUTE FUNCTION kardex_inalterable()
    """,
]


def crear_trigger_kardex(sender=None, using=DEFAULT_DB_ALIAS, **kwargs):
    """Segunda capa de proteccion del Kardex: PostgreSQL rechaza UPDATE y DELETE.

    Es idempotente y se ejecuta despues de cada `migrate`, por lo que no depende
    del numero de migracion.
    """
    conexion = connections[using]
    if conexion.vendor != "postgresql":
        return
    if TABLA not in conexion.introspection.table_names():
        return
    with conexion.cursor() as cursor:
        for sentencia in SENTENCIAS:
            cursor.execute(sentencia)
