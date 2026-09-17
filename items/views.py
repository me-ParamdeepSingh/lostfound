from django.shortcuts import render, redirect, get_object_or_404
from django.http import JsonResponse
from django.db.models import Q
from django.utils import timezone
import json
import uuid
import qrcode
import io
import base64
from rapidfuzz import fuzz

from lostfound import settings
from .models import Item, Profile, Claim, Conversation, ChatMessage, SmartTag
from django.contrib.auth.decorators import login_required
import random
from django.core.mail import send_mail
from .forms import RegisterForm
from django.contrib.auth.models import User
from django.contrib.auth import login


def mask_phone_number(phone):
    if not phone:
        return ''
    phone = str(phone).strip()
    if len(phone) >= 10:
        return phone[:2] + '*' * (len(phone) - 4) + phone[-2:]
    return phone[:1] + '*' * (len(phone) - 2) + phone[-1:]


def mask_email_address(email):
    if not email or '@' not in email:
        return '***@hidden.com'
    parts = email.split('@', 1)
    username = parts[0]
    domain = parts[1]
    if len(username) <= 2:
        masked_user = username[0] + '***'
    else:
        masked_user = username[0] + '*' * (len(username) - 2) + username[-1]
    return f"{masked_user}@{domain}"


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
        
        # AI Semantic Match Detection for newly posted item
        ai_matches = find_ai_matches(item, limit=6)
        if ai_matches:
            return render(request, 'match_results.html', {
                'matches': ai_matches,
                'item': item
            })
        
        return redirect('home')

    return render(request, 'add_item.html')

def item_detail(request, id):
    item = get_object_or_404(Item, id=id)

    raw_phone = ''
    if hasattr(item.user, 'profile') and item.user.profile.phone:
        raw_phone = item.user.profile.phone
    raw_email = item.user.email

    can_view_contact = False
    existing_chat_id = None

    if request.user.is_authenticated:
        if request.user == item.user:
            can_view_contact = True
        else:
            # Check if this user was granted permission in conversation
            chat = Conversation.objects.filter(item=item, starter=request.user).first()
            if chat:
                existing_chat_id = chat.id
                if chat.contact_shared:
                    can_view_contact = True

            # Also check if claim was approved
            if not can_view_contact and Claim.objects.filter(item=item, user=request.user, status='resolved').exists():
                can_view_contact = True

    masked_phone = mask_phone_number(raw_phone)
    masked_email = mask_email_address(raw_email)

    # Get AI Potential Matches for this item (opposite type)
    ai_matches = find_ai_matches(item, limit=3)

    return render(request, 'item_detail.html', {
        'item': item,
        'can_view_contact': can_view_contact,
        'raw_phone': raw_phone,
        'raw_email': raw_email,
        'masked_phone': masked_phone,
        'masked_email': masked_email,
        'existing_chat_id': existing_chat_id,
        'ai_matches': ai_matches,
    })


@login_required
def inbox(request):
    conversations = Conversation.objects.filter(
        Q(starter=request.user) | Q(receiver=request.user)
    ).select_related('item', 'starter', 'receiver').prefetch_related('messages')

    chat_list = []
    for conv in conversations:
        other_user = conv.receiver if conv.starter == request.user else conv.starter
        last_msg = conv.messages.last()
        unread_count = conv.messages.filter(is_read=False).exclude(sender=request.user).count()
        chat_list.append({
            'conversation': conv,
            'other_user': other_user,
            'last_message': last_msg,
            'unread_count': unread_count,
            'is_owner': (conv.receiver == request.user),
        })

    return render(request, 'inbox.html', {'chat_list': chat_list})


@login_required
def start_or_open_chat(request, item_id):
    item = get_object_or_404(Item, id=item_id)
    if item.user == request.user:
        first_chat = Conversation.objects.filter(item=item).first()
        if first_chat:
            return redirect('chat_room', chat_id=first_chat.id)
        return redirect('inbox')

    conversation, created = Conversation.objects.get_or_create(
        item=item,
        starter=request.user,
        defaults={'receiver': item.user}
    )
    return redirect('chat_room', chat_id=conversation.id)


