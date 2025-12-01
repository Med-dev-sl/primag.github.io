from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as DjangoUserAdmin
from django.contrib.auth.models import User
from django.utils.html import format_html
from .models import (
    UserProfile, Customer, Transaction, Receipt, Revenue, Role, UserRole, AuditLog,
    Category, Item, Sale, SaleItem, StockMovement
)
from .utils import CSVReporter, ExcelReporter, PDFReporter, ReceiptPDFGenerator, InvoicePDFGenerator
from django.db.models import Sum
from django.http import HttpResponse
from io import BytesIO
from reportlab.platypus import Image as RLImage
from reportlab.lib.utils import ImageReader


# ============ EXPORT ACTIONS ============

def export_to_csv(modeladmin, request, queryset):
    """Export selected items to CSV"""
    fields = [field.name for field in queryset.model._meta.get_fields() if not field.many_to_one and not field.one_to_many and not field.many_to_many]
    return CSVReporter.export_to_csv(queryset, fields, queryset.model.__name__)

export_to_csv.short_description = "📊 Export selected to CSV"


def export_to_excel(modeladmin, request, queryset):
    """Export selected items to Excel"""
    fields = [field.name for field in queryset.model._meta.get_fields() if not field.many_to_one and not field.one_to_many and not field.many_to_many]
    return ExcelReporter.export_to_excel(queryset, fields, queryset.model.__name__, title=f"{queryset.model.__name__} Report")

export_to_excel.short_description = "📈 Export selected to Excel"


def export_to_pdf(modeladmin, request, queryset):
    """Export selected items to PDF"""
    fields = [field.name for field in queryset.model._meta.get_fields() if not field.many_to_one and not field.one_to_many and not field.many_to_many]
    return PDFReporter.export_to_pdf(queryset, fields, queryset.model.__name__, title=f"{queryset.model.__name__} Report")

export_to_pdf.short_description = "📄 Export selected to PDF"


def generate_invoice_pdf(modeladmin, request, queryset):
    """Generate PDF invoice for a selected Sale (single selection required)"""
    if queryset.count() != 1:
        modeladmin.message_user(request, f"Please select exactly one sale to generate an invoice. You selected {queryset.count()}.")
        return
    sale = queryset.first()
    return InvoicePDFGenerator.generate_invoice(sale)

generate_invoice_pdf.short_description = "🧾 Generate Invoice PDF"


def view_sales_chart(modeladmin, request, queryset):
    """Generate a PNG sales chart (monthly totals) for selected sales or all sales if none selected."""
    # Import matplotlib only when needed
    try:
        import matplotlib
        matplotlib.use('Agg')
        import matplotlib.pyplot as plt
    except Exception:
        modeladmin.message_user(request, "Matplotlib is required to generate charts. Install it with `pip install matplotlib`.")
        return

    # Aggregate sales by month
    if queryset.count() > 0:
        sales_qs = queryset
    else:
        from .models import Sale
        sales_qs = Sale.objects.all()

    data = sales_qs.values('sale_date__year', 'sale_date__month').annotate(total=Sum('total_amount')).order_by('sale_date__year', 'sale_date__month')
    if not data:
        modeladmin.message_user(request, "No sales data available for charting.")
        return

    labels = []
    totals = []
    for row in data:
        year = row.get('sale_date__year')
        month = row.get('sale_date__month')
        labels.append(f"{year}-{month:02d}")
        totals.append(float(row.get('total') or 0))

    fig, ax = plt.subplots(figsize=(8, 4))
    ax.plot(labels, totals, marker='o', linestyle='-')
    ax.set_title('Sales Totals by Month')
    ax.set_xlabel('Month')
    ax.set_ylabel('Total Sales')
    plt.xticks(rotation=45)
    plt.tight_layout()

    buf = BytesIO()
    fig.savefig(buf, format='png')
    plt.close(fig)
    buf.seek(0)

    return HttpResponse(buf.getvalue(), content_type='image/png')

