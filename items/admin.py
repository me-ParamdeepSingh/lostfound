from django.contrib import admin
from .models import Item,Profile, Claim

# Register your models here.

admin.site.register(Item)
admin.site.register(Profile)
admin.site.register(Claim)