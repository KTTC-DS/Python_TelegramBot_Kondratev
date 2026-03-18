import os, datetime, psycopg2


# Создать класс Calendar
class Calendar:
    def __init__(self, conn):
        self.conn = conn


    # Работа с пользователями
    def register_user(self, user_id, username, first_name, last_name):
        """Добавляет пользователя в таблицу users, если его там нет."""
        try:
            with self.conn.cursor() as cur:
                cur.execute("SELECT user_id FROM users WHERE user_id = %s;", (user_id,))
                if cur.fetchone():
                    return False  # уже зарегистрирован
                cur.execute("""
                    INSERT INTO users (user_id, username, first_name, last_name)
                    VALUES (%s, %s, %s, %s);
                """, (user_id, username, first_name, last_name))
                self.conn.commit()
                return True
        except Exception:
            self.conn.rollback()
            raise

    def get_user(self, user_id):
        """Возвращает информацию о пользователе или None."""
        try:
            with self.conn.cursor() as cur:
                cur.execute("""
                    SELECT user_id, username, first_name, last_name, registered_at
                    FROM users
                    WHERE user_id = %s;
                """, (user_id,))
                row = cur.fetchone()
                if row:
                    return {
                        'user_id': row[0],
                        'username': row[1],
                        'first_name': row[2],
                        'last_name': row[3]
                    }
                return None
        except Exception:
            self.conn.rollback()  # откатываем транзакцию в случае ошибки
            raise  # пробрасываем исключение дальше

    def ensure_user(self, user_id, username, first_name, last_name):
        """Гарантирует наличие пользователя в БД (если нет — добавляет)."""
        user = self.get_user(user_id)
        if not user:
            self.register_user(user_id, username, first_name, last_name)
        return user


    # Создать метод
    def create_event(self, user_id, event_name, event_date, event_time, event_details):
        try:
            with self.conn.cursor() as cur:
                cur.execute("""
                    INSERT INTO events (user_id, name, date, time, details)
                    VALUES (%s, %s, %s, %s, %s)
                    RETURNING id;
                """, (user_id, event_name, event_date, event_time, event_details))
                event_id = cur.fetchone()[0]
                self.conn.commit()  # сохраняем изменения
                return event_id
        except Exception:
            self.conn.rollback()
        raise

    # Прочитать одно событие по id
    def read_event(self, user_id, event_id):
        try:
            with self.conn.cursor() as cur:
                cur.execute("""
                    SELECT id, name, date, time, details
                    FROM events
                    WHERE id = %s AND user_id = %s;
                """, (event_id, user_id))
                row = cur.fetchone()
                if row:
                    return {
                        'id': row[0],
                        'name': row[1],
                        'date': row[2],
                        'time': row[3],
                        'details': row[4]
                    }
                else:
                    return None
        except Exception:
            self.conn.rollback()
            raise

    # Изменить событие
    def edit_event(self, user_id, event_id, new_name=None, new_date=None, new_time=None, new_details=None):
        updates = []
        params = []
        try:
            if new_name is not None:
                updates.append("name = %s")
                params.append(new_name)
            if new_date is not None:
                updates.append("date = %s")
                params.append(new_date)
            if new_time is not None:
                updates.append("time = %s")
                params.append(new_time)
            if new_details is not None:
                updates.append("details = %s")
                params.append(new_details)
            if not updates:
                return False
            params.append(event_id)
            params.append(user_id)
            query = f"UPDATE events SET {', '.join(updates)} WHERE id = %s AND user_id = %s;"
            with self.conn.cursor() as cur:
                cur.execute(query, params)
                self.conn.commit()
                return cur.rowcount > 0  # True, если изменится хотя бы одна строка
        except Exception:
            self.conn.rollback()
            raise

    # Удалить событие
    def delete_event(self, user_id, event_id):
        try:
            with self.conn.cursor() as cur:
                cur.execute("DELETE FROM events WHERE id = %s AND user_id = %s;", (event_id, user_id))
                self.conn.commit()
                return cur.rowcount > 0
        except Exception:
            self.conn.rollback()
            raise

    # Показать событие
    def list_events(self, user_id):
        try:
            with self.conn.cursor() as cur:
                cur.execute("""
                    SELECT id, name, date, time, details
                    FROM events
                    WHERE user_id = %s
                    ORDER BY date, time;
                """, (user_id,))
                rows = cur.fetchall()
                events = []
                for row in rows:
                    events.append({
                        'id': row[0],
                        'name': row[1],
                        'date': row[2],
                        'time': row[3],
                        'details': row[4]
                    })
                return events
        except Exception:
            self.conn.rollback()
            raise