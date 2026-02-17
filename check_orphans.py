from database import SessionLocal, User, UserCohort, Presenter, PresenterCohort, Cohort

def check_orphans():
    db = SessionLocal()
    try:
        print("Checking UserCohort...")
        ucs = db.query(UserCohort).all()
        for uc in ucs:
            if uc.user is None:
                print(f"Orphaned UserCohort! ID: {uc.id}, UserID: {uc.user_id}")
        
        print("Checking PresenterCohort...")
        pcs = db.query(PresenterCohort).all()
        for pc in pcs:
            if pc.presenter is None:
                print(f"Orphaned PresenterCohort! ID: {pc.id}, PresenterID: {pc.presenter_id}")
        
        print("Checking Cohorts...")
        cohorts = db.query(Cohort).all()
        for c in cohorts:
            print(f"Cohort ID: {c.id}, Name: {c.name}")
            
    finally:
        db.close()

if __name__ == "__main__":
    check_orphans()
