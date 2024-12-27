USE mydb;
-- CREATE TABLE mobiles_search_history(
--     search_id INT PRIMARY KEY AUTO_INCREMENT,
--     title VARCHAR(300),
--     platform_id INT,
--     platform_name VARCHAR(20),
--     price DECIMAL(10, 2),
--     rating VARCHAR(50),
--     delivery_time VARCHAR(100),
--     image_url VARCHAR(512),
--     new_refurbished VARCHAR(255),
--     search_date_time DATETIME,
--     redirect_link VARCHAR(1024)
-- );
SELECT * FROM mobiles_search_history;

CREATE TABLE cases_search_history(
    search_id INT PRIMARY KEY AUTO_INCREMENT,
    title VARCHAR(300),
    platform_id INT,
    platform_name VARCHAR(20),
    price DECIMAL(10, 2),
    rating VARCHAR(50),
    delivery_time VARCHAR(100),
    image_url VARCHAR(512),
    search_date_time DATETIME,
    redirect_link VARCHAR(1024)
);
SELECT * FROM cases_search_history;