@login_required
def chat_room(request, chat_id):
    conversation = get_object_or_404(Conversation, id=chat_id)

    if request.user != conversation.starter and request.user != conversation.receiver:
        return redirect('inbox')

    conversation.messages.filter(is_read=False).exclude(sender=request.user).update(is_read=True)

    other_user = conversation.receiver if conversation.starter == request.user else conversation.starter
    is_owner = (request.user == conversation.receiver)

    owner_phone = ''
    if hasattr(conversation.receiver, 'profile') and conversation.receiver.profile.phone:
        owner_phone = conversation.receiver.profile.phone
    owner_email = conversation.receiver.email

    starter_phone = ''
    if hasattr(conversation.starter, 'profile') and conversation.starter.profile.phone:
        starter_phone = conversation.starter.profile.phone
    starter_email = conversation.starter.email

    target_phone = starter_phone if is_owner else owner_phone
    target_email = starter_email if is_owner else owner_email

    messages = conversation.messages.all()

    return render(request, 'chat_room.html', {
        'conversation': conversation,
        'other_user': other_user,
        'is_owner': is_owner,
        'messages': messages,
        'owner_phone': owner_phone,
        'owner_email': owner_email,
        'starter_phone': starter_phone,
        'starter_email': starter_email,
        'target_phone': target_phone,
        'target_email': target_email,
    })


@login_required
def toggle_share_contact(request, chat_id):
    conversation = get_object_or_404(Conversation, id=chat_id)
    if request.user != conversation.receiver:
        return redirect('chat_room', chat_id=chat_id)

    conversation.contact_shared = not conversation.contact_shared
    conversation.save()

    if conversation.contact_shared:
        announcement = f"🔓 {request.user.username} (Item Owner) has granted permission and shared their direct contact details with you!"
    else:
        announcement = f"🔒 {request.user.username} has revoked contact details access."

    ChatMessage.objects.create(
        conversation=conversation,
        sender=request.user,
        text=announcement
    )

    return redirect('chat_room', chat_id=chat_id)


@login_required
def api_send_message(request, chat_id):
    if request.method != 'POST':
        return JsonResponse({'status': 'error', 'message': 'Invalid request method'}, status=400)

    conversation = get_object_or_404(Conversation, id=chat_id)
    if request.user != conversation.starter and request.user != conversation.receiver:
        return JsonResponse({'status': 'error', 'message': 'Unauthorized'}, status=403)

    text = request.POST.get('text', '').strip()
    if not text:
        return JsonResponse({'status': 'error', 'message': 'Empty message'}, status=400)

    msg = ChatMessage.objects.create(
        conversation=conversation,
        sender=request.user,
        text=text
    )
    conversation.save()

    return JsonResponse({
        'status': 'success',
        'message_id': msg.id,
        'text': msg.text,
        'sender': msg.sender.username,
        'created_at': msg.created_at.strftime('%I:%M %p')
    })


@login_required
def api_get_messages(request, chat_id):
    conversation = get_object_or_404(Conversation, id=chat_id)
    if request.user != conversation.starter and request.user != conversation.receiver:
        return JsonResponse({'status': 'error', 'message': 'Unauthorized'}, status=403)

    conversation.messages.filter(is_read=False).exclude(sender=request.user).update(is_read=True)

    messages_data = [
        {
            'id': m.id,
            'text': m.text,
            'sender': m.sender.username,
            'is_me': (m.sender == request.user),
            'created_at': m.created_at.strftime('%I:%M %p')
        }
        for m in conversation.messages.all()
    ]

    return JsonResponse({
        'status': 'success',
        'contact_shared': conversation.contact_shared,
        'messages': messages_data
    })



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



def find_ai_matches(item, limit=6):
    """
    Intelligent AI matching engine:
    - Matches opposite type: Lost <-> Found
    - Compares text semantics (Title + Description) using Token Set Ratio & Partial Ratio
    - Gives strong category weight and location proximity bonus
    - Returns list of matched items sorted by match_score (0 - 100%)
    """
    target_type = 'found' if item.item_type == 'lost' else 'lost'
    candidates = Item.objects.filter(item_type=target_type, status='active').exclude(id=item.id)

    matched_results = []
    item_full_text = f"{item.title} {item.description}".lower()

    for candidate in candidates:
        cand_full_text = f"{candidate.title} {candidate.description}".lower()

        # Text similarity using RapidFuzz
        title_sim = fuzz.token_set_ratio(item.title.lower(), candidate.title.lower())
        desc_sim = fuzz.token_set_ratio(item_full_text, cand_full_text)
        text_score = (title_sim * 0.6) + (desc_sim * 0.4)

        # Category bonus (up to 20 pts)
        category_bonus = 20 if item.category.lower() == candidate.category.lower() else 0

        # Location similarity bonus (up to 15 pts)
        loc_sim = fuzz.partial_ratio(item.location.lower(), candidate.location.lower()) if (item.location and candidate.location) else 0
        location_bonus = (loc_sim / 100.0) * 15

        final_score = min(100, int((text_score * 0.65) + category_bonus + location_bonus))

        # Only consider meaningful matches (>= 45% score)
        if final_score >= 45:
            candidate.match_score = final_score
            matched_results.append(candidate)

    matched_results.sort(key=lambda x: x.match_score, reverse=True)
    return matched_results[:limit]


