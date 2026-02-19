from database import engine
from sqlalchemy import text

def check_columns():
    with engine.connect() as conn:
        try:
            res_courses = conn.execute(text("SHOW COLUMNS FROM courses"))
            print("Courses columns:", [r[0] for r in res_courses])
        except Exception as e:
            print(f"Error checking courses: {e}")
            
        try:
            res_cohort = conn.execute(text("SHOW COLUMNS FROM cohort_specific_courses"))
            print("Cohort Courses columns:", [r[0] for r in res_cohort])
        except Exception as e:
            print(f"Error checking cohort_specific_courses: {e}")

if __name__ == "__main__":
    check_columns()
