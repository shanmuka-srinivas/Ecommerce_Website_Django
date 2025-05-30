from django.shortcuts import render
from .models import *
from django.contrib import messages
from django.contrib.auth.models import User
from django.contrib.auth import authenticate, login, logout
from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_POST
import datetime
import stripe
from django.conf import settings
from django.views.decorators.csrf import csrf_exempt
from django.http import JsonResponse


def login_view(request):
    if request.user.is_authenticated:
        return redirect('store')
    if request.method == "POST":
        username = request.POST['username']
        password = request.POST['password']
        user = authenticate(request, username=username, password=password)
        if user is not None:
            login(request, user)
            return redirect('store')
        else:
            messages.error(request, 'Invalid username or password')
    return render(request, 'store/login.html')


def signup_view(request):
    if request.user.is_authenticated:
        return redirect('store')
    if request.method == "POST":
        username = request.POST['username']
        password = request.POST['password']
        password2 = request.POST['password2']
        if password != password2:
            messages.error(request, "Passwords do not match")
            return redirect('signup')
        if User.objects.filter(username=username).exists():
            messages.error(request, "Username already exists")
            return redirect('signup')
        user = User.objects.create_user(username=username, password=password)
        user.save()
        messages.success(request, "Account created successfully! Please login")
        return redirect('login')
    return render(request, 'store/signup.html')


def logout_view(request):
    if request.user.is_authenticated:
        customer = getattr(request.user, 'customer', None)
        if customer:
            Order.objects.filter(customer=customer, complete=False, transaction_id__isnull=True).delete()
            OrderItem.objects.filter(order__isnull=True).delete()
        logout(request)
    return redirect('login')


@login_required(login_url='login')
def store(request):
    if request.user.is_authenticated:
        customer = request.user.customer
        order = Order.objects.filter(customer=customer, complete=False).first()
        if order:
            items = order.orderitem_set.all()
            cartItems = order.get_cart_items
        else:
            items = []
            order = {'get_cart_total':0, 'get_cart_items':0, 'shipping':False}
            cartItems = order['get_cart_items']
    else:
        items = []
        order = {'get_cart_total':0, 'get_cart_items':0, 'shipping':False}
        cartItems = order['get_cart_items']
    products = Product.objects.all()
    context = {'products':products, 'cartItems':cartItems}
    return render(request , 'store/store.html' , context)


def cart(request):
    if request.user.is_authenticated:
        customer = request.user.customer
        order = Order.objects.filter(customer=customer, complete=False).first()
        if order:
            items = order.orderitem_set.all()
            cartItems = order.get_cart_items
        else:
            items = []
            order = {'get_cart_total':0, 'get_cart_items':0, 'shipping':False}
            cartItems = order['get_cart_items']
    else:
        items = []
        order = {'get_cart_total':0, 'get_cart_items':0, 'shipping':False}
        cartItems = order['get_cart_items']
    context = {'items':items, 'order':order, 'cartItems':cartItems}
    return render(request , 'store/cart.html' , context)


def checkout(request):
    if request.user.is_authenticated:
        customer = request.user.customer
        order = Order.objects.filter(customer=customer, complete=False).first()
        if order:
            items = order.orderitem_set.all()
            cartItems = order.get_cart_items
        else:
            items = []
            order = {'get_cart_total': 0, 'get_cart_items': 0, 'shipping': False}
            cartItems = order['get_cart_items']
    else:
        items = []
        order = {'get_cart_total': 0, 'get_cart_items': 0, 'shipping': False}
        cartItems = order['get_cart_items']
    context = {
        'items': items,
        'order': order,
        'cartItems': cartItems,
        # 'stripe_public_key': settings.STRIPE_PUBLIC_KEY
    }
    return render(request, 'store/checkout.html', context)


