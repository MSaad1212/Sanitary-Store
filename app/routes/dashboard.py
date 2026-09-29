from datetime import date, timedelta
from decimal import Decimal
from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session, joinedload
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
    yesterday = today - timedelta(days=1)

    # Today's Sales
    today_sales = db.query(func.coalesce(func.sum(Sale.total_amount), 0)).filter(Sale.date == today).scalar() or 0
    today_sales_count = db.query(func.count(Sale.id)).filter(Sale.date == today).scalar() or 0
    yesterday_sales = db.query(func.coalesce(func.sum(Sale.total_amount), 0)).filter(Sale.date == yesterday).scalar() or 0
    
    if yesterday_sales > 0:
        today_vs_yesterday_pct = round(((float(today_sales) - float(yesterday_sales)) / float(yesterday_sales)) * 100, 1)
    elif today_sales > 0:
        today_vs_yesterday_pct = 100.0
    else:
        today_vs_yesterday_pct = 0.0

    # Monthly Sales & Purchases
    month_sales = db.query(func.coalesce(func.sum(Sale.total_amount), 0)).filter(Sale.date >= this_month).scalar() or 0
    total_purchases = db.query(func.coalesce(func.sum(Purchase.total_amount), 0)).filter(Purchase.date >= this_month).scalar() or 0
    
    # Net Profit (Estimate: Monthly Sales - Monthly Purchases / Costs)
    # Also calculate margin %
    net_profit = float(month_sales) - float(total_purchases)
    profit_margin = round((net_profit / float(month_sales) * 100), 1) if month_sales > 0 else 0.0

    total_products = db.query(func.count(Item.id)).scalar() or 0
    total_customers = db.query(func.count(Customer.id)).scalar() or 0
    total_suppliers = db.query(func.count(Supplier.id)).scalar() or 0
    
    stock_value = db.query(func.coalesce(func.sum(Item.current_stock * Item.purchase_price), 0)).scalar() or 0

    cust_ret_total = db.query(func.coalesce(func.sum(CustomerReturn.total_amount), 0)).filter(CustomerReturn.date == today).scalar() or 0
    supp_ret_total = db.query(func.coalesce(func.sum(SupplierReturn.total_amount), 0)).filter(SupplierReturn.date == today).scalar() or 0
    today_returns = money(cust_ret_total) + money(supp_ret_total)

    low_stock = db.query(Item).filter(Item.status == "Active", Item.current_stock <= Item.reorder_level).order_by(Item.current_stock).limit(6).all()
    low_stock_count = db.query(func.count(Item.id)).filter(Item.status == "Active", Item.current_stock <= Item.reorder_level).scalar() or 0

    receivables = db.query(func.coalesce(func.sum(Customer.current_balance), 0)).filter(Customer.is_walk_in == False).scalar() or 0
    payables = db.query(func.coalesce(func.sum(Supplier.current_balance), 0)).scalar() or 0

    # Recent Transactions
    recent_sales = db.query(Sale).options(joinedload(Sale.customer)).order_by(Sale.id.desc()).limit(6).all()
    
    # 7-day Sales Trend
    trend_labels = []
    trend_data = []
    for d in range(6, -1, -1):
        day_date = today - timedelta(days=d)
        trend_labels.append(day_date.strftime("%a (%d %b)"))
        d_sales = db.query(func.coalesce(func.sum(Sale.total_amount), 0)).filter(Sale.date == day_date).scalar() or 0
        trend_data.append(float(d_sales))

    # Chart Data Setup
    # 1. Top Selling
    top_selling = db.query(Item.name, func.sum(SaleItem.quantity).label('qty')).join(SaleItem).group_by(Item.id).order_by(func.sum(SaleItem.quantity).desc()).limit(5).all()
    top_selling_labels = [i[0] for i in top_selling] if top_selling else []
    top_selling_data = [int(i[1]) for i in top_selling] if top_selling else []

    # 2. Sales by Category
    cat_sales = db.query(Item.category, func.sum(SaleItem.subtotal).label('tot')).join(SaleItem).group_by(Item.category).all()
    cat_labels = [i[0] for i in cat_sales] if cat_sales else []
    cat_data = [float(i[1]) for i in cat_sales] if cat_sales else []

    # If cat_data is empty, populate from current stock items distribution for rich initial display
    if not cat_labels:
        stock_cats = db.query(Item.category, func.count(Item.id)).group_by(Item.category).all()
        cat_labels = [c[0] for c in stock_cats]
        cat_data = [int(c[1]) for c in stock_cats]

    return templates.TemplateResponse("home.html", {
        "request": request,
        "current_user": current_user,
        "active_tab": "dashboard",
        "today_sales": today_sales,
        "today_sales_count": today_sales_count,
        "today_vs_yesterday_pct": today_vs_yesterday_pct,
        "month_sales": month_sales,
        "total_purchases": total_purchases,
        "net_profit": net_profit,
        "profit_margin": profit_margin,
        "total_products": total_products,
        "total_customers": total_customers,
        "total_suppliers": total_suppliers,
        "stock_value": stock_value,
        "today_returns": today_returns,
        "low_stock": low_stock,
        "low_stock_count": low_stock_count,
        "receivables": receivables,
        "payables": payables,
        "recent_sales": recent_sales,
        "sales_trend_labels": json.dumps(trend_labels),
        "sales_trend_data": json.dumps(trend_data),
        "top_selling_labels": json.dumps(top_selling_labels),
        "top_selling_data": json.dumps(top_selling_data),
        "cat_labels": json.dumps(cat_labels),
        "cat_data": json.dumps(cat_data),
        "error": None,
        "success": None,
    })
