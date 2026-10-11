from django.contrib import admin
from django.urls import include, path
from django.conf import settings
from django.conf.urls.static import static

from apps.views import (
    about_page,
    admin_page,
    cart_add,
    cart_remove,
    cart_update,
    cart_view,
    contact_page,
    game_play,
    game_status,
    home_page,
    login_page,
    logout_page,
    menu_page,
    order_create,
    order_success,
    product_delete,
    product_edit,
    product_like_toggle,
    product_review_create,
    product_reviews,
    product_toggle,
    register_page,
    bot,
)

urlpatterns = [
    path("admin/", admin.site.urls),
    path("", home_page, name="home"),
    path("menu/", menu_page, name="menu"),
    path("about/", about_page, name="about"),
    path("contact/", contact_page, name="contact"),
    path("cart/", cart_view, name="cart"),
    path("cart/add/<int:product_id>/", cart_add, name="cart_add"),
    path("cart/update/<int:item_id>/", cart_update, name="cart_update"),
    path("cart/remove/<int:item_id>/", cart_remove, name="cart_remove"),
    path("order/create/", order_create, name="order_create"),
    path("order/success/<int:order_id>/", order_success, name="order_success"),
    path("game/play/", game_play, name="game_play"),
    path("game/status/", game_status, name="game_status"),
    path("adminpanel/", admin_page, name="adminpanel"),
    path("adminpanel/products/<int:product_id>/edit/", product_edit, name="product_edit"),
    path("adminpanel/products/<int:product_id>/toggle/", product_toggle, name="product_toggle"),
    path("adminpanel/products/<int:product_id>/delete/", product_delete, name="product_delete"),
    path("product/<int:product_id>/reviews/", product_reviews, name="product_reviews"),
    path("product/<int:product_id>/reviews/add/", product_review_create, name="product_review_create"),
    path("product/<int:product_id>/like/", product_like_toggle, name="product_like"),
    path("login/", login_page, name="login"),
    path("register/", register_page, name="register"),
    path("logout/", logout_page, name="logout"),
    path("accounts/", include("allauth.urls")),
    path("bot/", bot, name='bot')
]

urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
