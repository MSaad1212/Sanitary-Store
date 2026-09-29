"""Comprehensive End-to-End Automated Test Suite for Arshaf Sanitary Store Management System.
Tests Authentication, Security, Products, Inventory, Customers, POS Sales, Suppliers,
Purchases, Returns, Ledgers, Reports, and Print Invoices against an isolated in-memory database.
"""
import unittest
from datetime import date, timedelta
from decimal import Decimal
import os
import sys

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

# Ensure project root is in sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from run import app
from app.database import get_db, Base
from app.models import (
    User, Item, ItemCategory, ItemType, StockMovement,
    Customer, CustomerLedger, Supplier, SupplierLedger,
    Sale, SaleItem, Purchase, PurchaseItem,
    CustomerReturn, CustomerReturnItem, SupplierReturn, SupplierReturnItem,
    PaymentReceived, PaymentMade, AuditLog
)
from app.auth import hash_password, create_session_token, SESSION_COOKIE_NAME
from app.services import ensure_walk_in_customer, money, apply_stock_change


class SanitaryStoreFullTestSuite(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # Create an isolated in-memory SQLite database
        cls.engine = create_engine(
            "sqlite://",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool
        )
        cls.TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=cls.engine)
        Base.metadata.create_all(bind=cls.engine)

        # Seed essential base data
        db = cls.TestingSessionLocal()
        # Admin user
        admin = User(
            username="admin",
            password_hash=hash_password("admin123"),
            role="Admin",
            status="Active"
        )
        db.add(admin)
        # Walk-in customer
        ensure_walk_in_customer(db)
        # Categories and types
        for cat in ["Wash Basins", "Taps & Faucets", "Showers & Panels", "Toilets & Commodes"]:
            db.add(ItemCategory(name=cat))
        for typ in ["Ceramic / Porcelain", "Brass / Chrome", "Stainless Steel"]:
            db.add(ItemType(name=typ))
        db.commit()
        cls.admin_id = admin.id
        db.close()

        def override_get_db():
            db_session = cls.TestingSessionLocal()
            try:
                yield db_session
            finally:
                db_session.close()

        app.dependency_overrides[get_db] = override_get_db
        cls.client = TestClient(app)

    @classmethod
    def tearDownClass(cls):
        app.dependency_overrides.clear()
        cls.engine.dispose()

    def setUp(self):
        # Authenticate client with admin token by default
        self.auth_token = create_session_token(self.admin_id)
        self.client.cookies.set(SESSION_COOKIE_NAME, self.auth_token)

    # =========================================================================
    # 1. AUTHENTICATION & SECURITY
    # =========================================================================
    def test_01_login_page_renders(self):
        # Client without cookies
        unauth_client = TestClient(app)
        res = unauth_client.get("/login")
        self.assertEqual(res.status_code, 200)
        self.assertIn("Arshaf Sanitary Store", res.text)
        self.assertIn("Sign In", res.text)

    def test_02_login_invalid_credentials(self):
        unauth_client = TestClient(app)
        res = unauth_client.post("/login", data={"username": "admin", "password": "wrongpassword"})
        self.assertEqual(res.status_code, 200)
        self.assertIn("Invalid username or password", res.text)

    def test_03_login_lockout_after_5_attempts(self):
        db = self.TestingSessionLocal()
        test_user = User(username="locktest", password_hash=hash_password("pass123"), role="Staff", status="Active")
        db.add(test_user)
        db.commit()
        db.close()

        unauth_client = TestClient(app)
        for i in range(1, 5):
            res = unauth_client.post("/login", data={"username": "locktest", "password": "bad"})
            self.assertIn(f"Attempt {i}/5", res.text)
        
        # 5th attempt locks the account
        res = unauth_client.post("/login", data={"username": "locktest", "password": "bad"})
        self.assertIn("Account locked", res.text)

    def test_04_login_success(self):
        unauth_client = TestClient(app)
        res = unauth_client.post("/login", data={"username": "admin", "password": "admin123"}, follow_redirects=False)
        self.assertEqual(res.status_code, 303)
        self.assertEqual(res.headers["location"], "/")
        self.assertIn(SESSION_COOKIE_NAME, res.cookies)

    def test_05_unauthorized_redirect(self):
        unauth_client = TestClient(app)
        res = unauth_client.get("/users", follow_redirects=False)
        self.assertEqual(res.status_code, 303)
        self.assertEqual(res.headers["location"], "/login")

    def test_06_user_crud_and_toggle_status(self):
        # Create user
        res = self.client.post("/users", data={"username": "manager1", "password": "secretpassword", "role": "Admin"}, follow_redirects=True)
        self.assertEqual(res.status_code, 200)
        self.assertIn("manager1", res.text)

        db = self.TestingSessionLocal()
        user = db.query(User).filter(User.username == "manager1").first()
        self.assertIsNotNone(user)
        user_id = user.id
        db.close()

        # Toggle status to Inactive
        res = self.client.post(f"/users/{user_id}/toggle-status", follow_redirects=True)
        self.assertEqual(res.status_code, 200)
        db = self.TestingSessionLocal()
        user = db.query(User).filter(User.id == user_id).first()
        self.assertEqual(user.status, "Inactive")
        db.close()

        # Deactivated user cannot login
        unauth_client = TestClient(app)
        res = unauth_client.post("/login", data={"username": "manager1", "password": "secretpassword"})
        self.assertIn("Account is inactive", res.text)

        # Toggle status back to Active
        self.client.post(f"/users/{user_id}/toggle-status", follow_redirects=True)

        # Reset password
        res = self.client.post(f"/users/{user_id}/reset-password", data={"new_password": "newpassword123"}, follow_redirects=True)
        self.assertEqual(res.status_code, 200)
        self.assertIn("Password reset for manager1", res.text)

    # =========================================================================
    # 2. SETTINGS & TAXONOMIES
    # =========================================================================
    def test_07_settings_categories_and_types(self):
        res = self.client.get("/settings")
        self.assertEqual(res.status_code, 200)
        self.assertIn("Wash Basins", res.text)

        # Add category
        res = self.client.post("/settings/categories/add", data={"name": "Kitchen Sinks"}, follow_redirects=True)
        self.assertEqual(res.status_code, 200)
        self.assertIn("Kitchen Sinks", res.text)

        # Add duplicate category rejected
        res = self.client.post("/settings/categories/add", data={"name": "Kitchen Sinks"}, follow_redirects=True)
        self.assertIn("Category already exists", res.text)

        # Add finish type
        res = self.client.post("/settings/types/add", data={"name": "Matte Black"}, follow_redirects=True)
        self.assertEqual(res.status_code, 200)
        self.assertIn("Matte Black", res.text)

    # =========================================================================
    # 3. PRODUCTS & INVENTORY
    # =========================================================================
    def test_08_create_and_update_item(self):
        # Create item
        res = self.client.post("/stock/new", data={
            "brand": "Master Sanitary",
            "name": "Luxury Wall-Hung Vanity Basin",
            "category": "Wash Basins",
            "description": "Ceramic / Porcelain",
            "barcode": "112233445566",
            "purchase_price": "8500.00",
            "sale_price": "12500.00",
            "reorder_level": "5",
            "unit": "Piece",
            "status": "Active"
        }, follow_redirects=True)
        self.assertEqual(res.status_code, 200)
        self.assertIn("Luxury Wall-Hung Vanity Basin", res.text)
        self.assertIn("ITM-0001", res.text)

        db = self.TestingSessionLocal()
        item = db.query(Item).filter(Item.item_code == "ITM-0001").first()
        self.assertIsNotNone(item)
        self.assertEqual(item.brand, "Master Sanitary")
        self.assertEqual(item.name, "Luxury Wall-Hung Vanity Basin")
        self.assertEqual(item.current_stock, 0)
        item_id = item.id
        db.close()

        # Update item
        res = self.client.post(f"/stock/{item_id}/edit", data={
            "brand": "Master Sanitary Pro",
            "name": "Luxury Wall-Hung Vanity Basin Elite",
            "category": "Wash Basins",
            "description": "Ceramic / Porcelain",
            "barcode": "112233445566",
            "purchase_price": "9000.00",
            "sale_price": "13000.00",
            "reorder_level": "8",
            "unit": "Piece",
            "status": "Active"
        }, follow_redirects=True)
        self.assertEqual(res.status_code, 200)
        self.assertIn("Master Sanitary Pro", res.text)

    def test_09_stock_adjustment_and_negative_prevention(self):
        db = self.TestingSessionLocal()
        item = db.query(Item).filter(Item.item_code == "ITM-0001").first()
        item_id = item.id
        db.close()

        # Adjust +25
        res = self.client.post(f"/stock/{item_id}/adjust", data={
            "quantity_change": "25",
            "reason": "Opening physical count verification"
        }, follow_redirects=True)
        self.assertEqual(res.status_code, 200)

        db = self.TestingSessionLocal()
        item = db.query(Item).filter(Item.id == item_id).first()
        self.assertEqual(item.current_stock, 25)
        # Verify movement logged
        mv = db.query(StockMovement).filter(StockMovement.item_id == item_id).order_by(StockMovement.id.desc()).first()
        self.assertIsNotNone(mv)
        self.assertEqual(mv.movement_type, "adjustment")
        self.assertEqual(mv.quantity_change, 25)
        self.assertEqual(mv.quantity_after, 25)
        db.close()

        # Adjust negative exceeding current stock (attempt -30 when stock is 25)
        res = self.client.post(f"/stock/{item_id}/adjust", data={
            "quantity_change": "-30",
            "reason": "Excess deduction"
        }, follow_redirects=True)
        self.assertEqual(res.status_code, 200)
        self.assertIn("Insufficient stock", res.text)

        # Verify stock remains unchanged at 25
        db = self.TestingSessionLocal()
        item = db.query(Item).filter(Item.id == item_id).first()
        self.assertEqual(item.current_stock, 25)
        db.close()

    def test_10_stock_deletion_safeguard(self):
        db = self.TestingSessionLocal()
        item = db.query(Item).filter(Item.item_code == "ITM-0001").first()
        item_id = item.id
        db.close()

        # Item has stock movements, so delete should deactivate ("Discontinued") instead of throwing FK error
        res = self.client.post(f"/stock/{item_id}/delete", follow_redirects=True)
        self.assertEqual(res.status_code, 200)

        db = self.TestingSessionLocal()
        item = db.query(Item).filter(Item.id == item_id).first()
        self.assertIsNotNone(item)
        self.assertEqual(item.status, "Discontinued")

        # Reactivate item for subsequent sales/purchase tests
        item.status = "Active"
        db.commit()
        db.close()

    # =========================================================================
    # 4. SUPPLIERS & PURCHASES
    # =========================================================================
    def test_11_create_supplier_and_ledger(self):
        res = self.client.post("/suppliers/new", data={
            "name": "Pak Sanitary Industries",
            "contact_person": "Haji Aslam",
            "phone": "0300-1234567",
            "address": "Gujranwala Industrial Estate",
            "opening_balance": "50000.00",
            "status": "Active"
        }, follow_redirects=True)
        self.assertEqual(res.status_code, 200)
        self.assertIn("Pak Sanitary Industries", res.text)

        db = self.TestingSessionLocal()
        supplier = db.query(Supplier).filter(Supplier.name == "Pak Sanitary Industries").first()
        self.assertIsNotNone(supplier)
        self.assertEqual(supplier.opening_balance, Decimal("50000.00"))
        self.assertEqual(supplier.current_balance, Decimal("50000.00"))
        # Verify opening ledger entry
        ledger = db.query(SupplierLedger).filter(SupplierLedger.supplier_id == supplier.id).first()
        self.assertIsNotNone(ledger)
        self.assertEqual(ledger.balance, Decimal("50000.00"))
        db.close()

    def test_12_purchase_inward_increases_stock_and_ledger(self):
        db = self.TestingSessionLocal()
        supplier = db.query(Supplier).filter(Supplier.name == "Pak Sanitary Industries").first()
        item = db.query(Item).filter(Item.item_code == "ITM-0001").first()
        supp_id = supplier.id
        item_id = item.id
        initial_stock = item.current_stock
        initial_balance = supplier.current_balance
        db.close()

        # Create purchase bill: 10 units @ Rs 9,000 = Rs 90,000. Paid Rs 30,000 cash.
        res = self.client.post("/suppliers/purchases/new", data={
            "supplier_id": str(supp_id),
            "date": date.today().isoformat(),
            "payment_method": "Cash",
            "amount_paid": "30000.00",
            "note": "Initial shipment container 1",
            "item_id": [str(item_id)],
            "quantity": ["10"],
            "unit_price": ["9000.00"]
        }, follow_redirects=True)
        self.assertEqual(res.status_code, 200)

        db = self.TestingSessionLocal()
        # Verify item stock increased by 10
        item = db.query(Item).filter(Item.id == item_id).first()
        self.assertEqual(item.current_stock, initial_stock + 10)

        # Verify supplier balance: initial (50,000) + total purchase (90,000) - paid (30,000) = 110,000
        supplier = db.query(Supplier).filter(Supplier.id == supp_id).first()
        self.assertEqual(supplier.current_balance, Decimal("110000.00"))

        # Verify purchase record
        purchase = db.query(Purchase).filter(Purchase.supplier_id == supp_id).first()
        self.assertIsNotNone(purchase)
        self.assertEqual(purchase.total_amount, Decimal("90000.00"))
        self.assertEqual(purchase.amount_paid, Decimal("30000.00"))
        self.assertEqual(purchase.balance, Decimal("60000.00"))
        db.close()

    def test_13_supplier_payment(self):
        db = self.TestingSessionLocal()
        supplier = db.query(Supplier).filter(Supplier.name == "Pak Sanitary Industries").first()
        supp_id = supplier.id
        current_bal = supplier.current_balance
        db.close()

        # Pay Rs 20,000 to supplier
        res = self.client.post("/suppliers/payments/new", data={
            "supplier_id": str(supp_id),
            "date": date.today().isoformat(),
            "amount": "20000.00",
            "payment_method": "Bank Transfer",
            "note": "Online payment via HBL"
        }, follow_redirects=True)
        self.assertEqual(res.status_code, 200)

        db = self.TestingSessionLocal()
        supplier = db.query(Supplier).filter(Supplier.id == supp_id).first()
        # Balance should decrease by 20,000
        self.assertEqual(supplier.current_balance, current_bal - Decimal("20000.00"))
        db.close()

    # =========================================================================
    # 5. CUSTOMERS & POS SALES
    # =========================================================================
    def test_14_create_customer(self):
        res = self.client.post("/customers/new", data={
            "name": "Al-Rehman Builders & Contractors",
            "phone": "0321-9876543",
            "address": "Model Town Lahore",
            "vehicle_info": "Toyota Hilux LE-7890",
            "opening_balance": "15000.00",
            "status": "Active"
        }, follow_redirects=True)
        self.assertEqual(res.status_code, 200)
        self.assertIn("Al-Rehman Builders", res.text)

        db = self.TestingSessionLocal()
        customer = db.query(Customer).filter(Customer.name == "Al-Rehman Builders & Contractors").first()
        self.assertIsNotNone(customer)
        self.assertEqual(customer.current_balance, Decimal("15000.00"))
        db.close()

    def test_15_pos_cash_sale_walk_in(self):
        db = self.TestingSessionLocal()
        walk_in = db.query(Customer).filter(Customer.is_walk_in == True).first()
        item = db.query(Item).filter(Item.item_code == "ITM-0001").first()
        walk_in_id = walk_in.id
        item_id = item.id
        stock_before = item.current_stock
        db.close()

        # Sell 2 units @ Rs 13,000 = Rs 26,000 (Full cash)
        res = self.client.post("/customers/sales/new", data={
            "customer_id": str(walk_in_id),
            "date": date.today().isoformat(),
            "payment_method": "Cash",
            "amount_received": "26000.00",
            "note": "POS Cash Sale Counter 1",
            "item_id": [str(item_id)],
            "quantity": ["2"],
            "unit_price": ["13000.00"]
        }, follow_redirects=True)
        self.assertEqual(res.status_code, 200)
        self.assertIn("Invoice", res.text)

        db = self.TestingSessionLocal()
        item = db.query(Item).filter(Item.id == item_id).first()
        self.assertEqual(item.current_stock, stock_before - 2)

        # Walk-in balance should always remain 0
        walk_in = db.query(Customer).filter(Customer.id == walk_in_id).first()
        self.assertEqual(walk_in.current_balance, Decimal("0.00"))
        db.close()

    def test_16_pos_credit_sale_and_insufficient_stock(self):
        db = self.TestingSessionLocal()
        cust = db.query(Customer).filter(Customer.name == "Al-Rehman Builders & Contractors").first()
        item = db.query(Item).filter(Item.item_code == "ITM-0001").first()
        cust_id = cust.id
        item_id = item.id
        stock_before = item.current_stock
        bal_before = cust.current_balance
        db.close()

        # Attempt to sell 999 units (exceeds stock) -> should reject
        res = self.client.post("/customers/sales/new", data={
            "customer_id": str(cust_id),
            "date": date.today().isoformat(),
            "payment_method": "Credit Account",
            "amount_received": "0",
            "item_id": [str(item_id)],
            "quantity": ["999"],
            "unit_price": ["13000.00"]
        })
        self.assertEqual(res.status_code, 200)
        self.assertIn("Insufficient stock", res.text)

        # Successful Credit Sale: 5 units @ Rs 13,000 = Rs 65,000. Received Rs 20,000 partial.
        res = self.client.post("/customers/sales/new", data={
            "customer_id": str(cust_id),
            "date": date.today().isoformat(),
            "payment_method": "Credit Account",
            "amount_received": "20000.00",
            "note": "Commercial Project Phase 2",
            "item_id": [str(item_id)],
            "quantity": ["5"],
            "unit_price": ["13000.00"]
        }, follow_redirects=True)
        self.assertEqual(res.status_code, 200)

        db = self.TestingSessionLocal()
        item = db.query(Item).filter(Item.id == item_id).first()
        self.assertEqual(item.current_stock, stock_before - 5)

        # Customer balance should increase by net credit (65,000 - 20,000 = +45,000)
        cust = db.query(Customer).filter(Customer.id == cust_id).first()
        self.assertEqual(cust.current_balance, bal_before + Decimal("45000.00"))
        db.close()

    def test_17_customer_payment_received(self):
        db = self.TestingSessionLocal()
        cust = db.query(Customer).filter(Customer.name == "Al-Rehman Builders & Contractors").first()
        cust_id = cust.id
        bal_before = cust.current_balance
        db.close()

        # Receive payment Rs 25,000
        res = self.client.post("/customers/payments/new", data={
            "customer_id": str(cust_id),
            "date": date.today().isoformat(),
            "amount": "25000.00",
            "payment_method": "Bank Transfer",
            "note": "Cheque clearance"
        }, follow_redirects=True)
        self.assertEqual(res.status_code, 200)

        db = self.TestingSessionLocal()
        cust = db.query(Customer).filter(Customer.id == cust_id).first()
        self.assertEqual(cust.current_balance, bal_before - Decimal("25000.00"))
        db.close()

    # =========================================================================
    # 6. RETURNS MANAGEMENT
    # =========================================================================
    def test_18_customer_return_restores_stock_and_credits_ledger(self):
        db = self.TestingSessionLocal()
        cust = db.query(Customer).filter(Customer.name == "Al-Rehman Builders & Contractors").first()
        item = db.query(Item).filter(Item.item_code == "ITM-0001").first()
        cust_id = cust.id
        item_id = item.id
        stock_before = item.current_stock
        bal_before = cust.current_balance
        db.close()

        # Customer returns 1 unit @ Rs 13,000
        res = self.client.post("/returns/customer/new", data={
            "customer_id": str(cust_id),
            "date": date.today().isoformat(),
            "refund_method": "Adjusted against balance",
            "note": "Wrong specification returned by site engineer",
            "item_id": [str(item_id)],
            "quantity": ["1"],
            "unit_price": ["13000.00"],
            "reason": ["Wrong size / finish"]
        }, follow_redirects=True)
        self.assertEqual(res.status_code, 200)

        db = self.TestingSessionLocal()
        # Item stock should increase back by 1
        item = db.query(Item).filter(Item.id == item_id).first()
        self.assertEqual(item.current_stock, stock_before + 1)

        # Customer receivable balance should decrease by 13,000
        cust = db.query(Customer).filter(Customer.id == cust_id).first()
        self.assertEqual(cust.current_balance, bal_before - Decimal("13000.00"))

        # Verify CustomerReturn record
        ret = db.query(CustomerReturn).filter(CustomerReturn.customer_id == cust_id).first()
        self.assertIsNotNone(ret)
        self.assertEqual(ret.total_amount, Decimal("13000.00"))
        db.close()

    def test_19_supplier_return_deducts_stock_and_adjusts_payable(self):
        db = self.TestingSessionLocal()
        supp = db.query(Supplier).filter(Supplier.name == "Pak Sanitary Industries").first()
        item = db.query(Item).filter(Item.item_code == "ITM-0001").first()
        supp_id = supp.id
        item_id = item.id
        stock_before = item.current_stock
        bal_before = supp.current_balance
        db.close()

        # Return 1 defective item back to supplier @ Rs 9,000
        res = self.client.post("/returns/supplier/new", data={
            "supplier_id": str(supp_id),
            "date": date.today().isoformat(),
            "refund_method": "Adjusted against balance",
            "note": "Glaze defect on ceramic surface",
            "item_id": [str(item_id)],
            "quantity": ["1"],
            "unit_price": ["9000.00"],
            "reason": ["Defective"]
        }, follow_redirects=True)
        self.assertEqual(res.status_code, 200)

        db = self.TestingSessionLocal()
        # Item stock should decrease by 1
        item = db.query(Item).filter(Item.id == item_id).first()
        self.assertEqual(item.current_stock, stock_before - 1)

        # Supplier payable balance should decrease by 9,000
        supp = db.query(Supplier).filter(Supplier.id == supp_id).first()
        self.assertEqual(supp.current_balance, bal_before - Decimal("9000.00"))
        db.close()

    # =========================================================================
    # 7. FINANCIAL LEDGERS & ANALYTICAL REPORTS
    # =========================================================================
    def test_20_general_ledger_overview(self):
        res = self.client.get("/ledger")
        self.assertEqual(res.status_code, 200)
        self.assertIn("General Ledger", res.text)
        self.assertIn("Customer Receivables", res.text)
        self.assertIn("Supplier Payables", res.text)

    def test_21_sales_and_purchases_reports(self):
        res = self.client.get("/reports/sales")
        self.assertEqual(res.status_code, 200)
        self.assertIn("Sales Revenue Report", res.text)

        res = self.client.get("/reports/purchases")
        self.assertEqual(res.status_code, 200)
        self.assertIn("Inbound Purchases Report", res.text)

    def test_22_profit_and_stock_valuation_reports(self):
        res = self.client.get("/reports/profit")
        self.assertEqual(res.status_code, 200)
        self.assertIn("Gross Profitability", res.text)

        res = self.client.get("/reports/stock-valuation")
        self.assertEqual(res.status_code, 200)
        self.assertIn("Asset Valuation", res.text)

    def test_23_outstanding_balances_report(self):
        res = self.client.get("/reports/outstanding")
        self.assertEqual(res.status_code, 200)
        self.assertIn("Al-Rehman Builders", res.text)
        self.assertIn("Pak Sanitary Industries", res.text)

    # =========================================================================
    # 8. PRINT VIEWS & DOCUMENTS
    # =========================================================================
    def test_24_print_invoice_documents(self):
        db = self.TestingSessionLocal()
        sale = db.query(Sale).first()
        sale_id = sale.id
        purchase = db.query(Purchase).first()
        purch_id = purchase.id
        cust = db.query(Customer).filter(Customer.is_walk_in == False).first()
        cust_id = cust.id
        supp = db.query(Supplier).first()
        supp_id = supp.id
        db.close()

        # A4 Sale Invoice
        res = self.client.get(f"/print/sale/{sale_id}")
        self.assertIn(res.status_code, [200, 303])
        if res.status_code == 200:
            self.assertIn("Arshaf Sanitary Store", res.text)

        # 80mm POS Thermal Receipt
        res = self.client.get(f"/print/sale-pos/{sale_id}")
        self.assertEqual(res.status_code, 200)
        self.assertIn("Arshaf Sanitary Store", res.text)

        # Purchase Invoice Print
        res = self.client.get(f"/print/purchase/{purch_id}")
        self.assertIn(res.status_code, [200, 303])

        # Customer Ledger Print
        res = self.client.get(f"/print/customer-ledger/{cust_id}")
        self.assertIn(res.status_code, [200, 303])

        # Supplier Ledger Print
        res = self.client.get(f"/print/supplier-ledger/{supp_id}")
        self.assertIn(res.status_code, [200, 303])

        # Cash Summary Print
        res = self.client.get("/print/cash-summary")
        self.assertIn(res.status_code, [200, 303])


if __name__ == "__main__":
    unittest.main(verbosity=2)
