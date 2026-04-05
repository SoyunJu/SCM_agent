from sqlalchemy.orm import sessionmaker, scoped_session

session_factory = sessionmaker(autocommit=False, autoflush=False, bind=engine)
SessionLocal = scoped_session(session_factory)