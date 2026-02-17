from database import SessionLocal, User, UserCohort, Presenter, PresenterCohort

def cleanup_orphans():
    db = SessionLocal()
    try:
        print("Cleaning up UserCohort orphans...")
        ucs = db.query(UserCohort).all()
        user_ids = {u.id for u in db.query(User.id).all()}
        deleted_count = 0
        for uc in ucs:
            if uc.user_id not in user_ids:
                print(f"Deleting orphaned UserCohort! ID: {uc.id}, UserID: {uc.user_id}")
                db.delete(uc)
                deleted_count += 1
        
        print("Cleaning up PresenterCohort orphans...")
        pcs = db.query(PresenterCohort).all()
        presenter_ids = {p.id for p in db.query(Presenter.id).all()}
        for pc in pcs:
            if pc.presenter_id not in presenter_ids:
                print(f"Deleting orphaned PresenterCohort! ID: {pc.id}, PresenterID: {pc.presenter_id}")
                db.delete(pc)
                deleted_count += 1
        
        db.commit()
        print(f"Cleanup complete. Total orphans deleted: {deleted_count}")
            
    except Exception as e:
        print(f"Error during cleanup: {e}")
        db.rollback()
    finally:
        db.close()

if __name__ == "__main__":
    cleanup_orphans()
