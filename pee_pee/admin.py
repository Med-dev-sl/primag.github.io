"""
Custom Admin Site Configuration for PriMag Sales Management Platform
Features:
- Customer Management (daily, weekly, monthly, yearly)
- Income & Expenditure Tracking
- Revenue Management
- Tax & GST Calculation
- Receipt Generation
- Role-Based Access Control (RBAC)
"""

from django.contrib.admin import AdminSite
from django.utils.html import format_html


class PriMagAdminSite(AdminSite):
    """
    Custom admin site for PriMag Sales Management Platform
    """
    site_header = "PriMag"
    site_title = "PriMag - Sales Management Platform"
    index_title = "PriMag Dashboard"
    
    def index(self, request, extra_context=None):
        """Custom admin dashboard"""
        extra_context = extra_context or {}
        extra_context['site_header'] = 'PriMag'
        extra_context['site_title'] = 'PriMag - Sales Management Platform'
        return super().index(request, extra_context)


# Create custom admin site instance
primag_admin_site = PriMagAdminSite(name='primag_admin')
