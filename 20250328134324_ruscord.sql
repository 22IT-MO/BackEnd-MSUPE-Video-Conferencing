-- +goose Up
-- +goose StatementBegin
CREATE TABLE IF NOT EXISTS users (
    id SERIAL PRIMARY KEY,
    username VARCHAR(255) NOT NULL,
    email VARCHAR(255) NOT NULL,
    password_hash VARCHAR(255) NOT NULL,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

INSERT INTO users (username, email, password_hash)
VALUES 
('user1', '1@gmail.com', 'pass1'),
('user2', '2@gmail.com', 'pass2'),
('user3', '3@gmail.com', 'pass3'),
('user4', '4@gmail.com', 'pass4'),
('user5', '5@gmail.com', 'pass5');

CREATE TABLE IF NOT EXISTS conferences (
    id SERIAL PRIMARY KEY,
    host_id INTEGER NOT NULL,
    conf_title VARCHAR(255) NOT NULL,
    conf_description TEXT NOT NULL,
    start_time TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    end_time TIMESTAMP NOT NULL,
    CONSTRAINT fk_users FOREIGN KEY(host_id) REFERENCES users(id)
);

INSERT INTO conferences (host_id, conf_title, conf_description, end_time)
VALUES 
('2', 'conf1', 'desc1', '2025-03-29'),
('5', 'conf2', 'desc2', '2025-03-30');

CREATE TABLE IF NOT EXISTS conf_participants (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL,
    conf_id INTEGER NOT NULL,
    user_role VARCHAR(255) NOT NULL,
    joined_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    left_at TIMESTAMP NOT NULL,
    CONSTRAINT fk_users FOREIGN KEY(user_id) REFERENCES users(id),
    CONSTRAINT fk_conferences FOREIGN KEY(conf_id) REFERENCES conferences(id)
);

INSERT INTO conf_participants (user_id, conf_id, user_role, left_at)
VALUES 
(1, 1, 'student', '2025-03-20'),
(2, 1, 'host', '2025-03-20'),
(4, 2, 'student', '2025-03-20'),
(5, 2, 'host', '2025-03-20'),
(3, 1, 'student', '2025-03-20');
-- +goose StatementEnd

-- +goose Down
-- +goose StatementBegin
DROP TABLE IF EXISTS users, conferences, conf_participants;
-- +goose StatementEnd