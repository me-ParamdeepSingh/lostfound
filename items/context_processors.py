from .models import Claim, Item

def claim_count(request):
    if request.user.is_authenticated:
        items = Item.objects.filter(user=request.user)
        count = Claim.objects.filter(item__in=items, status='active').count()
        return {'claim_count': count}
    return {'claim_count': 0}

def claim_notification(request):
    if request.user.is_authenticated:
        count = Claim.objects.filter(
            user=request.user,
            is_seen=False
        ).count()

        return {'claim_notify': count}

    return {'claim_notify': 0}