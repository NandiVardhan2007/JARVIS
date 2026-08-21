"""
VISION Task Tracker Database Layer.
Provides persistent storage, streak tracking, category analytics, and daily/monthly queries.
"""

import sqlite3
import os
from datetime import datetime, date
from typing import List, Dict, Any, Optional
from vision.logger import logger

DB_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "data", "task_tracker.sqlite")


class TaskTrackerDB:
    def __init__(self, db_path: str = DB_PATH):
        self.db_path = db_path
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
        self._init_db()

    def _get_conn(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path, timeout=15.0)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL;")
        return conn

    def _init_db(self):
        with self._get_conn() as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS tasks (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    title TEXT NOT NULL,
                    category TEXT NOT NULL DEFAULT 'General',
                    priority TEXT NOT NULL DEFAULT 'Medium',
                    year INTEGER NOT NULL,
                    month TEXT NOT NULL,
                    month_num INTEGER NOT NULL,
                    day INTEGER NOT NULL,
                    is_completed INTEGER NOT NULL DEFAULT 0,
                    created_at TEXT NOT NULL,
                    completed_at TEXT
                )
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_tasks_date ON tasks(year, month_num, day)
            """)
            conn.commit()

    @staticmethod
    def get_current_date_info():
        now = datetime.now()
        months = ["January", "February", "March", "April", "May", "June", 
                  "July", "August", "September", "October", "November", "December"]
        return {
            "year": now.year,
            "month": months[now.month - 1],
            "month_num": now.month,
            "day": now.day
        }

    def add_task(self, title: str, day: Optional[int] = None, month: Optional[str] = None, 
                 year: Optional[int] = None, category: str = "General", priority: str = "Medium") -> Dict[str, Any]:
        curr = self.get_current_date_info()
        year = year or curr["year"]
        
        months = ["January", "February", "March", "April", "May", "June", 
                  "July", "August", "September", "October", "November", "December"]
        
        if month:
            month_clean = month.capitalize()
            if month_clean in months:
                month_name = month_clean
                month_num = months.index(month_clean) + 1
            elif month.isdigit() and 1 <= int(month) <= 12:
                month_num = int(month)
                month_name = months[month_num - 1]
            else:
                month_name = curr["month"]
                month_num = curr["month_num"]
        else:
            month_name = curr["month"]
            month_num = curr["month_num"]

        day = day or curr["day"]
        created_at = datetime.now().isoformat()

        with self._get_conn() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO tasks (title, category, priority, year, month, month_num, day, is_completed, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, 0, ?)
            """, (title.strip(), category.capitalize(), priority.capitalize(), year, month_name, month_num, day, created_at))
            task_id = cursor.lastrowid
            conn.commit()

        logger.info(f"[TaskTrackerDB] Added task #{task_id}: '{title}' for {month_name} {day}, {year}")
        return self.get_task_by_id(task_id)

    def get_task_by_id(self, task_id: int) -> Optional[Dict[str, Any]]:
        with self._get_conn() as conn:
            row = conn.execute("SELECT * FROM tasks WHERE id = ?", (task_id,)).fetchone()
            if row:
                return dict(row)
        return None

    def toggle_task(self, task_id: int, completed: Optional[bool] = None) -> Optional[Dict[str, Any]]:
        with self._get_conn() as conn:
            row = conn.execute("SELECT is_completed FROM tasks WHERE id = ?", (task_id,)).fetchone()
            if not row:
                return None
            
            if completed is None:
                new_status = 0 if row["is_completed"] == 1 else 1
            else:
                new_status = 1 if completed else 0

            completed_at = datetime.now().isoformat() if new_status == 1 else None
            conn.execute("""
                UPDATE tasks 
                SET is_completed = ?, completed_at = ?
                WHERE id = ?
            """, (new_status, completed_at, task_id))
            conn.commit()

        logger.info(f"[TaskTrackerDB] Toggled task #{task_id} to completed={new_status}")
        return self.get_task_by_id(task_id)

    def complete_task_by_name(self, task_name: str, day: Optional[int] = None, month: Optional[str] = None, completed: bool = True) -> Optional[Dict[str, Any]]:
        curr = self.get_current_date_info()
        day = day or curr["day"]
        matched_id = None

        with self._get_conn() as conn:
            cursor = conn.cursor()
            query = "SELECT id, title FROM tasks WHERE LOWER(title) LIKE ? AND day = ?"
            params = [f"%{task_name.lower().strip()}%", day]
            if month:
                query += " AND (LOWER(month) = ? OR month_num = ?)"
                params.extend([month.lower(), int(month) if month.isdigit() else 0])
            
            row = cursor.execute(query, params).fetchone()
            if not row:
                # Try fallback matching title anywhere
                row = cursor.execute("SELECT id, title FROM tasks WHERE LOWER(title) LIKE ? ORDER BY id DESC LIMIT 1", (f"%{task_name.lower().strip()}%",)).fetchone()
            
            if row:
                matched_id = row["id"]

        if matched_id is not None:
            return self.toggle_task(matched_id, completed=completed)
        return None

    def delete_task(self, task_id: int) -> bool:
        with self._get_conn() as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM tasks WHERE id = ?", (task_id,))
            conn.commit()
            return cursor.rowcount > 0

    def get_tasks_for_day(self, day: Optional[int] = None, month: Optional[str] = None, year: Optional[int] = None) -> List[Dict[str, Any]]:
        curr = self.get_current_date_info()
        year = year or curr["year"]
        day = day or curr["day"]
        month_num = curr["month_num"]
        if month:
            months = ["January", "February", "March", "April", "May", "June", 
                      "July", "August", "September", "October", "November", "December"]
            if month.capitalize() in months:
                month_num = months.index(month.capitalize()) + 1
            elif month.isdigit():
                month_num = int(month)

        with self._get_conn() as conn:
            rows = conn.execute("""
                SELECT * FROM tasks 
                WHERE year = ? AND month_num = ? AND day = ?
                ORDER BY is_completed ASC, priority DESC, id ASC
            """, (year, month_num, day)).fetchall()
            return [dict(r) for r in rows]

    def get_tasks_for_month(self, month: Optional[str] = None, year: Optional[int] = None) -> List[Dict[str, Any]]:
        curr = self.get_current_date_info()
        year = year or curr["year"]
        month_num = curr["month_num"]
        if month:
            months = ["January", "February", "March", "April", "May", "June", 
                      "July", "August", "September", "October", "November", "December"]
            if month.capitalize() in months:
                month_num = months.index(month.capitalize()) + 1
    def ensure_daily_leetcode_tasks(self, year: Optional[int] = None, month_num: Optional[int] = None):
        """Ensure every single day (1..31) in the month has the Daily LeetCode Priority Habit scheduled."""
        curr = self.get_current_date_info()
        year = year or curr["year"]
        months = ["January", "February", "March", "April", "May", "June", 
                  "July", "August", "September", "October", "November", "December"]
        
        target_months = [month_num] if month_num else range(1, 13)
        created_at = datetime.now().isoformat()

        with self._get_conn() as conn:
            cursor = conn.cursor()
            for m in target_months:
                m_name = months[m - 1]
                for d in range(1, 32):
                    # Check if LeetCode task already exists for this day
                    row = cursor.execute("""
                        SELECT id FROM tasks 
                        WHERE year = ? AND month_num = ? AND day = ? AND LOWER(title) LIKE '%leetcode%'
                    """, (year, m, d)).fetchone()

                    if not row:
                        cursor.execute("""
                            INSERT INTO tasks (title, category, priority, year, month, month_num, day, is_completed, created_at)
                            VALUES (?, 'Coding', 'High', ?, ?, ?, ?, 0, ?)
                        """, ("Daily LeetCode Problem Solving (LeetCode / CodeChef / GFG)", year, m_name, m, d, created_at))
            conn.commit()

    def get_tasks_for_month(self, month: Optional[str] = None, year: Optional[int] = None) -> List[Dict[str, Any]]:
        curr = self.get_current_date_info()
        year = year or curr["year"]
        month_num = curr["month_num"]
        if month:
            months = ["January", "February", "March", "April", "May", "June", 
                      "July", "August", "September", "October", "November", "December"]
            if month.capitalize() in months:
                month_num = months.index(month.capitalize()) + 1
            elif month.isdigit():
                month_num = int(month)

        self.ensure_daily_leetcode_tasks(year=year, month_num=month_num)

        with self._get_conn() as conn:
            rows = conn.execute("""
                SELECT * FROM tasks 
                WHERE year = ? AND month_num = ?
                ORDER BY day ASC, priority DESC, is_completed ASC, id ASC
            """, (year, month_num)).fetchall()
            return [dict(r) for r in rows]

    def get_all_tasks(self, year: Optional[int] = None) -> List[Dict[str, Any]]:
        curr = self.get_current_date_info()
        year = year or curr["year"]
        self.ensure_daily_leetcode_tasks(year=year)
        with self._get_conn() as conn:
            rows = conn.execute("SELECT * FROM tasks WHERE year = ? ORDER BY month_num ASC, day ASC, id ASC", (year,)).fetchall()
            return [dict(r) for r in rows]

    def calculate_streak(self, year: Optional[int] = None) -> int:
        """Calculate continuous consecutive completed days up to today."""
        curr = self.get_current_date_info()
        today = date.today()
        streak = 0
        
        with self._get_conn() as conn:
            for i in range(365):
                check_date = date.fromordinal(today.toordinal() - i)
                rows = conn.execute("""
                    SELECT COUNT(*) as total, SUM(is_completed) as completed 
                    FROM tasks 
                    WHERE year = ? AND month_num = ? AND day = ?
                """, (check_date.year, check_date.month, check_date.day)).fetchone()
                
                total = rows["total"] or 0
                completed = rows["completed"] or 0
                
                if total > 0:
                    if completed == total:
                        streak += 1
                    else:
                        if i == 0:
                            continue
                        break
                else:
                    if i == 0:
                        continue
                    break
        return streak

    def calculate_leetcode_streak(self, year: Optional[int] = None) -> int:
        """Calculate consecutive days where the daily LeetCode task was solved."""
        curr = self.get_current_date_info()
        today = date.today()
        streak = 0
        
        with self._get_conn() as conn:
            for i in range(365):
                check_date = date.fromordinal(today.toordinal() - i)
                row = conn.execute("""
                    SELECT is_completed FROM tasks 
                    WHERE year = ? AND month_num = ? AND day = ? AND LOWER(title) LIKE '%leetcode%'
                """, (check_date.year, check_date.month, check_date.day)).fetchone()
                
                if row:
                    if row["is_completed"] == 1:
                        streak += 1
                    else:
                        if i == 0:
                            # Today hasn't been solved yet, don't break streak
                            continue
                        break
                else:
                    if i == 0:
                        continue
                    break
        return streak

    def get_dashboard_summary(self, day: Optional[int] = None, month: Optional[str] = None, year: Optional[int] = None) -> Dict[str, Any]:
        curr = self.get_current_date_info()
        day = day or curr["day"]
        month_name = month or curr["month"]
        year = year or curr["year"]
        
        day_tasks = self.get_tasks_for_day(day=day, month=month_name, year=year)
        month_tasks = self.get_tasks_for_month(month=month_name, year=year)

        day_total = len(day_tasks)
        day_completed = sum(1 for t in day_tasks if t["is_completed"] == 1)
        day_pending = day_total - day_completed
        day_rate = round((day_completed / day_total * 100) if day_total > 0 else 0, 1)

        month_total = len(month_tasks)
        month_completed = sum(1 for t in month_tasks if t["is_completed"] == 1)
        month_pending = month_total - month_completed
        month_rate = round((month_completed / month_total * 100) if month_total > 0 else 0, 1)

        categories = {}
        days_map = {d: {"day": d, "total": 0, "completed": 0, "pending": 0, "completion_rate": 0.0, "tasks": []} for d in range(1, 32)}
        
        for t in month_tasks:
            cat = t["category"] or "General"
            if cat not in categories:
                categories[cat] = {"total": 0, "completed": 0}
            categories[cat]["total"] += 1
            if t["is_completed"] == 1:
                categories[cat]["completed"] += 1

            t_day = t["day"]
            if 1 <= t_day <= 31:
                days_map[t_day]["tasks"].append(t)
                days_map[t_day]["total"] += 1
                if t["is_completed"] == 1:
                    days_map[t_day]["completed"] += 1

        for d, d_data in days_map.items():
            d_data["pending"] = d_data["total"] - d_data["completed"]
            d_data["completion_rate"] = round((d_data["completed"] / d_data["total"] * 100) if d_data["total"] > 0 else 0, 1)

        streak = self.calculate_streak(year=year)
        leetcode_streak = self.calculate_leetcode_streak(year=year)
        leetcode_today_done = any(t["is_completed"] == 1 and "leetcode" in (t["title"] or "").lower() for t in day_tasks)
        leetcode_month_done = sum(1 for t in month_tasks if t["is_completed"] == 1 and "leetcode" in (t["title"] or "").lower())

        return {
            "selected_day": day,
            "selected_month": month_name,
            "year": year,
            "today_info": curr,
            "day_metrics": {
                "total": day_total,
                "completed": day_completed,
                "pending": day_pending,
                "completion_rate": day_rate,
                "tasks": day_tasks
            },
            "month_metrics": {
                "total": month_total,
                "completed": month_completed,
                "pending": month_pending,
                "completion_rate": month_rate,
                "category_breakdown": categories,
                "days_breakdown": days_map
            },
            "leetcode_metrics": {
                "streak": leetcode_streak,
                "today_done": leetcode_today_done,
                "month_solved": leetcode_month_done,
                "monthly_target": len(days_map)
            },
            "streak_days": streak,
            "productivity_score": month_rate
        }


# Singleton database instance
task_db = TaskTrackerDB()
