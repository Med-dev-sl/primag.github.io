"""
PriMag Sales Management Platform Models

Core features:
- Customer Management (daily, weekly, monthly, yearly tracking)
- Income & Expenditure Tracking
- Revenue Management
- Tax & GST Calculation
- Receipt Generation
- Role-Based Access Control (RBAC)
"""

from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone
from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver
from decimal import Decimal
import uuid
import json


class UserProfile(models.Model):
    """Extended User Profile with PriMag features"""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='primag_profile')
    profile_picture = models.ImageField(
        upload_to='profile_pictures/%Y/%m/', 
        blank=True, 
        null=True,
        help_text="User profile picture"
    )
    phone = models.CharField(max_length=20, blank=True)
    department = models.CharField(max_length=100, blank=True)
    bio = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = 'User Profile'
        verbose_name_plural = 'User Profiles'
    
    def __str__(self):
        return f"{self.user.get_full_name() or self.user.username} - PriMag Profile"
    
    def delete_profile_picture(self):
        """Remove profile picture"""
        if self.profile_picture:
            self.profile_picture.delete()
            self.profile_picture = None
            self.save()


class Customer(models.Model):
    """Customer Management Model"""
    FREQUENCY_CHOICES = [
        ('daily', 'Daily'),
        ('weekly', 'Weekly'),
        ('monthly', 'Monthly'),
        ('yearly', 'Yearly'),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=255)
    email = models.EmailField(unique=True)
    phone = models.CharField(max_length=20)
    address = models.TextField()
    city = models.CharField(max_length=100)
    state = models.CharField(max_length=100)
    postal_code = models.CharField(max_length=20)
    country = models.CharField(max_length=100)
    
    # Business Info
    company_name = models.CharField(max_length=255, blank=True)
    gstin = models.CharField(max_length=20, blank=True, help_text="GST Identification Number")
    pan = models.CharField(max_length=20, blank=True, help_text="PAN Number")
    
    # Tracking Frequency
    frequency = models.CharField(max_length=20, choices=FREQUENCY_CHOICES, default='monthly')
    
    # Status
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    created_by = models.ForeignKey(User, on_delete=models.PROTECT, related_name='customers_created')
    
    class Meta:
        ordering = ['-created_at']
        verbose_name = 'Customer'
        verbose_name_plural = 'Customers'
    
    def __str__(self):
        return f"{self.name} ({self.company_name})" if self.company_name else self.name


