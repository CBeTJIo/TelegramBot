import sqlalchemy as sq
from sqlalchemy.orm import declarative_base, relationship

Base = declarative_base()

class Client(Base):
    __tablename__ = "client"

    id = sq.Column(sq.Integer, primary_key=True)
    name = sq.Column(sq.String(length=40), nullable=False, unique=True)
    user_step = sq.Column(sq.Integer, nullable=False)

class Words(Base):
    __tablename__ = "words"

    id = sq.Column(sq.Integer, primary_key=True)
    en_name = sq.Column(sq.String(length=40), nullable=False)
    ru_name = sq.Column(sq.String(length=40), nullable=False)
    client_id = sq.Column(sq.Integer, sq.ForeignKey("client.id"), nullable=False)

    client = relationship(Client, backref="words")

def create_tables(engine):
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)