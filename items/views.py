from django.shortcuts import render, redirect
from django.db.models import Q
import json

from lostfound import settings
from .models import Item, Profile, Claim
from django.contrib.auth.decorators import login_required
import random
from django.core.mail import send_mail
from .forms import RegisterForm
from django.contrib.auth.models import User
from django.contrib.auth import login
from django.shortcuts import get_object_or_404


def home(request):
    query = request.GET.get('q')
    item_type = request.GET.get('type')

    items = Item.objects.filter(status="active").order_by('-created_at')

    if query:
        items = items.filter(title__icontains=query)

    if item_type:
        items = items.filter(item_type=item_type)

    items_map_data = [
        {
            'id': item.id,
            'title': item.title,
            'description': item.description[:100] + ('...' if len(item.description) > 100 else ''),
            'category': item.category,
            'location': item.location,
            'date': item.date.strftime('%d %b %Y') if item.date else '',
            'item_type': item.item_type,
            'status': item.status,
            'image_url': item.image.url if item.image else '',
            'latitude': item.latitude,
            'longitude': item.longitude,
        }
        for item in items if item.latitude is not None and item.longitude is not None
    ]

    return render(request, 'home.html', {
        'items': items,
        'items_json': json.dumps(items_map_data)
    })

def register(request):
    if request.method == 'POST':
        form = RegisterForm(request.POST)

        if form.is_valid():
            otp = random.randint(1000, 9999)

            request.session['otp'] = otp
            request.session['user_data'] = form.cleaned_data

            send_mail(
                'Your OTP Code',
                f'Your OTP for Lost&Found is {otp}',
                'your_email@gmail.com',
                [form.cleaned_data['email']],
                fail_silently=False,
            )

            return redirect('verify_otp')

    else:
        form = RegisterForm()

    return render(request, 'register.html', {'form': form})


@login_required         
def add_item(request):
    if request.method == 'POST':
        title = request.POST.get('title', '')
        description = request.POST.get('description', '')
        category = request.POST.get('category', '')
        location = request.POST.get('location', '')
        date = request.POST.get('date', '')
        image = request.FILES.get('image')
        item_type = request.POST.get('item_type', 'lost')
        
        lat_val = request.POST.get('latitude')
        lng_val = request.POST.get('longitude')
        try:
            latitude = float(lat_val) if lat_val and lat_val.strip() else None
        except ValueError:
            latitude = None
            
        try:
            longitude = float(lng_val) if lng_val and lng_val.strip() else None
        except ValueError:
            longitude = None

        item = Item.objects.create(
            user=request.user,
            title=title,
            description=description,
            category=category,
            location=location,
            date=date,
            image=image,
            item_type=item_type,
            latitude=latitude,
            longitude=longitude
        )
        
        if item.item_type == 'lost':
            matches = find_matches(item)

            if matches.exists():
                return render(request, 'match_results.html', {
                    'matches': matches,
                    'item': item
                })
        
        return redirect('home')

    return render(request, 'add_item.html')

def item_detail(request, id):
    item = Item.objects.get(id=id)
    return render(request, 'item_detail.html', {'item': item})



@login_required
def my_posts(request):
    items = Item.objects.filter(user=request.user).order_by('-created_at')
    return render(request, 'my_posts.html', {'items': items})


@login_required
def edit_item(request, id):
    item = get_object_or_404(Item, id=id, user=request.user)

    if request.method == 'POST':
        item.title = request.POST.get('title', item.title)
        item.description = request.POST.get('description', item.description)
        item.category = request.POST.get('category', item.category)
        item.location = request.POST.get('location', item.location)
        item.date = request.POST.get('date', item.date)
        item.item_type = request.POST.get('item_type', item.item_type)

        lat_val = request.POST.get('latitude')
        lng_val = request.POST.get('longitude')
        try:
            item.latitude = float(lat_val) if lat_val and lat_val.strip() else None
        except ValueError:
            item.latitude = None
            
        try:
            item.longitude = float(lng_val) if lng_val and lng_val.strip() else None
        except ValueError:
            item.longitude = None

        if request.FILES.get('image'):
            item.image = request.FILES['image']

        item.save()
        return redirect('my_posts')

    return render(request, 'edit_item.html', {'item': item})


