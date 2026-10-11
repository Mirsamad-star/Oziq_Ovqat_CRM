from django.contrib import admin
from .models import (
    CartItem, Category, Color, GameDiscount, Order, OrderItem,
    Product, ProductImage, ProductLike, ProductReview, Size, Unit,
)


@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = ("id", "name", "price", "category", "rating", "sale", "likes_count", "is_active", "created_at")
    list_filter = ("is_active", "category")
    search_fields = ("name", "about")


@admin.register(ProductReview)
class ProductReviewAdmin(admin.ModelAdmin):
    list_display = ("id", "product", "name", "rating", "created_at")
    list_filter = ("rating",)
    search_fields = ("product__name", "name", "comment")


@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    list_display = ("id", "full_name", "phone", "total", "discount_percent", "status", "created_at")
    list_filter = ("status",)
    search_fields = ("full_name", "phone")


admin.site.register(ProductImage)
admin.site.register(Category)
admin.site.register(Unit)
admin.site.register(Size)
admin.site.register(Color)
admin.site.register(ProductLike)
admin.site.register(CartItem)
admin.site.register(OrderItem)
admin.site.register(GameDiscount)
