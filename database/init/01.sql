CREATE TABLE IF NOT EXISTS employees (
    id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    name VARCHAR(255) NOT NULL,
    surname VARCHAR(255) NOT NULL
);

CREATE TABLE IF NOT EXISTS projects (
    id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    name VARCHAR(255) NOT NULL
);

CREATE TABLE IF NOT EXISTS states (
    id integer PRIMARY KEY,
    name VARCHAR(255) NOT NULL
);

CREATE TABLE IF NOT EXISTS task_types (
    id integer PRIMARY KEY,
    name VARCHAR(255) NOT NULL
);

CREATE TABLE IF NOT EXISTS tasks (
    id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,

    project_id BIGINT NOT NULL REFERENCES projects(id),
    employee_id BIGINT NOT NULL REFERENCES employees(id),

    description TEXT NOT NULL,

    state_id BIGINT NOT NULL REFERENCES states(id),
    type_id BIGINT NOT NULL REFERENCES task_types(id),

    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    deadline_at TIMESTAMPTZ NOT NULL
);

-- Сотрудники
INSERT INTO employees (name, surname)
VALUES
    ('Иван', 'Иванов'),
    ('Петр', 'Петров'),
    ('Анна', 'Сидорова');

-- Проекты
INSERT INTO projects (name)
VALUES
    ('Разработка API'),
    ('Мобильное приложение'),
    ('Веб-интерфейс');

-- Состояния задач
INSERT INTO states (id, name)
VALUES
    (1, 'Зарегистрирован'),
    (2, 'В реализации'),
    (3, 'На проверке'),
    (4, 'На исправлении ошибок'),
    (5, 'Закрыт');

-- Типы задач
INSERT INTO task_types (id, name)
VALUES
    (1, 'Задача'),
    (2, 'Ошибка'),
    (3, 'Требование');

-- Задачи
INSERT INTO tasks (
    project_id,
    employee_id,
    description,
    state_id,
    type_id,
    deadline_at
)
VALUES
    (1, 1, 'Разработать REST API для управления задачами', 2, 1, '2026-12-01 18:00:00+03'),
    (1, 2, 'Настроить подключение к PostgreSQL', 5, 1, '2026-11-20 18:00:00+03'),
    (2, 3, 'Разработать экран авторизации', 1, 1, '2026-12-05 18:00:00+03'),
    (2, 1, 'Исправить ошибку получения списка задач', 4, 2, '2026-11-25 18:00:00+03'),
    (3, 2, 'Провести рефакторинг главной страницы', 2, 3, '2026-12-10 18:00:00+03'),
    (3, 3, 'Протестировать маршрутизацию', 3, 1, '2026-11-28 18:00:00+03'),
    (1, 3, 'Написать документацию REST API', 1, 1, '2026-12-15 18:00:00+03');