@require_POST
@login_required
def updateItem(request):
    productId = request.POST.get('productId')
    action = request.POST.get('action')
    customer = request.user.customer
    try:
        product = Product.objects.get(id=productId)
    except Product.DoesNotExist:
        return redirect('store')
    order,created = Order.objects.get_or_create(customer=customer, complete=False)
    orderItem,created = OrderItem.objects.get_or_create(order=order, product=product)
    if action == 'add':
        orderItem.quantity += 1
    elif action == 'remove':
        orderItem.quantity -= 1
    if orderItem.quantity <= 0:
        orderItem.delete()
    else:
        orderItem.save()
    return redirect(request.META.get('HTTP_REFERER', 'store'))


@login_required
@require_POST
def processOrder(request):
    transaction_id = datetime.datetime.now().timestamp()
    customer = request.user.customer
    order, created = Order.objects.get_or_create(customer=customer, complete=False)
    total = float(request.POST.get('total', 0))
    order.transaction_id = transaction_id
    if total == float(order.get_cart_total):
        order.complete = True
        order.save()
        order_items = order.orderitem_set.all()
        for item in order_items:
            if item.price_at_purchase is None:
                item.price_at_purchase = item.product.price
                item.save()
        if order.shipping:
            ShippingAddress.objects.create(
                customer=customer,
                order=order,
                address=request.POST.get('address'),
                city=request.POST.get('city'),
                state=request.POST.get('state'),
                zipcode=request.POST.get('zipcode'),
            )
        return redirect('store')
    return redirect('store')


@login_required
def OrderHistory(request):
    customer = request.user.customer
    order = Order.objects.filter(customer=customer, complete=False).first()
    if order:
        cartItems = order.get_cart_items
    else:
        cartItems = 0
    order_items = OrderItem.objects.filter(order__customer=customer,order__complete=True).order_by('-order__date_ordered')
    context = {'order_items': order_items,'cartItems': cartItems}
    return render(request, 'store/orderhistory.html', context)


# stripe.api_key = settings.STRIPE_SECRET_KEY
@csrf_exempt
def create_checkout_session(request):
    if request.method == 'POST':
        total = float(request.POST.get('total', 0))
        YOUR_DOMAIN = 'http://127.0.0.1:8000'
        checkout_session = stripe.checkout.Session.create(
            payment_method_types=['card'],
            line_items=[
                {
                    'price_data': {
                        'currency': 'usd',
                        'unit_amount': int(total * 100),
                        'product_data': {
                            'name': 'Cart Total',
                        },
                    },
                    'quantity': 1,
                },
            ],
            mode='payment',
            success_url = YOUR_DOMAIN + '/payment-success/',
            cancel_url = YOUR_DOMAIN + '/payment-cancelled/',
        )
        return JsonResponse({'id': checkout_session.id})
    

@csrf_exempt
def payment_success(request):
    if request.method == 'POST':
        transaction_id = datetime.datetime.now().timestamp()
        if request.user.is_authenticated:
            customer = request.user.customer
        else:
            name = request.POST.get('name')
            email = request.POST.get('email')
            customer, created = Customer.objects.get_or_create(email=email)
            customer.name = name
            customer.save()
        order, created = Order.objects.get_or_create(customer=customer, complete=False)
        order.transaction_id = transaction_id
        order.complete = True
        order.save()
        items = order.orderitem_set.all()
        for item in items:
            if item.price_at_purchase is None:
                item.price_at_purchase = item.product.price
                item.save()
        if order.shipping:
            address = request.POST.get('address')
            city = request.POST.get('city')
            state = request.POST.get('state')
            zipcode = request.POST.get('zipcode')
            if all([address, city, state, zipcode]):
                ShippingAddress.objects.create(
                    customer=customer,
                    order=order,
                    address=address,
                    city=city,
                    state=state,
                    zipcode=zipcode,
                )
        return render(request, 'store/payment_success.html')
    return render(request, 'store/payment_success.html')


def payment_cancelled(request):
    return render(request, 'store/payment_cancelled.html')