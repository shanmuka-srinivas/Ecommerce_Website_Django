
# This is for Automatically register the new User under STORE(app) -> Customers Fiels.

from django.db.models.signals import post_save
from django.dispatch import receiver
from django.contrib.auth.models import User
from .models import Customer

@receiver(post_save, sender=User)
def create_customer_profile(sender, instance, created, **kwargs):
    if created:
        username_cap = instance.username.capitalize()
        email = f"{instance.username}@gmail.com"
        Customer.objects.create(user=instance, name=username_cap, email=email)