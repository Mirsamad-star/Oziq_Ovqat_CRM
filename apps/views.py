import json
import random
import requests
import string
from datetime import timedelta

from django.contrib import messages
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.db.models import Avg, Count, Q, Sum
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.utils.text import slugify
from django.views.decorators.http import require_POST, require_GET
from httpx import post, get
from django.shortcuts import render
from django.urls import reverse
from functools import wraps


def login_required_json(view_func):
    """AJAX so'rovlar uchun login talab qiladi — login bo'lmasa JSON xato qaytaradi."""
    @wraps(view_func)
    def _wrapped(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return JsonResponse({
                "ok": False,
                "error": "Avval tizimga kiring yoki ro‘yxatdan o‘ting!",
                "login_required": True,
                "login_url": reverse("login") + "?next=" + request.path,
            }, status=401)
        return view_func(request, *args, **kwargs)
    return _wrapped

from .models import (
    CartItem,
    Category,
    Color,
    GameDiscount,
    Order,
    OrderItem,
    Product,
    ProductImage,
    ProductLike,
    ProductReview,
    Size,
    Unit,
)


def _ensure_session(request):
    if not request.session.session_key:
        request.session.create()
    return request.session.session_key


def _cart_qs(request):
    sk = _ensure_session(request)
    qs = CartItem.objects.filter(session_key=sk).select_related("product")
    if request.user.is_authenticated:
        qs = CartItem.objects.filter(
            Q(session_key=sk) | Q(user=request.user)
        ).select_related("product").distinct()
    return qs


def _cart_count(request):
    return _cart_qs(request).aggregate(total=Sum("quantity"))["total"] or 0


def _get_active_discount(request):
    sk = _ensure_session(request)
    now = timezone.now()
    qs = GameDiscount.objects.filter(
        session_key=sk, is_used=False
    ).filter(Q(expires_at__isnull=True) | Q(expires_at__gt=now))
    if request.user.is_authenticated:
        qs = GameDiscount.objects.filter(
            Q(session_key=sk) | Q(user=request.user),
            is_used=False,
        ).filter(Q(expires_at__isnull=True) | Q(expires_at__gt=now))
    return qs.order_by("-discount_percent").first()


# ─── HOME ───────────────────────────────────────────────────────────────────

def home_page(request):
    products = (
        Product.objects.filter(is_active=True)
        .select_related("category")
        .prefetch_related("images", "reviews")
        .annotate(
            review_average=Avg("reviews__rating"),
            review_count=Count("reviews"),
        )
        .order_by("-created_at")
    )
    categories = Category.objects.annotate(
        product_count=Count("products", filter=Q(products__is_active=True))
    ).order_by("name")
    overall = ProductReview.objects.aggregate(avg=Avg("rating"))["avg"]
    featured = products.filter(sale__gt=0)[:6]
    top_rated = products.order_by("-rating")[:6]
    cart_count = _cart_count(request)
    discount = _get_active_discount(request)

    liked_ids = set()
    sk = _ensure_session(request)
    liked_ids = set(
        ProductLike.objects.filter(session_key=sk).values_list("product_id", flat=True)
    )

    return render(request, "mijos.html", {
        "products": products,
        "categories": categories,
        "overall_rating": round(float(overall), 1) if overall is not None else None,
        "featured": featured,
        "top_rated": top_rated,
        "cart_count": cart_count,
        "active_discount": discount,
        "liked_ids": liked_ids,
        "total_products": products.count(),
    })


# ─── ADMIN PANEL ────────────────────────────────────────────────────────────

def admin_page(request):
    if request.method == "POST":
        name = request.POST.get("name", "").strip()
        about = request.POST.get("about", "").strip()
        if not name:
            messages.error(request, "Mahsulot nomi kiritilishi shart.")
            return redirect("adminpanel")

        try:
            price = max(0, int(request.POST.get("price", 0)))
            rating = min(5, max(0, int(request.POST.get("rating", 5))))
            sale = min(100, max(0, int(request.POST.get("sale", 0))))
            shopping_cost = max(0, int(request.POST.get("copping_cost", 0) or request.POST.get("shopping_cost", 0)))
            min_count = max(1, int(request.POST.get("min_count", 1)))
            men_olgan_narx = max(0, int(request.POST.get("men_olgan_narx", 0)))
        except (TypeError, ValueError):
            messages.error(request, "Raqamli maydonlarni to‘g‘ri kiriting.")
            return redirect("adminpanel")

        category = None
        category_name = request.POST.get("category", "").strip()
        if category_name:
            category, _ = Category.objects.get_or_create(
                slug=slugify(category_name) or slugify(category_name[:40]) or "cat",
                defaults={"name": category_name},
            )
            if category.name != category_name:
                category.name = category_name
                category.save(update_fields=["name", "updated_at"])

        product = Product.objects.create(
            name=name,
            price=price,
            about=about,
            category=category,
            rating=rating,
            sale=sale,
            is_active=request.POST.get("is_active") == "on",
            shopping_cost=shopping_cost,
            min_count=min_count,
            men_olgan_narx=men_olgan_narx,
            unit=request.POST.get("unit", "dona").strip() or "dona",
            size=request.POST.get("size", "").strip() or None,
            color=request.POST.get("color", "").strip() or None,
            owner=request.user if request.user.is_authenticated else None,
        )
        messages.success(request, f'"{product.name}" mahsulot bazaga saqlandi.')
        return redirect("adminpanel")

    products = (
        Product.objects.select_related("category", "owner")
        .prefetch_related("images", "reviews")
        .order_by("-id")
    )
    categories = Category.objects.all().order_by("name")
    units = Unit.objects.all().order_by("name")
    sizes = Size.objects.all().order_by("name")
    colors = Color.objects.all().order_by("name")
    orders = Order.objects.prefetch_related("items").order_by("-created_at")[:50]

    return render(request, "admin.html", {
        "products": products,
        "categories": categories,
        "units": units,
        "sizes": sizes,
        "colors": colors,
        "orders": orders,
        "products_count": Product.objects.count(),
        "active_products_count": Product.objects.filter(is_active=True).count(),
        "categories_count": categories.count(),
        "customers_count": User.objects.count(),
        "units_count": units.count(),
        "sizes_count": sizes.count(),
        "colors_count": colors.count(),
        "orders_count": Order.objects.count(),
    })


def product_edit(request, product_id):
    product = get_object_or_404(Product, pk=product_id)
    if request.method != "POST":
        return redirect("adminpanel")

    name = request.POST.get("name", "").strip()
    if not name:
        messages.error(request, "Mahsulot nomi kiritilishi shart.")
        return redirect("adminpanel")

    try:
        product.name = name
        product.price = max(0, int(request.POST.get("price", 0)))
        product.rating = min(5, max(0, int(request.POST.get("rating", 5))))
        product.sale = min(100, max(0, int(request.POST.get("sale", 0))))
        product.shopping_cost = max(0, int(request.POST.get("copping_cost", 0) or request.POST.get("shopping_cost", 0)))
        product.min_count = max(1, int(request.POST.get("min_count", 1)))
        product.men_olgan_narx = max(0, int(request.POST.get("men_olgan_narx", 0)))
    except (TypeError, ValueError):
        messages.error(request, "Raqamli maydonlarni to‘g‘ri kiriting.")
        return redirect("adminpanel")

    product.about = request.POST.get("about", "").strip()
    product.unit = request.POST.get("unit", "dona").strip() or "dona"
    product.size = request.POST.get("size", "").strip() or None
    product.color = request.POST.get("color", "").strip() or None
    product.is_active = request.POST.get("is_active") == "on"

    category_name = request.POST.get("category", "").strip()
    if category_name:
        category, _ = Category.objects.get_or_create(
            slug=slugify(category_name) or "cat",
            defaults={"name": category_name},
        )
        product.category = category
    else:
        product.category = None

    product.save()
    messages.success(request, f'"{product.name}" o‘zgarishlari saqlandi.')
    return redirect("adminpanel")


def product_toggle(request, product_id):
    product = get_object_or_404(Product, pk=product_id)
    if request.method == "POST":
        product.is_active = not product.is_active
        product.save(update_fields=["is_active", "updated_at"])
        status = "faollashtirildi" if product.is_active else "o‘chirildi"
        messages.success(request, f'"{product.name}" {status}.')
    return redirect("adminpanel")


def product_delete(request, product_id):
    product = get_object_or_404(Product, pk=product_id)
    if request.method == "POST":
        name = product.name
        product.delete()
        messages.success(request, f'"{name}" bazadan butunlay o‘chirildi.')
    return redirect("adminpanel")


# ─── REVIEWS ────────────────────────────────────────────────────────────────

def product_reviews(request, product_id):
    product = get_object_or_404(Product, pk=product_id)
    reviews = product.reviews.all()
    data = [{
        "id": review.id,
        "name": review.name,
        "rating": review.rating,
        "comment": review.comment,
        "created_at": review.created_at.strftime("%d.%m.%Y %H:%M"),
    } for review in reviews]
    average = reviews.aggregate(avg=Avg("rating"))["avg"]
    return JsonResponse({
        "product": product.name,
        "reviews": data,
        "average": round(float(average), 1) if average is not None else None,
        "count": len(data),
        "likes": product.likes_count,
    })


@require_POST
def product_review_create(request, product_id):
    product = get_object_or_404(Product, pk=product_id)
    name = request.POST.get("name", "").strip()
    comment = request.POST.get("comment", "").strip()
    try:
        rating = int(request.POST.get("rating", 0))
    except (TypeError, ValueError):
        rating = 0

    if not name:
        return JsonResponse({"ok": False, "error": "Ismingizni kiriting."}, status=400)
    if not comment:
        return JsonResponse({"ok": False, "error": "Kommentariya yozing."}, status=400)
    if rating < 1 or rating > 5:
        return JsonResponse({"ok": False, "error": "Yulduzlar 1 dan 5 gacha bo‘lishi kerak."}, status=400)

    review = ProductReview.objects.create(
        product=product,
        name=name,
        rating=rating,
        comment=comment,
    )
    average = product.reviews.aggregate(avg=Avg("rating"))["avg"]
    return JsonResponse({
        "ok": True,
        "message": "Bahoyingiz va kommentariyangiz saqlandi.",
        "review": {
            "id": review.id,
            "name": review.name,
            "rating": review.rating,
            "comment": review.comment,
            "created_at": review.created_at.strftime("%d.%m.%Y %H:%M"),
        },
        "average": round(float(average), 1),
        "count": product.reviews.count(),
    })


# ─── LIKES ──────────────────────────────────────────────────────────────────

@require_POST
def product_like_toggle(request, product_id):
    product = get_object_or_404(Product, pk=product_id)
    sk = _ensure_session(request)
    like = ProductLike.objects.filter(product=product, session_key=sk).first()
    if like:
        like.delete()
        product.likes_count = max(0, product.likes_count - 1)
        product.save(update_fields=["likes_count"])
        liked = False
    else:
        ProductLike.objects.create(
            product=product,
            session_key=sk,
            user=request.user if request.user.is_authenticated else None,
        )
        product.likes_count += 1
        product.save(update_fields=["likes_count"])
        liked = True
    return JsonResponse({
        "ok": True,
        "liked": liked,
        "likes": product.likes_count,
    })


# ─── CART ───────────────────────────────────────────────────────────────────

@require_POST
@login_required_json
def cart_add(request, product_id):
    product = get_object_or_404(Product, pk=product_id, is_active=True)
    sk = _ensure_session(request)
    try:
        qty = max(1, int(request.POST.get("quantity", 1)))
    except (TypeError, ValueError):
        qty = 1
    qty = max(product.min_count, qty)

    item, created = CartItem.objects.get_or_create(
        session_key=sk,
        product=product,
        defaults={
            "quantity": qty,
            "user": request.user,
        },
    )
    if not created:
        item.quantity += qty
        item.save(update_fields=["quantity", "updated_at"])

    return JsonResponse({
        "ok": True,
        "message": f'"{product.name}" savatga qo‘shildi.',
        "cart_count": _cart_count(request),
    })


@require_POST
@login_required_json
def cart_update(request, item_id):
    sk = _ensure_session(request)
    item = get_object_or_404(CartItem, pk=item_id, session_key=sk)
    try:
        qty = int(request.POST.get("quantity", 1))
    except (TypeError, ValueError):
        qty = 1
    if qty < 1:
        item.delete()
    else:
        item.quantity = qty
        item.save(update_fields=["quantity", "updated_at"])
    return JsonResponse({"ok": True, "cart_count": _cart_count(request)})


@require_POST
@login_required_json
def cart_remove(request, item_id):
    sk = _ensure_session(request)
    CartItem.objects.filter(pk=item_id, session_key=sk).delete()
    return JsonResponse({"ok": True, "cart_count": _cart_count(request)})


@login_required(login_url="/login/")
def cart_view(request):
    items = list(_cart_qs(request))
    subtotal = sum(i.subtotal for i in items)
    discount = _get_active_discount(request)
    discount_amount = 0
    if discount and discount.discount_percent > 0:
        discount_amount = int(subtotal * discount.discount_percent / 100)
    total = max(0, subtotal - discount_amount)
    return render(request, "cart.html", {
        "items": items,
        "subtotal": subtotal,
        "discount": discount,
        "discount_amount": discount_amount,
        "total": total,
        "cart_count": _cart_count(request),
    })


# ─── ORDERS ─────────────────────────────────────────────────────────────────

@require_POST
@login_required(login_url="/login/")
def order_create(request):
    items = list(_cart_qs(request))
    if not items:
        messages.error(request, "Savat bo‘sh.")
        return redirect("cart")

    full_name = request.POST.get("full_name", "").strip()
    phone = request.POST.get("phone", "").strip()
    address = request.POST.get("address", "").strip()
    note = request.POST.get("note", "").strip()

    if not full_name or not phone or not address:
        messages.error(request, "Ism, telefon va manzil majburiy.")
        return redirect("cart")

    subtotal = sum(i.subtotal for i in items)
    discount = _get_active_discount(request)
    discount_pct = discount.discount_percent if discount else 0
    discount_amount = int(subtotal * discount_pct / 100) if discount_pct else 0
    total = max(0, subtotal - discount_amount)

    order = Order.objects.create(
        session_key=_ensure_session(request),
        user=request.user,
        full_name=full_name,
        phone=phone,
        address=address,
        note=note,
        total=total,
        discount_percent=discount_pct,
        status="pending",
    )
    for item in items:
        OrderItem.objects.create(
            order=order,
            product=item.product,
            product_name=item.product.name,
            price=item.product.final_price,
            quantity=item.quantity,
        )
        item.delete()

    if discount:
        discount.is_used = True
        discount.save(update_fields=["is_used"])

    messages.success(request, f"Buyurtma #{order.pk} qabul qilindi! Tez orada bog‘lanamiz.")
    return redirect("order_success", order_id=order.pk)


def order_success(request, order_id):
    order = get_object_or_404(Order, pk=order_id)
    return render(request, "order_success.html", {
        "order": order,
        "cart_count": _cart_count(request),
    })


# ─── GAME (chegirma o'yini) ─────────────────────────────────────────────────

@require_POST
@login_required_json
def game_play(request):
    """Oddiy '3 ta eshik' o'yini — to'g'ri eshikni topsa chegirma. Faqat login qilganlar."""
    sk = _ensure_session(request)
    try:
        choice = int(request.POST.get("choice", 0))
    except (TypeError, ValueError):
        choice = 0

    if choice not in (1, 2, 3):
        return JsonResponse({"ok": False, "error": "1, 2 yoki 3 ni tanlang."}, status=400)

    # Kuniga 5 marta urinish
    today_start = timezone.now().replace(hour=0, minute=0, second=0, microsecond=0)
    plays_today = GameDiscount.objects.filter(
        session_key=sk, created_at__gte=today_start
    ).count()
    if plays_today >= 5:
        return JsonResponse({
            "ok": False,
            "error": "Bugun 5 marta o‘ynadingiz. Ertaga qayta urinib ko‘ring!",
        })

    winning = random.randint(1, 3)
    won = choice == winning

    if won:
        pct = random.choice([5, 10, 10, 15, 20])
        code = "WIN" + "".join(random.choices(string.ascii_uppercase + string.digits, k=6))
        disc = GameDiscount.objects.create(
            session_key=sk,
            user=request.user,
            discount_percent=pct,
            code=code,
            expires_at=timezone.now() + timedelta(hours=24),
        )
        return JsonResponse({
            "ok": True,
            "won": True,
            "winning_door": winning,
            "discount_percent": pct,
            "code": code,
            "message": f"Tabriklaymiz! Siz {pct}% chegirma yutdingiz. Kod: {code}",
        })
    else:
        # Yutmagan urinishni ham yozib qo'yamiz (limit uchun)
        GameDiscount.objects.create(
            session_key=sk,
            user=request.user,
            discount_percent=0,
            code="LOSE" + "".join(random.choices(string.ascii_uppercase + string.digits, k=6)),
            is_used=True,
        )
        return JsonResponse({
            "ok": True,
            "won": False,
            "winning_door": winning,
            "message": f"Afsus! To‘g‘ri eshik {winning}-chi edi. Yana urinib ko‘ring!",
        })


@require_GET
def game_status(request):
    disc = _get_active_discount(request)
    if disc and disc.discount_percent > 0:
        return JsonResponse({
            "has_discount": True,
            "percent": disc.discount_percent,
            "code": disc.code,
        })
    return JsonResponse({"has_discount": False})


# ─── AUTH ───────────────────────────────────────────────────────────────────

def login_page(request):
    if request.user.is_authenticated:
        return redirect("home")
    if request.method == "POST":
        username = request.POST.get("username", "").strip()
        password = request.POST.get("password", "")
        user = authenticate(request, username=username, password=password)
        if user is not None:
            login(request, user)
            messages.success(request, f"Xush kelibsiz, {user.get_full_name() or user.username}!")
            next_url = request.GET.get("next") or request.POST.get("next") or "/"
            return redirect(next_url)
        messages.error(request, "Login yoki parol noto‘g‘ri.")
    return render(request, "login.html")


def register_page(request):
    if request.user.is_authenticated:
        return redirect("home")
    if request.method == "POST":
        username = request.POST.get("username", "").strip()
        email = request.POST.get("email", "").strip()
        password = request.POST.get("password", "")
        password2 = request.POST.get("password2", "") or request.POST.get("password_confirm", "")

        if not username or not password:
            messages.error(request, "Login va parolni kiriting.")
            return render(request, "register.html")
        if len(password) < 6:
            messages.error(request, "Parol kamida 6 ta belgidan iborat bo‘lishi kerak.")
            return render(request, "register.html")
        if password2 and password != password2:
            messages.error(request, "Parollar mos kelmadi.")
            return render(request, "register.html")
        if User.objects.filter(username__iexact=username).exists():
            messages.error(request, "Bu login allaqachon mavjud.")
            return render(request, "register.html")
        if email and User.objects.filter(email__iexact=email).exists():
            messages.error(request, "Bu email allaqachon ro‘yxatdan o‘tgan.")
            return render(request, "register.html")

        user = User.objects.create_user(username=username, email=email or "", password=password)
        login(request, user, backend="django.contrib.auth.backends.ModelBackend")
        messages.success(request, "Ro‘yxatdan muvaffaqiyatli o‘tdingiz!")
        return redirect("home")
    return render(request, "register.html")


def logout_page(request):
    logout(request)
    messages.info(request, "Tizimdan chiqdingiz.")
    return redirect("home")


# ─── EXTRA PAGES ────────────────────────────────────────────────────────────

def about_page(request):
    return render(request, "about.html", {"cart_count": _cart_count(request)})


def contact_page(request):
    if request.method == "POST":
        messages.success(request, "Xabaringiz qabul qilindi! Tez orada javob beramiz.")
        return redirect("contact")
    return render(request, "contact.html", {"cart_count": _cart_count(request)})


def menu_page(request):
    cat_slug = request.GET.get("cat", "")
    q = request.GET.get("q", "").strip()
    products = (
        Product.objects.filter(is_active=True)
        .select_related("category")
        .prefetch_related("images", "reviews")
        .annotate(review_average=Avg("reviews__rating"), review_count=Count("reviews"))
    )
    if cat_slug:
        products = products.filter(category__slug=cat_slug)
    if q:
        products = products.filter(Q(name__icontains=q) | Q(about__icontains=q))
    categories = Category.objects.annotate(
        product_count=Count("products", filter=Q(products__is_active=True))
    ).order_by("name")
    sk = _ensure_session(request)
    liked_ids = set(
        ProductLike.objects.filter(session_key=sk).values_list("product_id", flat=True)
    )
    return render(request, "menu.html", {
        "products": products,
        "categories": categories,
        "current_cat": cat_slug,
        "q": q,
        "cart_count": _cart_count(request),
        "liked_ids": liked_ids,
        "active_discount": _get_active_discount(request),
    })




# TELEGRAM_BOT_TOKEN = "8896432673:AAGuDUQQx5fhOXEkWMs_ufujwws0g4KTJ0c"
# CHAT_ID = 7500183115

# def send_message(chat_id, message):
#     url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"

#     params = {
#         "chat_id": chat_id,
#         "text": message
#     }

#     response = requests.get(url, params=params, timeout=10)

#     print(response.status_code)
#     print(response.json())

#     response.raise_for_status()

# def bot(request):
#     if request.method == "POST":
#         name = request.POST.get("name")
#         phone = request.POST.get("phone")
#         message = request.POST.get("message")

#         text = f"""🧑 Foydalanuvchi: {name}
# 📞 Raqami: {phone}
# 📕 Xabar: {message}"""

#         send_message(CHAT_ID, text)

#     return render(request, "contact.html")



TELEGRAM_BOT_TOKEN = "8896432673:AAGuDUQQx5fhOXEkWMs_ufujwws0g4KTJ0c"
CHAT_ID = "7500183115"

def bot(request):
    print("BOT VIEW ISHLADI!")
    print("METHOD:", request.method)

    if request.method == "POST":
        print("POST ISHLADI!")

        name = request.POST.get("name")
        phone = request.POST.get("phone")
        message = request.POST.get("message")

        print("DATA:", name, phone, message)

        text = f"""🧑 Foydalanuvchi: {name}
📞 Raqami: {phone}
📕 Xabar: {message}"""

        url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"

        try:
            response = requests.post(
                url,
                data={"chat_id": CHAT_ID, "text": text},
                timeout=10
            )
            print("TELEGRAM STATUS:", response.status_code)
            print("TELEGRAM JAVOBI:", response.text)
        except requests.RequestException as e:
            print("TELEGRAM XATOSI:", e)

    return render(request, "contact.html")