import os

def update_files():
    base_path = "app/templates/base.html"
    with open(base_path, 'r', encoding='utf-8') as f:
        base_html = f.read()
    
    if "chart.js" not in base_html:
        head_end = base_html.find("</head>")
        if head_end != -1:
            chart_js_script = '    <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>\n'
            base_html = base_html[:head_end] + chart_js_script + base_html[head_end:]
            with open(base_path, 'w', encoding='utf-8') as f:
                f.write(base_html)
            print("Added Chart.js to base.html")

    dashboard_route = """from datetime import date, timedelta
from decimal import Decimal
from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from sqlalchemy import func, extract
import json

from app.database import get_db
from app.models import User, Item, Sale, CustomerReturn, SupplierReturn, Customer, Supplier, Purchase, SaleItem, PurchaseItem
from app.auth import get_current_user
from app.services import money, ensure_walk_in_customer

router = APIRouter()
templates = Jinja2Templates(directory="app/templates")

@router.get("/", response_class=HTMLResponse)
def dashboard_home(request: Request, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    ensure_walk_in_customer(db)
    db.commit()
    today = date.today()
    this_month = today.replace(day=1)

    today_sales = db.query(func.coalesce(func.sum(Sale.total_amount), 0)).filter(Sale.date == today).scalar() or 0
    today_sales_count = db.query(func.count(Sale.id)).filter(Sale.date == today).scalar() or 0

    month_sales = db.query(func.coalesce(func.sum(Sale.total_amount), 0)).filter(Sale.date >= this_month).scalar() or 0
    total_purchases = db.query(func.coalesce(func.sum(Purchase.total_amount), 0)).filter(Purchase.date >= this_month).scalar() or 0
    
    total_products = db.query(func.count(Item.id)).scalar() or 0
    total_customers = db.query(func.count(Customer.id)).scalar() or 0
    total_suppliers = db.query(func.count(Supplier.id)).scalar() or 0
    
    stock_value = db.query(func.coalesce(func.sum(Item.current_stock * Item.purchase_price), 0)).scalar() or 0

    cust_ret_total = db.query(func.coalesce(func.sum(CustomerReturn.total_amount), 0)).filter(CustomerReturn.date == today).scalar() or 0
    supp_ret_total = db.query(func.coalesce(func.sum(SupplierReturn.total_amount), 0)).filter(SupplierReturn.date == today).scalar() or 0
    today_returns = money(cust_ret_total) + money(supp_ret_total)

    low_stock = db.query(Item).filter(Item.status == "Active", Item.current_stock <= Item.reorder_level).order_by(Item.current_stock).limit(8).all()
    low_stock_count = db.query(func.count(Item.id)).filter(Item.status == "Active", Item.current_stock <= Item.reorder_level).scalar() or 0

    receivables = db.query(func.coalesce(func.sum(Customer.current_balance), 0)).filter(Customer.is_walk_in == False).scalar() or 0
    payables = db.query(func.coalesce(func.sum(Supplier.current_balance), 0)).scalar() or 0
    
    # Chart Data Setup
    # 1. Top Selling
    top_selling = db.query(Item.name, func.sum(SaleItem.quantity).label('qty')).join(SaleItem).group_by(Item.id).order_by(func.sum(SaleItem.quantity).desc()).limit(5).all()
    top_selling_labels = [i[0] for i in top_selling] if top_selling else []
    top_selling_data = [i[1] for i in top_selling] if top_selling else []

    # 2. Sales by Category
    cat_sales = db.query(Item.category, func.sum(SaleItem.subtotal).label('tot')).join(SaleItem).group_by(Item.category).all()
    cat_labels = [i[0] for i in cat_sales] if cat_sales else []
    cat_data = [float(i[1]) for i in cat_sales] if cat_sales else []
    
    # Note: For time series, a real app would group by date. We'll pass empty for now if no data.

    return templates.TemplateResponse("home.html", {
        "request": request,
        "current_user": current_user,
        "active_tab": "dashboard",
        "today_sales": today_sales,
        "today_sales_count": today_sales_count,
        "month_sales": month_sales,
        "total_purchases": total_purchases,
        "total_products": total_products,
        "total_customers": total_customers,
        "total_suppliers": total_suppliers,
        "stock_value": stock_value,
        "today_returns": today_returns,
        "low_stock": low_stock,
        "low_stock_count": low_stock_count,
        "receivables": receivables,
        "payables": payables,
        "top_selling_labels": json.dumps(top_selling_labels),
        "top_selling_data": json.dumps(top_selling_data),
        "cat_labels": json.dumps(cat_labels),
        "cat_data": json.dumps(cat_data),
        "error": None,
        "success": None,
    })
"""
    with open("app/routes/dashboard.py", 'w', encoding='utf-8') as f:
        f.write(dashboard_route)
    print("Updated app/routes/dashboard.py")
    
if __name__ == "__main__":
    update_files()
