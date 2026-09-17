from django import forms
from django.contrib.auth.models import User
from .models import Profile

class RegisterForm(forms.Form):
    username = forms.CharField()
    email = forms.EmailField()
    phone = forms.CharField()
    password = forms.CharField(widget=forms.PasswordInput)

    # Email validation
    def clean_email(self):
        email = self.cleaned_data.get('email')
        if User.objects.filter(email=email).exists():
            raise forms.ValidationError("Email already exists")
        return email

    # Phone validation
    def clean_phone(self):
        phone = self.cleaned_data.get('phone')

        if not phone.isdigit() or len(phone) != 10:
            raise forms.ValidationError("Enter valid 10-digit phone number")

        if Profile.objects.filter(phone=phone).exists():
            raise forms.ValidationError("Phone number already exists")

        return phone