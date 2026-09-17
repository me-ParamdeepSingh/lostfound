from django.db import models
from django.contrib.auth.models import User
import uuid

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


class Conversation(models.Model):
    item = models.ForeignKey(Item, on_delete=models.CASCADE, related_name='conversations')
    starter = models.ForeignKey(User, on_delete=models.CASCADE, related_name='started_conversations')
    receiver = models.ForeignKey(User, on_delete=models.CASCADE, related_name='received_conversations')
    contact_shared = models.BooleanField(default=False)  # Owner sets this to True to reveal unmasked contact
    updated_at = models.DateTimeField(auto_now=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('item', 'starter')
        ordering = ['-updated_at']

    def __str__(self):
        return f"Chat: {self.starter.username} & {self.receiver.username} ({self.item.title})"


class ChatMessage(models.Model):
    conversation = models.ForeignKey(Conversation, on_delete=models.CASCADE, related_name='messages')
    sender = models.ForeignKey(User, on_delete=models.CASCADE)
    text = models.TextField()
    is_read = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['created_at']

    def __str__(self):
        return f"{self.sender.username}: {self.text[:30]}"


class SmartTag(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='smart_tags')
    item_name = models.CharField(max_length=200)
    category = models.CharField(max_length=100)
    reward_note = models.CharField(max_length=255, blank=True, null=True)
    tag_code = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    scans_count = models.IntegerField(default=0)
    last_scanned_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.item_name} (Tag: {self.tag_code})"