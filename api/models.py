from django.db import models
from django.contrib.auth.models import User
from django.db.models.signals import post_save
from django.dispatch import receiver

class Profile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    nickname = models.CharField(max_length=50, blank=True)

    def __str__(self):
        return f'{self.user.username} Profile'

@receiver(post_save, sender=User)
def ensure_user_profile(sender, instance, created, **kwargs):
    profile, _ = Profile.objects.get_or_create(user=instance, defaults={'nickname': instance.username})
    if created and not profile.nickname:
        profile.nickname = instance.username
        profile.save(update_fields=['nickname'])

class Stream(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    stream_key = models.CharField(max_length=255, unique=True)
    stream_url = models.CharField(max_length=255)
    viewer_url = models.CharField(max_length=255) # Actually stores the UID
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.user.username

class ChatMessage(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    stream = models.ForeignKey(Stream, on_delete=models.CASCADE)
    message = models.TextField()
    timestamp = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f'{self.user.username}: {self.message}'

class Ban(models.Model):
    streamer = models.ForeignKey(User, related_name='banned_by', on_delete=models.CASCADE)
    banned_user = models.ForeignKey(User, related_name='banned_user', on_delete=models.CASCADE)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('streamer', 'banned_user')

    def __str__(self):
        return f'{self.banned_user.username} banned by {self.streamer.username}'
