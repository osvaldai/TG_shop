from django.db import models


# Ваша существующая модель Users
class Users(models.Model):
    user_id = models.CharField(max_length=25)
    count_deposits = models.PositiveIntegerField(default=0)
    count_orders = models.PositiveIntegerField(default=0)
    balance = models.PositiveIntegerField(default=0)


# Ваша существующая модель PurchaseHistory
class PurchaseHistory(models.Model):
    user = models.ForeignKey(Users, on_delete=models.CASCADE)
    product = models.CharField(max_length=255)
    price = models.PositiveIntegerField(default=0)


# Модель для промокода
class PromoCode(models.Model):
    code = models.CharField(max_length=50, unique=True)
    discount = models.FloatField()
    expiration_date = models.DateTimeField(null=True, blank=True)
    # users = models.ManyToManyField(Users, through='UsedPromo', related_name='promo_codes')


# Модель для отслеживания использованных промокодов
class UsedPromo(models.Model):
    user = models.ForeignKey(Users, on_delete=models.CASCADE)
    promo = models.ForeignKey(PromoCode, on_delete=models.CASCADE)
    used = models.BooleanField(default=True)


class MainCategory(models.Model):
    name = models.CharField(max_length=100, unique=True)

    def __str__(self):
        return self.name


class SubCategory(models.Model):
    name = models.CharField(max_length=100)
    main_category = models.ForeignKey(MainCategory, related_name='subcategories', on_delete=models.CASCADE)

    def __str__(self):
        return f"{self.main_category.name} - {self.name}"


class Product(models.Model):
    main_category = models.ForeignKey(MainCategory, related_name='products', on_delete=models.CASCADE)
    sub_category = models.ForeignKey(SubCategory, related_name='products', on_delete=models.CASCADE, null=True,
                                     blank=True)
    name = models.CharField(max_length=255)
    price = models.DecimalField(max_digits=10, decimal_places=2)
    description = models.TextField()

    def __str__(self):
        return self.name
