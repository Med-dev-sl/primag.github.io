"""
Views for PriMag Enterprise sales management.
Includes admin dashboard with analytics charts.
"""
from django.shortcuts import render
from django.contrib.admin.views.decorators import staff_member_required
from django.http import HttpResponse
from django.db.models import Sum, Count
from django.utils.html import format_html
from datetime import datetime, timedelta
from io import BytesIO
import base64

try:
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    MATPLOTLIB_AVAILABLE = True
except ImportError:
    MATPLOTLIB_AVAILABLE = False

from .models import Sale, Customer, Category


@staff_member_required
def sales_dashboard(request):
    """
    Admin dashboard with sales analytics and charts.
    Requires staff authentication.
    """
    if not MATPLOTLIB_AVAILABLE:
        return HttpResponse(
            "Matplotlib is required for the dashboard. "
            "Install it with: pip install matplotlib",
            status=503
        )

    context = {}

    # Sales Summary Statistics - count only confirmed/dispatched/delivered sales
    confirmed_sales = Sale.objects.filter(status__in=['confirmed', 'dispatched', 'delivered'])
    context['total_sales'] = confirmed_sales.count()
    
    # Calculate total revenue from completed sales
    total_revenue_agg = confirmed_sales.aggregate(Sum('total_amount'))['total_amount__sum']
    context['total_revenue'] = float(total_revenue_agg) if total_revenue_agg else 0.0
    
    context['total_customers'] = Customer.objects.count()
    context['avg_order_value'] = (
        context['total_revenue'] / context['total_sales'] 
        if context['total_sales'] > 0 else 0.0
    )

    # Monthly sales trend chart - only confirmed/dispatched/delivered sales
    end_date = datetime.now()
    start_date = end_date - timedelta(days=365)

    monthly_data = (Sale.objects
                    .filter(
                        sale_date__gte=start_date, 
                        sale_date__lte=end_date,
                        status__in=['confirmed', 'dispatched', 'delivered']
                    )
                    .values('sale_date__year', 'sale_date__month')
                    .annotate(total=Sum('total_amount'), count=Count('id'))
                    .order_by('sale_date__year', 'sale_date__month'))

    months = []
    totals = []
    counts = []
    for item in monthly_data:
        year = int(item['sale_date__year'])
        month = int(item['sale_date__month'])
        months.append(f"{year}-{month:02d}")
        totals.append(float(item['total'] or 0))
        counts.append(int(item['count'] or 0))

    # Generate monthly sales chart
    if totals:
        fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(10, 7), dpi=100)

        # Revenue trend
        ax1.plot(months, totals, marker='o', linewidth=2, color='#366092', markersize=6)
        ax1.fill_between(range(len(months)), totals, alpha=0.3, color='#366092')
        ax1.set_title('Monthly Revenue Trend', fontsize=12, fontweight='bold')
        ax1.set_ylabel('Revenue (SLe)', fontsize=10)
        ax1.tick_params(axis='x', rotation=45, labelsize=8)
        ax1.tick_params(axis='y', labelsize=9)
        ax1.grid(True, alpha=0.3)

        # Transaction count
        ax2.bar(months, counts, color='#4CAF50', alpha=0.7, edgecolor='black', linewidth=0.5)
        ax2.set_title('Monthly Transaction Count', fontsize=12, fontweight='bold')
        ax2.set_ylabel('Number of Sales', fontsize=10)
        ax2.set_xlabel('Month', fontsize=10)
        ax2.tick_params(axis='x', rotation=45, labelsize=8)
        ax2.tick_params(axis='y', labelsize=9)
        ax2.grid(True, alpha=0.3, axis='y')

        plt.tight_layout()

        # Convert to base64 for embedding in HTML
        buf = BytesIO()
        fig.savefig(buf, format='png', dpi=100, bbox_inches='tight')
        plt.close(fig)
        buf.seek(0)
        img_base64 = base64.b64encode(buf.getvalue()).decode()
        context['monthly_chart'] = f'data:image/png;base64,{img_base64}'

    # Top customers by sales (only confirmed/dispatched/delivered)
    top_customers = (Customer.objects
                     .filter(sale__status__in=['confirmed', 'dispatched', 'delivered'])
                     .annotate(total_sales=Sum('sale__total_amount'), sale_count=Count('sale', distinct=True))
                     .order_by('-total_sales')[:5])
    context['top_customers'] = [(
        c.name, 
        f"SLe{c.total_sales:.2f}", 
        c.sale_count
    ) for c in top_customers]

    # Sales by category (only from confirmed/dispatched/delivered sales)
    from django.db.models import F, Q
    category_data = (Category.objects
                     .filter(saleitem__sale__status__in=['confirmed', 'dispatched', 'delivered'])
                     .annotate(total_sales=Sum('saleitem__line_total'), count=Count('saleitem', distinct=True))
                     .order_by('-total_sales')
                     .filter(total_sales__isnull=False))

    if category_data.exists():
        cat_names = [c.name for c in category_data]
        cat_amounts = [float(c.total_sales or 0) for c in category_data]

        fig, ax = plt.subplots(figsize=(10, 5), dpi=100)
        bars = ax.barh(cat_names, cat_amounts, color='#FF9800', alpha=0.7, edgecolor='black', linewidth=0.5)
        ax.set_xlabel('Total Sales (SLe)', fontsize=10)
        ax.set_title('Sales by Category', fontsize=12, fontweight='bold')
        ax.tick_params(axis='both', labelsize=9)

        # Add value labels on bars
        for i, (bar, amount) in enumerate(zip(bars, cat_amounts)):
            ax.text(amount, i, f' SLe{amount:.2f}', va='center', fontsize=9)

        plt.tight_layout()

        buf = BytesIO()
        fig.savefig(buf, format='png', dpi=100, bbox_inches='tight')
        plt.close(fig)
        buf.seek(0)
        img_base64 = base64.b64encode(buf.getvalue()).decode()
        context['category_chart'] = f'data:image/png;base64,{img_base64}'

    return render(request, 'admin/sales_dashboard.html', context)
