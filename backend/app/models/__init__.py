from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    """Shared declarative base. Every ORM model inherits from this,

    so ``Base.metadata`` contains all tables for Alembic autogenerate checks.
    """
