//Used initially to setup the tables and users

CREATE DATABASE IF NOT EXISTS Wellmark;

USE Wellmark;

CREATE USER 'wellmark_user'@'%' IDENTIFIED BY 'WellmarkBlueXBulldogs';

GRANT SELECT ON Wellmark.* TO 'wellmark_user'@'%';

-- Create table
CREATE TABLE TestTable (
    ID INT PRIMARY KEY AUTO_INCREMENT,
    Name VARCHAR(50),
    Age INT,
    Email VARCHAR(100)
);

-- Insert dummy data
INSERT INTO TestTable (Name, Age, Email) VALUES
('John Doe', 30, 'john.doe@example.com'),
('Jane Smith', 25, 'jane.smith@example.com'),
('Alice Johnson', 35, 'alice.johnson@example.com'),
('Bob Brown', 28, 'bob.brown@example.com'),
('Emily Davis', 32, 'emily.davis@example.com'),
('Michael Wilson', 40, 'michael.wilson@example.com'),
('Sarah Lee', 27, 'sarah.lee@example.com'),
('David Martinez', 33, 'david.martinez@example.com'),
('Olivia Taylor', 29, 'olivia.taylor@example.com'),
('James Anderson', 38, 'james.anderson@example.com');