@login_required
def delete_item(request, id):
    item = get_object_or_404(Item, id=id, user=request.user)

    item.delete()
    return redirect('my_posts')

def verify_otp(request):
    if request.method == 'POST':
        user_otp = request.POST['otp']
        session_otp = request.session.get('otp')

        if str(user_otp) == str(session_otp):
            data = request.session.get('user_data')

            user = User.objects.create_user(
                username=data['username'],
                email=data['email'],
                password=data['password']
            )

            # phone save
            Profile.objects.create(
                user=user,
                phone=data['phone']
            )

            login(request, user)
            return redirect('home')

    return render(request, 'verify_otp.html')

@login_required
def claim_item(request, id):
    item = Item.objects.get(id=id)

    if item.user == request.user:
        return redirect('home')

    # ❌ Lost item pe claim allow nahi
    if item.item_type == 'lost':
        return redirect('home')

    if request.method == 'POST':
        message = request.POST['message']

        Claim.objects.create(
            item=item,
            user=request.user,
            message=message
        )

        msg = f"""
        Hello {item.user.username},

        You got new claim request for item "{item.title}" from "{request.user.username}".

        Please check the website for further details.

        Thanks,
        Lost & Found Team
        """
        send_mail(
            "Claim Request",
            msg,
            settings.DEFAULT_FROM_EMAIL,
            [item.user.email],
            fail_silently=True,
        )

        return redirect('home')

    return render(request, 'claim_item.html', {'item': item})

@login_required
def view_claims(request):
    items = Item.objects.filter(user=request.user)
    claims = Claim.objects.filter(item__in=items)

    return render(request, 'view_claims.html', {'claims': claims})


@login_required
def approve_claim(request, id):
    claim = get_object_or_404(Claim, id=id)

    # security: sirf owner hi approve kare
    if claim.item.user != request.user:
        return redirect('home')

    claim.status = 'resolved'
    claim.is_seen = False
    claim.save()

    claim.item.status = 'resolved'
    claim.item.save()

    message = f"""
    Hello {claim.user.username},

    Your claim request for item "{claim.item.title}" has been approved.

    Please contact the owner for further details.

    Thanks,
    Lost & Found Team
    """

    send_mail(
        "Claim Approved",
        message,
        settings.DEFAULT_FROM_EMAIL,
        [claim.user.email],
        fail_silently=True,
    )

    return redirect('view_claims')


@login_required
def reject_claim(request, id):
    claim = get_object_or_404(Claim, id=id)

    if claim.item.user != request.user:
        return redirect('home')

    claim.status = 'rejected'
    claim.is_seen = False
    claim.save()

    message = f"""
    Hello {claim.user.username},

    Your claim request for item "{claim.item.title}" has been rejected.

    Please contact the owner for further details.

    Thanks,
    Lost & Found Team
    """
    send_mail(
        "Claim Rejected",
        message,
        settings.DEFAULT_FROM_EMAIL,
        [claim.user.email],
        fail_silently=True,
    )

    return redirect('view_claims')

@login_required
def my_claims(request):
    claims = Claim.objects.filter(user=request.user).order_by('-created_at')

    # 👇 sabko seen mark kar do
    claims.update(is_seen=True)

    return render(request, 'my_claims.html', {'claims': claims})



def find_matches(item):
    words = item.title.lower().split()

    query = Q()
    for word in words:
        query |= Q(title__icontains=word)

    matches = Item.objects.filter(
        item_type='found',
        category=item.category
    ).filter(query)

    # optional: location filter
    matches = matches.filter(location__icontains=item.location)

    return matches[:5]  # top 5 matches