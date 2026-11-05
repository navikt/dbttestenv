DECLARE
    PROCEDURE ensure_schema_exists(p_schema_name VARCHAR2) IS
        v_schema_count NUMBER;
    BEGIN
        SELECT COUNT(*) INTO v_schema_count FROM dba_users WHERE username = UPPER(p_schema_name);
        IF v_schema_count = 0 THEN
            EXECUTE IMMEDIATE 'CREATE USER ' || p_schema_name || ' IDENTIFIED BY ' || p_schema_name;

            EXECUTE IMMEDIATE 'GRANT CREATE SESSION TO ' || p_schema_name;
            EXECUTE IMMEDIATE 'ALTER USER ' || p_schema_name || ' QUOTA UNLIMITED ON USERS';
            -- fra https://confluence.adeo.no/spaces/DEP/pages/336744171/Forvaltning+av+eierskjema+og+tilganger
            EXECUTE IMMEDIATE 'GRANT CREATE CLUSTER TO ' || p_schema_name;
            EXECUTE IMMEDIATE 'GRANT CREATE INDEXTYPE TO ' || p_schema_name;
            EXECUTE IMMEDIATE 'GRANT CREATE JOB TO ' || p_schema_name;
            EXECUTE IMMEDIATE 'GRANT CREATE OPERATOR TO ' || p_schema_name;
            EXECUTE IMMEDIATE 'GRANT CREATE PROCEDURE TO ' || p_schema_name;
            EXECUTE IMMEDIATE 'GRANT CREATE SEQUENCE TO ' || p_schema_name;
            EXECUTE IMMEDIATE 'GRANT CREATE TABLE TO ' || p_schema_name;
            EXECUTE IMMEDIATE 'GRANT CREATE TRIGGER TO ' || p_schema_name;
            EXECUTE IMMEDIATE 'GRANT CREATE TYPE TO ' || p_schema_name;
            EXECUTE IMMEDIATE 'GRANT CREATE DATABASE LINK TO ' || p_schema_name;
            EXECUTE IMMEDIATE 'GRANT CREATE MATERIALIZED VIEW TO ' || p_schema_name;
            EXECUTE IMMEDIATE 'GRANT CREATE SYNONYM TO ' || p_schema_name;
            EXECUTE IMMEDIATE 'GRANT CREATE VIEW TO ' || p_schema_name;
            EXECUTE IMMEDIATE 'GRANT EXEMPT ACCESS POLICY TO ' || p_schema_name;
            EXECUTE IMMEDIATE 'GRANT CREATE PUBLIC SYNONYM TO  ' || p_schema_name;
            EXECUTE IMMEDIATE 'GRANT SET CONTAINER TO  ' || p_schema_name;
            EXECUTE IMMEDIATE 'GRANT CREATE JOB TO   ' || p_schema_name;
            EXECUTE IMMEDIATE 'GRANT ADVISOR TO ' || p_schema_name;
            EXECUTE IMMEDIATE 'GRANT ADMINISTER SQL TUNING SET TO ' || p_schema_name;
            EXECUTE IMMEDIATE 'GRANT SELECT ANY DICTIONARY TO ' || p_schema_name;
        END IF;
    END;
BEGIN
    ensure_schema_exists(:schema_name);
END;
