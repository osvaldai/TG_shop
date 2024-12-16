from django.contrib import admin
from .models import Users, PurchaseHistory, PromoCode, UsedPromo, MainCategory, SubCategory, Product


# Настройка отображения для модели Users
@admin.register(Users)
class UsersAdmin(admin.ModelAdmin):
    list_display = ['user_id', 'count_deposits', 'count_orders', 'balance']


# Настройка отображения для модели PurchaseHistory
@admin.register(PurchaseHistory)
class PurchaseHistoryAdmin(admin.ModelAdmin):
    list_display = ['user', 'product', 'price']


# Настройка отображения для модели PromoCode
@admin.register(PromoCode)
class PromoCodeAdmin(admin.ModelAdmin):
    list_display = ['code', 'discount', 'expiration_date']


# Настройка отображения для модели UsedPromo
@admin.register(UsedPromo)
class UsedPromoAdmin(admin.ModelAdmin):
    list_display = ['user', 'promo', 'used']


# Настройка отображения для модели MainCategory
@admin.register(MainCategory)
class MainCategoryAdmin(admin.ModelAdmin):
    list_display = ['name']


# Настройка отображения для модели SubCategory
@admin.register(SubCategory)
class SubCategoryAdmin(admin.ModelAdmin):
    list_display = ['name', 'main_category']


# Настройка отображения для модели Product
@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = ['name', 'main_category', 'sub_category', 'price', 'description']
