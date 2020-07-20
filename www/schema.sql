
-- schema.sql

DROP DATABASE IF EXISTS awesome;

CREATE DATABASE awesome;

USE awesome;

CREATE TABLE users(
    id VARCHAR(50) NOT NULL,
    email VARCHAR(50) NOT NULL,
    password VARCHAR(50) NOT NULL,
    admin BOOLEAN NOT NULL,
    name VARCHAR(50) NOT NULL,
    image VARCHAR(500) NOT NULL,
    create_at REAL NOT NULL,
    PRIMARY KEY (id),
    UNIQUE KEY user_email(email),
    INDEX user_create_at(create_at)
)ENGINE=InnoDB DEFAULT CHARSET=utf8;

CREATE TABLE blogs(
    id VARCHAR(50) NOT NULL,
    user_id VARCHAR(50) NOT NULL,
    user_name VARCHAR(50) NOT NULL,
    user_image VARCHAR(500) NOT NULL,
    name VARCHAR(50) NOT NULL,
    summary VARCHAR(200) NOT NULL,
    content MEDIUMTEXT  NOT NULL,
    create_at REAL NOT NULL,
    PRIMARY KEY (id),
    INDEX blog_create_at(create_at)
)ENGINE=InnoDB DEFAULT CHARSET=utf8;

CREATE TABLE comments(
    id VARCHAR(50) NOT NULL,
    blog_id VARCHAR(50) NOT NULL,
    user_id VARCHAR(50) NOT NULL,
    user_name VARCHAR(50) NOT NULL,
    user_image VARCHAR(500) NOT NULL,
    content MEDIUMTEXT  NOT NULL,
    create_at REAL NOT NULL,
    PRIMARY KEY (id),
    INDEX comment_create_at(create_at)
)ENGINE=InnoDB DEFAULT CHARSET=utf8;

