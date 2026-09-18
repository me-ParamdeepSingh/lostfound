from .models import Claim, Item, Conversation, ChatMessage
from django.db.models import Q

def claim_count(request):
    if hasattr(request, 'user') and request.user.is_authenticated:
        count = Claim.objects.filter(item__user=request.user, status='active').count()
        return {'claim_count': count}
    return {'claim_count': 0}

def claim_notification(request):
    if hasattr(request, 'user') and request.user.is_authenticated:
        count = Claim.objects.filter(
            user=request.user,
            is_seen=False
        ).count()
        return {'claim_notify': count}
    return {'claim_notify': 0}

def chat_notification(request):
    if hasattr(request, 'user') and request.user.is_authenticated:
        count = ChatMessage.objects.filter(
            Q(conversation__starter=request.user) | Q(conversation__receiver=request.user),
            is_read=False
        ).exclude(sender=request.user).count()
        return {'chat_unread_count': count}
    return {'chat_unread_count': 0}