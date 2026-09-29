import os
from decimal import Decimal
from datetime import date, timedelta
from dotenv import load_dotenv

from app.database import engine, Base, SessionLocal
from app.models import Supplier, Customer, Item, Sale, SaleItem, User
from app.services import next_code, apply_stock_change, money

load_dotenv()
Base.metadata.create_all(bind=engine)

db = SessionLocal()
try:
    print("Checking database records...")
    
    # Ensure suppliers
    supps_data = [
        ("Master Sanitary Ware Ltd", "Muhammad Tariq", "0300-5551234", "Industrial Area, Gujranwala", 0),
        ("Sonex Ceramics & Sanitary", "Hamza Siddiqui", "0321-7774321", "G.T. Road, Wazirabad", 15000),
        ("Porta Bath & Fixtures", "Kashif Mehmood", "0333-8889900", "Plot 45, SITE Industrial Estate, Karachi", 25000),
        ("Grohe Fittings & Valves", "Salman Rizvi", "0345-1239876", "Ferozepur Road, Lahore", 0),
    ]
    for name, cp, phone, addr, bal in supps_data:
        exists = db.query(Supplier).filter(Supplier.name == name).first()
        if not exists:
            s = Supplier(
                supplier_code=next_code(db, Supplier, "supplier_code", "SUPP"),
                name=name, contact_person=cp, phone=phone, address=addr,
                opening_balance=bal, current_balance=bal, status="Active"
            )
            db.add(s)
            db.flush()

    # Ensure customers
    custs_data = [
        ("Al-Rehman Builders & Contractors", "0301-4445566", "DHA Phase 6, Lahore", "DHA Phase 6 Villa Project", 45000),
        ("Apex Interior Decorators", "0322-8881122", "Blue Area, Islamabad", "Centaurus Plaza Suite 402", 0),
        ("Modern Living Developers", "0334-9993344", "Clifton Block 4, Karachi", "Ocean Heights Tower", 18500),
        ("Tariq Construction Co.", "0312-3334455", "Gulberg III, Lahore", "Gulberg Commercial Center", 0),
    ]
    for name, phone, addr, proj, bal in custs_data:
        exists = db.query(Customer).filter(Customer.name == name).first()
        if not exists:
            c = Customer(
                customer_code=next_code(db, Customer, "customer_code", "CUST"),
                name=name, phone=phone, address=addr, vehicle_info=proj,
                opening_balance=bal, current_balance=bal, status="Active", is_walk_in=False
            )
            db.add(c)
            db.flush()

    # Update any existing items with category names
    i_basin = db.query(Item).filter(Item.item_code == "SANI-0001").first()
    if i_basin:
        i_basin.category = "Wash Basins"
        i_basin.description = "Ceramic / Porcelain"
    i_wc = db.query(Item).filter(Item.item_code == "SANI-0002").first()
    if i_wc:
        i_wc.category = "Toilets & Commodes"
        i_wc.description = "Ceramic / Porcelain"
    i_tap = db.query(Item).filter(Item.item_code == "SANI-0003").first()
    if i_tap:
        i_tap.category = "Taps & Faucets"
        i_tap.description = "Brass / Chrome"

    # Add realistic sanitary catalog
    sanitary_items = [
        ("Grohe", "Luxury Rain Shower System 300", "GR-RS300", "Showers & Panels", "Brass / Chrome", 22000.00, 27500.00, 18, 5, "Set"),
        ("Porta", "Double Bowl Kitchen Sink SS304", "PT-KS202", "Kitchen Sinks", "Stainless Steel", 14500.00, 18200.00, 22, 6, "Piece"),
        ("Faisal", "Italian Bath Vanity Set 80cm", "FS-VN80", "Vanities & Cabinets", "Ceramic / Porcelain", 38000.00, 46000.00, 8, 3, "Set"),
        ("Sonex", "Concealed Diverter Bath Valve", "SX-DV04", "Taps & Faucets", "Brass / Chrome", 5500.00, 6900.00, 45, 10, "Piece"),
        ("Master", "Dual Flush One-Piece Toilet Suite", "MS-DF01", "Toilets & Commodes", "Ceramic / Porcelain", 18500.00, 22800.00, 14, 4, "Set"),
        ("Sonex", "6-Piece Chrome Accessory Set", "SX-AC06", "Bathroom Accessories", "Brass / Chrome", 4200.00, 5600.00, 35, 8, "Set"),
        ("IIL", "PPR High-Pressure Pipes 25mm", "IIL-PPR25", "Plumbing & Pipes", "PPR / UPVC", 850.00, 1150.00, 120, 25, "Piece"),
        ("Faisal", "Heavy Brass Floor Drain 150mm", "FS-FD15", "Plumbing & Pipes", "Brass / Chrome", 1600.00, 2200.00, 60, 15, "Piece"),
        ("Porta", "Smart LED Touch Vanity Mirror 60x80", "PT-MR60", "Bathroom Accessories", "Other", 9500.00, 12500.00, 12, 4, "Piece"),
        ("Sonex", "Swan Neck Tall Basin Mixer", "SX-SN10", "Taps & Faucets", "Matte Black", 4800.00, 6200.00, 28, 8, "Piece"),
    ]

    for brand, name, bcode, cat, desc, p_price, s_price, stock, reorder, unit in sanitary_items:
        exists = db.query(Item).filter(Item.barcode == bcode).first()
        if not exists:
            item = Item(
                item_code=next_code(db, Item, "item_code", "SANI"),
                brand=brand,
                name=name,
                barcode=bcode,
                category=cat,
                description=desc,
                purchase_price=Decimal(str(p_price)),
                sale_price=Decimal(str(s_price)),
                current_stock=stock,
                reorder_level=reorder,
                unit=unit,
                status="Active"
            )
            db.add(item)
            db.flush()

    db.commit()

    # Add 2 sample sales if none exist so dashboard has active metrics
    admin_user = db.query(User).filter(User.username == "admin").first()
    user_id = admin_user.id if admin_user else 1
    
    if db.query(Sale).count() == 0:
        cust1 = db.query(Customer).filter(Customer.name.like("%Rehman%")).first()
        cust_id = cust1.id if cust1 else 1
        
        item1 = db.query(Item).filter(Item.brand == "Grohe").first()
        item2 = db.query(Item).filter(Item.brand == "Faisal").first()
        
        if item1 and item2:
            s1_inv = next_code(db, Sale, "invoice_no", "SINV")
            s1_tot = money(item1.sale_price * 2 + item2.sale_price * 1)
            sale1 = Sale(
                invoice_no=s1_inv, date=date.today(), customer_id=cust_id,
                total_amount=s1_tot, amount_received=s1_tot, balance=0,
                payment_method="Bank Transfer", note="Project Delivery Phase 1",
                created_by=user_id
            )
            db.add(sale1)
            db.flush()
            db.add(SaleItem(sale_id=sale1.id, item_id=item1.id, quantity=2, unit_price=item1.sale_price, subtotal=money(item1.sale_price * 2)))
            db.add(SaleItem(sale_id=sale1.id, item_id=item2.id, quantity=1, unit_price=item2.sale_price, subtotal=money(item2.sale_price * 1)))
            
            # Yesterday sale
            s2_inv = next_code(db, Sale, "invoice_no", "SINV")
            s2_tot = money(item2.sale_price * 2)
            sale2 = Sale(
                invoice_no=s2_inv, date=date.today() - timedelta(days=1), customer_id=cust_id,
                total_amount=s2_tot, amount_received=s2_tot, balance=0,
                payment_method="Cash", note="Direct Counter Sale",
                created_by=user_id
            )
            db.add(sale2)
            db.flush()
            db.add(SaleItem(sale_id=sale2.id, item_id=item2.id, quantity=2, unit_price=item2.sale_price, subtotal=s2_tot))
            
            db.commit()
            print("Created 2 sample sales with line items.")

        # Seed sample purchase if none exist
        from app.models import Purchase, PurchaseItem
        if db.query(Purchase).count() == 0:
            supp = db.query(Supplier).first()
            i1 = db.query(Item).filter(Item.item_code == "SANI-0001").first()
            i2 = db.query(Item).filter(Item.item_code == "SANI-0003").first()
            if supp and i1 and i2:
                p_inv = next_code(db, Purchase, "invoice_no", "PINV")
                p_tot = money((i1.cost_price * 5) + (i2.cost_price * 10))
                p_paid = money(p_tot * Decimal("0.7"))
                purchase1 = Purchase(
                    invoice_no=p_inv, date=date.today() - timedelta(days=2),
                    supplier_id=supp.id, total_amount=p_tot, amount_paid=p_paid,
                    balance=money(p_tot - p_paid), payment_method="Bank Transfer",
                    note="Initial Inventory Stocking - Bath Fixtures",
                    created_by=user_id
                )
                db.add(purchase1)
                db.flush()
                db.add(PurchaseItem(purchase_id=purchase1.id, item_id=i1.id, quantity=5, unit_price=i1.cost_price, subtotal=money(i1.cost_price * 5)))
                db.add(PurchaseItem(purchase_id=purchase1.id, item_id=i2.id, quantity=10, unit_price=i2.cost_price, subtotal=money(i2.cost_price * 10)))
                db.commit()
                print("Created sample purchase order with line items.")

    print(f"Database successfully enriched: {db.query(Item).count()} items, {db.query(Supplier).count()} suppliers, {db.query(Customer).count()} customers.")
except Exception as e:
    print(f"Error seeding database: {e}")
    db.rollback()
finally:
    db.close()
