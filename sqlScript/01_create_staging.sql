/* =========================================================
   1. TẠO DATABASE NẾU CHƯA CÓ
   ========================================================= */

USE master;
GO

IF DB_ID(N'Olist_Staging') IS NULL
    CREATE DATABASE Olist_Staging;
GO

USE Olist_Staging;
GO

/* =========================================================
   2. BẢNG CUSTOMERS — FULL LOAD
   ========================================================= */

IF OBJECT_ID(N'dbo.stg_customers', N'U') IS NULL
BEGIN
    CREATE TABLE dbo.stg_customers
    (
        -- Các cột dữ liệu nguồn
        customer_id               NVARCHAR(100) NULL,
        customer_unique_id        NVARCHAR(100) NULL,
        customer_zip_code_prefix  NVARCHAR(20)  NULL,
        customer_city             NVARCHAR(255) NULL,
        customer_state            NVARCHAR(20)  NULL,

        -- Metadata
        _source_file              NVARCHAR(255) NULL,
        _loaded_at                DATETIME2     NULL
    );
END;
GO

/* =========================================================
   3. BẢNG PRODUCTS — FULL LOAD
   ========================================================= */

IF OBJECT_ID(N'dbo.stg_products', N'U') IS NULL
BEGIN
    CREATE TABLE dbo.stg_products
    (
        -- Các cột dữ liệu nguồn
        product_id                 NVARCHAR(100) NULL,
        product_category_name      NVARCHAR(255) NULL,
        product_name_lenght         NVARCHAR(50)  NULL,
        product_description_lenght  NVARCHAR(50)  NULL,
        product_photos_qty         NVARCHAR(50)  NULL,
        product_weight_g           NVARCHAR(50)  NULL,
        product_length_cm          NVARCHAR(50)  NULL,
        product_height_cm          NVARCHAR(50)  NULL,
        product_width_cm           NVARCHAR(50)  NULL,

        -- Metadata
        _source_file               NVARCHAR(255) NULL,
        _loaded_at                 DATETIME2     NULL
    );
END;
GO


/* =========================================================
   4. KIỂM TRA DỮ LIỆU
   ========================================================= */

SELECT N'stg_customers' AS table_name, COUNT(*) AS total_rows
FROM dbo.stg_customers
UNION ALL
SELECT N'stg_products', COUNT(*)
FROM dbo.stg_products;

SELECT TOP (10) * FROM dbo.stg_customers;
SELECT TOP (10) * FROM dbo.stg_products;
GO

IF OBJECT_ID(N'dbo.stg_sellers', N'U') IS NULL
BEGIN
    CREATE TABLE dbo.stg_sellers
    (
        -- Dữ liệu nguồn
        seller_id               NVARCHAR(100) NULL,
        seller_zip_code_prefix  NVARCHAR(20)  NULL,
        seller_city             NVARCHAR(255) NULL,
        seller_state            NVARCHAR(20)  NULL,

        -- Metadata
        _source_file            NVARCHAR(255) NULL,
        _loaded_at              DATETIME2     NULL
    );
END;
GO
SELECT COUNT(*) AS total_sellers
FROM dbo.stg_sellers;
SELECT TOP (10) * FROM dbo.stg_sellers;

-- geolocation
USE Olist_Staging;
GO

IF OBJECT_ID(N'dbo.stg_geolocation', N'U') IS NULL
BEGIN
    CREATE TABLE dbo.stg_geolocation
    (
        geolocation_zip_code_prefix NVARCHAR(20)  NULL,
        geolocation_lat             NVARCHAR(50)  NULL,
        geolocation_lng             NVARCHAR(50)  NULL,
        geolocation_city            NVARCHAR(255) NULL,
        geolocation_state           NVARCHAR(20)  NULL,

        _source_file                NVARCHAR(255) NULL,
        _loaded_at                  DATETIME2     NULL
    );
END;
GO
SELECT COUNT(*) AS total_geolocation
FROM dbo.stg_geolocation;
SELECT TOP (10) *
FROM dbo.stg_geolocation;

IF OBJECT_ID(N'dbo.stg_category_translation', N'U') IS NULL
BEGIN
    CREATE TABLE dbo.stg_category_translation
    (
        product_category_name         NVARCHAR(255) NULL,
        product_category_name_english NVARCHAR(255) NULL,

        _source_file                  NVARCHAR(255) NULL,
        _loaded_at                    DATETIME2     NULL
    );
END;
GO

SELECT COUNT(*) AS total_rows
FROM dbo.stg_category_translation;

SELECT TOP (10) *
FROM dbo.stg_category_translation;

USE Olist_Staging;
GO

SELECT 'customers' AS table_name, COUNT(*) AS total_rows FROM dbo.stg_customers
UNION ALL
SELECT 'products', COUNT(*) FROM dbo.stg_products
UNION ALL
SELECT 'sellers', COUNT(*) FROM dbo.stg_sellers
UNION ALL
SELECT 'geolocation', COUNT(*) FROM dbo.stg_geolocation
UNION ALL
SELECT 'category_translation', COUNT(*) FROM dbo.stg_category_translation;