"""所有 ORM 模型的声明式基类。"""

from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    """共享的声明式基类。

    所有 persistence 模型继承自此类。
    """
