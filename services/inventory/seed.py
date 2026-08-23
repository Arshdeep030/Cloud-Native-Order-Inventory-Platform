from database import SessionLocal
from repository import create_inventory, get_inventory


def seed_inventory():
    db = SessionLocal()
    try:
        if not get_inventory(db, 1):
            create_inventory(db, product_id=1, quantity=100)
        if not get_inventory(db, 2):
            create_inventory(db, product_id=2, quantity=50)
        print("Inventory seeded successfully", flush=True)
    finally:
        db.close()


if __name__ == "__main__":
    seed_inventory()
