from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from products.models import Product
from .models import QuoteEnquiry, QuoteItem, CustomerOrder, CustomerOrderItem


from products.models import Product, ProductSKU

def _get_cart_items(request):
    """
    Helper: resolve cart session into list of dicts.
    Cart stores SKU_ID as the unique key where possible, falls back to product_id if not.
    """
    cart = request.session.get('enquiry_cart', {})
    items = []
    total_shipping = 0
    for item_key, item_data in cart.items():
        try:
            # We first try to see if item_key is a SKU_ID (alnum string)
            sku = ProductSKU.objects.filter(sku_id=item_key).first()
            if not sku:
                # Fallback to product ID if SKU not found
                product = Product.objects.get(id=int(item_key))
                sku = product.skus.first() # Assume first SKU for basic products
            else:
                product = sku.product
            
            if not sku: continue

            qty = int(item_data.get('quantity', 1))
            price_info = sku.get_price_info()
            
            unit_price = price_info['final_price']
            total_item = round(unit_price * qty, 2)
            
            # Shipping logic
            shipping_per_unit = 0 if sku.free_shipping else (sku.additional_shipping_charge or 0)
            shipping_item = round(shipping_per_unit * qty, 2)
            total_shipping += shipping_item

            offer_applied = price_info.get('offer')
            bogo_message = None
            if offer_applied and offer_applied.offer_type == 'bogo':
                # BOGO Logic: Every 2nd item is FREE or "Add 1 Get 1"
                # If they have 1 in cart, we can suggest adding another, or we can just double it.
                # Requirement: "should show the other product also as per the offer"
                # So if they have 1, we show a message or just calculate properly.
                bogo_message = "BOGO Applied: Buy 1 Get 1 Free"
                # Effective total: 1 unit price for every 2 items
                payable_qty = (qty // 2) + (qty % 2)
                total_item = round(unit_price * payable_qty, 2)

            items.append({
                'product': product,
                'sku': sku,
                'quantity': qty,
                'unit_price': unit_price,
                'regular_price': price_info['regular_price'],
                'total_item': total_item,
                'shipping_item': shipping_item,
                'is_free_shipping': sku.free_shipping,
                'has_offer': price_info['has_offer'],
                'offer_name': offer_applied.name if offer_applied else None,
                'bogo_message': bogo_message,
            })
        except (Product.DoesNotExist, ValueError):
            continue
    return items, round(total_shipping, 2)


# ── Cart ─────────────────────────────────────────────────────────────────────

def enquiry_cart(request):
    cart_items, total_shipping = _get_cart_items(request)
    subtotal = sum(item['total_item'] for item in cart_items)
    grand_total = subtotal + total_shipping
    return render(request, 'orders/enquiry_cart.html', {
        'cart_items': cart_items,
        'subtotal': subtotal,
        'total_shipping': total_shipping,
        'grand_total': grand_total
    })


def add_to_cart(request, product_id):
    product = get_object_or_404(Product, id=product_id)
    sku_id = request.GET.get('sku')
    
    sku = None
    if sku_id:
        sku = ProductSKU.objects.filter(sku_id=sku_id).first()
    if not sku:
        sku = product.skus.first() # Fallback to first SKU
    
    if not sku:
        messages.error(request, "This product has no active variants.")
        return redirect('product_detail', slug=product.slug)

    cart = request.session.get('enquiry_cart', {})
    item_key = sku.sku_id # Store by SKU ID for uniqueness and offer tracking
    
    if item_key in cart:
        cart[item_key]['quantity'] += 1
    else:
        cart[item_key] = {'quantity': 1}

    request.session['enquiry_cart'] = cart
    messages.success(request, f"✅ {product.name} (Variant: {sku.title or 'Standard'}) added to cart.")
    return redirect('enquiry_cart')


def remove_from_cart(request, product_id):
    # Support both product_id (legacy) and SKU ID in URL
    sku_id = request.GET.get('sku')
    cart = request.session.get('enquiry_cart', {})
    
    if sku_id and sku_id in cart:
        del cart[sku_id]
    elif str(product_id) in cart:
        del cart[str(product_id)]
    
    request.session['enquiry_cart'] = cart
    messages.info(request, "Item removed from cart.")
    return redirect('enquiry_cart')


# ── Checkout Step 1 — Billing ─────────────────────────────────────────────────

def checkout_billing(request):
    cart_items, total_shipping = _get_cart_items(request)
    if not cart_items:
        messages.warning(request, "Your cart is empty.")
        return redirect('enquiry_cart')

    if request.method == 'POST':
        billing = {
            'first_name': request.POST.get('first_name', ''),
            'last_name':  request.POST.get('last_name', ''),
            'email':      request.POST.get('email', ''),
            'phone':      request.POST.get('phone', ''),
            'department': request.POST.get('department', ''),
            'country':    request.POST.get('country', ''),
            'city':       request.POST.get('city', ''),
            'street':     request.POST.get('street', ''),
            'comment':    request.POST.get('comment', ''),
        }
        request.session['checkout_billing'] = billing
        return redirect('checkout_payment')

    form_data = request.session.get('checkout_billing', {})
    subtotal = sum(item['total_item'] for item in cart_items)
    return render(request, 'orders/checkout_billing.html', {
        'cart_items': cart_items,
        'form_data': form_data,
        'subtotal': subtotal,
        'total_shipping': total_shipping,
        'grand_total': subtotal + total_shipping
    })


# ── Checkout Step 2 — Payment ─────────────────────────────────────────────────

def checkout_payment(request):
    cart_items, total_shipping = _get_cart_items(request)
    billing = request.session.get('checkout_billing')

    if not cart_items:
        return redirect('enquiry_cart')
    if not billing:
        return redirect('checkout_billing')

    subtotal = sum(item['total_item'] for item in cart_items)
    grand_total = subtotal + total_shipping

    if request.method == 'POST':
        payment_method = request.POST.get('payment_method', 'card')

        # Create the CustomerOrder record
        order = CustomerOrder.objects.create(
            first_name=billing.get('first_name', ''),
            last_name=billing.get('last_name', ''),
            email=billing.get('email', ''),
            phone=billing.get('phone', ''),
            department=billing.get('department', ''),
            country=billing.get('country', ''),
            city=billing.get('city', ''),
            street=billing.get('street', ''),
            comment=billing.get('comment', ''),
            payment_method=payment_method,
            status='pending',
            payment_status='pending',
            shipping_amount=total_shipping,
            total_amount=grand_total
        )

        # Save line items
        for item in cart_items:
            product = item['product']
            CustomerOrderItem.objects.create(
                order=order,
                product=product,
                product_name=f"{product.name} ({item['sku'].title})" if item.get('sku') else product.name,
                quantity=item['quantity'],
                unit_price=item['unit_price'],
                shipping_charge=item['shipping_item'],
                total_price=item['total_item']
            )

        # Clear cart & billing from session
        request.session['enquiry_cart'] = {}
        request.session.pop('checkout_billing', None)

        # Store order id for the success page
        request.session['last_order_id'] = order.id

        return redirect('checkout_success')

    return render(request, 'orders/checkout_payment.html', {
        'cart_items': cart_items,
        'billing': billing,
        'subtotal': subtotal,
        'total_shipping': total_shipping,
        'grand_total': grand_total
    })


# ── Checkout Step 3 — Success ─────────────────────────────────────────────────

def checkout_success(request):
    order_id = request.session.pop('last_order_id', None)
    if not order_id:
        return redirect('enquiry_cart')
        
    order = get_object_or_404(CustomerOrder, id=order_id)
    return render(request, 'orders/checkout_success.html', {
        'order': order,
    })


# ── Legacy enquiry submit (kept for compatibility) ───────────────────────────

def submit_enquiry(request):
    if request.method == 'POST':
        cart = request.session.get('enquiry_cart', {})
        if not cart:
            messages.warning(request, "Your cart is empty.")
            return redirect('enquiry_cart')
        billing = {k: request.POST.get(k, '') for k in
                   ['first_name','last_name','email','department','country','city','street','phone','comment']}
        enquiry = QuoteEnquiry.objects.create(**billing)
        for product_id, item_data in cart.items():
            product = get_object_or_404(Product, id=int(product_id))
            QuoteItem.objects.create(enquiry=enquiry, product=product, quantity=item_data['quantity'])
        request.session['enquiry_cart'] = {}
        # For legacy, we keep using the old success page or redirect to home
        messages.success(request, "Your enquiry has been submitted successfully.")
        return redirect('home')
    return redirect('enquiry_cart')
