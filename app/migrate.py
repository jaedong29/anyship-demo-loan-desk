"""Create this new demo's tables; does not alter existing columns or move data."""

from app.db import get_engine
from app.models import Base


def main() -> None:
    Base.metadata.create_all(get_engine())
    print("Loan Desk schema is ready.")


if __name__ == "__main__":
    main()