def generate_qr_base64(data_url):
    qr = qrcode.QRCode(
        version=1,
        error_correction=qrcode.constants.ERROR_CORRECT_M,
        box_size=10,
        border=2,
    )
    qr.add_data(data_url)
    qr.make(fit=True)
    img = qr.make_image(fill_color="#0f172a", back_color="#ffffff")
    buffer = io.BytesIO()
    img.save(buffer, format="PNG")
    return base64.b64encode(buffer.getvalue()).decode('utf-8')


@login_required
def my_smart_tags(request):
    tags = SmartTag.objects.filter(user=request.user)
    tag_list = []
    for tag in tags:
        scan_url = request.build_absolute_uri(f"/scan/{tag.tag_code}/")
        qr_b64 = generate_qr_base64(scan_url)
        tag_list.append({
            'tag': tag,
            'scan_url': scan_url,
            'qr_b64': qr_b64,
        })
    return render(request, 'smart_tags.html', {'tag_list': tag_list})


@login_required
def create_smart_tag(request):
    if request.method == 'POST':
        item_name = request.POST.get('item_name', '').strip()
        category = request.POST.get('category', '').strip()
        reward_note = request.POST.get('reward_note', '').strip()
        if item_name and category:
            SmartTag.objects.create(
                user=request.user,
                item_name=item_name,
                category=category,
                reward_note=reward_note
            )
    return redirect('my_smart_tags')


@login_required
def delete_smart_tag(request, tag_code):
    tag = get_object_or_404(SmartTag, tag_code=tag_code, user=request.user)
    tag.delete()
    return redirect('my_smart_tags')


@login_required
def print_smart_tag(request, tag_code):
    tag = get_object_or_404(SmartTag, tag_code=tag_code, user=request.user)
    scan_url = request.build_absolute_uri(f"/scan/{tag.tag_code}/")
    qr_b64 = generate_qr_base64(scan_url)
    return render(request, 'print_tag_card.html', {
        'tag': tag,
        'scan_url': scan_url,
        'qr_b64': qr_b64
    })


def scan_smart_tag(request, tag_code):
    tag = get_object_or_404(SmartTag, tag_code=tag_code)

    # Increment scan count on GET
    if request.method == 'GET':
        tag.scans_count += 1
        tag.last_scanned_at = timezone.now()
        tag.save()

    success_message = None

    if request.method == 'POST':
        finder_name = request.POST.get('finder_name', 'A Good Samaritan').strip()
        finder_phone = request.POST.get('finder_phone', '').strip()
        message_note = request.POST.get('message_note', '').strip()
        location_text = request.POST.get('location_text', '').strip()
        latitude = request.POST.get('latitude', '').strip()
        longitude = request.POST.get('longitude', '').strip()

        maps_link = ""
        if latitude and longitude:
            maps_link = f"https://www.google.com/maps/search/?api=1&query={latitude},{longitude}"

        email_content = f"""
        🚨 ALERT: Someone scanned your Smart QR Tag for '{tag.item_name}'!

        Finder Details:
        - Name: {finder_name}
        - Phone: {finder_phone or 'Not provided'}

        Message:
        "{message_note or 'I have found your item. Please reach out to recover it.'}"

        Location: {location_text or 'Location shared by finder'}
        {f'Google Maps Pin: {maps_link}' if maps_link else ''}

        Scanned At: {timezone.now().strftime('%d %b %Y, %I:%M %p')}

        Thanks,
        Lost & Found Smart Tag System
        """

        send_mail(
            f"🚨 Smart Tag Scanned: {tag.item_name}",
            email_content,
            settings.DEFAULT_FROM_EMAIL,
            [tag.user.email],
            fail_silently=True,
        )

        success_message = "Thank you! An instant notification has been dispatched to the owner with your message and location."

    masked_owner_email = mask_email_address(tag.user.email)

    return render(request, 'scan_portal.html', {
        'tag': tag,
        'masked_owner_email': masked_owner_email,
        'success_message': success_message
    })