class Transaction(models.Model):
    """Income & Expenditure Transaction Model"""
    TRANSACTION_TYPE = [
        ('income', 'Income'),
        ('expense', 'Expense'),
    ]
    
    PAYMENT_METHOD = [
        ('cash', 'Cash'),
        ('cheque', 'Cheque'),
        ('bank_transfer', 'Bank Transfer'),
        ('credit_card', 'Credit Card'),
        ('online', 'Online'),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    customer = models.ForeignKey(Customer, on_delete=models.CASCADE, related_name='transactions')
    transaction_type = models.CharField(max_length=20, choices=TRANSACTION_TYPE)
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    description = models.TextField()
    payment_method = models.CharField(max_length=20, choices=PAYMENT_METHOD)
    reference_no = models.CharField(max_length=100, blank=True)
    
    # Tax Information
    is_taxable = models.BooleanField(default=True)
    tax_percentage = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    tax_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    
    # GST Information
    gst_applicable = models.BooleanField(default=False)
    gst_percentage = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    gst_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    
    # Total with taxes
    total_amount = models.DecimalField(max_digits=12, decimal_places=2)
    
    transaction_date = models.DateField()
    created_at = models.DateTimeField(auto_now_add=True)
    created_by = models.ForeignKey(User, on_delete=models.PROTECT, related_name='transactions_created')
    
    class Meta:
        ordering = ['-transaction_date', '-created_at']
        verbose_name = 'Transaction'
        verbose_name_plural = 'Transactions'
    
    def __str__(self):
        return f"{self.get_transaction_type_display()} - {self.customer.name} - ₹{self.amount}"
    
    def save(self, *args, **kwargs):
        """Auto-calculate tax and GST"""
        if self.is_taxable:
            self.tax_amount = (self.amount * self.tax_percentage) / 100
        
        if self.gst_applicable:
            self.gst_amount = (self.amount * self.gst_percentage) / 100
        
        self.total_amount = self.amount + self.tax_amount + self.gst_amount
        super().save(*args, **kwargs)


class Receipt(models.Model):
    """Receipt Generation Model"""
    RECEIPT_STATUS = [
        ('draft', 'Draft'),
        ('issued', 'Issued'),
        ('cancelled', 'Cancelled'),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    receipt_number = models.CharField(max_length=100, unique=True)
    transaction = models.OneToOneField(Transaction, on_delete=models.CASCADE, related_name='receipt')
    
    status = models.CharField(max_length=20, choices=RECEIPT_STATUS, default='draft')
    issued_date = models.DateTimeField(auto_now_add=True)
    issued_by = models.ForeignKey(User, on_delete=models.PROTECT, related_name='receipts_issued')
    
    notes = models.TextField(blank=True)
    is_printed = models.BooleanField(default=False)
    
    class Meta:
        ordering = ['-issued_date']
        verbose_name = 'Receipt'
        verbose_name_plural = 'Receipts'
    
    def __str__(self):
        return f"Receipt {self.receipt_number}"


class Revenue(models.Model):
    """Revenue Tracking Model"""
    FREQUENCY = [
        ('daily', 'Daily'),
        ('weekly', 'Weekly'),
        ('monthly', 'Monthly'),
        ('yearly', 'Yearly'),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    customer = models.ForeignKey(Customer, on_delete=models.CASCADE, related_name='revenues')
    total_revenue = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    frequency = models.CharField(max_length=20, choices=FREQUENCY)
    start_date = models.DateField()
    end_date = models.DateField()
    
    # Summary
    total_transactions = models.IntegerField(default=0)
    total_tax = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    total_gst = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    
    created_at = models.DateTimeField(auto_now_add=True)
    created_by = models.ForeignKey(User, on_delete=models.PROTECT, related_name='revenues_created')
    
    class Meta:
        ordering = ['-start_date']
        verbose_name = 'Revenue'
        verbose_name_plural = 'Revenues'
        unique_together = ('customer', 'frequency', 'start_date')
    
    def __str__(self):
        return f"{self.customer.name} - {self.frequency.title()} Revenue"


class Role(models.Model):
    """Role-Based Access Control"""
    ROLE_TYPES = [
        ('admin', 'Admin'),
        ('super_admin', 'Super Admin'),
        ('salesperson', 'Salesperson'),
        ('delivery_person', 'Delivery Person'),
        ('inventory_manager', 'Inventory Manager'),
        ('accountant', 'Accountant'),
        ('viewer', 'Viewer'),
    ]
    
    PERMISSION_CHOICES = [
        # Customer Permissions
        ('view_customers', 'View Customers'),
        ('add_customers', 'Add Customers'),
        ('edit_customers', 'Edit Customers'),
        ('delete_customers', 'Delete Customers'),
        
        # Transaction Permissions
        ('view_transactions', 'View Transactions'),
        ('add_transactions', 'Add Transactions'),
        ('edit_transactions', 'Edit Transactions'),
        ('delete_transactions', 'Delete Transactions'),
        
        # Receipt Permissions
        ('view_receipts', 'View Receipts'),
        ('generate_receipts', 'Generate Receipts'),
        ('edit_receipts', 'Edit Receipts'),
        ('cancel_receipts', 'Cancel Receipts'),
        
        # Item/Inventory Permissions
        ('view_items', 'View Items'),
        ('add_items', 'Add Items'),
        ('edit_items', 'Edit Items'),
        ('delete_items', 'Delete Items'),
        ('view_inventory', 'View Inventory'),
        ('manage_stock', 'Manage Stock'),
        
        # Sales Permissions
        ('view_sales', 'View Sales'),
        ('create_sales', 'Create Sales'),
        ('edit_sales', 'Edit Sales'),
        ('delete_sales', 'Delete Sales'),
        ('dispatch_sales', 'Dispatch Sales'),
        ('deliver_sales', 'Deliver Sales'),
        
        # Report & Analytics
        ('view_reports', 'View Reports'),
        ('export_data', 'Export Data'),
        ('view_analytics', 'View Analytics'),
        
        # Admin Permissions
        ('manage_users', 'Manage Users'),
        ('manage_roles', 'Manage Roles'),
        ('view_audit_logs', 'View Audit Logs'),
        ('system_settings', 'System Settings'),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=100, unique=True)
    role_type = models.CharField(max_length=50, choices=ROLE_TYPES, unique=True)
    description = models.TextField(blank=True)
    permissions = models.JSONField(default=list, help_text="List of permission codes")
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['name']
        verbose_name = 'Role'
        verbose_name_plural = 'Roles'
    
    def __str__(self):
        return self.name


class UserRole(models.Model):
    """User Role Assignment"""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='role_assignment')
    role = models.ForeignKey(Role, on_delete=models.PROTECT)
    assigned_at = models.DateTimeField(auto_now_add=True)
    assigned_by = models.ForeignKey(User, on_delete=models.PROTECT, related_name='roles_assigned')
    
    class Meta:
        verbose_name = 'User Role'
        verbose_name_plural = 'User Roles'
    
    def __str__(self):
        return f"{self.user.username} - {self.role.name}"


class AuditLog(models.Model):
    """Audit Trail for Compliance"""
    ACTION_CHOICES = [
        ('create', 'Create'),
        ('update', 'Update'),
        ('delete', 'Delete'),
        ('view', 'View'),
        ('export', 'Export'),
        ('login', 'Login'),
        ('logout', 'Logout'),
        ('permission_change', 'Permission Change'),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='audit_logs')
    action = models.CharField(max_length=20, choices=ACTION_CHOICES)
    model_name = models.CharField(max_length=100)
    object_id = models.CharField(max_length=100, blank=True)
    object_str = models.CharField(max_length=500, blank=True)
    old_values = models.JSONField(null=True, blank=True)
    new_values = models.JSONField(null=True, blank=True)
    changes = models.JSONField(null=True, blank=True)
    description = models.TextField(blank=True)
    timestamp = models.DateTimeField(auto_now_add=True, db_index=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.CharField(max_length=500, blank=True)
    
    class Meta:
        ordering = ['-timestamp']
        verbose_name = 'Audit Log'
        verbose_name_plural = 'Audit Logs'
        indexes = [
            models.Index(fields=['user', '-timestamp']),
            models.Index(fields=['model_name', '-timestamp']),
            models.Index(fields=['action', '-timestamp']),
        ]
    
    def __str__(self):
        return f"{self.user} - {self.action} - {self.model_name} - {self.timestamp}"
    
    @staticmethod
    def log_action(user, action, model_name, object_id='', object_str='', old_values=None, 
                   new_values=None, ip_address=None, description=''):
        """Helper method to log actions"""
        try:
            changes = {}
            if old_values and new_values:
                for key in new_values:
                    if key in old_values and old_values[key] != new_values[key]:
                        changes[key] = {
                            'old': str(old_values[key]),
                            'new': str(new_values[key])
                        }
            
            AuditLog.objects.create(
                user=user,
                action=action,
                model_name=model_name,
                object_id=str(object_id),
                object_str=object_str[:500],
                old_values=old_values,
                new_values=new_values,
                changes=changes if changes else None,
                ip_address=ip_address,
                description=description
            )
        except Exception as e:
            # Log error but don't break the main transaction
            print(f"Error logging audit: {str(e)}")


class Category(models.Model):
    """Product Category Model"""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=255, unique=True)
    description = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['name']
        verbose_name = 'Category'
        verbose_name_plural = 'Categories'
    
    def __str__(self):
        return self.name


class Item(models.Model):
    """Item/Product Inventory Model"""
    UNIT_CHOICES = [
        ('piece', 'Piece'),
        ('kg', 'Kilogram'),
        ('liter', 'Liter'),
        ('meter', 'Meter'),
        ('box', 'Box'),
        ('pack', 'Pack'),
        ('dozen', 'Dozen'),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    category = models.ForeignKey(Category, on_delete=models.PROTECT, related_name='items')
    name = models.CharField(max_length=255)
    sku = models.CharField(max_length=100, unique=True, help_text="Stock Keeping Unit")
    description = models.TextField(blank=True)
    
    # Pricing
    cost_price = models.DecimalField(max_digits=10, decimal_places=2, help_text="Purchase cost per unit")
    selling_price = models.DecimalField(max_digits=10, decimal_places=2, help_text="Sale price per unit")
    wholesale_price = models.DecimalField(max_digits=10, decimal_places=2, blank=True, null=True)
    
    # Inventory
    quantity_on_hand = models.IntegerField(default=0)
    minimum_stock_level = models.IntegerField(default=10)
    maximum_stock_level = models.IntegerField(default=100)
    unit_of_measure = models.CharField(max_length=20, choices=UNIT_CHOICES, default='piece')
    
    # Tax
    tax_percentage = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    is_taxable = models.BooleanField(default=True)
    
    # Status
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    created_by = models.ForeignKey(User, on_delete=models.PROTECT, related_name='items_created')
    
    class Meta:
        ordering = ['name']
        verbose_name = 'Item'
        verbose_name_plural = 'Items'
        indexes = [
            models.Index(fields=['sku']),
            models.Index(fields=['category']),
        ]
    
    def __str__(self):
        return f"{self.name} ({self.sku})"
    
    @property
    def profit_per_unit(self):
        """Calculate profit per unit"""
        if self.selling_price is None or self.cost_price is None:
            return 0
        return self.selling_price - self.cost_price
    
    @property
    def margin_percentage(self):
        """Calculate profit margin percentage"""
        if self.selling_price is None or self.cost_price is None or self.selling_price == 0:
            return 0
        return ((self.selling_price - self.cost_price) / self.selling_price) * 100
    
    @property
    def is_low_stock(self):
        """Check if item is below minimum stock level"""
        return self.quantity_on_hand <= self.minimum_stock_level


class Sale(models.Model):
    """Sales Order Model"""
    SALE_STATUS = [
        ('draft', 'Draft'),
        ('confirmed', 'Confirmed'),
        ('dispatched', 'Dispatched'),
        ('delivered', 'Delivered'),
        ('cancelled', 'Cancelled'),
        ('returned', 'Returned'),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    sale_number = models.CharField(max_length=100, unique=True, blank=True)
    customer = models.ForeignKey(Customer, on_delete=models.CASCADE, related_name='sales', null=True, blank=True)
    
    # Sale details
    sale_date = models.DateField()
    delivery_date = models.DateField(blank=True, null=True)
    status = models.CharField(max_length=20, choices=SALE_STATUS, default='draft')
    
    # Amounts
    subtotal = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    total_tax = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    total_gst = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    total_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    
    # Notes
    notes = models.TextField(blank=True)
    
    # User tracking
    created_by = models.ForeignKey(User, on_delete=models.PROTECT, related_name='sales_created')
    delivered_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='sales_delivered')
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['-sale_date', '-created_at']
        verbose_name = 'Sale'
        verbose_name_plural = 'Sales'
        indexes = [
            models.Index(fields=['-sale_date']),
            models.Index(fields=['customer']),
        ]
    
    def __str__(self):
        return f"Sale {self.sale_number}"

    def save(self, *args, **kwargs):
        """Auto-generate sale_number if not provided"""
        if not self.sale_number:
            import datetime
            # Generate sale number: SAL-YYYYMMDD-XXXXX
            date_str = datetime.datetime.now().strftime('%Y%m%d')
            # Get count of sales today
            today_count = Sale.objects.filter(
                created_at__date=datetime.date.today()
            ).count() + 1
            self.sale_number = f"SAL-{date_str}-{today_count:05d}"
        super().save(*args, **kwargs)


class SaleItem(models.Model):
    """Individual items in a sale"""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    sale = models.ForeignKey(Sale, on_delete=models.CASCADE, related_name='items')
    item = models.ForeignKey(Item, on_delete=models.PROTECT)
    
    quantity = models.IntegerField(default=1)
    unit_price = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    tax_percentage = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    tax_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    gst_percentage = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    gst_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    line_total = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['created_at']
        verbose_name = 'Sale Item'
        verbose_name_plural = 'Sale Items'
    
    def __str__(self):
        return f"{self.item.name} x {self.quantity}"
    
    def save(self, *args, **kwargs):
        """Auto-calculate tax, GST and line total"""
        # Calculate tax amount
        self.tax_amount = (self.unit_price * self.quantity * self.tax_percentage) / 100
        
        # Calculate GST amount
        self.gst_amount = (self.unit_price * self.quantity * self.gst_percentage) / 100
        
        # Calculate line total
        self.line_total = (self.unit_price * self.quantity) + self.tax_amount + self.gst_amount
        
        super().save(*args, **kwargs)


class StockMovement(models.Model):
    """Track all inventory movements"""
    MOVEMENT_TYPE = [
        ('purchase', 'Purchase'),
        ('sale', 'Sale'),
        ('return', 'Return'),
        ('adjustment', 'Adjustment'),
        ('damage', 'Damage'),
        ('transfer', 'Transfer'),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    item = models.ForeignKey(Item, on_delete=models.CASCADE, related_name='stock_movements')
    movement_type = models.CharField(max_length=20, choices=MOVEMENT_TYPE)
    quantity = models.IntegerField()
    reference_number = models.CharField(max_length=100, blank=True)
    notes = models.TextField(blank=True)
    
    created_by = models.ForeignKey(User, on_delete=models.PROTECT)
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['-created_at']
        verbose_name = 'Stock Movement'
        verbose_name_plural = 'Stock Movements'
        indexes = [
            models.Index(fields=['item', '-created_at']),
            models.Index(fields=['movement_type', '-created_at']),
        ]
    
    def __str__(self):
        return f"{self.item.name} - {self.movement_type.title()}: {self.quantity}"


# ============ SIGNALS FOR AUDIT LOGGING ============

@receiver(post_save, sender=UserProfile)
def create_user_profile(sender, instance, created, **kwargs):
    """Automatically create user profile when user is created"""
    if created:
        AuditLog.log_action(
            user=instance.user,
            action='create',
            model_name='UserProfile',
            object_id=str(instance.id),
            object_str=str(instance),
            description=f'User profile created for {instance.user.username}'
        )


@receiver(post_save, sender=Customer)
def log_customer_changes(sender, instance, created, **kwargs):
    """Log customer creation and updates"""
    if created:
        AuditLog.log_action(
            user=instance.created_by,
            action='create',
            model_name='Customer',
            object_id=str(instance.id),
            object_str=str(instance),
            description=f'Customer created: {instance.name}'
        )


@receiver(post_save, sender=Sale)
def log_sale_changes(sender, instance, created, **kwargs):
    """Log sale creation and updates and auto-generate Revenue records"""
    if created:
        customer_info = instance.customer.name if instance.customer else 'No Customer'
        AuditLog.log_action(
            user=instance.created_by,
            action='create',
            model_name='Sale',
            object_id=str(instance.id),
            object_str=str(instance),
            description=f'Sale created: {instance.sale_number} for {customer_info}'
        )
    
    # Auto-generate or update Revenue record for this sale (only if customer exists)
    if instance.customer:
        try:
            from datetime import datetime as dt, timedelta
            
            # Determine the period (monthly by default)
            sale_date = instance.sale_date
            start_date = sale_date.replace(day=1)  # First day of month
            
            # Last day of month
            if sale_date.month == 12:
                end_date = sale_date.replace(year=sale_date.year + 1, month=1, day=1) - timedelta(days=1)
            else:
                end_date = sale_date.replace(month=sale_date.month + 1, day=1) - timedelta(days=1)
            
            # Get or create Revenue record
            revenue, _ = Revenue.objects.get_or_create(
                customer=instance.customer,
                frequency='monthly',
                start_date=start_date,
                defaults={
                    'end_date': end_date,
                    'created_by': instance.created_by,
                    'total_revenue': 0,
                    'total_transactions': 0,
                    'total_tax': 0,
                    'total_gst': 0,
                }
            )
            
            # Recalculate revenue for this period (only confirmed/dispatched/delivered)
            from django.db.models import Sum
            period_sales = Sale.objects.filter(
                customer=instance.customer,
                sale_date__gte=start_date,
                sale_date__lte=end_date,
                status__in=['confirmed', 'dispatched', 'delivered']
            )
            
            revenue.total_revenue = period_sales.aggregate(Sum('total_amount'))['total_amount__sum'] or 0
            revenue.total_transactions = period_sales.count()
            revenue.total_tax = period_sales.aggregate(Sum('total_tax'))['total_tax__sum'] or 0
            revenue.total_gst = period_sales.aggregate(Sum('total_gst'))['total_gst__sum'] or 0
            revenue.save()
        except Exception as e:
            # Silently fail to not break the sale save
            pass


@receiver(post_save, sender=Transaction)
def log_transaction_changes(sender, instance, created, **kwargs):
    """Log transaction creation"""
    if created:
        AuditLog.log_action(
            user=instance.created_by,
            action='create',
            model_name='Transaction',
            object_id=str(instance.id),
            object_str=str(instance),
            description=f'{instance.transaction_type.title()} transaction created: {instance.amount}'
        )


@receiver(post_save, sender=Receipt)
def log_receipt_changes(sender, instance, created, **kwargs):
    """Log receipt creation"""
    if created:
        AuditLog.log_action(
            user=instance.issued_by,
            action='create',
            model_name='Receipt',
            object_id=str(instance.id),
            object_str=str(instance),
            description=f'Receipt issued: {instance.receipt_number}'
        )


@receiver(post_delete, sender=Sale)
def log_sale_deletion(sender, instance, **kwargs):
    """Log sale deletion"""
    AuditLog.log_action(
        user=None,
        action='delete',
        model_name='Sale',
        object_id=str(instance.id),
        object_str=str(instance),
        description=f'Sale deleted: {instance.sale_number}'
    )


@receiver(post_delete, sender=Customer)
def log_customer_deletion(sender, instance, **kwargs):
    """Log customer deletion"""
    AuditLog.log_action(
        user=None,
        action='delete',
        model_name='Customer',
        object_id=str(instance.id),
        object_str=str(instance),
        description=f'Customer deleted: {instance.name}'
    )


@receiver(post_save, sender=SaleItem)
def log_saleitem_changes(sender, instance, created, **kwargs):
    """Log sale item creation"""
    if created:
        AuditLog.log_action(
            user=None,  # SaleItem doesn't have a created_by field
            action='create',
            model_name='SaleItem',
            object_id=str(instance.id),
            object_str=str(instance),
            description=f'Sale item created: {instance.item.name} x {instance.quantity}'
        )


@receiver(post_delete, sender=SaleItem)
def log_saleitem_deletion(sender, instance, **kwargs):
    """Log sale item deletion"""
    AuditLog.log_action(
        user=None,
        action='delete',
        model_name='SaleItem',
        object_id=str(instance.id),
        object_str=str(instance),
        description=f'Sale item deleted: {instance.item.name} x {instance.quantity}'
    )
