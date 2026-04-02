from django.db import models
from django.conf import settings
from products.models import Product


# ─── Legacy Order (kept for compatibility) ────────────────────────────────────

class Order(models.Model):
    STATUS = (
        ('Pending', 'Pending'),
        ('Processing', 'Processing'),
        ('Shipped', 'Shipped'),
        ('Delivered', 'Delivered'),
        ('Cancelled', 'Cancelled'),
    )
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True)
    full_name = models.CharField(max_length=255)
    total_amount = models.DecimalField(max_digits=12, decimal_places=2)
    payment_status = models.BooleanField(default=False)
    status = models.CharField(max_length=20, choices=STATUS, default='Pending')
    created_at = models.DateTimeField(auto_now_add=True)


class OrderItem(models.Model):
    order = models.ForeignKey(Order, related_name='items', on_delete=models.CASCADE)
    sku = models.ForeignKey('products.ProductSKU', on_delete=models.CASCADE)
    quantity = models.IntegerField()
    price = models.DecimalField(max_digits=10, decimal_places=2)


# ─── Quote Enquiry ────────────────────────────────────────────────────────────

class QuoteEnquiry(models.Model):
    first_name = models.CharField(max_length=100)
    last_name = models.CharField(max_length=100)
    email = models.EmailField()
    department = models.CharField(max_length=255, blank=True)
    country = models.CharField(max_length=100)
    city = models.CharField(max_length=100)
    street = models.CharField(max_length=255, blank=True)
    phone = models.CharField(max_length=50)
    comment = models.TextField(blank=True)
    status = models.CharField(max_length=20, default='New', choices=(
        ('New', 'New'),
        ('Processing', 'Processing'),
        ('Quoted', 'Quoted'),
        ('Closed', 'Closed'),
    ))
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Enquiry from {self.first_name} {self.last_name} - {self.created_at.strftime('%Y-%m-%d')}"

    class Meta:
        verbose_name = "Quote Enquiry"
        verbose_name_plural = "Quote Enquiries"


class QuoteItem(models.Model):
    enquiry = models.ForeignKey(QuoteEnquiry, related_name='items', on_delete=models.CASCADE)
    product = models.ForeignKey(Product, on_delete=models.CASCADE)
    quantity = models.PositiveIntegerField(default=1)

    def __str__(self):
        return f"{self.product.name} x {self.quantity}"


# ─── Customer Order (full checkout flow) ──────────────────────────────────────

class CustomerOrder(models.Model):

    PAYMENT_METHOD_CHOICES = (
        ('card',   'Credit / Debit Card'),
        ('tabby',  'Tabby – Pay in 4'),
        ('tamara', 'Tamara – Pay in 3'),
        ('cod',    'Cash on Delivery'),
    )

    PAYMENT_STATUS_CHOICES = (
        ('pending',   'Pending'),
        ('paid',      'Paid'),
        ('failed',    'Failed'),
        ('refunded',  'Refunded'),
    )

    ORDER_STATUS_CHOICES = (
        ('pending',           'Pending'),
        ('packaging',         'Packaging'),
        ('ready_for_shipment', 'Ready for shipment'),
        ('shipped',           'Shipped'),
        ('delivered',         'Delivered'),
        ('return_to_origin',   'Return to origin'),
        ('refund',            'Refund'),
    )

    # ── Billing / Customer ──────────────────────────────────────────────────
    first_name  = models.CharField(max_length=100)
    last_name   = models.CharField(max_length=100)
    email       = models.EmailField()
    phone       = models.CharField(max_length=50)
    department  = models.CharField(max_length=255, blank=True)
    country     = models.CharField(max_length=100)
    city        = models.CharField(max_length=100)
    street      = models.CharField(max_length=255, blank=True)
    comment     = models.TextField(blank=True, verbose_name="Customer Notes")

    # ── Payment ─────────────────────────────────────────────────────────────
    payment_method  = models.CharField(max_length=20, choices=PAYMENT_METHOD_CHOICES, default='cod')
    payment_status  = models.CharField(max_length=20, choices=PAYMENT_STATUS_CHOICES, default='pending')

    # ── Order Management ─────────────────────────────────────────────────────
    status          = models.CharField(max_length=30, choices=ORDER_STATUS_CHOICES, default='pending', verbose_name="Order Status")
    shipping_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0, help_text="Total shipping cost for this order")
    total_amount    = models.DecimalField(max_digits=12, decimal_places=2, default=0, help_text="Grand Total (Items + Shipping)")
    admin_notes     = models.TextField(blank=True, verbose_name="Internal Admin Notes")
    created_at      = models.DateTimeField(auto_now_add=True)
    updated_at      = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']
        verbose_name = "Customer Order"
        verbose_name_plural = "Customer Orders"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.__status = self.status

    def __str__(self):
        return f"Order #{self.pk} — {self.first_name} {self.last_name}"

    @property
    def full_name(self):
        return f"{self.first_name} {self.last_name}"

    def compute_total(self):
        items_total = sum(item.total_price for item in self.items.all())
        self.total_amount = items_total + self.shipping_amount
        self.save(update_fields=['total_amount'])
        return self.total_amount

    def save(self, *args, **kwargs):
        is_new = self.pk is None
        status_changed = not is_new and self.status != self.__status
        
        super().save(*args, **kwargs)
        
        if is_new or status_changed:
            # 1. Log history
            OrderStatusHistory.objects.create(order=self, status=self.status)
            
            # 2. Trigger notifications
            from .notifications import send_customer_notification
            send_customer_notification(self)
            
            self.__status = self.status


class OrderStatusHistory(models.Model):
    order = models.ForeignKey(CustomerOrder, related_name='history', on_delete=models.CASCADE)
    status = models.CharField(max_length=30)
    changed_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-changed_at']
        verbose_name = "Order Status History"
        verbose_name_plural = "Order Status Histories"

    def __str__(self):
        return f"{self.order} — {self.status} at {self.changed_at}"


class CustomerOrderItem(models.Model):
    order        = models.ForeignKey(CustomerOrder, related_name='items', on_delete=models.CASCADE)
    product      = models.ForeignKey(Product, on_delete=models.SET_NULL, null=True, blank=True)
    product_name = models.CharField(max_length=255, help_text="Snapshot of name at time of order")
    quantity     = models.PositiveIntegerField(default=1)
    unit_price      = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    shipping_charge = models.DecimalField(max_digits=10, decimal_places=2, default=0, help_text="Shipping cost for this specific item")
    total_price     = models.DecimalField(max_digits=10, decimal_places=2, default=0)

    def save(self, *args, **kwargs):
        self.total_price = self.unit_price * self.quantity
        if self.product and not self.product_name:
            self.product_name = self.product.name
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.product_name} × {self.quantity}"

    class Meta:
        verbose_name = "Order Item"
        verbose_name_plural = "Order Items"