view_sales_chart.short_description = "📊 View Sales Chart"


def generate_sales_report_pdf_with_chart(modeladmin, request, queryset):
    """Generate a PDF report with an embedded sales chart (monthly totals)."""
    try:
        import matplotlib
        matplotlib.use('Agg')
        import matplotlib.pyplot as plt
    except Exception:
        modeladmin.message_user(request, "Matplotlib is required to generate charts. Install it with `pip install matplotlib`.")
        return

    # If no selection, include all sales
    if queryset.count() > 0:
        sales_qs = queryset
    else:
        from .models import Sale
        sales_qs = Sale.objects.all()

    data = sales_qs.values('sale_date__year', 'sale_date__month').annotate(total=Sum('total_amount')).order_by('sale_date__year', 'sale_date__month')
    if not data:
        modeladmin.message_user(request, "No sales data available for charting.")
        return

    labels = []
    totals = []
    for row in data:
        year = row.get('sale_date__year')
        month = row.get('sale_date__month')
        labels.append(f"{year}-{month:02d}")
        totals.append(float(row.get('total') or 0))

    fig, ax = plt.subplots(figsize=(8, 4))
    ax.plot(labels, totals, marker='o', linestyle='-')
    ax.set_title('Sales Totals by Month')
    ax.set_xlabel('Month')
    ax.set_ylabel('Total Sales')
    plt.xticks(rotation=45)
    plt.tight_layout()

    img_buf = BytesIO()
    fig.savefig(img_buf, format='png')
    plt.close(fig)
    img_buf.seek(0)

    # Build PDF with embedded image
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer
    from reportlab.lib.styles import getSampleStyleSheet
    from reportlab.lib.units import inch

    out_buf = BytesIO()
    doc = SimpleDocTemplate(out_buf, pagesize=letter)
    elements = []
    styles = getSampleStyleSheet()
    title = Paragraph('Sales Report with Chart', styles['Heading1'])
    elements.append(title)
    elements.append(Spacer(1, 0.2 * inch))

    # Add metadata
    meta = Paragraph(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} | Records: {len(labels)}", styles['Normal'])
    elements.append(meta)
    elements.append(Spacer(1, 0.2 * inch))

    # Embed image
    img = ImageReader(img_buf)
    elements.append(RLImage(img, width=6 * inch, height=3 * inch))
    elements.append(Spacer(1, 0.2 * inch))

    # Summary
    total_all = sum(totals)
    summary = Paragraph(f"<b>Total Sales (selected):</b> ${total_all:,.2f}", styles['Normal'])
    elements.append(summary)

    doc.build(elements)
    out_buf.seek(0)

    response = HttpResponse(out_buf.getvalue(), content_type='application/pdf')
    response['Content-Disposition'] = 'attachment; filename="sales_report_chart.pdf"'
    return response

generate_sales_report_pdf_with_chart.short_description = "📈 Sales Report PDF (with chart)"


# ============ CUSTOM USER ADMIN ============

class UserProfileInline(admin.StackedInline):
    """Inline admin for UserProfile"""
    model = UserProfile
    fields = ('profile_picture', 'phone', 'department', 'bio', 'is_active')
    extra = 0


