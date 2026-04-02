from django.db import models
from django.utils.text import slugify
from django.utils import timezone
from ckeditor.fields import RichTextField
from decimal import Decimal

class Attribute(models.Model):
    FIELD_TYPES = (
        ('text', 'Text Input'),
        ('number', 'Numeric Value'),
        ('select', 'Dropdown Menu'),
    )
    name = models.CharField(max_length=50)
    field_type = models.CharField(max_length=10, choices=FIELD_TYPES, default='text')
    def __str__(self): return self.name

class AttributeOption(models.Model):
    attribute = models.ForeignKey(Attribute, related_name='options', on_delete=models.CASCADE)
    value = models.CharField(max_length=100)
    def __str__(self): return f"{self.attribute.name}: {self.value}"

class Category(models.Model):
    parent = models.ForeignKey('self', related_name='subcategories', null=True, blank=True, on_delete=models.CASCADE)
    name = models.CharField(max_length=100)
    slug = models.SlugField(unique=True, blank=True)
    image = models.ImageField(
        upload_to='categories/', 
        null=True, 
        blank=True, 
        help_text="Recommended: 512x512px. JPG, PNG, WEBP. Max 1MB."
    )
    image_url = models.URLField(blank=True, null=True, help_text="Alternative: Direct link to an externally hosted image.")
    attributes = models.ManyToManyField(Attribute, blank=True, related_name='categories')
    
    # Homepage Config
    show_on_homepage = models.BooleanField(default=False, verbose_name="Show on Homepage")
    homepage_order   = models.PositiveIntegerField(default=0, verbose_name="Homepage Display Order")

    # SEO — Standard
    meta_title = models.CharField(max_length=255, blank=True, verbose_name="SEO Title Tag")
    meta_description = models.TextField(blank=True, verbose_name="SEO Meta Description")
    meta_keywords = models.CharField(max_length=255, blank=True, verbose_name="SEO Meta Keywords")
    url_alias = models.CharField(max_length=255, blank=True, verbose_name="SEO URL Alias")
    # SEO — English
    meta_title_en = models.CharField(max_length=255, blank=True, verbose_name="Title Tag (EN)")
    meta_description_en = models.TextField(blank=True, verbose_name="Meta Description (EN)")
    meta_keywords_en = models.CharField(max_length=255, blank=True, verbose_name="Meta Keywords (EN)")
    url_alias_en = models.CharField(max_length=255, blank=True, verbose_name="URL Alias (EN)")
    # SEO — Arabic
    meta_title_ar = models.CharField(max_length=255, blank=True, verbose_name="Title Tag (AR)")
    meta_description_ar = models.TextField(blank=True, verbose_name="Meta Description (AR)")
    meta_keywords_ar = models.CharField(max_length=255, blank=True, verbose_name="Meta Keywords (AR)")
    url_alias_ar = models.CharField(max_length=255, blank=True, verbose_name="URL Alias (AR)")

    @property
    def get_image_url(self):
        if self.image_url: return self.image_url
        if self.image: return self.image.url
        return "https://via.placeholder.com/300"

    def save(self, *args, **kwargs):
        if not self.slug: self.slug = slugify(self.name)
        super().save(*args, **kwargs)
    def __str__(self): return f"{self.parent.name} > {self.name}" if self.parent else self.name
    class Meta: verbose_name_plural = "Categories"

