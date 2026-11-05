DECLARE
    v_sql VARCHAR2(4000);
    v_owner VARCHAR2(4000) := UPPER(:schema_name);
BEGIN
    FOR t IN (
        SELECT table_name
        FROM dba_tables
        WHERE owner = v_owner
    ) LOOP
        v_sql := 'TRUNCATE TABLE ' || '"' || v_owner || '"."' || t.table_name || '" CASCADE';
        EXECUTE IMMEDIATE v_sql;
    END LOOP;
END;
