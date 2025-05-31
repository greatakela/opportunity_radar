# src/db.py
from sqlalchemy import (create_engine, Column, Integer, String, Text, Date,
                        Boolean, Float, ForeignKey, DateTime)
from sqlalchemy.orm import declarative_base, relationship, sessionmaker
from datetime import datetime
engine = create_engine("sqlite:///data/oppradar.db", echo=False, future=True)
Base = declarative_base()
Session = sessionmaker(bind=engine, expire_on_commit=False)

class Company(Base):
    __tablename__ = "company"
    id = Column(Integer, primary_key=True)
    name = Column(String, unique=True)
    domain = Column(String, unique=True)
    description = Column(Text)
    funding_stage = Column(String)
    employees = Column(Integer)
    headquarters = Column(String)
    created_at = Column(DateTime, default=datetime.utcnow)
    jobs = relationship("Job", back_populates="company")

class Job(Base):
    __tablename__ = "job"
    id = Column(Integer, primary_key=True)
    company_id = Column(Integer, ForeignKey("company.id"))
    title = Column(String)
    location = Column(String)
    posting_date = Column(Date)
    description = Column(Text)
    url = Column(String)
    remote = Column(Boolean)
    score = Column(Float)
    created_at = Column(DateTime, default=datetime.utcnow)
    company = relationship("Company", back_populates="jobs")

def init_db():
    Base.metadata.create_all(engine)
