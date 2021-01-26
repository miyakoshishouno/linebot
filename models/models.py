from sqlalchemy import Column, Integer, String, Text, DateTime
from models.database import Base
from datetime import datetime

class yoyaku(Base):
    __tablename__ = 'yoyaku_table'
    id = Column(Integer, primary_key=True)
    # people = Column(String(10))
    note = Column(Text)
    yoyaku_date = Column(DateTime, default=datetime.now())