class Product(models.Model):
    category = models.ForeignKey(Category, related_name='products', on_delete=models.CASCADE)
    name = models.CharField(max_length=255)
    slug = models.SlugField(unique=True, null=True, blank=True)
    image = models.ImageField(
        upload_to='products/', 
        null=True, 
        blank=True,
        help_text="Primary Product Image. Recommended: 1000x1000px. JPG, PNG, WEBP. Max 2MB."
    )
    image_url = models.URLField(blank=True, null=True, help_text="Alternative: Direct link to an externally hosted image.")

    @property
    def get_image_url(self):
        if self.image_url: return self.image_url
        if self.image: return self.image.url
        return "https://via.placeholder.com/600x400"

    def save(self, *args, **kwargs):
        if not self.slug: self.slug = slugify(self.name)
        super().save(*args, **kwargs)
    
    features = models.TextField(help_text="One feature per line", blank=True)
    overview = RichTextField(blank=True, null=True)
    technical_info = RichTextField(blank=True, null=True)
    brochure = models.FileField(upload_to='brochures/', null=True, blank=True, help_text="PDF format recommended.")
    regular_price = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    sale_price = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
    # Advanced SEO - Multilingual
    # Standard/Default
    meta_title = models.CharField(max_length=255, blank=True, verbose_name="SEO Title Tag")
    meta_description = models.TextField(blank=True, verbose_name="SEO Meta Description")
    meta_keywords = models.CharField(max_length=255, blank=True, verbose_name="SEO Meta Keywords")
    url_alias = models.CharField(max_length=255, blank=True, verbose_name="SEO URL Alias")
    
    # English (EN)
    meta_title_en = models.CharField(max_length=255, blank=True, verbose_name="SEO Title Tag (EN)")
    meta_description_en = models.TextField(blank=True, verbose_name="SEO Meta Description (EN)")
    meta_keywords_en = models.CharField(max_length=255, blank=True, verbose_name="SEO Meta Keywords (EN)")
    url_alias_en = models.CharField(max_length=255, blank=True, verbose_name="SEO URL Alias (EN)")
    
    # Arabic (AR)
    meta_title_ar = models.CharField(max_length=255, blank=True, verbose_name="SEO Title Tag (AR)")
    meta_description_ar = models.TextField(blank=True, verbose_name="SEO Meta Description (AR)")
    meta_keywords_ar = models.CharField(max_length=255, blank=True, verbose_name="SEO Meta Keywords (AR)")
    url_alias_ar = models.CharField(max_length=255, blank=True, verbose_name="SEO URL Alias (AR)")
    
    def get_best_price_info(self):
        """
        Scans all related SKUs for active offers and returns the best overall pricing dictionary.
        """
        all_skus = self.skus.all()
        if not all_skus:
            reg = self.regular_price or 0
            sale = self.sale_price or reg
            return {
                'has_offer': sale < reg,
                'final_price': sale,
                'regular_price': reg,
                'discount_amount': reg - sale,
                'discount_percentage': self.get_discount_percentage(),
                'discount_display': f"{self.get_discount_percentage()}% OFF" if sale < reg else None
            }
        
        # Get all SKU price infos and sort by lowest final price
        sku_infos = [sku.get_price_info() for sku in all_skus]
        best_info = min(sku_infos, key=lambda x: x['final_price'])
        return best_info

    def get_discount_amount(self):
        reg = self.regular_price or 0
        sale = self.sale_price or 0
        return reg - sale if reg > sale else 0
    
    def get_discount_percentage(self):
        reg = self.regular_price or 0
        sale = self.sale_price or 0
        if reg > 0 and sale < reg:
            return int(round(((reg - sale) / reg) * 100))
        return 0
    def is_in_stock(self): return self.skus.filter(quantity__gt=0, shipping_status='available').exists()
    def __str__(self): return self.name

class ProductAttributeValue(models.Model):
    product = models.ForeignKey(Product, related_name='characteristics', on_delete=models.CASCADE)
    attribute = models.ForeignKey(Attribute, on_delete=models.CASCADE)
    value = models.CharField(max_length=255, default="")
    def __str__(self): return f"{self.product.name} - {self.attribute.name}: {self.value}"

class ProductImage(models.Model):
    product = models.ForeignKey(Product, related_name='images', on_delete=models.CASCADE)
    image = models.ImageField(
        upload_to='products/gallery/', 
        null=True, 
        blank=True,
        help_text="Gallery Image. Recommended: 1000x1000px. JPG, PNG, WEBP. Max 2MB."
    )
    image_url = models.URLField(blank=True, null=True, help_text="Alternative: Direct link to an externally hosted image.")
    order = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ['order']

    @property
    def get_image_url(self):
        if self.image_url: return self.image_url
        if self.image: return self.image.url
        return "https://via.placeholder.com/600x400"

from django.utils import timezone