@admin.register(UserProfile)
class UserProfileAdmin(admin.ModelAdmin):
    """User Profile Management Admin"""
    list_display = ('get_user', 'get_profile_picture', 'phone', 'department', 'is_active', 'created_at')
    list_filter = ('is_active', 'department', 'created_at')
    search_fields = ('user__username', 'user__first_name', 'user__last_name', 'phone')
    readonly_fields = ('id', 'created_at', 'updated_at', 'get_profile_picture_preview')
    
    fieldsets = (
        ('User Information', {
            'fields': ('user', 'id')
        }),
        ('Profile Picture', {
            'fields': ('profile_picture', 'get_profile_picture_preview')
        }),
        ('Contact Information', {
            'fields': ('phone',)
        }),
        ('Additional Information', {
            'fields': ('department', 'bio', 'is_active')
        }),
        ('Metadata', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    def get_user(self, obj):
        return f"{obj.user.get_full_name() or obj.user.username}"
    get_user.short_description = 'User'
    
    def get_profile_picture(self, obj):
        if obj.profile_picture:
            return format_html(
                '<img src="{}" width="30" height="30" style="border-radius: 50%;" />',
                obj.profile_picture.url
            )
        return '—'
    get_profile_picture.short_description = 'Picture'
    
    def get_profile_picture_preview(self, obj):
        if obj.profile_picture:
            return format_html(
                '<img src="{}" width="150" height="150" style="border-radius: 10px;" />',
                obj.profile_picture.url
            )
        return 'No profile picture uploaded'
    get_profile_picture_preview.short_description = 'Profile Picture Preview'
    
    actions = ['delete_profile_picture']
    
    def delete_profile_picture(self, request, queryset):
        for profile in queryset:
            profile.delete_profile_picture()
        self.message_user(request, f"Profile pictures deleted for {queryset.count()} user(s)")
    delete_profile_picture.short_description = "Delete selected profile pictures"


@admin.register(Customer)
class CustomerAdmin(admin.ModelAdmin):
    """Customer Management Admin"""
    list_display = ('name', 'email', 'phone', 'company_name', 'frequency', 'is_active', 'created_at')
    list_filter = ('is_active', 'frequency', 'created_at')
    search_fields = ('name', 'email', 'company_name', 'gstin')
    readonly_fields = ('id', 'created_at', 'updated_at')
    actions = [export_to_csv, export_to_excel, export_to_pdf, generate_invoice_pdf, view_sales_chart, generate_sales_report_pdf_with_chart]
    
    fieldsets = (
        ('Personal Information', {
            'fields': ('id', 'name', 'email', 'phone')
        }),
        ('Address', {
            'fields': ('address', 'city', 'state', 'postal_code', 'country')
        }),
        ('Business Information', {
            'fields': ('company_name', 'gstin', 'pan')
        }),
        ('Tracking', {
            'fields': ('frequency', 'is_active')
        }),
        ('Metadata', {
            'fields': ('created_at', 'updated_at', 'created_by'),
            'classes': ('collapse',)
        }),
    )
    
    def save_model(self, request, obj, form, change):
        if not change:
            obj.created_by = request.user
        super().save_model(request, obj, form, change)


@admin.register(Transaction)
class TransactionAdmin(admin.ModelAdmin):
    """Transaction Management Admin"""
    list_display = ('get_customer', 'transaction_type_badge', 'amount', 'tax_amount', 'gst_amount', 'total_amount', 'transaction_date')
    list_filter = ('transaction_type', 'transaction_date', 'is_taxable', 'gst_applicable')
    search_fields = ('customer__name', 'reference_no', 'description')
    readonly_fields = ('id', 'tax_amount', 'gst_amount', 'total_amount', 'created_at')
    date_hierarchy = 'transaction_date'
    actions = [export_to_csv, export_to_excel, export_to_pdf]
    
    fieldsets = (
        ('Transaction Details', {
            'fields': ('id', 'customer', 'transaction_type', 'reference_no')
        }),
        ('Amount', {
            'fields': ('amount', 'description', 'payment_method')
        }),
        ('Tax Information', {
            'fields': ('is_taxable', 'tax_percentage', 'tax_amount')
        }),
        ('GST Information', {
            'fields': ('gst_applicable', 'gst_percentage', 'gst_amount')
        }),
        ('Total', {
            'fields': ('total_amount',)
        }),
        ('Metadata', {
            'fields': ('transaction_date', 'created_at', 'created_by'),
            'classes': ('collapse',)
        }),
    )
    
    def get_customer(self, obj):
        return obj.customer.name
    get_customer.short_description = 'Customer'
    
    def transaction_type_badge(self, obj):
        if obj.transaction_type == 'income':
            color = 'green'
            label = '💰 Income'
        else:
            color = 'red'
            label = '💸 Expense'
        return format_html(f'<span style="color: {color}; font-weight: bold;">{label}</span>')
    transaction_type_badge.short_description = 'Type'
    
    def save_model(self, request, obj, form, change):
        if not change:
            obj.created_by = request.user
        super().save_model(request, obj, form, change)


@admin.register(Receipt)
class ReceiptAdmin(admin.ModelAdmin):
    """Receipt Generation Admin"""
    list_display = ('receipt_number', 'get_customer', 'status_badge', 'issued_date', 'is_printed')
    list_filter = ('status', 'issued_date', 'is_printed')
    search_fields = ('receipt_number', 'transaction__customer__name')
    readonly_fields = ('id', 'issued_date', 'receipt_number')
    actions = [export_to_csv, export_to_excel, export_to_pdf, 'generate_pdf_receipt']
    
    fieldsets = (
        ('Receipt Details', {
            'fields': ('id', 'receipt_number', 'transaction')
        }),
        ('Status', {
            'fields': ('status', 'is_printed')
        }),
        ('Notes', {
            'fields': ('notes',)
        }),
        ('Metadata', {
            'fields': ('issued_date', 'issued_by'),
            'classes': ('collapse',)
        }),
    )
    
    def get_customer(self, obj):
        return obj.transaction.customer.name
    get_customer.short_description = 'Customer'
    
    def status_badge(self, obj):
        colors = {'draft': 'blue', 'issued': 'green', 'cancelled': 'red'}
        return format_html(f'<span style="color: {colors.get(obj.status)}; font-weight: bold;">{obj.get_status_display()}</span>')
    status_badge.short_description = 'Status'
    
    def generate_pdf_receipt(self, request, queryset):
        """Generate PDF receipt for selected items"""
        if queryset.count() == 1:
            return ReceiptPDFGenerator.generate_receipt(queryset.first())
        else:
            self.message_user(request, f"Please select exactly one receipt. You selected {queryset.count()}.")
    
    generate_pdf_receipt.short_description = "📋 Generate PDF Receipt"
    
    def save_model(self, request, obj, form, change):
        if not change:
            obj.issued_by = request.user
        super().save_model(request, obj, form, change)


@admin.register(Revenue)
class RevenueAdmin(admin.ModelAdmin):
    """Revenue Tracking Admin"""
    list_display = ('get_customer', 'frequency', 'total_revenue', 'start_date', 'end_date', 'total_transactions')
    list_filter = ('frequency', 'start_date')
    search_fields = ('customer__name',)
    readonly_fields = ('id', 'created_at', 'total_revenue')
    date_hierarchy = 'start_date'
    
    fieldsets = (
        ('Customer & Frequency', {
            'fields': ('customer', 'frequency')
        }),
        ('Period', {
            'fields': ('start_date', 'end_date')
        }),
        ('Revenue Summary', {
            'fields': ('total_revenue', 'total_transactions', 'total_tax', 'total_gst')
        }),
        ('Metadata', {
            'fields': ('created_at', 'created_by'),
            'classes': ('collapse',)
        }),
    )
    
    def get_customer(self, obj):
        return obj.customer.name
    get_customer.short_description = 'Customer'
    
    def save_model(self, request, obj, form, change):
        if not change:
            obj.created_by = request.user
        super().save_model(request, obj, form, change)


@admin.register(Role)
class RoleAdmin(admin.ModelAdmin):
    """Role Management Admin"""
    list_display = ('name', 'is_active', 'permission_count', 'created_at')
    list_filter = ('is_active', 'created_at')
    search_fields = ('name', 'description')
    readonly_fields = ('id', 'created_at', 'updated_at')
    
    fieldsets = (
        ('Role Information', {
            'fields': ('id', 'name', 'description')
        }),
        ('Permissions', {
            'fields': ('permissions',),
            'description': 'Select permissions for this role'
        }),
        ('Status', {
            'fields': ('is_active',)
        }),
        ('Metadata', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    def permission_count(self, obj):
        return len(obj.permissions)
    permission_count.short_description = 'Permissions'


@admin.register(UserRole)
class UserRoleAdmin(admin.ModelAdmin):
    """User Role Assignment Admin"""
    list_display = ('get_username', 'get_role', 'assigned_at')
    list_filter = ('assigned_at', 'role')
    search_fields = ('user__username', 'role__name')
    readonly_fields = ('id', 'assigned_at')
    
    fieldsets = (
        ('Assignment', {
            'fields': ('user', 'role')
        }),
        ('Metadata', {
            'fields': ('assigned_at', 'assigned_by'),
            'classes': ('collapse',)
        }),
    )
    
    def get_username(self, obj):
        return obj.user.username
    get_username.short_description = 'User'
    
    def get_role(self, obj):
        return obj.role.name
    get_role.short_description = 'Role'
    
    def save_model(self, request, obj, form, change):
        if not change:
            obj.assigned_by = request.user
        super().save_model(request, obj, form, change)


@admin.register(AuditLog)
class AuditLogAdmin(admin.ModelAdmin):
    """Audit Trail Admin - Comprehensive Logging"""
    list_display = ('get_user', 'action_badge', 'model_name', 'object_str_short', 'timestamp_display')
    list_filter = ('action', 'model_name', 'timestamp')
    search_fields = ('user__username', 'model_name', 'object_id', 'object_str', 'description')
    readonly_fields = ('id', 'timestamp', 'user', 'action', 'model_name', 'object_id', 'object_str',
                      'old_values_pretty', 'new_values_pretty', 'changes_pretty', 'ip_address', 'user_agent')
    date_hierarchy = 'timestamp'
    
    fieldsets = (
        ('Action Details', {
            'fields': ('user', 'action_badge', 'model_name', 'object_id', 'object_str', 'description')
        }),
        ('Changes Tracking', {
            'fields': ('old_values_pretty', 'new_values_pretty', 'changes_pretty')
        }),
        ('System Information', {
            'fields': ('timestamp', 'ip_address', 'user_agent'),
            'classes': ('collapse',)
        }),
    )
    
    def action_badge(self, obj):
        """Color-coded action badge"""
        colors = {
            'create': '#28a745',
            'update': '#ffc107',
            'delete': '#dc3545',
            'view': '#17a2b8',
            'export': '#6f42c1',
            'login': '#20c997',
            'logout': '#fd7e14',
            'permission_change': '#e83e8c'
        }
        color = colors.get(obj.action, '#6c757d')
        return format_html(
            '<span style="background-color: {}; color: white; padding: 3px 8px; border-radius: 3px;">{}</span>',
            color,
            obj.get_action_display()
        )
    action_badge.short_description = 'Action'
    
    def object_str_short(self, obj):
        """Truncated object string"""
        text = obj.object_str or obj.object_id
        if len(text) > 50:
            return f"{text[:47]}..."
        return text
    object_str_short.short_description = 'Object'
    
    def timestamp_display(self, obj):
        """Formatted timestamp"""
        return obj.timestamp.strftime('%Y-%m-%d %H:%M:%S')
    timestamp_display.short_description = 'Timestamp'
    
    def old_values_pretty(self, obj):
        """Pretty print old values"""
        if obj.old_values:
            import json
            return format_html('<pre><code>{}</code></pre>', 
                             json.dumps(obj.old_values, indent=2, ensure_ascii=False))
        return '—'
    old_values_pretty.short_description = 'Old Values'
    
    def new_values_pretty(self, obj):
        """Pretty print new values"""
        if obj.new_values:
            import json
            return format_html('<pre><code>{}</code></pre>', 
                             json.dumps(obj.new_values, indent=2, ensure_ascii=False))
        return '—'
    new_values_pretty.short_description = 'New Values'
    
    def changes_pretty(self, obj):
        """Pretty print changes"""
        if obj.changes:
            import json
            return format_html('<pre><code>{}</code></pre>', 
                             json.dumps(obj.changes, indent=2, ensure_ascii=False))
        return '—'
    changes_pretty.short_description = 'Changes Summary'
    
    def get_user(self, obj):
        if obj.user:
            return format_html(
                '<strong>{}</strong>',
                obj.user.get_full_name() or obj.user.username
            )
        return 'System'
    get_user.short_description = 'User'
    
    def has_add_permission(self, request):
        return False
    
    def has_delete_permission(self, request, obj=None):
        return False
    
    def has_change_permission(self, request, obj=None):
        return False
    get_user.short_description = 'User'


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    """Category Management Admin"""
    list_display = ('name', 'is_active', 'item_count', 'created_at')
    list_filter = ('is_active', 'created_at')
    search_fields = ('name', 'description')
    readonly_fields = ('id', 'created_at', 'updated_at')
    
    fieldsets = (
        ('Category Information', {
            'fields': ('id', 'name', 'description')
        }),
        ('Status', {
            'fields': ('is_active',)
        }),
        ('Metadata', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    def item_count(self, obj):
        return obj.items.count()
    item_count.short_description = 'Items'


@admin.register(Item)
class ItemAdmin(admin.ModelAdmin):
    """Item/Inventory Management Admin"""
    list_display = ('sku', 'name', 'category', 'quantity_status', 'cost_price', 'selling_price', 'profit_margin', 'is_active')
    list_filter = ('category', 'is_active', 'is_taxable', 'created_at')
    search_fields = ('name', 'sku', 'description')
    readonly_fields = ('id', 'created_at', 'updated_at', 'profit_per_unit', 'margin_percentage')
    actions = [export_to_csv, export_to_excel, export_to_pdf]
    
    fieldsets = (
        ('Product Information', {
            'fields': ('id', 'category', 'name', 'sku', 'description')
        }),
        ('Pricing', {
            'fields': ('cost_price', 'selling_price', 'wholesale_price', 'profit_per_unit', 'margin_percentage')
        }),
        ('Inventory', {
            'fields': ('quantity_on_hand', 'minimum_stock_level', 'maximum_stock_level', 'unit_of_measure')
        }),
        ('Tax', {
            'fields': ('is_taxable', 'tax_percentage')
        }),
        ('Status', {
            'fields': ('is_active',)
        }),
        ('Metadata', {
            'fields': ('created_at', 'updated_at', 'created_by'),
            'classes': ('collapse',)
        }),
    )
    
    def quantity_status(self, obj):
        if obj.is_low_stock:
            return format_html('<span style="color: red; font-weight: bold;">⚠️ Low ({}/{})</span>', 
                             obj.quantity_on_hand, obj.minimum_stock_level)
        else:
            return format_html('<span style="color: green;">✓ {} units</span>', obj.quantity_on_hand)
    quantity_status.short_description = 'Stock Status'
    
    def profit_margin(self, obj):
        margin = obj.margin_percentage
        color = 'green' if margin > 0 else 'red'
        return format_html(f'<span style="color: {color}; font-weight: bold;">{margin:.1f}%</span>')
    profit_margin.short_description = 'Margin %'
    
    def save_model(self, request, obj, form, change):
        if not change:
            obj.created_by = request.user
        super().save_model(request, obj, form, change)


class SaleItemInline(admin.TabularInline):
    """Inline admin for Sale Items"""
    model = SaleItem
    extra = 1
    readonly_fields = ('tax_amount', 'gst_amount', 'line_total')
    fields = ('item', 'quantity', 'unit_price', 'tax_percentage', 'tax_amount', 'gst_percentage', 'gst_amount', 'line_total')


@admin.register(Sale)
class SaleAdmin(admin.ModelAdmin):
    """Sales Management Admin"""
    list_display = ('sale_number', 'get_customer', 'sale_date', 'status_badge', 'total_amount', 'get_created_by')
    list_filter = ('status', 'sale_date', 'created_at')
    search_fields = ('sale_number', 'customer__name')
    readonly_fields = ('id', 'sale_number', 'subtotal', 'total_tax', 'total_gst', 'total_amount', 'created_at', 'updated_at')
    inlines = [SaleItemInline]
    date_hierarchy = 'sale_date'
    actions = [export_to_csv, export_to_excel, export_to_pdf]
    
    fieldsets = (
        ('Sale Information', {
            'fields': ('id', 'sale_number', 'customer', 'sale_date', 'delivery_date', 'status')
        }),
        ('Items', {
            'fields': ()  # Items are shown via inline
        }),
        ('Amounts', {
            'fields': ('subtotal', 'total_tax', 'total_gst', 'total_amount')
        }),
        ('Additional Information', {
            'fields': ('notes',)
        }),
        ('Tracking', {
            'fields': ('created_by', 'delivered_by', 'created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    def get_customer(self, obj):
        return obj.customer.name
    get_customer.short_description = 'Customer'
    
    def get_created_by(self, obj):
        return obj.created_by.username
    get_created_by.short_description = 'Salesperson'
    
    def status_badge(self, obj):
        colors = {
            'draft': 'blue',
            'confirmed': 'purple',
            'dispatched': 'orange',
            'delivered': 'green',
            'cancelled': 'red',
            'returned': 'gray'
        }
        return format_html(f'<span style="color: {colors.get(obj.status)}; font-weight: bold;">{obj.get_status_display()}</span>')
    status_badge.short_description = 'Status'
    
    def save_model(self, request, obj, form, change):
        if not change:
            obj.created_by = request.user
        super().save_model(request, obj, form, change)


@admin.register(SaleItem)
class SaleItemAdmin(admin.ModelAdmin):
    """Sale Item Details Admin"""
    list_display = ('get_sale', 'item', 'quantity', 'unit_price', 'line_total')
    list_filter = ('sale__sale_date', 'item__category')
    search_fields = ('sale__sale_number', 'item__name')
    readonly_fields = ('id', 'tax_amount', 'gst_amount', 'line_total', 'created_at')
    
    fieldsets = (
        ('Item Details', {
            'fields': ('id', 'sale', 'item', 'quantity', 'unit_price')
        }),
        ('Tax & GST', {
            'fields': ('tax_percentage', 'tax_amount', 'gst_percentage', 'gst_amount')
        }),
        ('Total', {
            'fields': ('line_total',)
        }),
        ('Metadata', {
            'fields': ('created_at',),
            'classes': ('collapse',)
        }),
    )
    
    def get_sale(self, obj):
        return obj.sale.sale_number
    get_sale.short_description = 'Sale'


@admin.register(StockMovement)
class StockMovementAdmin(admin.ModelAdmin):
    """Stock Movement Tracking Admin"""
    list_display = ('item', 'movement_type_badge', 'quantity', 'reference_number', 'created_by', 'created_at')
    list_filter = ('movement_type', 'created_at', 'item__category')
    search_fields = ('item__name', 'reference_number', 'notes')
    readonly_fields = ('id', 'created_at')
    date_hierarchy = 'created_at'
    
    fieldsets = (
        ('Movement Details', {
            'fields': ('id', 'item', 'movement_type', 'quantity', 'reference_number')
        }),
        ('Notes', {
            'fields': ('notes',)
        }),
        ('Metadata', {
            'fields': ('created_by', 'created_at'),
            'classes': ('collapse',)
        }),
    )
    
    def movement_type_badge(self, obj):
        colors = {
            'purchase': 'blue',
            'sale': 'green',
            'return': 'orange',
            'adjustment': 'purple',
            'damage': 'red',
            'transfer': 'gray'
        }
        return format_html(f'<span style="color: {colors.get(obj.movement_type)}; font-weight: bold;">{obj.get_movement_type_display()}</span>')
    movement_type_badge.short_description = 'Type'
    
    def save_model(self, request, obj, form, change):
        if not change:
            obj.created_by = request.user
        super().save_model(request, obj, form, change)
