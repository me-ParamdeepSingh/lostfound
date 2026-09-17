from django.db import models
from django.contrib.auth.models import User

# Create your models here.

class Item(models.Model):
    ITEM_TYPE = (
        ('lost', 'Lost'),
        ('found', 'Found'),
    )

    user = models.ForeignKey(User, on_delete=models.CASCADE)
    title = models.CharField(max_length=200)
    description = models.TextField()
    category = models.CharField(max_length=100)
    location = models.CharField(max_length=200)
    date = models.DateField()
    image = models.ImageField(upload_to='items/')
    item_type = models.CharField(max_length=10, choices=ITEM_TYPE)
    status = models.CharField(max_length=10, default='active')
    latitude = models.FloatField(null=True, blank=True)
    longitude = models.FloatField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.title
    

class Profile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    phone = models.CharField(max_length=15)

    def __str__(self):
        return self.user.username
    

class Claim(models.Model):
    item = models.ForeignKey(Item, on_delete=models.CASCADE)
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    message = models.TextField()  # proof ya message
    status = models.CharField(max_length=10, default='active')
    is_seen = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.user.username} -> {self.item.title}"