class ProductSKU(models.Model):
    product = models.ForeignKey(Product, related_name='skus', on_delete=models.CASCADE)
    title = models.CharField(max_length=255, blank=True, help_text="e.g. Small, Blue, standard, etc.")
    sku_id = models.CharField(max_length=50, unique=True, blank=True, help_text="Auto-generated if left blank.")
    quantity = models.IntegerField(null=True, blank=True)
    unit = models.CharField(max_length=20, choices=[('pcs', 'Pieces'), ('box', 'Box'), ('set', 'Set')], default='pcs')
    
    # Dimensions & Weight
    weight = models.FloatField(help_text="in kg", null=True, blank=True)
    length = models.FloatField(help_text="in cm", null=True, blank=True)
    width = models.FloatField(help_text="in cm", null=True, blank=True)
    height = models.FloatField(help_text="in cm", null=True, blank=True)
    
    # Shipping
    delivery_time = models.CharField(max_length=100, blank=True)
    shipping_status = models.CharField(max_length=50, choices=[
        ('available', 'In Stock'), ('out_of_stock', 'Out of Stock'), ('pre_order', 'Pre-Order')
    ], default='available')
    free_shipping = models.BooleanField(default=False)
    additional_shipping_charge = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True, help_text="Extra shipping fee in AED")

    def get_active_offer(self):
        now = timezone.now()
        # Returns the first active offer (highest priority in the future if needed)
        return self.offers.filter(
            is_active=True,
            start_date__lte=now,
            end_date__gte=now
        ).first()

    def get_price_info(self):
        """
        Returns a dictionary of price-related fields: 
        final_price, regular_price, has_offer, offer_id, etc.
        """
        offer = self.get_active_offer()
        # Default to product's prices
        regular_price = self.product.regular_price or 0
        current_sale_price = self.product.sale_price or regular_price
        
        if not offer:
            return {
                'has_offer': False,
                'offer': None,
                'regular_price': regular_price,
                'final_price': current_sale_price,
                'discount_display': None
            }
        
        # Apply offer on top of CURRENT sale_price if it's set, else regular
        base_to_discount = Decimal(str(current_sale_price))
        final_price = base_to_discount

        if offer.offer_type == 'percentage':
            # Calculate: base * (1 - discount/100)
            multiplier = Decimal('1') - (Decimal(str(offer.discount_value)) / Decimal('100'))
            final_price = base_to_discount * multiplier
        elif offer.offer_type == 'fixed':
            final_price = base_to_discount - Decimal(str(offer.discount_value))
        elif offer.offer_type == 'final':
            final_price = Decimal(str(offer.discount_value))
        
        reg = Decimal(str(regular_price))
        final = max(Decimal('0'), final_price.quantize(Decimal('0.01')))

        return {
            'has_offer': True,
            'offer': offer,
            'regular_price': reg,
            'final_price': final,
            'discount_amount': reg - final,
            'discount_percentage': int(round(((reg - final) / reg) * 100)) if reg > 0 else 0,
            'discount_display': f"{int(offer.discount_value)}% OFF" if offer.offer_type == 'percentage' else "OFFER"
        }

    def save(self, *args, **kwargs):
        if not self.sku_id:
            import random, string
            # Generate a unique SKU if not provided
            prefix = slugify(self.product.name)[:10].upper()
            suffix = ''.join(random.choices(string.ascii_uppercase + string.digits, k=4))
            self.sku_id = f"JKR-{prefix}-{suffix}"
            # Ensure uniqueness
            while ProductSKU.objects.filter(sku_id=self.sku_id).exists():
                suffix = ''.join(random.choices(string.ascii_uppercase + string.digits, k=4))
                self.sku_id = f"JKR-{prefix}-{suffix}"
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.product.name} - {self.sku_id}"

class Offer(models.Model):
    OFFER_TYPES = (
        ('percentage', 'Percentage Discount (%)'),
        ('fixed', 'Fixed Discount Entry (AED)'),
        ('final', 'Final Set Price (AED)'),
        ('bogo', 'Buy One Get One (BOGO)'),
    )
    name = models.CharField(max_length=100)
    offer_type = models.CharField(max_length=20, choices=OFFER_TYPES, default='percentage')
    discount_value = models.DecimalField(max_digits=10, decimal_places=2, help_text="Percentage or AED amount")
    skus = models.ManyToManyField(ProductSKU, related_name='offers', blank=True)
    start_date = models.DateTimeField()
    end_date = models.DateTimeField()
    is_active = models.BooleanField(default=True)

    def __str__(self):
        return f"{self.name} ({self.discount_value}{'%' if self.offer_type == 'percentage' else ' AED'})"

class Collection(models.Model):
    name = models.CharField(max_length=100)
    slug = models.SlugField(unique=True, blank=True)
    banner = models.ImageField(upload_to='collections/', null=True, blank=True, help_text="Homepage Banner for this collection.")
    skus = models.ManyToManyField(ProductSKU, related_name='collections', blank=True)
    is_active = models.BooleanField(default=True)
    display_order = models.PositiveIntegerField(default=0)

    def save(self, *args, **kwargs):
        if not self.slug: self.slug = slugify(self.name)
        super().save(*args, **kwargs)

    def __str__(self):
        return self.name

    class Meta:
        ordering = ['display_order']
