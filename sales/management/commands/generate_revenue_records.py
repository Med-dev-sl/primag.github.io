"""
Django management command to auto-generate Revenue records for existing Sales.
Usage: py manage.py generate_revenue_records
"""
from django.core.management.base import BaseCommand
from django.db.models import Sum, Count
from sales.models import Sale, Revenue, Customer
from datetime import datetime, timedelta
from dateutil.relativedelta import relativedelta


class Command(BaseCommand):
    help = 'Auto-generate Revenue records for all existing Sales'

    def handle(self, *args, **options):
        self.stdout.write(self.style.SUCCESS('Starting Revenue record generation...'))
        
        # Get all unique customer + month combinations from Sales
        sales = Sale.objects.filter(
            status__in=['confirmed', 'dispatched', 'delivered']
        ).order_by('customer', 'sale_date')
        
        if not sales.exists():
            self.stdout.write(self.style.WARNING('No confirmed sales found.'))
            return
        
        # Group by customer and month
        processed = {}
        created_count = 0
        updated_count = 0
        
        for sale in sales:
            customer = sale.customer
            sale_date = sale.sale_date
            
            # Determine period
            start_date = sale_date.replace(day=1)
            if sale_date.month == 12:
                end_date = sale_date.replace(year=sale_date.year + 1, month=1, day=1) - timedelta(days=1)
            else:
                end_date = sale_date.replace(month=sale_date.month + 1, day=1) - timedelta(days=1)
            
            key = (customer.id, start_date.isoformat())
            
            if key not in processed:
                # Get or create Revenue record
                revenue, created = Revenue.objects.get_or_create(
                    customer=customer,
                    frequency='monthly',
                    start_date=start_date,
                    defaults={
                        'end_date': end_date,
                        'created_by': sale.created_by,
                        'total_revenue': 0,
                        'total_transactions': 0,
                        'total_tax': 0,
                        'total_gst': 0,
                    }
                )
                
                # Recalculate revenue for this period
                period_sales = Sale.objects.filter(
                    customer=customer,
                    sale_date__gte=start_date,
                    sale_date__lte=end_date,
                    status__in=['confirmed', 'dispatched', 'delivered']
                )
                
                revenue.total_revenue = period_sales.aggregate(Sum('total_amount'))['total_amount__sum'] or 0
                revenue.total_transactions = period_sales.count()
                revenue.total_tax = period_sales.aggregate(Sum('total_tax'))['total_tax__sum'] or 0
                revenue.total_gst = period_sales.aggregate(Sum('total_gst'))['total_gst__sum'] or 0
                revenue.save()
                
                if created:
                    created_count += 1
                    self.stdout.write(
                        f'✓ Created: {customer.name} - {start_date.strftime("%B %Y")} - '
                        f'Revenue: ${revenue.total_revenue:.2f}'
                    )
                else:
                    updated_count += 1
                    self.stdout.write(
                        f'⟳ Updated: {customer.name} - {start_date.strftime("%B %Y")} - '
                        f'Revenue: ${revenue.total_revenue:.2f}'
                    )
                
                processed[key] = True
        
        self.stdout.write(
            self.style.SUCCESS(
                f'\n✓ Completed!\n'
                f'  Created: {created_count} new revenue records\n'
                f'  Updated: {updated_count} existing records\n'
                f'  Total: {created_count + updated_count} revenue records processed'
            )
        )
