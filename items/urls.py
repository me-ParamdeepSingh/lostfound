from django.urls import path
from . import views

urlpatterns = [
    path('', views.home, name='home'),
    path('add/', views.add_item, name='add_item'),
    path('item/<int:id>/', views.item_detail, name='item_detail'),
    path('my-posts/', views.my_posts, name='my_posts'),
    path('edit/<int:id>/', views.edit_item, name='edit_item'),
    path('delete/<int:id>/', views.delete_item, name='delete_item'),
    path('register/', views.register, name='register'),
    path('verify-otp/', views.verify_otp, name='verify_otp'),
    path('claim/<int:id>/', views.claim_item, name='claim_item'),
    path('claims/', views.view_claims, name='view_claims'),
    path('approve-claim/<int:id>/', views.approve_claim, name='approve_claim'),
    path('reject-claim/<int:id>/', views.reject_claim, name='reject_claim'),
    path('my-claims/', views.my_claims, name='my_claims'),
]